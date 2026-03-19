#!/usr/bin/env -S uv run --python 3.14 --script
# /// script
# requires-python = ">=3.14"
# ///
"""Sync local paths with their upstream remote sources.

Usage:
    uv run sync.py                  # install at pinned versions (default)
    uv run sync.py install [key]    # same as above, optionally targeting one key
    uv run sync.py update [key]     # fetch latest and update lock file
    uv run sync.py check [key]      # check for upstream updates (with GitHub links)
    uv run sync.py list             # list all mappings
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).parent
LOCK_FILE = ROOT / "sync-lock.json"

# ── ANSI helpers ─────────────────────────────────────────────────────

_COLOR = sys.stdout.isatty()

def green(s: str) -> str: return f"\033[32m{s}\033[0m" if _COLOR else s
def yellow(s: str) -> str: return f"\033[33m{s}\033[0m" if _COLOR else s
def red(s: str) -> str: return f"\033[31m{s}\033[0m" if _COLOR else s
def dim(s: str) -> str: return f"\033[2m{s}\033[0m" if _COLOR else s
def bold(s: str) -> str: return f"\033[1m{s}\033[0m" if _COLOR else s

# ── Mappings ──────────────────────────────────────────────────────────
# "local/path" (relative to repo root) -> "github:owner/repo/path@ref"
#
# Format: "github:<owner>/<repo>/<path>@<branch>"
#   - <path> can be a file or directory
#   - @<branch> is optional, defaults to "main"

COMMANDS_DIR = "agents/commands"
SKILLS_DIR = "agents/skills"

MAPPINGS: dict[str, str] = {
    f"{SKILLS_DIR}/ext/frontend-design": "github:anthropics/skills/skills/frontend-design@main",
    f"{SKILLS_DIR}/ext/skill-creator": "github:anthropics/skills/skills/skill-creator@main",
    f"{SKILLS_DIR}/ext/hegelian-dialectic/SKILL.md": "github:KyleAMathews/hegelian-dialectic-skill/SKILL.md@main",
    f"{SKILLS_DIR}/ext/humanizer/SKILL.md": "github:blader/humanizer/SKILL.md@main",
    f"{SKILLS_DIR}/ext/visual-explainer/SKILL.md": "github:nicobailon/visual-explainer/plugins/visual-explainer/SKILL.md@main",
    f"{SKILLS_DIR}/ext/impeccable-design": "github:pbakaus/impeccable/source/skills@main",
    f"{SKILLS_DIR}/ext/emil-design-eng/SKILL.md": "github:emilkowalski/skill/skills/emil-design-eng/SKILL.md@main",

    f"{COMMANDS_DIR}/ext/visual-explainer": "github:nicobailon/visual-explainer/plugins/visual-explainer/commands@main"
}


type Remote = tuple[str, str, str, str]  # (owner, repo, path, ref)


def parse_remote(remote: str) -> Remote:
    """Parse a remote string into (owner, repo, path, ref)."""
    match remote.split(":", 1):
        case ["github", rest]:
            path_part, _, ref = rest.rpartition("@")
            if not path_part:
                path_part, ref = ref, "main"
            match path_part.split("/", 2):
                case [owner, repo, path]:
                    return owner, repo, path, ref
                case _:
                    raise ValueError(f"Expected github:owner/repo/path, got: {remote}")
        case _:
            raise ValueError(f"Unsupported remote format: {remote}")


# ── Lock file ─────────────────────────────────────────────────────────


def read_lock() -> dict:
    if LOCK_FILE.exists():
        return json.loads(LOCK_FILE.read_text())
    return {}


def write_lock(lock: dict):
    LOCK_FILE.write_text(json.dumps(lock, indent=2) + "\n")


# ── Hashing ───────────────────────────────────────────────────────────


def hash_path(p: Path) -> str:
    """Content hash for a file or directory."""
    h = hashlib.sha256()
    if p.is_file():
        h.update(p.read_bytes())
    elif p.is_dir():
        for f in sorted(p.rglob("*")):
            if f.is_file():
                h.update(str(f.relative_to(p)).encode())
                h.update(f.read_bytes())
    return h.hexdigest()


# ── GitHub URLs ───────────────────────────────────────────────────────


def github_blob_url(owner: str, repo: str, path: str, ref: str) -> str:
    return f"https://github.com/{owner}/{repo}/blob/{ref}/{path}"


def github_history_url(owner: str, repo: str, path: str, ref: str) -> str:
    return f"https://github.com/{owner}/{repo}/commits/{ref}/{path}"


# ── Remote operations ─────────────────────────────────────────────────


def get_latest_commit(owner: str, repo: str, ref: str) -> str:
    """Get the latest commit SHA on a branch without cloning."""
    result = subprocess.run(
        ["git", "ls-remote", f"git@github.com:{owner}/{repo}.git", ref],
        capture_output=True, text=True, check=True,
    )
    for line in result.stdout.strip().splitlines():
        sha, _ = line.split("\t", 1)
        return sha
    raise ValueError(f"Ref '{ref}' not found in {owner}/{repo}")


def fetch_remote(
    owner: str, repo: str, path: str, target: str, dest: Path,
    *, is_commit: bool = False,
) -> str:
    """Sparse-checkout a specific path from GitHub into dest. Returns commit SHA."""
    url = f"git@github.com:{owner}/{repo}.git"
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "repo"

        if is_commit:
            # Fetch exact commit by SHA
            subprocess.run(
                ["git", "init", str(tmp_path)],
                check=True, capture_output=True, text=True,
            )
            subprocess.run(
                ["git", "sparse-checkout", "init", "--no-cone"],
                cwd=tmp_path, check=True, capture_output=True, text=True,
            )
            subprocess.run(
                ["git", "sparse-checkout", "set", "--no-cone", path],
                cwd=tmp_path, check=True, capture_output=True, text=True,
            )
            subprocess.run(
                ["git", "fetch", "--depth=1", url, target],
                cwd=tmp_path, check=True, capture_output=True, text=True,
            )
            subprocess.run(
                ["git", "checkout", "FETCH_HEAD"],
                cwd=tmp_path, check=True, capture_output=True, text=True,
            )
        else:
            # Clone latest from branch
            subprocess.run(
                ["git", "clone", "--depth=1", "--filter=blob:none", "--sparse",
                 f"--branch={target}", url, str(tmp_path)],
                check=True, capture_output=True, text=True,
            )
            subprocess.run(
                ["git", "sparse-checkout", "set", "--no-cone", path],
                cwd=tmp_path, check=True, capture_output=True, text=True,
            )

        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=tmp_path,
            capture_output=True, text=True, check=True,
        ).stdout.strip()

        src = tmp_path / path
        if not src.exists():
            raise FileNotFoundError(
                f"Path '{path}' not found in {owner}/{repo}@{target}"
            )

        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
        src.copy(dest, preserve_metadata=True)

        return commit


# ── Commands ──────────────────────────────────────────────────────────


def install_one(key: str, remote: str, lock: dict) -> str:
    """Install at pinned commit from lock file. Returns status: 'installed'|'fresh'|'not_pinned'."""
    owner, repo, path, ref = parse_remote(remote)
    remote_label = f"{owner}/{repo}/{path}@{ref}"
    entry = lock.get(key)

    if not entry:
        print(f"{red('Not pinned')}  {key}  {dim('(run update)')}")
        return "not_pinned"

    dest = ROOT / key
    if dest.exists() and hash_path(dest) == entry["hash"]:
        print(f"    {green('Fresh')}  {key}")
        return "fresh"

    sha = entry["commit"][:7]
    fetch_remote(owner, repo, path, entry["commit"], dest, is_commit=True)
    print(f"{green('Installed')}  {key}  {dim(f'({sha})')}")
    print(f"           {dim(remote_label)}")
    return "installed"


def update_one(key: str, remote: str, lock: dict) -> str:
    """Fetch latest from remote branch and update lock entry. Returns status: 'updated'|'pinned'|'fresh'."""
    owner, repo, path, ref = parse_remote(remote)
    remote_label = f"{owner}/{repo}/{path}@{ref}"
    dest = ROOT / key
    entry = lock.get(key)

    commit = fetch_remote(owner, repo, path, ref, dest)
    new_hash = hash_path(dest)

    if entry and new_hash == entry["hash"]:
        print(f"    {green('Fresh')}  {key}")
        return "fresh"

    lock[key] = {"commit": commit, "hash": new_hash}
    if entry:
        old_sha = entry["commit"][:7]
        new_sha = commit[:7]
        print(f"  {yellow('Updated')}  {key}  {dim(f'({old_sha} → {new_sha})')}")
        print(f"           {dim(remote_label)}")
        return "updated"
    else:
        print(f"   {green('Pinned')}  {key}  {dim(f'({commit[:7]})')}")
        print(f"           {dim(remote_label)}")
        return "pinned"


def check_one(key: str, remote: str, lock: dict) -> str:
    """Check if upstream has updates. Returns status: 'fresh'|'outdated'|'not_pinned'."""
    owner, repo, path, ref = parse_remote(remote)
    entry = lock.get(key)

    if not entry:
        print(f"{red('Not pinned')}  {key}")
        return "not_pinned"

    latest = get_latest_commit(owner, repo, ref)

    if latest == entry["commit"]:
        print(f"    {green('Fresh')}  {key}  {dim(f'({entry["commit"][:7]})')}")
        dest = ROOT / key
        if dest.exists() and hash_path(dest) != entry["hash"]:
            print(f"           {dim('(locally modified)')}")
        return "fresh"
    else:
        pinned_sha = entry["commit"][:7]
        latest_sha = latest[:7]
        print(f" {yellow('Outdated')}  {key}  {dim(f'({pinned_sha} → {latest_sha})')}")
        print(f"           {dim('pinned:  ' + github_blob_url(owner, repo, path, entry['commit']))}")
        print(f"           {dim('latest:  ' + github_blob_url(owner, repo, path, latest))}")
        print(f"           {dim('history: ' + github_history_url(owner, repo, path, ref))}")
        dest = ROOT / key
        if dest.exists() and hash_path(dest) != entry["hash"]:
            print(f"           {dim('(locally modified)')}")
        return "outdated"


def resolve_targets(key: str | None) -> dict[str, str]:
    """Resolve which mappings to operate on."""
    if key:
        if key not in MAPPINGS:
            print(f"{red('Error')}: unknown key {bold(key)}")
            print(f"  available: {dim(', '.join(MAPPINGS.keys()))}")
            sys.exit(1)
        return {key: MAPPINGS[key]}
    return MAPPINGS


def cmd_install(args: argparse.Namespace):
    """Install at pinned versions from lock file."""
    if not LOCK_FILE.exists():
        print(f"{red('Error')}: no lock file found. Run {bold('update')} first.")
        sys.exit(1)

    targets = resolve_targets(args.key)
    lock = read_lock()
    t0 = time.monotonic()

    changed = failed = 0
    for key, remote in targets.items():
        try:
            status = install_one(key, remote, lock)
            if status == "installed":
                changed += 1
        except Exception as e:
            print(f"   {red('Failed')}  {key}: {e}")
            failed += 1

    elapsed = time.monotonic() - t0
    unchanged = len(targets) - changed - failed
    parts = []
    if changed:
        parts.append(bold(green(f"{changed} installed")))
    if unchanged:
        parts.append(f"{unchanged} unchanged")
    if failed:
        parts.append(bold(red(f"{failed} failed")))
    print(f"\n  {', '.join(parts)} {dim(f'in {elapsed:.1f}s')}")


def cmd_update(args: argparse.Namespace):
    """Fetch latest from upstream and update lock file."""
    targets = resolve_targets(args.key)
    lock = read_lock()
    t0 = time.monotonic()

    changed = failed = 0
    for key, remote in targets.items():
        try:
            status = update_one(key, remote, lock)
            if status in ("updated", "pinned"):
                changed += 1
        except Exception as e:
            print(f"   {red('Failed')}  {key}: {e}")
            failed += 1

    write_lock(lock)

    elapsed = time.monotonic() - t0
    unchanged = len(targets) - changed - failed
    parts = []
    if changed:
        parts.append(bold(green(f"{changed} updated")))
    if unchanged:
        parts.append(f"{unchanged} unchanged")
    if failed:
        parts.append(bold(red(f"{failed} failed")))
    print(f"\n  {', '.join(parts)} {dim(f'in {elapsed:.1f}s')}")


def cmd_check(args: argparse.Namespace):
    """Check for upstream updates without modifying anything."""
    if not LOCK_FILE.exists():
        print(f"{red('Error')}: no lock file found. Run {bold('update')} first.")
        sys.exit(1)

    targets = resolve_targets(args.key)
    lock = read_lock()
    t0 = time.monotonic()

    outdated = failed = 0
    for key, remote in targets.items():
        try:
            status = check_one(key, remote, lock)
            if status == "outdated":
                outdated += 1
        except Exception as e:
            print(f"   {red('Failed')}  {key}: {e}")
            failed += 1

    elapsed = time.monotonic() - t0
    parts = []
    if outdated:
        parts.append(bold(yellow(f"{outdated} outdated")))
    parts.append(f"{len(targets) - outdated - failed} fresh")
    if failed:
        parts.append(bold(red(f"{failed} failed")))
    print(f"\n  {', '.join(parts)} {dim(f'in {elapsed:.1f}s')}")


def cmd_list(args: argparse.Namespace):
    """List all mappings and their status."""
    lock = read_lock()
    for key, remote in MAPPINGS.items():
        dest = ROOT / key
        entry = lock.get(key)
        if not dest.exists():
            print(f"  {red('Missing')}  {key}")
        elif entry:
            print(f"    {green('Fresh')}  {key}  {dim(f'({entry["commit"][:7]})')}")
        else:
            print(f"{red('Not pinned')}  {key}")
        print(f"           {dim(remote)}")


def main():
    parser = argparse.ArgumentParser(
        description="Sync local paths with upstream remotes.",
        suggest_on_error=True,
        color=True,
    )
    sub = parser.add_subparsers(dest="command")

    p_install = sub.add_parser("install", help="Install at pinned versions from lock file (default)")
    p_install.add_argument("key", nargs="?", help="Target a single mapping by its local path key")
    p_install.set_defaults(func=cmd_install)

    p_update = sub.add_parser("update", help="Fetch latest and update lock file")
    p_update.add_argument("key", nargs="?", help="Target a single mapping by its local path key")
    p_update.set_defaults(func=cmd_update)

    p_check = sub.add_parser("check", help="Check for upstream updates")
    p_check.add_argument("key", nargs="?", help="Target a single mapping by its local path key")
    p_check.set_defaults(func=cmd_check)

    p_list = sub.add_parser("list", help="List all mappings")
    p_list.set_defaults(func=cmd_list)

    args = parser.parse_args()

    if not MAPPINGS:
        print("No mappings configured. Edit MAPPINGS in sync.py.")
        return

    if not args.command:
        args.key = None
        cmd_install(args)
    else:
        args.func(args)


if __name__ == "__main__":
    main()
