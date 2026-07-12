"""Shared machinery for the deterministic code-layer detectors.

Zero model judgment. Everything here is lexical: comment/string stripping,
brace-matched type-block extraction, and CamelCase tokenisation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path as FSPath

RESET = "\033[0m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
DIM = "\033[2m"


# Directories that hold generated or third-party Swift, never the project's own views.
SKIP_DIRS = {".git", ".build", "build", "DerivedData", "Pods", "Carthage", "checkouts"}


def collect_sources(target: str | FSPath) -> list[FSPath]:
    """Every .swift file under `target`, recursively, skipping build/dependency dirs.

    An empty result is the CALLER's problem to surface: a detector that scanned
    zero files must exit 2 ("the check did not run") — it must never print clean.
    """
    root = FSPath(target)
    if not root.is_dir():
        return []
    out = []
    for p in sorted(root.rglob("*.swift")):
        parts = p.relative_to(root).parts[:-1]
        if any(part in SKIP_DIRS or part.startswith(".") for part in parts):
            continue
        out.append(p)
    return out


def rel(p: FSPath) -> str:
    """Path relative to the CWD when possible, absolute otherwise, for citations."""
    try:
        return str(p.relative_to(FSPath.cwd()))
    except ValueError:
        return str(p)


# ---------------------------------------------------------------------------
# Lexical scrubbing
# ---------------------------------------------------------------------------

def scrub(src: str) -> str:
    """Blank out comments and string literals, preserving byte offsets and newlines.

    Brace counting and regex matching run on the scrubbed text so that a `{`
    inside a comment or a `"…"` cannot corrupt scope detection, and so a
    commented-out `.padding(.top, 64)` is never reported.
    """
    out = list(src)
    i, n = 0, len(src)
    state = "code"  # code | line | block | string | mstring
    depth = 0  # nested /* */ depth

    def blank(k: int) -> None:
        if out[k] != "\n":
            out[k] = " "

    while i < n:
        c = src[i]
        nxt = src[i + 1] if i + 1 < n else ""
        if state == "code":
            if c == "/" and nxt == "/":
                state = "line"
                blank(i)
                blank(i + 1)
                i += 2
                continue
            if c == "/" and nxt == "*":
                state = "block"
                depth = 1
                blank(i)
                blank(i + 1)
                i += 2
                continue
            if c == '"' and src[i:i + 3] == '"""':
                state = "mstring"
                for k in range(i, i + 3):
                    blank(k)
                i += 3
                continue
            if c == '"':
                state = "string"
                blank(i)
                i += 1
                continue
            i += 1
            continue

        if state == "line":
            if c == "\n":
                state = "code"
                i += 1
                continue
            blank(i)
            i += 1
            continue

        if state == "block":
            if c == "/" and nxt == "*":
                depth += 1
                blank(i)
                blank(i + 1)
                i += 2
                continue
            if c == "*" and nxt == "/":
                depth -= 1
                blank(i)
                blank(i + 1)
                i += 2
                if depth == 0:
                    state = "code"
                continue
            blank(i)
            i += 1
            continue

        if state == "string":
            if c == "\\" and nxt:
                blank(i)
                blank(i + 1)
                i += 2
                continue
            if c == '"':
                blank(i)
                state = "code"
                i += 1
                continue
            if c == "\n":  # unterminated; bail back to code
                state = "code"
                i += 1
                continue
            blank(i)
            i += 1
            continue

        if state == "mstring":
            if src[i:i + 3] == '"""':
                for k in range(i, i + 3):
                    blank(k)
                state = "code"
                i += 3
                continue
            blank(i)
            i += 1
            continue

    return "".join(out)


# ---------------------------------------------------------------------------
# Type blocks (brace-matched scopes)
# ---------------------------------------------------------------------------

DECL_RE = re.compile(
    r"^[ \t]*(?:(?:public|private|fileprivate|internal|final|@\w+)\s+)*"
    r"(struct|class|enum|extension|actor)\s+(\w+)",
    re.M,
)


@dataclass
class Block:
    kind: str          # struct | class | enum | extension | actor
    name: str
    decl_line: int     # 1-based
    start_line: int    # 1-based, line of the opening brace
    end_line: int      # 1-based, line of the matching close brace
    header: str        # declaration line text (raw)
    body: str          # scrubbed source of the block, offsets preserved
    is_view: bool
    file: FSPath

    def contains(self, line: int) -> bool:
        return self.start_line <= line <= self.end_line

    @property
    def span(self) -> int:
        return self.end_line - self.start_line


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def type_blocks(path: FSPath) -> list[Block]:
    """Brace-matched type declarations in a Swift file (nested types included)."""
    raw = path.read_text(encoding="utf-8", errors="replace")
    s = scrub(raw)
    raw_lines = raw.splitlines()
    blocks: list[Block] = []

    for m in DECL_RE.finditer(s):
        kind, name = m.group(1), m.group(2)
        open_i = s.find("{", m.end())
        if open_i == -1:
            continue
        # header = everything from decl to the opening brace (conformance list)
        header = s[m.start():open_i]
        depth, j = 0, open_i
        while j < len(s):
            if s[j] == "{":
                depth += 1
            elif s[j] == "}":
                depth -= 1
                if depth == 0:
                    break
            j += 1
        if depth != 0:
            continue
        decl_line = line_of(s, m.start())
        blocks.append(
            Block(
                kind=kind,
                name=name,
                decl_line=decl_line,
                start_line=line_of(s, open_i),
                end_line=line_of(s, j),
                header=raw_lines[decl_line - 1] if decl_line <= len(raw_lines) else header,
                body=s[open_i:j + 1],
                is_view=bool(re.search(r":[^{]*\bView\b", header)),
                file=path,
            )
        )
    return blocks


def innermost_block(blocks: list[Block], line: int) -> Block | None:
    hits = [b for b in blocks if b.contains(line)]
    return min(hits, key=lambda b: b.span) if hits else None


def body_lines(b: Block) -> list[tuple[int, str]]:
    """(1-based absolute line number, scrubbed text) for each line of the block."""
    return [
        (b.start_line + i, txt)
        for i, txt in enumerate(b.body.splitlines())
    ]


# ---------------------------------------------------------------------------
# CamelCase tokenisation
# ---------------------------------------------------------------------------

_CAMEL = re.compile(r"[A-Z]+(?![a-z])|[A-Z][a-z0-9]*|[a-z0-9]+")


def camel_tokens(name: str) -> list[str]:
    """`SparkleIcon` -> ['sparkle','icon'];  `MiniBars` -> ['mini','bars']."""
    return [t.lower() for t in _CAMEL.findall(name)]


_CLOSERS = {")": "(", "}": "{", "]": "["}
_IDENT_CH = re.compile(r"[A-Za-z0-9_]")


def chain_head(body: str, dot_offset: int) -> str:
    """The head of the SwiftUI modifier chain that the `.` at `dot_offset` hangs off.

    Walks backward over the SCRUBBED body, jumping over balanced `(…)` / `{…}` /
    `[…]` groups, so that

        ZStack {           <- head
            Foo()
        }
        .ignoresSafeArea()

    reports `ZStack`, not `Foo` (the last line before the modifier). Getting this
    wrong is the whole point: `.ignoresSafeArea()` on a wallpaper is correct,
    on the content container it is the leak.
    """
    i = dot_offset - 1
    while i >= 0:
        c = body[i]
        if c.isspace():
            i -= 1
            continue
        if c in _CLOSERS:  # jump the balanced group
            want, depth = _CLOSERS[c], 0
            close = c
            while i >= 0:
                if body[i] == close:
                    depth += 1
                elif body[i] == want:
                    depth -= 1
                    if depth == 0:
                        break
                i -= 1
            i -= 1
            continue
        if _IDENT_CH.match(c):
            j = i
            while j >= 0 and _IDENT_CH.match(body[j]):
                j -= 1
            token = body[j + 1: i + 1]
            k = j
            while k >= 0 and body[k].isspace():
                k -= 1
            if k >= 0 and body[k] == ".":  # mid-chain member, keep walking
                i = k - 1
                continue
            return token
        return "?"
    return "?"


def _singular(tok: str) -> str:
    return tok[:-1] if len(tok) > 3 and tok.endswith("s") else tok


def token_subsequence(term_tokens: list[str], name_tokens: list[str]) -> bool:
    """True if `term_tokens` appears as a contiguous run inside `name_tokens`.

    Plural-insensitive on every token, so `charts` matches `Chart`, and
    `minibars` (-> ['mini','bars']) matches `MiniBars`. Crucially token-aligned,
    so `spark` does NOT match `Sparkle` and `minibars` does NOT match
    `RuneticTabBar`.
    """
    t = [_singular(x) for x in term_tokens]
    n = [_singular(x) for x in name_tokens]
    if not t or len(t) > len(n):
        return False
    for i in range(len(n) - len(t) + 1):
        if n[i:i + len(t)] == t:
            return True
    return False
