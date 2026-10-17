#!/usr/bin/env python3
"""Find bug fixes that shipped without a test.

SQLite's rule: "that bug is not considered fixed until new test cases that would
exhibit the bug have been added." This script measures how close a repository
comes to that rule, by finding commits that look like bug fixes and checking
whether each one also touched a test.

A fix with no test is not proof of a gap -- the test may have landed separately,
or the bug may have been unreachable from any test seam. It is a list of places
worth looking, ordered by the fact that someone already paid to find each one.

Usage:
    regression_gap.py [REPO] [--since REV] [--limit N] [--json] [--all]

    REPO        path to the repository (default: cwd)
    --since     only consider commits after this rev/date (e.g. v1.2.0, 6.months.ago)
    --limit     stop after N fix commits (default: 200)
    --json      emit machine-readable JSON instead of a table
    --all       list every fix commit, not just the ones missing a test
"""

import argparse
import json
import re
import subprocess
import sys

# Subjects that mean "this commit repaired broken behaviour". Deliberately not
# matching "fix lint", "fix typo", "fix formatting" -- those have no behaviour to
# regress, so demanding a test for them is noise.
FIX_SUBJECT = re.compile(
    r"""(?ix)
    ^(?:\w+)?(?:\([^)]*\))?!?:\s*(?:fix|bugfix|hotfix)\b   # conventional: fix(scope): ...
    | \bfix(?:e[sd])?\b
    | \bbug\b
    | \bregress(?:ion|ed)\b
    | \bcrash(?:es|ed)?\b
    | \bbroken\b
    | \bhotfix\b
    | \bpatch(?:es|ed)\b
    | \bcorrect(?:s|ed)\b
    | \bresolve[sd]?\s+\#\d+
    """
)

NOT_REALLY_A_FIX = re.compile(
    r"""(?ix)
    \b(?:typo|lint|linter|format(?:ting)?|whitespace|indent(?:ation)?|spelling
      |comment|docs?|readme|changelog|rename|gofmt|prettier|clippy|style)\b
    """
)

# Path shapes that mean "this is a test".
TEST_PATH = re.compile(
    r"""(?ix)
    (?:^|/)(?:tests?|spec|specs|__tests__|testdata|fixtures|e2e|integration|it|features)(?:/|$)
    | (?:^|/)conftest\.py$
    | _test\.(?:go|py|rb|exs?|dart|cc|cpp|c)$
    | (?:^|/)test_[^/]+\.py$
    | \.(?:test|spec)\.(?:ts|tsx|js|jsx|mjs|cjs|svelte|vue)$
    | (?:^|/)[^/]*(?:Test|Tests|TestCase|Spec)\.(?:java|kt|kts|scala|cs|swift)$
    | _spec\.rb$
    | \.feature$
    | (?:^|/)fuzz/
    | (?:^|/)proptest/
    """
)

# Test declarations added inside a non-test file. Rust, C# and Kotlin routinely
# keep tests beside the code, so path matching alone under-reports them badly.
TEST_DECL = re.compile(
    r"""(?x)
    \#\[(?:test|bench|cfg\(test\)|tokio::test|proptest|kani::proof)
    | ^\s*func\s+(?:Test|Fuzz|Benchmark|Example)[A-Z_]
    | ^\s*(?:async\s+)?def\s+test_
    | ^\s*(?:it|test|describe|bench)\s*[.(]
    | ^\s*@(?:Test|ParameterizedTest|Property|RepeatedTest|Fact|Theory)\b
    | ^\s*(?:it|describe|context)\s+['"]
    | ^\s*TEST(?:_F|_P)?\s*\(
    | ^\s*assert_cmd|^\s*t\.Run\(
    """
)


def git(repo, *args):
    out = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
    )
    if out.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n{out.stderr.strip()}")
    return out.stdout


def is_test_path(path):
    return bool(TEST_PATH.search(path))


def adds_test_decl(repo, sha):
    """True if the commit adds a test declaration inside a non-test file."""
    try:
        diff = git(repo, "show", "--format=", "--unified=0", sha)
    except SystemExit:
        return False
    current = None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("+") and not line.startswith("+++"):
            if current and not is_test_path(current) and TEST_DECL.search(line[1:]):
                return True
    return False


def collect(repo, since, limit, log_args):
    sep = "\x1f"  # unit separator: not a str.splitlines() boundary, unlike \x1e
    fmt = f"%H{sep}%h{sep}%an{sep}%ad{sep}%s"
    args = ["log", f"--format={fmt}", "--date=short", "--no-merges", *log_args]
    if since:
        args.append(f"{since}..HEAD" if _is_rev(repo, since) else f"--since={since}")

    fixes = []
    for line in git(repo, *args).split("\n"):
        if not line.strip():
            continue
        sha, short, author, date, subject = line.split(sep, 4)
        if not FIX_SUBJECT.search(subject) or NOT_REALLY_A_FIX.search(subject):
            continue
        files = [f for f in git(repo, "show", "--format=", "--name-only", sha).splitlines() if f]
        if not files:
            continue
        touched_tests = [f for f in files if is_test_path(f)]
        inline = False
        if not touched_tests:
            inline = adds_test_decl(repo, sha)
        fixes.append(
            {
                "sha": short,
                "full_sha": sha,
                "date": date,
                "author": author,
                "subject": subject,
                "files_changed": len(files),
                "test_files_touched": touched_tests,
                "inline_test_added": inline,
                "has_test": bool(touched_tests) or inline,
                "code_files": [f for f in files if not is_test_path(f)][:5],
            }
        )
        if len(fixes) >= limit:
            break
    return fixes


def _is_rev(repo, s):
    return (
        subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"{s}^{{commit}}"],
            capture_output=True,
        ).returncode
        == 0
    )


def hotspots(fixes):
    """Files that keep getting fixed without a test. These are the real targets."""
    counts = {}
    for f in fixes:
        if f["has_test"]:
            continue
        for path in f["code_files"]:
            counts[path] = counts.get(path, 0) + 1
    return sorted(counts.items(), key=lambda kv: -kv[1])


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("repo", nargs="?", default=".")
    p.add_argument("--since", help="rev or date to start from (e.g. v1.2.0, 6.months.ago)")
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--json", action="store_true")
    p.add_argument("--all", action="store_true", help="list every fix, not just untested ones")
    p.add_argument("--path", action="append", default=[], help="restrict to a path (repeatable)")
    a = p.parse_args()

    log_args = ["--", *a.path] if a.path else []
    fixes = collect(a.repo, a.since, a.limit, log_args)

    if not fixes:
        print("No commits matched as bug fixes. Try --since, or check the commit subject style.")
        return

    untested = [f for f in fixes if not f["has_test"]]
    ratio = (len(fixes) - len(untested)) / len(fixes)

    if a.json:
        json.dump(
            {
                "fix_commits": len(fixes),
                "with_test": len(fixes) - len(untested),
                "without_test": len(untested),
                "regression_discipline": round(ratio, 3),
                "hotspots": [{"file": f, "untested_fixes": n} for f, n in hotspots(fixes)[:10]],
                "commits": fixes if a.all else untested,
            },
            sys.stdout,
            indent=2,
        )
        print()
        return

    print(f"Fix commits examined : {len(fixes)}")
    print(f"Shipped with a test  : {len(fixes) - len(untested)}")
    print(f"Shipped without one  : {len(untested)}")
    print(f"Regression discipline: {ratio:.0%}")
    print()

    shown = fixes if a.all else untested
    if shown:
        label = "All fix commits" if a.all else "Fixes with no accompanying test"
        print(f"{label} (newest first):")
        print()
        for f in shown:
            mark = "OK " if f["has_test"] else "   "
            print(f"  {mark}{f['sha']}  {f['date']}  {f['subject'][:72]}")
            if f["code_files"]:
                print(f"           touched: {', '.join(f['code_files'])}")
        print()

    hs = hotspots(fixes)
    if hs:
        print("Files repeatedly fixed without a test -- start here:")
        for path, n in hs[:10]:
            print(f"  {n:>3}x  {path}")
        print()

    print("A fix with no test is a lead, not a verdict. For each one, ask whether a test")
    print("could have caught it, and whether the same class of bug can still recur.")


if __name__ == "__main__":
    main()
