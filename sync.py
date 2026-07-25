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
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parent

# Where our own things live in this repo.
SKILLS_DIR = REPO / "skills"
AGENTS_DIR = REPO / "agents"
PLUGINS_DIR = REPO / "plugins"
VENDOR_DIR = REPO / "vendor"
MARKETPLACE = REPO / ".claude-plugin" / "marketplace.json"

HOME = Path.home()

# Claude Code reads skills from ~/.claude/skills and agents from ~/.claude/agents.
CLAUDE_SKILLS = HOME / ".claude" / "skills"
CLAUDE_AGENTS = HOME / ".claude" / "agents"
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


# --------------------------------------------------------------------------
# symlink fan-out
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Link:
    src: Path  # what this repo owns
    dst: Path  # where an agent tool looks for it


def link_plan() -> list[Link]:
    """Every symlink this repo wants to exist.

    Loose skills reach all three roots. Agents are Claude-Code-only — ~/.agents and
    ~/.cursor have no equivalent concept.

    A plugin is linked as a *directory* into ~/.claude/skills, which is what makes it
    a skills-dir plugin and gives it a /namespace:command prefix. The other two roots
    do not understand plugin namespacing, so they get the plugin's individual skills
    instead; that is what "everything reaches Cursor too" means for a plugin.
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
                plan.append(Link(skill, root / skill.name))

    return plan


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
    * **stale** — a live link into this repo that the plan no longer contains,
      which is what a renamed or deleted skill leaves behind.

    A live link into the plugin cache is never pruned as stale: third-party links
    are added to the plan by a later phase, and being conservative here costs a
    dangling link at worst while the alternative deletes working ones.
    """
    wanted = {link.dst for link in plan}
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
            elif entry not in wanted and REPO in target.parents:
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
            print(f"  {ok(verb):<22} {tilde(link.dst)} -> {link.src.relative_to(REPO)}")
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


def cmd_status(args: argparse.Namespace) -> int:
    return not_yet("status")


def cmd_check(args: argparse.Namespace) -> int:
    return not_yet("check")


def cmd_diff(args: argparse.Namespace) -> int:
    return not_yet("diff")


def cmd_update(args: argparse.Namespace) -> int:
    return not_yet("update")


def cmd_vendor(args: argparse.Namespace) -> int:
    return not_yet("vendor")


def cmd_unvendor(args: argparse.Namespace) -> int:
    return not_yet("unvendor")


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

    p_check = sub.add_parser("check", help="which entries are behind upstream [network]")
    p_check.set_defaults(func=cmd_check)

    p_diff = sub.add_parser("diff", help="upstream patch, filtered to what we consume [network]")
    p_diff.add_argument("plugin")
    p_diff.set_defaults(func=cmd_diff)

    p_update = sub.add_parser("update", help="bump a pinned sha and reinstall [network]")
    p_update.add_argument("plugin", nargs="?")
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
