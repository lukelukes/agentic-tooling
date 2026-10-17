#!/usr/bin/env python3
"""Split a timestamped transcript into chunks of about N words on paragraph boundaries.

    chunk_transcript.py <transcript.txt> <words-per-chunk> <out-dir>

Writes <out-dir>/chunk-01.txt, chunk-02.txt, ...; each keeps the transcript's
header line and states its time range. Prints one line per chunk. Stdlib only.
"""
import re
import sys
from pathlib import Path


def main():
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    src, size, out = Path(sys.argv[1]), int(sys.argv[2]), Path(sys.argv[3])
    lines = src.read_text(encoding="utf-8").splitlines()
    header = next((l for l in lines if l.startswith("Source:")), f"Source: {src.name}")
    paras = [l for l in lines if re.match(r"^\[(?:\d+:)?\d+:\d\d\]", l)]
    total = sum(len(p.split()) for p in paras)
    n = max(1, round(total / size))
    target = total / n
    chunks, cur, count = [], [], 0
    for p in paras:
        cur.append(p)
        count += len(p.split())
        if count >= target * (len(chunks) + 1) and len(chunks) < n - 1:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    out.mkdir(parents=True, exist_ok=True)
    for i, c in enumerate(chunks, 1):
        first = c[0].split("]")[0] + "]"
        last = c[-1].split("]")[0] + "]"
        body = "\n".join(c)
        (out / f"chunk-{i:02d}.txt").write_text(
            f"{header}\nChunk {i} of {len(chunks)}, {first}–{last}\n\n{body}\n", encoding="utf-8")
        print(f"chunk-{i:02d}.txt  {first}–{last}  {len(body.split())} words")


if __name__ == "__main__":
    main()
