#!/usr/bin/env python3
"""sync.py — fan out this repo's components, and track the third-party plugins it uses.

Replaces the old sync.py + sync-lock.json + install.sh.

Own components are *symlinked* into the agent tools' skill directories, so editing
a file here takes effect in a running session with no install step. Third-party
components are not vendored: they are entries in .claude-plugin/marketplace.json,
installed by Claude Code itself, and linked out of its plugin cache.

Subcommands
    link                 (default) idempotent symlink fan-out, then prune
    status               offline report: link state, plugins, skill-listing budget
    readme               regenerate the README index between its markers
    check                which marketplace entries are behind upstream        [network]
    diff <plugin>        the upstream patch, filtered to what we consume      [network]
    update [plugin]      bump a pinned sha, reinstall, relink                 [network]
    vendor <plugin>      promote an entry to a checked-in copy under vendor/  [network]
    unvendor <plugin>    the reverse

Only check/diff/update/vendor/unvendor touch the network. link and status never do.

Deliberately plain stdlib Python 3 with no dependency pin: this script manipulates
symlinks and shells out, and sync.py's `uv run --python 3.14` shebang was a
portability trap for that kind of work.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from concurrent import futures
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent

# Where our own things live in this repo.
SKILLS_DIR = REPO / "skills"
AGENTS_DIR = REPO / "agents"
PLUGINS_DIR = REPO / "plugins"
VENDOR_DIR = REPO / "vendor"
# Where a vendored entry's upstream coordinates go, so marketplace.json can hold
# a plain relative path and check/diff still know what to compare against.
VENDOR_SOURCES = VENDOR_DIR / "sources.json"
MARKETPLACE = REPO / ".claude-plugin" / "marketplace.json"

HOME = Path.home()

# Claude Code reads skills from ~/.claude/skills and agents from ~/.claude/agents.
CLAUDE_SKILLS = HOME / ".claude" / "skills"
CLAUDE_AGENTS = HOME / ".claude" / "agents"
# Commands were merged into skills: both produce /name and draw on the same
# listing budget. Nothing is linked here — it is read for the budget report, and
# is empty once Phase 4 has converted everything.
CLAUDE_COMMANDS = HOME / ".claude" / "commands"
# The cross-tool roots. ~/.agents is the shared convention; ~/.cursor is Cursor's.
AGENTS_SKILLS = HOME / ".agents" / "skills"
CURSOR_SKILLS = HOME / ".cursor" / "skills"

SKILL_ROOTS = (CLAUDE_SKILLS, AGENTS_SKILLS, CURSOR_SKILLS)

# Claude Code's own plugin cache. Links into it are ours to prune, because the
# path is version-keyed and the old directory disappears on `plugin update`.
PLUGIN_CACHE = HOME / ".claude" / "plugins" / "cache"


# --------------------------------------------------------------------------
# repo model
# --------------------------------------------------------------------------


def own_skills() -> list[Path]:
    """Loose skills we author: skills/<name>/SKILL.md."""
    if not SKILLS_DIR.is_dir():
        return []
    return sorted(d for d in SKILLS_DIR.iterdir() if (d / "SKILL.md").is_file())


def own_agents() -> list[Path]:
    """Subagent definitions we author: agents/<name>.md."""
    if not AGENTS_DIR.is_dir():
        return []
    return sorted(f for f in AGENTS_DIR.iterdir() if f.suffix == ".md" and f.is_file())


def own_plugins() -> list[Path]:
    """Plugins we author: plugins/<name>/.claude-plugin/plugin.json."""
    if not PLUGINS_DIR.is_dir():
        return []
    return sorted(
        d for d in PLUGINS_DIR.iterdir() if (d / ".claude-plugin" / "plugin.json").is_file()
    )


def plugin_skills(plugin: Path) -> list[Path]:
    """The individual skills inside one of our plugins."""
    skills = plugin / "skills"
    if not skills.is_dir():
        return []
    return sorted(d for d in skills.iterdir() if (d / "SKILL.md").is_file())


def cache_link_name(plugin: str, skill: Path, root: Path) -> str:
    """What to call a third-party skill in the flat cross-tool roots.

    A single-skill plugin keeps SKILL.md at its root, and that root directory is
    named after the *version* (`4812a83ab03c`), so the plugin name is the only
    usable label. A multi-skill plugin gets `<plugin>-<skill>`, the same prefixing
    our own plugins get — except when the two are equal, which would otherwise
    produce `impeccable-impeccable`.
    """
    if skill == root:
        return plugin
    return skill.name if skill.name == plugin else f"{plugin}-{skill.name}"


@dataclass(frozen=True)
class CacheSkill:
    """One skill inside an installed third-party plugin, and where it came from."""

    link: str  # what to call it in the flat cross-tool roots
    path: Path  # the skill directory in the plugin cache
    pid: str  # the plugin's qualified id, <name>@<marketplace>
    inner: str  # the skill's path inside the plugin; "" when it is the plugin root


def plugin_cache_skills() -> list[CacheSkill]:
    """Every skill in an installed, enabled plugin.

    Deliberately *not* linked into ~/.claude/skills: Claude Code already loads
    these from the plugin itself, and a copy there would list the same skill
    twice. ~/.agents and ~/.cursor have no plugin mechanism, so a link is the
    only way those tools see them at all.

    Disabled plugins are skipped. Disabling is how the plan says to decline a
    plugin's listing cost without uninstalling it, so it should mean the skill
    is gone from every tool, not just this one.
    """
    out: list[CacheSkill] = []
    for plugin in installed_plugins():
        if not plugin.get("enabled"):
            continue
        root = Path(plugin.get("installPath", ""))
        # Our own plugins are installed from a symlink in ~/.claude/skills, not
        # from the cache; own_plugins() already fans their skills out.
        if not root.is_dir() or PLUGIN_CACHE not in root.parents:
            continue
        name = plugin["id"].split("@")[0]
        for skill_md in sorted(root.rglob("SKILL.md")):
            skill = skill_md.parent
            inner = skill.relative_to(root)
            out.append(
                CacheSkill(
                    cache_link_name(name, skill, root),
                    skill,
                    plugin["id"],
                    "" if inner == Path(".") else inner.as_posix(),
                )
            )
    return out


def load_marketplace() -> dict:
    """The third-party tracking artifact. Absent is not an error — it arrives in Phase 5."""
    if not MARKETPLACE.is_file():
        return {"plugins": []}
    with MARKETPLACE.open() as fh:
        return json.load(fh)


def marketplace_entries() -> list[dict]:
    return load_marketplace().get("plugins", [])


# --------------------------------------------------------------------------
# output helpers
# --------------------------------------------------------------------------

_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _COLOR else text


def ok(text: str) -> str:
    return _c("32", text)


def warn(text: str) -> str:
    return _c("33", text)


def bad(text: str) -> str:
    return _c("31", text)


def dim(text: str) -> str:
    return _c("2", text)


def not_yet(name: str) -> int:
    print(f"{warn('not implemented')}: {name}")
    return 1


def tilde(path: Path) -> str:
    """~/.claude/skills/diataxis reads better than the absolute path."""
    try:
        return "~/" + str(path.relative_to(HOME))
    except ValueError:
        return str(path)


def source_label(path: Path) -> str:
    """A link's target, short: repo-relative for ours, ~-relative for the cache."""
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return tilde(path)


def column(names: Iterable[str], minimum: int = 26) -> int:
    """Width for a name column: enough for its longest entry.

    A fixed 26 was fine until mattpocock-skills arrived carrying names like
    `mattpocock-skills-improve-codebase-architecture`, each of which shoved every
    column right of it out of alignment.
    """
    return max([minimum, *(len(name) + 2 for name in names)])


# --------------------------------------------------------------------------
# symlink fan-out
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Link:
    src: Path  # what this repo owns
    dst: Path  # where an agent tool looks for it


def own_link_plan() -> list[Link]:
    """Every symlink this repo's *own* components want.

    Loose skills reach all three roots. Agents are Claude-Code-only — ~/.agents and
    ~/.cursor have no equivalent concept.

    A plugin is linked as a *directory* into ~/.claude/skills, which is what makes it
    a skills-dir plugin and gives it a /namespace:command prefix. The other two roots
    do not understand plugin namespacing, so they get the plugin's individual skills
    instead; that is what "everything reaches Cursor too" means for a plugin.

    Those roots are flat, so a plugin skill lands there as `<plugin>-<skill>`. Without
    that prefix `plugins/<p>/skills/review` and `skills/review` — distinct commands
    under Claude Code, /<p>:review and /review — would both want
    ~/.agents/skills/review, and each run of this script would repoint the link at
    the other one, forever.
    """
    plan: list[Link] = []

    for skill in own_skills():
        for root in SKILL_ROOTS:
            plan.append(Link(skill, root / skill.name))

    for agent in own_agents():
        plan.append(Link(agent, CLAUDE_AGENTS / agent.name))

    for plugin in own_plugins():
        plan.append(Link(plugin, CLAUDE_SKILLS / plugin.name))
        for skill in plugin_skills(plugin):
            for root in (AGENTS_SKILLS, CURSOR_SKILLS):
                plan.append(Link(skill, root / f"{plugin.name}-{skill.name}"))

    return plan


def cache_link_plan() -> list[Link]:
    """Every symlink the installed third-party plugins want, in the two flat roots."""
    return [
        Link(cs.path, root / cs.link)
        for cs in plugin_cache_skills()
        for root in (AGENTS_SKILLS, CURSOR_SKILLS)
    ]


def link_plan() -> list[Link]:
    return own_link_plan() + cache_link_plan()


def is_ours(path: Path) -> bool:
    """True if `path` points inside this repo or Claude Code's plugin cache.

    These are the only two places whose links we may remove or repoint. Anything
    else in a target root belongs to another tool — ui.sh's skills, for instance.
    Resolution is deliberately non-strict so a *dangling* link still classifies.
    """
    resolved = Path(os.path.normpath(path))
    for owned in (REPO, PLUGIN_CACHE):
        if resolved == owned or owned in resolved.parents:
            return True
    return False


# What we found at a link's destination, and therefore what we may do about it.
LINKED = "linked"  # already correct
CREATE = "create"  # nothing there
REPOINT = "repoint"  # our link, wrong target
BLOCKED_FILE = "blocked-file"  # a real file or directory
BLOCKED_LINK = "blocked-link"  # someone else's symlink


def classify(link: Link) -> str:
    dst = link.dst
    if not dst.is_symlink() and not dst.exists():
        return CREATE
    if dst.is_symlink():
        target = Path(os.path.normpath(dst.parent / os.readlink(dst)))
        if target == link.src:
            return LINKED
        return REPOINT if is_ours(target) else BLOCKED_LINK
    return BLOCKED_FILE


def apply_link(link: Link, state: str, dry_run: bool) -> None:
    if dry_run:
        return
    link.dst.parent.mkdir(parents=True, exist_ok=True)
    if state == REPOINT:
        link.dst.unlink()
    link.dst.symlink_to(link.src, target_is_directory=link.src.is_dir())


def prune_candidates(plan: list[Link]) -> list[tuple[Path, str]]:
    """Links in the target roots that this repo owns and no longer wants.

    Two cases, deliberately narrow:

    * **dangling** — the link's target is gone. For the plugin cache this is the
      normal aftermath of `claude plugin update`, because the cache path carries
      the version; it is why `update` has to call `link`.
    * **stale** — a live link into this repo or the cache that the plan no longer
      contains: a renamed or deleted skill, or a plugin that has since been
      disabled or uninstalled.

    Stale pruning of cache links is skipped entirely when `claude plugin list`
    could not be read, because an empty plan there is indistinguishable from
    "every plugin is gone" and would take out every working third-party link.
    """
    wanted = {link.dst for link in plan}
    prune_cache = plugin_query_ok()
    found: list[tuple[Path, str]] = []

    for root in (*SKILL_ROOTS, CLAUDE_AGENTS):
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir()):
            if not entry.is_symlink():
                continue
            target = Path(os.path.normpath(entry.parent / os.readlink(entry)))
            if not is_ours(target):
                continue
            if not target.exists():
                found.append((entry, "dangling"))
            elif entry in wanted:
                continue
            elif REPO in target.parents or prune_cache:
                found.append((entry, "stale"))

    return found


def cmd_link(args: argparse.Namespace) -> int:
    plan = link_plan()
    if not plan:
        print("nothing to link — this repo owns no skills, agents or plugins yet")
        return 0

    counts = {LINKED: 0, CREATE: 0, REPOINT: 0}
    blocked: list[tuple[Link, str]] = []

    for link in plan:
        state = classify(link)
        if state in (BLOCKED_FILE, BLOCKED_LINK):
            blocked.append((link, state))
            continue
        if state in (CREATE, REPOINT):
            apply_link(link, state, args.dry_run)
            verb = "would link" if args.dry_run else ("linked" if state == CREATE else "repointed")
            print(f"  {ok(verb):<22} {tilde(link.dst)} -> {source_label(link.src)}")
        counts[state] += 1

    pruned = prune_candidates(plan)
    for path, why in pruned:
        if not args.dry_run:
            path.unlink()
        verb = "would prune" if args.dry_run else "pruned"
        print(f"  {warn(verb):<22} {tilde(path)} {dim(f'({why})')}")

    for link, state in blocked:
        what = "real file" if state == BLOCKED_FILE else "foreign symlink"
        print(f"  {bad('collision'):<22} {tilde(link.dst)} {dim(f'({what}, left alone)')}")

    changed = counts[CREATE] + counts[REPOINT] + len(pruned)
    summary = f"{counts[LINKED]} already linked, {changed} changed"
    if blocked:
        summary += f", {len(blocked)} collisions"
    print(summary)

    if blocked:
        print(
            dim(
                "\nCollisions are reported, never resolved. Remove the file yourself if you\n"
                "want this repo's copy to win — see ./sync.py status for what owns what."
            )
        )
    return 0


# --------------------------------------------------------------------------
# subcommands
# --------------------------------------------------------------------------


# --------------------------------------------------------------------------
# skill listing budget
# --------------------------------------------------------------------------
#
# Claude Code loads every skill's name and description into every session. The
# budget is a fraction of the context window, and when it overflows descriptions
# are dropped starting with the skills you invoke least — silent degradation with
# /doctor as the only signal. So the number is worth keeping in front of you.


def parse_frontmatter(path: Path) -> tuple[dict[str, str], str]:
    """Minimal YAML front matter reader. Returns (fields, body).

    Deliberately not a YAML parser: skill front matter is flat scalars, and taking
    a dependency to read it would defeat the point of a stdlib script. Block
    scalars (`|`, `>`) are folded to a single line, which is all the caller needs.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}, ""
    if not text.startswith("---"):
        return {}, text

    _, _, rest = text.partition("\n")
    raw, sep, body = rest.partition("\n---")
    if not sep:
        return {}, text
    body = body.partition("\n")[2]

    fields: dict[str, str] = {}
    key: str | None = None
    for line in raw.split("\n"):
        if line[:1] in (" ", "\t") and key:  # continuation of a block scalar
            fields[key] = (fields[key] + " " + line.strip()).strip()
            continue
        name, colon, value = line.partition(":")
        if not colon:
            continue
        key = name.strip()
        value = value.strip()
        if value in ("|", ">", "|-", ">-"):
            value = ""
        fields[key] = value.strip("'\"")
    return fields, body


def listing_text(path: Path) -> tuple[str, str, bool]:
    """(name, description, suppressed) exactly as the skill listing would see it."""
    fields, body = parse_frontmatter(path)
    # A skill is named by its directory; a command by its own filename.
    fallback = path.parent.name if path.name == "SKILL.md" else path.stem
    name = fields.get("name") or fallback
    description = fields.get("description", "")
    if not description:
        # No description means the first paragraph of the body is used instead,
        # which is how /brainstorm came to contribute 323 chars of "You are a
        # brainstorming partner designed to...".
        for para in body.split("\n\n"):
            para = para.strip()
            if para and not para.startswith("#"):
                description = " ".join(para.split())
                break
    suppressed = fields.get("disable-model-invocation", "").lower() == "true"
    return name, description, suppressed


def listed_skills() -> list[tuple[str, int, bool, str]]:
    """Every skill Claude Code would list: (label, chars, suppressed, origin)."""
    out: list[tuple[str, int, bool, str]] = []
    seen: set[Path] = set()

    def add(skill_md: Path, origin: str) -> None:
        real = skill_md.resolve()
        if real in seen:  # a symlinked skill reachable from two roots counts once
            return
        seen.add(real)
        name, description, suppressed = listing_text(skill_md)
        out.append((name, len(name) + len(description), suppressed, origin))

    if CLAUDE_SKILLS.is_dir():
        for entry in sorted(CLAUDE_SKILLS.iterdir()):
            if (entry / "SKILL.md").is_file():
                add(entry / "SKILL.md", "~/.claude/skills")
            # A skills-dir plugin holds its skills one level down.
            for nested in sorted((entry / "skills").glob("*/SKILL.md")):
                add(nested, f"{entry.name}@skills-dir")

    # Commands were merged into skills, so they draw on the same budget — and
    # they are the expensive half, because almost none of them has a description.
    if CLAUDE_COMMANDS.is_dir():
        for command in sorted(CLAUDE_COMMANDS.rglob("*.md")):
            add(command, "~/.claude/commands")

    for plugin in installed_plugins():
        if not plugin.get("enabled"):
            continue
        root = Path(plugin.get("installPath", ""))
        if not root.is_dir():
            continue
        for skill_md in sorted(root.rglob("SKILL.md")):
            add(skill_md, plugin["id"])

    return out


_PLUGINS: list[dict] | None = None
_PLUGINS_OK = False


def installed_plugins() -> list[dict]:
    """`claude plugin list --json`. A subprocess, but never a network call.

    Queried once per run: the fan-out, the prune and three sections of `status`
    all want it, and it is the slowest thing either offline subcommand does.
    """
    global _PLUGINS, _PLUGINS_OK
    if _PLUGINS is not None:
        return _PLUGINS
    _PLUGINS = []
    try:
        proc = subprocess.run(
            ["claude", "plugin", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return _PLUGINS
    if proc.returncode != 0:
        return _PLUGINS
    try:
        _PLUGINS = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return _PLUGINS
    _PLUGINS_OK = True
    return _PLUGINS


def plugin_query_ok() -> bool:
    """Whether the answer above is real, as opposed to the empty list we fall back to."""
    installed_plugins()
    return _PLUGINS_OK


# --------------------------------------------------------------------------
# status
# --------------------------------------------------------------------------


def cache_origin(cs: CacheSkill) -> str:
    """Where a cached third-party skill was synced from, as a URL.

    The cache path is <marketplace>/<plugin>/<version>/…, which says who
    installed a skill but not what was installed: the version is a manifest
    string or a sha prefix, and neither is something you can open. So the plugin
    name is resolved back through marketplace.json to the commit we pinned, and
    the skill's own position inside the plugin is appended, so that
    `mattpocock-skills-tdd` lands on skills/engineering/tdd at that sha rather
    than on the repo root it shares with every other skill in that plugin.

    Two fallbacks. A plugin from someone else's marketplace has no entry here and
    so no coordinates, and keeps the plugin@marketplace label it had before. A
    vendored entry is installed from the checked-in copy, so that is what it is
    synced from, whatever its coordinates still say.
    """
    plugin = cs.pid.partition("@")[0]
    entry = next((e for e in marketplace_entries() if e.get("name") == plugin), None)
    up = entry_upstream(entry) if entry else None
    if up is None:
        return cs.pid
    if up.vendored:
        return "/".join(part for part in (f"vendor/{plugin}", cs.inner) if part)
    return upstream_url(up, cs.inner, short=True)


def cmd_status(args: argparse.Namespace) -> int:
    plan = link_plan()
    by_src: dict[Path, dict[Path, str]] = {}
    for link in own_link_plan():
        by_src.setdefault(link.src, {})[link.dst.parent] = classify(link)

    # Pad first, colour second — an escape code inside a format spec silently
    # inflates the field width and shears the table.
    marks = {
        LINKED: ("link", ok),
        CREATE: ("--", warn),
        REPOINT: ("moved", warn),
        BLOCKED_FILE: ("file!", bad),
        BLOCKED_LINK: ("other", bad),
    }

    def cell(state: str, width: int = 12) -> str:
        text, paint = marks.get(state, ("?", dim))
        return paint(f"{text:<{width}}")

    print(_c("1", "own components"))
    print(dim(f"  {'':<26}{'~/.claude':<12}{'~/.agents':<12}{'~/.cursor':<12}"))
    for src in sorted(by_src, key=lambda p: (p.parent != SKILLS_DIR, p.name)):
        states = by_src[src]
        if CLAUDE_AGENTS in states:  # agents live in one root only
            cells = cell(states[CLAUDE_AGENTS]) + dim("(agent, ~/.claude only)")
        else:
            cells = "".join(cell(states.get(root, CREATE)) for root in SKILL_ROOTS)
        print(f"  {src.name:<26}{cells}")

    print()
    print(_c("1", "third-party skills, linked out of the plugin cache"))
    cache = plugin_cache_skills()
    width = column(cs.link for cs in cache)
    print(dim(f"  {'':<{width}}{'~/.agents':<12}{'~/.cursor':<12}{'synced from'}"))
    if not cache:
        print(dim("  none — no enabled plugin in the cache ships a skill"))
    for cs in cache:
        cells = "".join(
            cell(classify(Link(cs.path, root / cs.link)))
            for root in (AGENTS_SKILLS, CURSOR_SKILLS)
        )
        print(f"  {cs.link:<{width}}{cells}{dim(cache_origin(cs))}")

    print()
    print(_c("1", "marketplace entries"))
    entries = marketplace_entries()
    if not entries:
        print(dim(f"  none — {tilde(MARKETPLACE)} not written yet"))
    else:
        width = column(e["name"] for e in entries)
        print(dim(f"  {'':<{width}}{'version':<26}{'state':<16}{'synced from'}"))
        installed = {p["id"].split("@")[0]: p for p in installed_plugins()}
        for entry in entries:
            got = installed.get(entry["name"])
            if got:
                label = "enabled" if got.get("enabled") else "disabled"
                state = (ok if got.get("enabled") else warn)(f"{label:<16}")
                version = got.get("version", "?")
            else:
                state, version = bad(f"{'not installed':<16}"), "-"
            up = entry_upstream(entry)
            if up is None:
                source = str(entry.get("source", "?"))
            elif up.vendored:
                # Installed from the checked-in copy; the pin says what it was cut from.
                source = f"vendor/{entry['name']}  <- {upstream_url(up, short=True)}"
            else:
                source = upstream_url(up, short=True)
            print(f"  {entry['name']:<{width}}{version:<26}{state}{dim(source)}")

    print()
    print(_c("1", "other plugins installed"))
    names = {e["name"] for e in entries}
    others = [p for p in installed_plugins() if p["id"].split("@")[0] not in names]
    if not others:
        print(dim("  none"))
    for plugin in others:
        state = ok("enabled") if plugin.get("enabled") else dim("disabled")
        print(f"  {plugin['id']:<44}{plugin.get('version', '?'):<12}{state}")

    print()
    print(_c("1", "not ours, in the target roots"))
    wanted = {link.dst for link in plan}
    foreign: list[str] = []
    for root in (*SKILL_ROOTS, CLAUDE_AGENTS):
        if not root.is_dir():
            continue
        for entry in sorted(root.iterdir()):
            if entry in wanted:
                continue
            kind = "symlink elsewhere" if entry.is_symlink() else "real"
            foreign.append(f"  {tilde(entry):<48}{dim(kind)}")
    print("\n".join(foreign) if foreign else dim("  none"))

    print()
    print(_c("1", "skill listing budget"))
    listed = listed_skills()
    counted = [s for s in listed if not s[2]]
    total = sum(s[1] for s in counted)
    hidden = len(listed) - len(counted)
    print(f"  {total:,} chars across {len(counted)} listed entries")
    if hidden:
        print(dim(f"  {hidden} more suppressed by disable-model-invocation, costing nothing"))
    print(dim("  top contributors:"))
    for name, chars, _, origin in sorted(counted, key=lambda s: -s[1])[:8]:
        print(f"    {chars:>5}  {name:<28}{dim(origin)}")
    print(dim("\n  An estimate of what /doctor and the /context Skills row report."))
    return 0


# --------------------------------------------------------------------------
# upstream
# --------------------------------------------------------------------------
#
# Everything that talks to GitHub. The unit of work is a marketplace entry
# resolved to (repo, ref, pinned sha, consumed subpath) — the subpath is what
# makes a review of impeccable readable rather than a wall of 900 filenames.


@dataclass(frozen=True)
class Upstream:
    name: str
    repo: str  # owner/name
    ref: str  # the branch we compare against
    sha: str  # what we are pinned to
    subpath: str | None  # the slice we consume; None means the whole repo
    vendored: bool = False  # content checked in under vendor/, not fetched on install


def entry_upstream(entry: dict) -> Upstream | None:
    """An entry's upstream coordinates, or None if it has none to resolve.

    A string `source` is a relative path — a vendored entry. Its coordinates
    moved to vendor/sources.json when it was vendored, so `check` and `diff`
    keep working: vendoring should change where the bytes come from, not
    whether you can see what upstream did since.
    """
    source = entry.get("source")
    vendored = False
    if isinstance(source, str):
        record = vendor_sources().get(entry["name"], {})
        source = record.get("source")
        vendored = True
    if not isinstance(source, dict):
        return None
    kind = source.get("source")
    if kind == "github":
        repo, subpath = source.get("repo", ""), None
    elif kind == "git-subdir":
        repo, subpath = source.get("url", ""), source.get("path") or None
    else:
        return None
    ref, sha = source.get("ref"), source.get("sha")
    if not (repo and ref and sha):
        return None
    return Upstream(entry["name"], repo, ref, sha, subpath, vendored)


def upstreams(names: list[str] | None = None) -> list[Upstream]:
    """The entries to act on, or all of them. Unknown names are an error, not a no-op."""
    entries = {e["name"]: e for e in marketplace_entries()}
    if names:
        unknown = [n for n in names if n not in entries]
        if unknown:
            raise SystemExit(bad(f"no such marketplace entry: {', '.join(unknown)}"))
        wanted = [entries[n] for n in names]
    else:
        wanted = list(entries.values())
    return [u for u in (entry_upstream(e) for e in wanted) if u]


def upstream_url(up: Upstream, inner: str = "", short: bool = False) -> str:
    """Where a pinned entry's bytes come from, on GitHub.

    `inner` reaches a skill *inside* the consumed subpath, which is what a
    multi-skill plugin needs: mattpocock-skills consumes a whole repo, so its
    subpath is empty and only `inner` tells one of its skills from the rest.

    `short` drops the scheme and abbreviates the sha. The full form is a README
    link, where the text is the sha and the href has to resolve; the short form
    is a terminal column, where 33 characters of `https://` and trailing sha are
    33 characters of nothing.
    """
    path = "/".join(part.strip("/") for part in (up.subpath or "", inner) if part.strip("/"))
    scheme = "" if short else "https://"
    sha = up.sha[:7] if short else up.sha
    return f"{scheme}github.com/{up.repo}/tree/{sha}" + (f"/{path}" if path else "")


def have_gh() -> bool:
    return shutil.which("gh") is not None


def gh_api(path: str) -> tuple[dict | None, str]:
    """GET a GitHub API path through `gh`. Returns (payload, error message)."""
    try:
        proc = subprocess.run(
            ["gh", "api", path], capture_output=True, text=True, timeout=120
        )
    except FileNotFoundError:
        return None, "gh is not installed"
    except subprocess.SubprocessError as exc:
        return None, str(exc)
    if proc.returncode != 0:
        return None, proc.stderr.strip().split("\n")[-1] or f"gh exited {proc.returncode}"
    try:
        return json.loads(proc.stdout), ""
    except json.JSONDecodeError as exc:
        return None, f"unreadable response: {exc}"


def ls_remote(repo: str, ref: str) -> tuple[str, str]:
    """The sha `ref` currently points at, without gh. Returns (sha, error)."""
    try:
        proc = subprocess.run(
            ["git", "ls-remote", f"https://github.com/{repo}.git", ref],
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return "", str(exc)
    if proc.returncode != 0 or not proc.stdout.strip():
        return "", proc.stderr.strip().split("\n")[-1] or "ref not found"
    return proc.stdout.split()[0], ""


@dataclass
class Comparison:
    """`compare/{base}...{head}`, with the file list narrowed to what we consume."""

    up: Upstream
    head: str = ""  # what ref points at now
    commits: int = 0
    files: list[dict] = field(default_factory=list)  # already filtered
    total_files: int = 0  # before filtering
    truncated: bool = False
    error: str = ""

    @property
    def behind(self) -> bool:
        return bool(self.head) and self.head != self.up.sha

    @property
    def relevant(self) -> bool:
        """Behind upstream *in a way that reaches us*."""
        return self.behind and bool(self.files or self.up.subpath is None)

    @property
    def url(self) -> str:
        return f"https://github.com/{self.up.repo}/compare/{self.up.sha}...{self.head}"


def consumed(up: Upstream, filename: str) -> bool:
    if up.subpath is None:
        return True
    return filename == up.subpath or filename.startswith(up.subpath.rstrip("/") + "/")


def compare(up: Upstream) -> Comparison:
    """One entry's drift. Network; safe to call concurrently."""
    if not have_gh():
        head, err = ls_remote(up.repo, up.ref)
        return Comparison(up, head=head, error=err)

    payload, err = gh_api(f"repos/{up.repo}/compare/{up.sha}...{up.ref}")
    if payload is None:
        return Comparison(up, error=err)

    head = (payload.get("commits") or [{}])[-1].get("sha") or up.sha
    files = payload.get("files") or []
    return Comparison(
        up,
        head=head,
        commits=payload.get("total_commits", 0),
        files=[f for f in files if consumed(up, f.get("filename", ""))],
        total_files=len(files),
        # The compare API stops listing files at 300; the commit count stays right.
        truncated=len(files) >= 300,
    )


def compare_all(ups: list[Upstream]) -> list[Comparison]:
    """Concurrently, because six sequential round trips is the whole runtime."""
    if not ups:
        return []
    with futures.ThreadPoolExecutor(max_workers=min(8, len(ups))) as pool:
        return list(pool.map(compare, ups))


def cmd_check(args: argparse.Namespace) -> int:
    ups = upstreams(args.plugin)
    if not ups:
        print(dim("no marketplace entry has a remote to check"))
        return 0

    if not have_gh():
        print(
            dim(
                "gh is not installed — falling back to `git ls-remote`, which can say\n"
                "whether an entry moved but not what changed in it.\n"
            )
        )

    behind = 0
    for comp in compare_all(ups):
        up = comp.up
        if comp.error:
            print(f"  {bad('error'):<22}{up.name:<26}{dim(comp.error)}")
            continue
        if not comp.behind:
            print(f"  {ok('up to date'):<22}{up.name:<26}{dim(up.sha[:7])}")
            continue

        behind += 1
        moved = f"{up.sha[:7]}..{comp.head[:7]}"
        if not have_gh():
            print(f"  {warn('behind'):<22}{up.name:<26}{dim(moved)}")
            continue

        count = f"{comp.commits} commit{'s' if comp.commits != 1 else ''}"
        if up.subpath and not comp.files:
            # Behind, but every one of those commits landed outside our slice.
            note = f"{count}, none touching {up.subpath}"
            print(f"  {dim('behind elsewhere'):<22}{up.name:<26}{dim(moved)}  {dim(note)}")
            continue

        scope = f"{len(comp.files)} file{'s' if len(comp.files) != 1 else ''}"
        if up.subpath:
            scope += f" under {up.subpath}"
            if comp.total_files != len(comp.files):
                scope += dim(f" (of {comp.total_files} total)")
        note = f"{count}, {scope}"
        print(f"  {warn('behind'):<22}{up.name:<26}{dim(moved)}  {note}")
        if comp.truncated:
            print(dim(f"  {'':<22}{'':<26}upstream file list capped at 300"))

    if behind:
        print(dim(f"\n./sync.py diff <name> to read one; ./sync.py update <name> to accept it."))
    return 0


def print_patch(patch: str) -> None:
    for line in patch.split("\n"):
        if line.startswith("@@"):
            print("    " + _c("36", line))
        elif line.startswith("+"):
            print("    " + ok(line))
        elif line.startswith("-"):
            print("    " + bad(line))
        else:
            print("    " + line)


def cmd_diff(args: argparse.Namespace) -> int:
    (up,) = upstreams([args.plugin]) or [None]
    if up is None:
        print(bad(f"{args.plugin} has no remote to diff — it is vendored"))
        return 1
    if not have_gh():
        print(bad("diff needs gh: the patch comes from the compare API, not a clone"))
        return 1

    comp = compare(up)
    if comp.error:
        print(bad(comp.error))
        return 1
    if not comp.behind:
        print(f"{ok('up to date')} {up.name} at {up.sha[:7]}")
        return 0

    scope = up.subpath or "the whole repo"
    print(_c("1", f"{up.name}  {up.sha[:7]}..{comp.head[:7]}"))
    print(dim(f"  {comp.commits} commits upstream; showing {scope}"))
    print(dim(f"  {comp.url}\n"))

    if not comp.files:
        print(dim(f"  nothing under {scope} changed — safe to accept with ./sync.py update"))
        return 0

    for entry in comp.files:
        status = entry.get("status", "modified")
        paint = {"added": ok, "removed": bad, "renamed": warn}.get(status, warn)
        counts = dim(f"+{entry.get('additions', 0)} -{entry.get('deletions', 0)}")
        print(f"  {paint(status):<20}{entry.get('filename', '?')}  {counts}")
        patch = entry.get("patch")
        if patch:
            print_patch(patch)
        else:
            # No patch means binary, or a file GitHub judged too large to inline.
            print(dim("    (no inline patch — binary or too large; see the URL above)"))
        print()

    if comp.truncated:
        print(dim("  upstream file list capped at 300; the URL above is complete"))
    return 0


def rewrite_sha(text: str, name: str, new: str) -> str:
    """Repoint one entry's `sha`, textually.

    Deliberately not a json round-trip: re-serialising the whole manifest would
    reformat it and bury a one-line change in a whole-file diff. The point of
    this file is that `git log -p` on it reads as the history of what was
    accepted, and that only works if a bump is one line.

    Anchored on the entry's own `"name"` because two entries can share a sha —
    frontend-design and skill-creator are both slices of anthropics/skills.
    """
    anchor = re.search(rf'"name"\s*:\s*"{re.escape(name)}"', text)
    if not anchor:
        raise SystemExit(bad(f"{name} not found in {tilde(MARKETPLACE)}"))
    field_re = re.compile(r'("sha"\s*:\s*")([0-9a-fA-F]{7,40})(")')
    m = field_re.search(text, anchor.end())
    if not m:
        raise SystemExit(bad(f"{name} has no sha to bump"))
    return text[: m.start(2)] + new + text[m.end(2) :]


def git(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(REPO), *argv], capture_output=True, text=True)


def is_clean(*paths: str) -> bool:
    """Whether these paths have no edits a bump commit would sweep up.

    vendor/ counts as well as the manifest: a vendored bump commits content, so
    an unrelated edit in there would ride along just as easily.
    """
    for rel in paths:
        if git("diff", "--quiet", "--", rel).returncode != 0:
            return False
        if git("diff", "--cached", "--quiet", "--", rel).returncode != 0:
            return False
        if git("ls-files", "--others", "--exclude-standard", "--", rel).stdout.strip():
            return False
    return True


def update_message(comp: Comparison) -> str:
    """The commit body: what was accepted, and the evidence it was reviewable."""
    up = comp.up
    scope = up.subpath or "the whole repo"
    lines = [
        f"chore(deps): update {up.name} to {comp.head[:7]}",
        "",
        f"{comp.commits} commit{'s' if comp.commits != 1 else ''} upstream since "
        f"{up.sha[:7]}; {len(comp.files)} file(s) under {scope}"
        + (f", of {comp.total_files} changed in total" if up.subpath else "")
        + ".",
        "",
        comp.url,
    ]
    if comp.files:
        lines.append("")
        for entry in comp.files:
            lines.append(f"  {entry.get('status', 'modified')[:1].upper()} {entry['filename']}")
    if comp.truncated:
        lines += ["", "Upstream file list capped at 300 by the compare API."]
    return "\n".join(lines) + "\n"


def run_claude(*argv: str) -> bool:
    proc = subprocess.run(["claude", *argv], capture_output=True, text=True, timeout=600)
    label = " ".join(argv)
    if proc.returncode == 0:
        print(f"  {ok('ran'):<22}{label}")
        return True
    tail = (proc.stderr or proc.stdout).strip().split("\n")[-1]
    print(f"  {bad('failed'):<22}{label}  {dim(tail)}")
    return False


def reinstall(names: list[str]) -> None:
    """Make Claude Code act on the new pin, then repoint the links it invalidated.

    Uninstall-then-install rather than `claude plugin update`, because update
    compares the plugin's *manifest version*, not the pinned commit. impeccable
    ships `"version": "4.0.2"`, so rolling its sha back 13 commits and running
    update reports "already at the latest version" and leaves the cache holding
    content from a commit the manifest no longer pins. Reinstalling honors the
    pin: the same test then correctly drops the agent those 13 commits added.

    Entries with no manifest version are keyed by sha prefix instead, so their
    cache directory moves and every ~/.agents and ~/.cursor link into it
    dangles. That is the other reason this ends in a relink.
    """
    market = load_marketplace().get("name", "luke")
    disabled = {p["id"].split("@")[0] for p in installed_plugins() if not p.get("enabled")}

    run_claude("plugin", "marketplace", "update", market)
    for name in names:
        qualified = f"{name}@{market}"  # the bare name is not enough for the CLI
        run_claude("plugin", "uninstall", qualified, "--keep-data")
        if run_claude("plugin", "install", qualified) and name in disabled:
            # A fresh install comes up enabled; a deliberate disable should survive.
            run_claude("plugin", "disable", qualified)

    global _PLUGINS, _PLUGINS_OK
    _PLUGINS, _PLUGINS_OK = None, False
    cmd_link(argparse.Namespace(dry_run=False))


def cmd_update(args: argparse.Namespace) -> int:
    ups = upstreams(args.plugin)
    if not ups:
        print(dim("nothing to update"))
        return 0
    tracked = [str(MARKETPLACE.relative_to(REPO)), str(VENDOR_DIR.relative_to(REPO))]
    if not args.no_commit and not is_clean(*tracked):
        print(bad("marketplace.json or vendor/ has uncommitted edits"))
        print(dim("  commit or stash them first, or pass --no-commit to bump without committing"))
        return 1

    # Drift is worth reporting whether or not it blocks anything: a vendored tree
    # that no longer matches vendor/sources.json is no longer described by it.
    drifted = {u.name for u in ups if u.vendored and vendor_drift(u.name)}
    for name in sorted(drifted):
        print(f"  {warn('drifted'):<22}{name:<26}{dim('edited since it was fetched')}")

    comparisons = compare_all(ups)
    for comp in comparisons:
        if comp.error:
            print(f"  {bad('error'):<22}{comp.up.name:<26}{dim(comp.error)}")
    behind = [c for c in comparisons if c.behind and not c.error]

    refused = [c for c in behind if c.up.name in drifted]
    for comp in refused:
        print(f"  {bad('refused'):<22}{comp.up.name:<26}{dim('would overwrite the edited copy')}")
    if refused:
        print(
            dim(
                "\n  A vendored tree that no longer matches what was fetched holds a\n"
                "  decision, and a bump would overwrite it. Land the edit upstream, or\n"
                "  ./sync.py unvendor then vendor again to start from upstream.\n"
            )
        )
    behind = [c for c in behind if c not in refused]

    if not behind:
        if not refused:
            print(f"{ok('up to date')} — nothing to bump")
        return 1 if refused else 0

    bumped: list[Comparison] = []
    for comp in behind:
        scope = f"{len(comp.files)} file(s) under {comp.up.subpath or 'the whole repo'}"
        paths = [str(MARKETPLACE.relative_to(REPO))]
        if comp.up.vendored:
            # The pin lives in vendor/sources.json, and accepting it means the
            # content itself changes — so the commit is the content, not one line.
            vendor_entry(comp.up, comp.head)
            paths = [str(VENDOR_DIR.relative_to(REPO))]
        else:
            MARKETPLACE.write_text(rewrite_sha(MARKETPLACE.read_text(), comp.up.name, comp.head))
        bumped.append(comp)
        print(f"  {ok('bumped'):<22}{comp.up.name:<26}{comp.up.sha[:7]}..{comp.head[:7]}  {dim(scope)}")
        if args.no_commit:
            continue
        # Stage first: --only cannot commit a path git has never seen, which is
        # every file of a freshly re-fetched vendor tree.
        git("add", "--", *paths)
        # --only so a bump never sweeps up whatever else is staged.
        proc = subprocess.run(
            ["git", "-C", str(REPO), "commit", "--only", *paths, "-F", "-"],
            input=update_message(comp),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            print(f"  {bad('commit failed'):<22}{dim(proc.stderr.strip())}")
            return 1

    reinstall([c.up.name for c in bumped])
    return 1 if refused else 0


# --------------------------------------------------------------------------
# vendoring
# --------------------------------------------------------------------------
#
# Vendoring is not a second system. A relative path is a first-class marketplace
# source, so a vendored entry installs by exactly the same machinery — the only
# change is where the bytes come from. What moves out of marketplace.json is the
# *coordinates*, into vendor/sources.json, so that check and diff still work and
# unvendor has something to restore.


def vendor_sources() -> dict:
    if not VENDOR_SOURCES.is_file():
        return {}
    try:
        with VENDOR_SOURCES.open() as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def rewrite_source(name: str, source: object) -> None:
    """Swap one entry's `source` between a remote object and a vendor path.

    A json round-trip is safe here only because the manifest is written in
    exactly json.dumps(indent=2) form; the assertion keeps it that way, since
    silently reformatting all seven entries would wreck the reviewability the
    file exists for. A sha bump still goes through rewrite_sha() — this shape
    change cannot be done textually, but it is also not the frequent one.
    """
    text = MARKETPLACE.read_text()
    data = json.loads(text)
    if json.dumps(data, indent=2) + "\n" != text:
        raise SystemExit(bad(f"{tilde(MARKETPLACE)} is hand-formatted; refusing to reformat it"))
    for entry in data.get("plugins", []):
        if entry.get("name") == name:
            entry["source"] = source
            break
    else:
        raise SystemExit(bad(f"{name} not found in {tilde(MARKETPLACE)}"))
    write_json(MARKETPLACE, data)


def tree_digest(root: Path) -> str:
    """A content fingerprint of a vendored tree, so drift is detectable.

    Path and bytes of every file, in sorted order. This is what `update` checks
    before overwriting: a hand-edited vendored copy is a decision, and silently
    replacing it with upstream would throw that decision away.
    """
    digest = hashlib.sha256()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def fetch_subtree(up: Upstream, dest: Path) -> None:
    """Check out just the consumed subpath at the pinned sha into `dest`.

    Blobless and depth-1 against a sparse checkout: for a git-subdir entry this
    is the difference between a few files and impeccable's 337 MB.
    """
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)

        def run(*argv: str) -> None:
            proc = subprocess.run(
                ["git", "-C", str(work), *argv], capture_output=True, text=True, timeout=600
            )
            if proc.returncode != 0:
                raise SystemExit(bad(f"git {argv[0]}: {proc.stderr.strip().split(chr(10))[-1]}"))

        run("init", "-q")
        run("remote", "add", "origin", f"https://github.com/{up.repo}.git")
        if up.subpath:
            run("sparse-checkout", "set", "--no-cone", up.subpath)
        run("fetch", "-q", "--depth", "1", "--filter=blob:none", "origin", up.sha)
        run("checkout", "-q", "FETCH_HEAD")

        src = work / up.subpath if up.subpath else work
        if not src.is_dir():
            raise SystemExit(bad(f"{up.subpath} does not exist in {up.repo} at {up.sha[:7]}"))
        if dest.exists():
            shutil.rmtree(dest)
        # .git would otherwise be checked into this repo as a nested repository.
        shutil.copytree(src, dest, ignore=shutil.ignore_patterns(".git"))


def vendor_entry(up: Upstream, sha: str) -> Path:
    """Fetch `sha` into vendor/<name>/ and record the coordinates that produced it."""
    dest = VENDOR_DIR / up.name
    pinned = Upstream(up.name, up.repo, up.ref, sha, up.subpath, up.vendored)
    fetch_subtree(pinned, dest)

    source: dict = {"source": "github", "repo": up.repo, "ref": up.ref, "sha": sha}
    if up.subpath:
        source = {
            "source": "git-subdir",
            "url": up.repo,
            "path": up.subpath,
            "ref": up.ref,
            "sha": sha,
        }
    sources = vendor_sources()
    sources[up.name] = {"source": source, "digest": tree_digest(dest)}
    write_json(VENDOR_SOURCES, dict(sorted(sources.items())))
    return dest


def vendor_drift(name: str) -> bool:
    """Whether the checked-in copy no longer matches what was fetched."""
    record = vendor_sources().get(name, {})
    dest = VENDOR_DIR / name
    if not record.get("digest") or not dest.is_dir():
        return False
    return tree_digest(dest) != record["digest"]


def cmd_vendor(args: argparse.Namespace) -> int:
    (up,) = upstreams([args.plugin]) or [None]
    if up is None:
        print(bad(f"{args.plugin} has no upstream coordinates to fetch from"))
        return 1
    if up.vendored:
        print(f"{args.plugin} is already vendored under {tilde(VENDOR_DIR / up.name)}")
        return 0

    dest = vendor_entry(up, up.sha)
    files = sum(1 for p in dest.rglob("*") if p.is_file())
    rewrite_source(up.name, f"./vendor/{up.name}")
    print(f"  {ok('vendored'):<22}{up.name:<26}{files} file(s) at {up.sha[:7]}")
    print(dim(f"  source is now ./vendor/{up.name}; coordinates in {tilde(VENDOR_SOURCES)}"))
    reinstall([up.name])
    return 0


def cmd_unvendor(args: argparse.Namespace) -> int:
    (up,) = upstreams([args.plugin]) or [None]
    if up is None or not up.vendored:
        print(bad(f"{args.plugin} is not vendored"))
        return 1

    record = vendor_sources()
    source = record.pop(up.name)["source"]
    rewrite_source(up.name, source)

    dest = VENDOR_DIR / up.name
    if dest.is_dir():
        shutil.rmtree(dest)
    if record:
        write_json(VENDOR_SOURCES, record)
    elif VENDOR_SOURCES.is_file():
        VENDOR_SOURCES.unlink()
    if VENDOR_DIR.is_dir() and not any(VENDOR_DIR.iterdir()):
        VENDOR_DIR.rmdir()

    print(f"  {ok('unvendored'):<22}{up.name:<26}back to {up.repo} at {up.sha[:7]}")
    reinstall([up.name])
    return 0


# --------------------------------------------------------------------------
# readme
# --------------------------------------------------------------------------
#
# The repo went its whole life without a README; the workflow lived in sync.py's
# docstring, which is the one place nobody looks. An index is worth having and
# not worth maintaining by hand, so it is generated between markers and the
# prose around it stays hand-written.

BEGIN = "<!-- BEGIN GENERATED — ./sync.py readme -->"
END = "<!-- END GENERATED -->"

SCAFFOLD = f"""# agentic-tooling

Skills, agents and plugins for Claude Code, and the third-party ones this setup
consumes. `./sync.py` fans them out; `.claude-plugin/marketplace.json` tracks the
rest. Everything below this line is generated — run `./sync.py readme`.

{BEGIN}
{END}
"""


def cell_text(text: str, limit: int = 180) -> str:
    """One table cell: no raw pipes or newlines, and short enough to scan.

    The reference skills still carry the long trigger-phrase descriptions they
    were written with for model invocation — 700 chars of "also trigger when".
    Under `disable-model-invocation` that text does no work, and in an index it
    does less, so the first sentence is what the table shows.
    """
    text = " ".join(text.split()).replace("|", "\\|")
    if len(text) <= limit:
        return text
    stop = text.find(". ", 40)
    if 0 < stop <= limit:
        return text[: stop + 1]
    return text[: text.rfind(" ", 0, limit)] + " …"


def readme_body() -> str:
    out: list[str] = []
    plugins = {p["id"].split("@")[0]: p for p in installed_plugins()}

    def describe(skill_md: Path) -> tuple[str, str]:
        name, description, suppressed = listing_text(skill_md)
        return name, ("manual" if suppressed else "**automatic**"), description

    own = own_skills()
    out.append(f"## Skills ({len(own)})\n")
    out.append("Invoked by name. *manual* means `disable-model-invocation`: it")
    out.append("appears in the `/` menu, costs nothing in the skill listing, and")
    out.append("Claude will not reach for it on its own.\n")
    out.append("| | Invocation | |")
    out.append("|---|---|---|")
    for skill in own:
        name, mode, description = describe(skill / "SKILL.md")
        out.append(f"| `/{name}` | {mode} | {cell_text(description)} |")

    for plugin in own_plugins():
        manifest = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text())
        skills = plugin_skills(plugin)
        out.append(f"\n## `{plugin.name}` plugin ({len(skills)} skills)\n")
        out.append(f"{manifest.get('description', '')}\n")
        out.append(
            f"Version {manifest.get('version', '?')}. Toggle the whole family with "
            f"`claude plugin disable {plugin.name}@skills-dir`.\n"
        )
        out.append("| | Invocation | |")
        out.append("|---|---|---|")
        for skill in skills:
            name, mode, description = describe(skill / "SKILL.md")
            out.append(f"| `/{plugin.name}:{name}` | {mode} | {cell_text(description)} |")

    agents = own_agents()
    if agents:
        out.append(f"\n## Agents ({len(agents)})\n")
        out.append("| | |")
        out.append("|---|---|")
        for agent in agents:
            fields, _ = parse_frontmatter(agent)
            label = fields.get("name") or agent.stem
            out.append(f"| `{label}` | {cell_text(fields.get('description', ''))} |")

    entries = marketplace_entries()
    out.append(f"\n## Third party ({len(entries)})\n")
    out.append("Installed by Claude Code from `.claude-plugin/marketplace.json`, each")
    out.append("pinned to a reviewed commit. `./sync.py check` says what moved upstream,")
    out.append("`./sync.py diff <name>` shows it, `./sync.py update <name>` accepts it.\n")
    out.append("| | Pinned | Consumed | |")
    out.append("|---|---|---|---|")
    for entry in entries:
        up = entry_upstream(entry)
        name = entry["name"]
        got = plugins.get(name)
        state = "" if got and got.get("enabled") else " *(disabled)*" if got else " *(not installed)*"
        if up is None:
            out.append(f"| {name}{state} | — | — | {cell_text(entry.get('description', ''))} |")
            continue
        pin = f"[`{up.sha[:7]}`]({upstream_url(up)})"
        scope = f"`{up.subpath}`" if up.subpath else "whole repo"
        if up.vendored:
            scope += f", vendored in `vendor/{name}/`"
        if got:
            count = len(list(Path(got["installPath"]).rglob("SKILL.md")))
            scope += f" — {count} skill{'s' if count != 1 else ''}"
        out.append(
            f"| [{name}](https://github.com/{up.repo}){state} | {pin} | {scope} | "
            f"{cell_text(entry.get('description', ''))} |"
        )

    listed = listed_skills()
    counted = [s for s in listed if not s[2]]
    out.append("\n## Listing budget\n")
    out.append(
        f"{sum(s[1] for s in counted):,} chars across {len(counted)} listed entries; "
        f"{len(listed) - len(counted)} more are manual-only and cost nothing. "
        "`./sync.py status` breaks it down."
    )
    return "\n".join(out) + "\n"


def cmd_readme(args: argparse.Namespace) -> int:
    readme = REPO / "README.md"
    text = readme.read_text() if readme.is_file() else SCAFFOLD
    if BEGIN not in text or END not in text:
        print(bad(f"{readme.name} has no {BEGIN} … {END} markers"))
        print(dim("  delete it to regenerate from scratch, or add the markers by hand"))
        return 1

    head, _, rest = text.partition(BEGIN)
    _, _, tail = rest.partition(END)
    new = f"{head}{BEGIN}\n\n{readme_body()}\n{END}{tail}"
    if new == text:
        print(f"{ok('unchanged')} {readme.name}")
        return 0
    readme.write_text(new)
    print(f"{ok('wrote')} {readme.name}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sync.py",
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command")

    p_link = sub.add_parser("link", help="symlink fan-out (default)")
    p_link.add_argument(
        "-n", "--dry-run", action="store_true", help="report what would change, change nothing"
    )
    p_link.set_defaults(func=cmd_link)

    p_status = sub.add_parser("status", help="offline report; no network")
    p_status.set_defaults(func=cmd_status)

    p_readme = sub.add_parser("readme", help="regenerate the README index")
    p_readme.set_defaults(func=cmd_readme)

    p_check = sub.add_parser("check", help="which entries are behind upstream [network]")
    p_check.add_argument("plugin", nargs="*", help="default: every entry")
    p_check.set_defaults(func=cmd_check)

    p_diff = sub.add_parser("diff", help="upstream patch, filtered to what we consume [network]")
    p_diff.add_argument("plugin")
    p_diff.set_defaults(func=cmd_diff)

    p_update = sub.add_parser("update", help="bump a pinned sha and reinstall [network]")
    p_update.add_argument("plugin", nargs="*", help="default: every entry that is behind")
    p_update.add_argument(
        "--no-commit", action="store_true", help="bump the sha but leave the commit to you"
    )
    p_update.set_defaults(func=cmd_update)

    p_vendor = sub.add_parser("vendor", help="promote an entry to a checked-in copy [network]")
    p_vendor.add_argument("plugin")
    p_vendor.set_defaults(func=cmd_vendor)

    p_unvendor = sub.add_parser("unvendor", help="restore an entry's remote source")
    p_unvendor.add_argument("plugin")
    p_unvendor.set_defaults(func=cmd_unvendor)

    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    # Bare `./sync.py` means `./sync.py link`, the thing you run most often.
    if not argv or argv[0].startswith("-") and argv[0] not in ("-h", "--help"):
        argv = ["link", *argv]
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
