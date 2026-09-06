"""Conservative Groovy lexical views and root-confined filesystem access.

No Groovy evaluation, network access, or symlink traversal. This is not a parser:
interpolation, metaprogramming, and plugin-supplied configuration need human review.
"""
from __future__ import annotations

import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path


def blank(text: str) -> str:
    return re.sub(r"[^\n]", " ", text)


@dataclass
class Literal:
    start: int
    end: int
    value: str
    delimiter: str


class Groovy:
    """Offset-preserving views: text has no comments; code also masks strings."""

    def __init__(self, src: str):
        text, code = list(src), list(src)
        self.literals: list[Literal] = []
        self.issues: list[str] = []
        i, n = 0, len(src)
        while i < n:
            if src.startswith("/*", i) or src.startswith("//", i):
                if src.startswith("/*", i):
                    close = src.find("*/", i + 2)
                    end = n if close < 0 else close + 2
                    if close < 0:
                        self.issues.append("unterminated block comment")
                else:
                    end = src.find("\n", i)
                    if end < 0:
                        end = n
                text[i:end] = code[i:end] = blank(src[i:end])
                i = end
                continue
            delimiter = next((q for q in ("'''", '\"\"\"', "'", '\"', "$/")
                              if src.startswith(q, i)), None)
            # Slash is ambiguous in Groovy. Treat expression-start /.../ as a
            # literal and disclose the heuristic; division remains executable code.
            if delimiter is None and src[i] == "/":
                prefix = src[:i].rstrip()
                if not prefix or prefix[-1] in "=(:,[!~{" or re.search(r"\breturn$", prefix):
                    delimiter = "/"
                    self.issues.append("slashy-string recognition is heuristic")
            if delimiter is None:
                i += 1
                continue
            closing = "/$" if delimiter == "$/" else delimiter
            j = i + len(delimiter)
            while j < n:
                if delimiter == "$/" and src[j:j + 2] in ("$$", "$/"):
                    j += 2
                elif delimiter != "$/" and src[j] == "\\":
                    j += 2
                elif src.startswith(closing, j):
                    break
                else:
                    j += 1
            end = min(n, j + len(closing))
            value = src[i + len(delimiter):min(j, n)]
            if j >= n:
                self.issues.append("unterminated string literal")
            if delimiter not in ("'", "'''") and re.search(r"\$(?:\{|[A-Za-z_])", value):
                self.issues.append("GString interpolation is not evaluated or audited")
            self.literals.append(Literal(i, end, value, delimiter))
            code[i:end] = blank(src[i:end])
            i = end
        self.text, self.code = "".join(text), "".join(code)
        self.blocks = []
        stack = []
        boundary = 0
        for m in re.finditer(r"[{};]", self.code):
            pos = m.start()
            if m.group() == "{":
                prefix = self.code[boundary:pos]
                name = re.search(r"([\w.]+)\s*(?:\([^{}]*\))?\s*$", prefix)
                stack.append((pos, name.group(1) if name else ""))
            elif m.group() == "}":
                if stack:
                    start, name = stack.pop()
                    self.blocks.append((start, pos, name))
                else:
                    self.issues.append("unmatched closing brace")
            boundary = pos + 1
        if stack:
            self.issues.append("unmatched opening brace")
        self.blocks.sort()

    def matches(self, pattern):
        """Match text including literal arguments, but never start inside a string."""
        for m in re.finditer(pattern, self.text):
            start = m.start() + len(m.group()) - len(m.group().lstrip())
            if start < len(self.code) and not self.code[start].isspace():
                yield m

    def parents(self, pos: int) -> list[str]:
        return [name for start, end, name in self.blocks if start < pos < end]

    def body(self, name: str) -> str:
        for start, end, block_name in self.blocks:
            if block_name == name and not self.parents(start):
                return self.text[start + 1:end]
        return ""


class ConfinedFiles:
    """All inspected paths must be lexical descendants without symlink components.

    Symlinks are deliberately skipped even when their target appears local: checking
    resolve() would itself inspect targets outside the scan root. This is a
    cooperative local scanner, not a sandbox against concurrent filesystem mutation.
    """

    def __init__(self, root: Path, skip_dirs=()):
        self.root = Path(os.path.abspath(root))
        self.skip_dirs = set(skip_dirs)
        self.scanned = set()
        self.skipped: dict[tuple[str, str], dict] = {}
        self._cache = {}

    def skip(self, path: Path, reason: str):
        key = (str(path), reason)
        self.skipped[key] = {"path": str(path), "reason": reason}

    def safe(self, path: Path) -> Path | None:
        path = Path(os.path.abspath(path))
        if not path.is_relative_to(self.root):
            self.skip(path, "outside scan root")
            return None
        # Inspect root ancestors for symlinks without following any of them.
        for part in (*reversed(path.parents), path):
            try:
                if stat.S_ISLNK(part.lstat().st_mode):
                    self.skip(path, "symlink path not followed")
                    return None
            except FileNotFoundError:
                break
            except OSError as exc:
                self.skip(path, f"cannot inspect path: {exc.__class__.__name__}")
                return None
        return path

    def exists(self, path: Path) -> bool:
        p = self.safe(path)
        try:
            return p is not None and p.exists()
        except OSError as exc:
            self.skip(path, f"cannot inspect path: {exc.__class__.__name__}")
            return False

    def is_dir(self, path: Path) -> bool:
        p = self.safe(path)
        try:
            return p is not None and p.is_dir()
        except OSError as exc:
            self.skip(path, f"cannot inspect directory: {exc.__class__.__name__}")
            return False

    def unavailable(self, path: Path) -> bool:
        """Distinguish not inspected/unreadable from an observed missing file."""
        name = str(Path(os.path.abspath(path)))
        return any(row["path"] == name for row in self.skipped.values())

    def read(self, path: Path) -> str:
        p = self.safe(path)
        if p is None:
            return ""
        if p in self._cache:
            return self._cache[p]
        try:
            # Refuse FIFOs/devices as well as links; never block reading a special file.
            mode = p.lstat().st_mode
            if not stat.S_ISREG(mode):
                self.skip(p, "not a regular file")
                return ""
            with p.open(encoding="utf-8") as stream:
                value = stream.read()
        except FileNotFoundError:
            return ""
        except (OSError, UnicodeError) as exc:
            self.skip(p, f"unreadable file: {exc.__class__.__name__}")
            return ""
        self.scanned.add(str(p))
        self._cache[p] = value
        return value

    def walk(self, directory: Path, build_boundaries=False):
        p = self.safe(directory)
        if p is None or not self.is_dir(p):
            return
        def onerror(exc):
            self.skip(Path(exc.filename), f"unreadable directory: {exc.__class__.__name__}")
        for dirname, dirs, files in os.walk(p, followlinks=False, onerror=onerror):
            dp = Path(dirname)
            allowed = []
            for name in sorted(dirs):
                child = dp / name
                if name in self.skip_dirs:
                    continue
                if self.safe(child) is None:
                    continue
                if build_boundaries and (name == "buildSrc" or any(
                        self.exists(child / s) for s in ("settings.gradle", "settings.gradle.kts"))):
                    continue
                allowed.append(name)
            dirs[:] = allowed
            yield dp, [dp / name for name in sorted(files) if self.safe(dp / name) is not None]
