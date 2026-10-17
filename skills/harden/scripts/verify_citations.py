#!/usr/bin/env python3
"""Check that every path:line citation in a report points where it claims.

A citation is checkable, so it should be checked. In this skill's own evaluation
every run produced at least one claim its evidence did not support, and the most
durable form was a citation whose quoted text was verbatim correct while the line
number was 8-23 lines off -- exactly the shape that survives a human skim.

Usage:
    verify_citations.py REPORT [REPO_ROOT] [--drift N] [--json] [-v]

Exit status is 1 if any citation is WRONG-LINE or names a file that does not
exist, so it can gate a report.

Deliberately conservative. It reports a problem only when the report's own quoted
text is findable in the cited file at a *different but nearby* line -- the signature
of a real off-by-N citation. Anything more ambiguous is reported as "unverified"
rather than as an error, because a checker that cries wolf gets switched off, and
then the real drift ships.
"""

import argparse
import json
import re
import sys
from pathlib import Path

# file.ext:123, path/to/file.ext:123, and extensionless executables like `link:378`.
# Permissive by design: candidates that do not resolve to a real file are discarded
# silently, so timestamps and "Step 4:12" never become noise.
CITATION = re.compile(
    r"""(?<![\w/.:-])
    (?P<path>(?:[\w.-]+/)*[\w][\w.-]*)
    :(?P<line>\d+)
    (?![\w:])""",
    re.X,
)

SOURCE_EXT = {
    "py","go","ts","tsx","js","jsx","mjs","cjs","rs","java","kt","kts","scala","cs",
    "c","cc","cpp","h","hpp","rb","sh","bash","zsh","sql","yaml","yml","toml","json","swift",
}

FENCE = re.compile(r"```[^\n]*\n(.*?)```", re.S)
INLINE = re.compile(r"`([^`\n]{6,200})`")
NOISE = re.compile(r"^\s*(?:#|//|\*|-{3,}|\d+\s*[.)]\s|\$ )")
IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]{3,}")

# How far from the citation to look for the text it is quoting.
QUOTE_RADIUS = 300


def norm(s):
    return re.sub(r"\s+", " ", s).strip()


def quotes_with_pos(text):
    """(normalised_fragment, position) for every plausible quoted source fragment."""
    out = []
    for m in FENCE.finditer(text):
        base = m.start(1)
        off = 0
        for line in m.group(1).splitlines(keepends=True):
            t = norm(line)
            if len(t) >= 8 and not NOISE.match(line):
                out.append((t, base + off))
            off += len(line)
    for m in INLINE.finditer(text):
        t = norm(m.group(1))
        if len(t) >= 8:
            out.append((t, m.start(1)))
    return out


def same_line(a, b):
    """Is the quoted fragment plausibly the cited source line?"""
    if not a or not b:
        return False
    if a in b or b in a:
        return True
    ia, ib = set(IDENT.findall(a)), set(IDENT.findall(b))
    # Two distinctive identifiers in common is a strong signal for wrapped lines.
    return len(ia & ib) >= 2


def locate(lines, frag):
    """First line number whose text plausibly matches frag, else None."""
    for i, l in enumerate(lines, 1):
        n = norm(l)
        if len(n) >= 8 and same_line(frag, n):
            return i
    return None


def check(report_path, repo_root, drift):
    text = Path(report_path).read_text(errors="ignore")
    allq = quotes_with_pos(text)
    cache = {}
    best = {}  # citation -> result, best verdict wins

    RANK = {"ok": 0, "unverified": 1, "WRONG-LINE": 2, "missing-file": 3, "out-of-range": 3}

    def record(cite, status, detail):
        prev = best.get(cite)
        if prev is None or RANK[status] < RANK[prev["status"]]:
            best[cite] = {"citation": cite, "status": status, "detail": detail}

    for m in CITATION.finditer(text):
        rel, lineno = m.group("path"), int(m.group("line"))
        cite = f"{rel}:{lineno}"

        cand = [repo_root / rel]
        if not cand[0].is_file():
            cand += [p for p in sorted(repo_root.rglob(Path(rel).name))
                     if ".git" not in p.parts and "node_modules" not in p.parts][:3]
        target = next((c for c in cand if c.is_file()), None)

        if target is None:
            if Path(rel).suffix.lstrip(".").lower() in SOURCE_EXT:
                record(cite, "missing-file", "no such file under repo root")
            continue  # not a citation at all

        if target not in cache:
            cache[target] = target.read_text(errors="ignore").splitlines()
        lines = cache[target]

        if not (1 <= lineno <= len(lines)):
            record(cite, "out-of-range", f"{target.name} has {len(lines)} lines")
            continue

        cited = norm(lines[lineno - 1])
        near = sorted(((q, abs(pos - m.start())) for q, pos in allq
                       if abs(pos - m.start()) <= QUOTE_RADIUS),
                      key=lambda x: x[1])

        if not near:
            record(cite, "unverified", f"line {lineno} is {cited[:55]!r}; no quoted text nearby")
            continue

        if any(same_line(q, cited) for q, _ in near):
            record(cite, "ok", cited[:70] or "(blank line, but quoted text matches)")
            continue

        # The report quotes something here that is not on the cited line. Only call
        # it an error if that text really does live nearby in the same file. Among
        # the candidate quotes, take the one landing closest to the cited line --
        # an off-by-N citation is precisely a quote that sits a few lines away, and
        # picking the merely-first candidate would fingerprint an unrelated fragment.
        hits = [(q, at) for q, _ in near if (at := locate(lines, q)) is not None]
        hit = min(hits, key=lambda h: abs(h[1] - lineno)) if hits else None

        if hit and abs(hit[1] - lineno) <= drift:
            record(cite, "WRONG-LINE",
                   f"quoted text is at line {hit[1]} ({hit[1]-lineno:+d}); "
                   f"line {lineno} is {cited[:45]!r}")
        else:
            record(cite, "unverified",
                   f"line {lineno} is {cited[:55]!r}; nearby quote not matched here")

    return sorted(best.values(), key=lambda r: (RANK[r["status"]] * -1, r["citation"]))


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("report")
    p.add_argument("repo_root", nargs="?", default=".")
    p.add_argument("--drift", type=int, default=60,
                   help="max line distance still counted as a citation error (default 60); "
                        "beyond this the quote probably matched something unrelated")
    p.add_argument("--json", action="store_true")
    p.add_argument("-v", "--verbose", action="store_true", help="also list ok and unverified")
    a = p.parse_args()

    res = check(Path(a.report), Path(a.repo_root).resolve(), a.drift)

    if a.json:
        json.dump(res, sys.stdout, indent=2)
        print()
        return 1 if any(r["status"] in ("WRONG-LINE", "missing-file", "out-of-range") for r in res) else 0

    if not res:
        print("No path:line citations found.")
        print("Fine if every claim is backed by executed output instead — but check that it is.")
        return 0

    bad = [r for r in res if r["status"] in ("WRONG-LINE", "missing-file", "out-of-range")]
    unver = [r for r in res if r["status"] == "unverified"]
    for r in res:
        if not a.verbose and r["status"] == "ok":
            continue
        mark = {"ok": "  ok", "unverified": "   ?"}.get(r["status"], "FAIL")
        print(f"{mark}  {r['citation']:32} {r['detail']}")

    print()
    print(f"{len(res)} citations · {len(bad)} wrong · {len(unver)} unverified · "
          f"{len(res)-len(bad)-len(unver)} ok")
    if bad:
        print()
        print("Fix the wrong ones before the report goes out. A citation nobody can follow is")
        print("worse than no citation, because it reads as though it was checked.")
    if unver:
        print("Unverified means this script could not match quoted text to the cited line —")
        print("usually its own imprecision, not an error. Spot-check them yourself.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
