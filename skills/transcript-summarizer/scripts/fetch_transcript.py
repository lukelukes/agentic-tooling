#!/usr/bin/env python3
"""Turn a YouTube URL or a caption file into a timestamped plain-text transcript.

    fetch_transcript.py <youtube-url | file.vtt | file.srt> <out.txt> [--lang en]

Output: a metadata header, then one paragraph per ~30 s, each prefixed [mm:ss]
(or [h:mm:ss] past an hour). ">>" marks a speaker change where captions have one.
Needs yt-dlp on PATH for URLs. Stdlib only.
"""
import html
import re
import subprocess
import sys
import tempfile
from pathlib import Path

CUE = re.compile(r"^(?:(\d+):)?(\d+):(\d+)[.,]\d+\s+-->")
WORD_TIMING = re.compile(r"<\d\d:\d\d[:.]")
TAG = re.compile(r"<[^>]+>")
PARAGRAPH_SECONDS = 30


def fetch(url: str, lang: str, workdir: Path) -> tuple[Path, str]:
    meta = subprocess.run(
        ["yt-dlp", "--skip-download", "--no-warnings", "--print",
         "%(title)s | %(channel)s | %(duration_string)s | %(upload_date)s", url],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    # Prefer human-made subtitles, then the original-language auto track, then translated auto.
    for flags, langs in (
        (["--write-subs"], f"{lang},{lang}-.*"),
        (["--write-auto-subs"], f"{lang}-orig"),
        (["--write-auto-subs"], lang),
    ):
        subprocess.run(
            ["yt-dlp", "--skip-download", "--no-warnings", *flags, "--sub-langs", langs,
             "--sub-format", "vtt", "-o", str(workdir / "subs"), url],
            capture_output=True, text=True,
        )
        found = sorted(workdir.glob("subs*.vtt"))
        if found:
            return found[0], meta
    sys.exit(f"no '{lang}' subtitles or auto-captions available for {url}")


def cues(text: str):
    """Yield (seconds, line) for caption text lines, dropping rolling-caption repeats."""
    lines = text.splitlines()
    # YouTube auto-captions repeat each line in the next cue; only lines with
    # inline word timings are new text. Human-made captions have none.
    rolling = any(WORD_TIMING.search(l) for l in lines)
    t, last = None, None
    for line in lines:
        m = CUE.match(line)
        if m:
            h, mnt, s = m.groups()
            t = int(h or 0) * 3600 + int(mnt) * 60 + int(s)
            continue
        if t is None or not line.strip() or line.strip().isdigit():
            continue
        if rolling and not WORD_TIMING.search(line):
            continue
        clean = html.unescape(TAG.sub("", line)).replace("\xa0", " ").strip()
        if clean and clean != last:
            yield t, clean
            last = clean


def stamp(s: int) -> str:
    h, rem = divmod(s, 3600)
    return f"[{h}:{rem // 60:02d}:{rem % 60:02d}]" if h else f"[{rem // 60:02d}:{rem % 60:02d}]"


def paragraphs(items):
    out, cur, start = [], [], None
    for t, txt in items:
        if start is None:
            start = t
        cur.append(txt)
        if t - start >= PARAGRAPH_SECONDS:
            out.append(f"{stamp(start)} {' '.join(cur)}")
            cur, start = [], None
    if cur:
        out.append(f"{stamp(start)} {' '.join(cur)}")
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    lang = sys.argv[sys.argv.index("--lang") + 1] if "--lang" in sys.argv else "en"
    if lang in args:
        args.remove(lang)
    if len(args) != 2:
        sys.exit(__doc__)
    src, out = args
    with tempfile.TemporaryDirectory() as tmp:
        if re.match(r"https?://", src):
            path, meta = fetch(src, lang, Path(tmp))
        else:
            path, meta = Path(src), Path(src).name
        text = path.read_text(encoding="utf-8", errors="replace")
    paras = paragraphs(cues(text))
    if not paras:
        sys.exit(f"no caption text found in {src}")
    body = "\n".join(paras)
    Path(out).write_text(f"Source: {meta}\n\n{body}\n", encoding="utf-8")
    print(f"{out}: {len(body.split())} words, {len(paras)} paragraphs | {meta}")


if __name__ == "__main__":
    main()
