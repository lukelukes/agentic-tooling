#!/usr/bin/env -S uv run --python 3.14 --script
# /// script
# requires-python = ">=3.14"
# ///
"""Sync local paths with their upstream remote sources.

Usage:
    uv run sync.py                  # sync all mappings
    uv run sync.py --dry-run        # show what would be done
    uv run sync.py --check          # check which are out of date
    uv run sync.py <key>            # sync a single mapping by key
"""

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).parent

# ── Mappings ──────────────────────────────────────────────────────────
# "local/path" (relative to repo root) -> "github:owner/repo/path@ref"
#
# Format: "github:<owner>/<repo>/<path>@<branch>"
#   - <path> can be a file or directory
#   - @<branch> is optional, defaults to "main"

MAPPINGS: dict[str, str] = {
    "agents/skills/skill-creator": "github:anthropics/skills/skills/skill-creator@main",
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


def fetch_remote(owner: str, repo: str, path: str, ref: str, dest: Path):
    """Sparse-checkout a specific path from a github repo into dest."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "repo"
        subprocess.run(
            ["git", "clone", "--depth=1", "--filter=blob:none", "--sparse",
             f"--branch={ref}", f"https://github.com/{owner}/{repo}.git",
             str(tmp_path)],
            check=True, capture_output=True, text=True,
        )
        subprocess.run(
            ["git", "sparse-checkout", "set", path],
            cwd=tmp_path, check=True, capture_output=True, text=True,
        )

        src = tmp_path / path
        if not src.exists():
            raise FileNotFoundError(f"Path '{path}' not found in {owner}/{repo}@{ref}")

        if dest.exists():
            shutil.rmtree(dest) if dest.is_dir() else dest.unlink()
        src.copy(dest, preserve_metadata=True)


def hash_path(p: Path) -> str:
    """Content hash for a file or directory."""
    h = hashlib.sha256()
    if p.info.is_file():
        h.update(p.read_bytes())
    elif p.info.is_dir():
        for f in sorted(p.rglob("*")):
            if f.info.is_file():
                h.update(str(f.relative_to(p)).encode())
                h.update(f.read_bytes())
    return h.hexdigest()


def sync_one(key: str, remote: str, *, dry_run: bool = False, check_only: bool = False) -> bool:
    """Sync a single mapping. Returns True if changes were made/detected."""
    owner, repo, path, ref = parse_remote(remote)
    dest = ROOT / key
    tag = f"{key} <- {owner}/{repo}/{path}@{ref}"

    if check_only or dry_run:
        old_hash = hash_path(dest) if dest.exists() else None
        with tempfile.TemporaryDirectory() as tmp:
            fetch_remote(owner, repo, path, ref, Path(tmp) / "check")
            new_hash = hash_path(Path(tmp) / "check")

        match (old_hash, old_hash == new_hash):
            case (_, True):
                print(f"  up-to-date  {tag}")
                return False
            case (None, _):
                print(f"  NEW         {tag}")
            case _:
                print(f"  outdated    {tag}")

        if dry_run:
            print(f"              would sync {tag}")
        return True

    print(f"  syncing     {tag}")
    old_hash = hash_path(dest) if dest.exists() else None
    fetch_remote(owner, repo, path, ref, dest)
    new_hash = hash_path(dest)

    if old_hash == new_hash:
        print(f"  up-to-date  {tag}")
        return False

    print(f"  updated     {tag}")
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Sync local paths with upstream remotes.",
        suggest_on_error=True,
        color=True,
    )
    parser.add_argument("key", nargs="?", help="Sync a single mapping by its local path key")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--check", action="store_true", help="Check which mappings are out of date")
    parser.add_argument("--list", action="store_true", help="List all mappings")
    args = parser.parse_args()

    if not MAPPINGS:
        print("No mappings configured. Edit MAPPINGS in sync.py.")
        return

    if args.list:
        for key, remote in MAPPINGS.items():
            exists = "ok" if (ROOT / key).exists() else "MISSING"
            print(f"  [{exists:>7}]  {key} <- {remote}")
        return

    if args.key and args.key not in MAPPINGS:
        print(f"Unknown mapping key: {args.key}")
        print(f"Available: {', '.join(MAPPINGS.keys())}")
        sys.exit(1)

    targets = {args.key: MAPPINGS[args.key]} if args.key else MAPPINGS
    changed = failed = 0
    for key, remote in targets.items():
        try:
            if sync_one(key, remote, dry_run=args.dry_run, check_only=args.check):
                changed += 1
        except Exception as e:
            print(f"  FAILED      {key}: {e}")
            failed += 1

    label = "need updating" if args.check else "would be synced" if args.dry_run else "updated"
    parts = [f"{changed}/{len(targets)} {label}"]
    if failed:
        parts.append(f"{failed} failed")
    print(f"\n{', '.join(parts)}.")


if __name__ == "__main__":
    main()
