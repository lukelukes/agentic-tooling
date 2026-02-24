#!/usr/bin/env -S uv run --python 3.14 --script
# /// script
# requires-python = ">=3.14"
# ///
"""Sync local paths with their upstream remote sources.

Usage:
    uv run sync.py                  # install at pinned versions from lock file
    uv run sync.py --update [key]   # fetch latest and update lock file
    uv run sync.py --check          # check for upstream updates (with GitHub links)
    uv run sync.py --list           # list all mappings
"""

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent
LOCK_FILE = ROOT / "sync-lock.json"

# ── Mappings ──────────────────────────────────────────────────────────
# "local/path" (relative to repo root) -> "github:owner/repo/path@ref"
#
# Format: "github:<owner>/<repo>/<path>@<branch>"
#   - <path> can be a file or directory
#   - @<branch> is optional, defaults to "main"

SKILLS_DIR = "agents/skills"

MAPPINGS: dict[str, str] = {
    f"{SKILLS_DIR}/skill-creator": "github:anthropics/skills/skills/skill-creator@main",
    f"{SKILLS_DIR}/humanizer/SKILL.md": "github:blader/humanizer/SKILL.md@main",
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
        ["git", "ls-remote", f"https://github.com/{owner}/{repo}.git", ref],
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
    url = f"https://github.com/{owner}/{repo}.git"
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


def install_one(key: str, remote: str, lock: dict) -> bool:
    """Install at pinned commit from lock file. Returns True if installed."""
    owner, repo, path, ref = parse_remote(remote)
    tag = f"{key} <- {owner}/{repo}/{path}@{ref}"
    entry = lock.get(key)

    if not entry:
        print(f"  NOT PINNED  {tag}  (run --update)")
        return False

    dest = ROOT / key
    if dest.exists() and hash_path(dest) == entry["hash"]:
        print(f"  up-to-date  {tag}")
        return False

    print(f"  installing  {tag}  ({entry['commit'][:8]})")
    fetch_remote(owner, repo, path, entry["commit"], dest, is_commit=True)
    return True


def update_one(key: str, remote: str, lock: dict) -> bool:
    """Fetch latest from remote branch and update lock entry. Returns True if changed."""
    owner, repo, path, ref = parse_remote(remote)
    tag = f"{key} <- {owner}/{repo}/{path}@{ref}"
    dest = ROOT / key
    entry = lock.get(key)

    print(f"  syncing     {tag}")
    commit = fetch_remote(owner, repo, path, ref, dest)
    new_hash = hash_path(dest)

    if entry and entry["commit"] == commit:
        print(f"  up-to-date  {tag}")
        return False

    lock[key] = {"commit": commit, "hash": new_hash}
    if entry:
        print(f"  updated     {tag}  ({entry['commit'][:8]} -> {commit[:8]})")
    else:
        print(f"  pinned      {tag}  ({commit[:8]})")
    return True


def check_one(key: str, remote: str, lock: dict):
    """Check if upstream has updates. Prints GitHub links for comparison."""
    owner, repo, path, ref = parse_remote(remote)
    tag = f"{key} <- {owner}/{repo}/{path}@{ref}"
    entry = lock.get(key)

    if not entry:
        print(f"  NOT PINNED  {tag}")
        return

    latest = get_latest_commit(owner, repo, ref)

    if latest == entry["commit"]:
        print(f"  up-to-date  {tag}  ({entry['commit'][:8]})")
    else:
        print(f"  outdated    {tag}  (pinned: {entry['commit'][:8]}, latest: {latest[:8]})")
        print(f"              pinned:  {github_blob_url(owner, repo, path, entry['commit'])}")
        print(f"              latest:  {github_blob_url(owner, repo, path, latest)}")
        print(f"              history: {github_history_url(owner, repo, path, ref)}")

    dest = ROOT / key
    if dest.exists() and hash_path(dest) != entry["hash"]:
        print(f"              (locally modified)")


def main():
    parser = argparse.ArgumentParser(
        description="Sync local paths with upstream remotes.",
        suggest_on_error=True,
        color=True,
    )
    parser.add_argument("key", nargs="?", help="Target a single mapping by its local path key")
    parser.add_argument("--update", action="store_true", help="Fetch latest and update lock file")
    parser.add_argument("--check", action="store_true", help="Check for upstream updates")
    parser.add_argument("--list", action="store_true", help="List all mappings")
    args = parser.parse_args()

    if not MAPPINGS:
        print("No mappings configured. Edit MAPPINGS in sync.py.")
        return

    if args.list:
        lock = read_lock()
        for key, remote in MAPPINGS.items():
            dest = ROOT / key
            entry = lock.get(key)
            status = "ok" if dest.exists() else "MISSING"
            pin = f"  ({entry['commit'][:8]})" if entry else "  (not pinned)"
            print(f"  [{status:>7}]  {key} <- {remote}{pin}")
        return

    if args.key and args.key not in MAPPINGS:
        print(f"Unknown mapping key: {args.key}")
        print(f"Available: {', '.join(MAPPINGS.keys())}")
        sys.exit(1)

    targets = {args.key: MAPPINGS[args.key]} if args.key else MAPPINGS
    lock = read_lock()

    if args.check:
        for key, remote in targets.items():
            try:
                check_one(key, remote, lock)
            except Exception as e:
                print(f"  FAILED      {key}: {e}")
        return

    # No lock file yet → auto-update to create it
    update = args.update or not LOCK_FILE.exists()

    changed = failed = 0
    for key, remote in targets.items():
        try:
            if update:
                result = update_one(key, remote, lock)
            else:
                result = install_one(key, remote, lock)
            if result:
                changed += 1
        except Exception as e:
            print(f"  FAILED      {key}: {e}")
            failed += 1

    if update:
        write_lock(lock)

    label = "updated" if update else "installed"
    parts = [f"{changed}/{len(targets)} {label}"]
    if failed:
        parts.append(f"{failed} failed")
    print(f"\n{', '.join(parts)}.")


if __name__ == "__main__":
    main()
