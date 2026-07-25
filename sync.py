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


# --------------------------------------------------------------------------
# subcommands
# --------------------------------------------------------------------------


def cmd_link(args: argparse.Namespace) -> int:
    return not_yet("link")


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
