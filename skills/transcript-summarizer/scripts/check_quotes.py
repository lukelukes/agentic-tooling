#!/usr/bin/env python3
"""Check every quote in a summary against its transcript, mechanically.

    check_quotes.py <transcript.txt> <summary.md>

For each quoted span of 4+ words: is it verbatim in the transcript (case and
punctuation ignored, "…" splits it into parts), and does a [mm:ss] on its line
cite it: the first stamp after the quote must be within one paragraph; a stamp
leading a list item may precede it by up to three. Prints the
failures and a count. Exit code 1 if any quote is missing. Stdlib only.

This covers QUOTE and TIMESTAMP issues so the LLM verify pass can spend its
attention on attribution and meaning.
"""
import difflib
import re
import sys

T = r"(?:\d+:)?\d+:\d\d"
# [mm:ss] or a range [mm:ss–mm:ss]
STAMP = re.compile(r"\[(%s)(?:\s*[–-]\s*(%s))?\]" % (T, T))
QUOTE = re.compile(r'"([^"]+)"|“([^”]+)”')
MIN_WORDS = 4


def secs(stamp: str) -> int:
    parts = [int(p) for p in stamp.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    h, m, s = parts
    return h * 3600 + m * 60 + s


def norm(text: str) -> str:
    text = text.lower().replace("’", "'")
    return " ".join(re.sub(r"[^\w' ]+", " ", text).split())


def fmt(s: int) -> str:
    h, rem = divmod(s, 3600)
    return f"[{h}:{rem // 60:02d}:{rem % 60:02d}]" if h else f"[{rem // 60:02d}:{rem % 60:02d}]"


def para_index(times, t: int) -> int:
    """Index of the paragraph a [mm:ss] stamp points into."""
    return max((k for k, start in enumerate(times) if start <= t), default=0)


def load_paragraphs(path):
    paras = []
    for line in open(path, encoding="utf-8"):
        m = re.match(r"^\[((?:\d+:)?\d+:\d\d)\]\s*(.*)", line)
        if m:
            paras.append((secs(m[1]), norm(m[2])))
    return paras


def locate(part, joined, starts):
    """Return the paragraph index where `part` starts, or None."""
    i = joined.find(part)
    if i < 0:
        return None
    return max(k for k, s in enumerate(starts) if s <= i)


def closest(part, joined):
    words = part.split()
    anchor = max(words, key=len)
    best, best_ratio = "", 0.0
    for m in re.finditer(r"\b%s\b" % re.escape(anchor), joined):
        lo = max(0, m.start() - len(part))
        window = joined[lo : m.end() + len(part)]
        sm = difflib.SequenceMatcher(None, part, window)
        a, b, size = sm.find_longest_match(0, len(part), 0, len(window))
        cand = window[max(0, b - a) : max(0, b - a) + len(part)]
        r = difflib.SequenceMatcher(None, part, cand).ratio()
        if r > best_ratio:
            best, best_ratio = cand, r
    return best, best_ratio


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    paras = load_paragraphs(sys.argv[1])
    if not paras:
        sys.exit("no [mm:ss] paragraphs in transcript")
    starts, pos = [], 0
    for _, text in paras:
        starts.append(pos)
        pos += len(text) + 1
    joined = " ".join(t for _, t in paras)
    times = [t for t, _ in paras]

    summary = open(sys.argv[2], encoding="utf-8").read()
    checked = missing = misplaced = 0
    for m in QUOTE.finditer(summary):
        raw = m[1] or m[2]
        parts = [norm(p) for p in re.split(r"…|\.\.\.", raw)]
        parts = [p for p in parts if len(p.split()) >= MIN_WORDS]
        if not parts:
            continue
        checked += 1
        line_no = summary.count("\n", 0, m.start()) + 1
        # Candidate stamps: the first after the quote on its line (summary style) and the
        # last before it (list style, "- [mm:ss] idea, "quote""). Either may cite it.
        eol = summary.find("\n", m.end())
        bol = summary.rfind("\n", 0, m.start()) + 1
        after = STAMP.search(summary[m.end() : eol if eol >= 0 else None])
        before = list(STAMP.finditer(summary[bol : m.start()]))
        candidates = [x for x in (after, before[-1] if before else None) if x]
        # (stamps, paragraphs of slack after) — a leading list stamp marks where an idea
        # starts, and its quote may land a few paragraphs later as the idea unfolds.
        ranges = [([secs(g) for g in c.groups() if g], 1 if c is after else 3) for c in candidates]
        for part in parts:
            k = locate(part, joined, starts)
            if k is None:
                missing += 1
                best, ratio = closest(part, joined)
                print(f"MISSING  L{line_no}: \"{raw[:90]}\"")
                if ratio > 0.6:
                    print(f"         closest ({ratio:.0%}): \"{best[:90]}\"")
                continue
            if ranges:
                # A cited range [a]–[b] covers every paragraph between them, plus one either side.
                spans = [(para_index(times, min(r)), para_index(times, max(r)) + slack) for r, slack in ranges]
                if not any(lo - 1 <= k <= hi for lo, hi in spans):
                    misplaced += 1
                    print(f"STAMP    L{line_no}: \"{raw[:60]}\" cited {candidates[0].group(0)}, "
                          f"found at {fmt(times[k])}")
    print(f"\n{checked} quotes checked: {missing} not verbatim, {misplaced} timestamp off by >1 paragraph")
    sys.exit(1 if missing else 0)


if __name__ == "__main__":
    main()
