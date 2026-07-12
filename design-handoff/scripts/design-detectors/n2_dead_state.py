#!/usr/bin/env python3
"""N2 — State liveness (catches D5: @State declared but never written).

For every `@State (private) var X` / `@StateObject …` / `@Published var X`, the
module (= the arm's whole Sources dir) must contain at least one WRITE POINT:

    X = …            direct assignment      (`==`, `<=`, `>=`, `!=` excluded)
    X += …           compound assignment
    X.prop = …       assignment through it  (mutates a struct / @Observable)
    X.toggle() / .append / .insert / .remove / .removeAll / .sort …  mutating calls
    $X               a Binding handed to a child — the child writes it

Zero write points -> DEAD-STATE: state that can never change. Either it should be
a `let`, or (the real defect) a state matrix was declared and then never driven.

Two details are load-bearing and easy to get wrong:
  * the DECLARATION LINE is excluded from the write scan — otherwise the
    initialiser `= .recovery` reads as a write and every dead state is missed;
  * matching is CASE-SENSITIVE and word-bounded — case-insensitivity makes the
    TYPE token in `readiness: Readiness = .recovery` match the property name,
    and `showReadinessInfo` must not count as a write to `readiness`.

Usage:  python3 n2_dead_state.py [--arm ARM ...]
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field

from common import (
    DIM, GREEN, RED, RESET,
    collect_sources, line_of, rel, scrub,
)

DECL_RE = re.compile(
    r"@(?P<wrapper>State|StateObject|ObservedObject|Published)\b[^\n]*?"
    r"\bvar\s+(?P<name>\w+)\b",
)

MUTATORS = (
    "toggle", "append", "insert", "remove", "removeAll", "removeFirst",
    "removeLast", "popLast", "sort", "reverse", "cancel", "formUnion",
)

# `=` not preceded by = ! < > + - * / % and not followed by =  → a real assignment
ASSIGN = r"(?<![=!<>+\-*/%&|^])=(?!=)"


@dataclass
class Decl:
    arm: str
    file: str
    line: int
    wrapper: str
    name: str
    text: str
    writes: list[str] = field(default_factory=list)


def write_patterns(name: str) -> list[tuple[str, re.Pattern[str]]]:
    n = re.escape(name)
    return [
        ("direct assign", re.compile(rf"(?<![\w.$]){n}\s*{ASSIGN}")),
        ("compound assign", re.compile(rf"(?<![\w.$]){n}\s*(?:\+|-|\*|/|%)=")),
        ("member assign", re.compile(rf"(?<![\w.$]){n}\??\.\w+(?:\[[^\]]*\])?\s*{ASSIGN}")),
        ("mutating call", re.compile(rf"(?<![\w.$]){n}\??\.(?:{'|'.join(MUTATORS)})\s*\(")),
        ("binding $", re.compile(rf"\${n}\b")),
    ]


def scan_arm(arm: str) -> list[Decl]:
    files = collect_sources(arm)
    scrubbed = {p: scrub(p.read_text(encoding="utf-8", errors="replace")) for p in files}

    decls: list[Decl] = []
    for p, s in scrubbed.items():
        raw_lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        for m in DECL_RE.finditer(s):
            ln = line_of(s, m.start())
            decls.append(Decl(
                arm=arm, file=rel(p), line=ln,
                wrapper=m.group("wrapper"), name=m.group("name"),
                text=raw_lines[ln - 1].strip() if ln <= len(raw_lines) else "",
            ))

    for d in decls:
        pats = write_patterns(d.name)
        for p, s in scrubbed.items():
            for i, line_text in enumerate(s.splitlines(), start=1):
                # Exclude the declaration line itself: its initialiser is not a write.
                if rel(p) == d.file and i == d.line:
                    continue
                for label, pat in pats:
                    if pat.search(line_text):
                        d.writes.append(f"{rel(p)}:{i} [{label}]")
                        break
    return decls


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", action="append", default=None)
    ap.add_argument("--verbose", action="store_true", help="also list live state")
    a = ap.parse_args()

    print(f"{DIM}N2 — state liveness. A declaration with zero write points is DEAD.{RESET}\n")
    if not a.arm:
        print(f"{RED}✖ no target given{RESET}", file=sys.stderr)
        print("  Pass --arm <dir-holding-swift-sources> (repeatable).", file=sys.stderr)
        print("  (exit 2 = the check did not run. This is NOT a pass.)", file=sys.stderr)
        return 2
    dead_total = 0
    for arm in a.arm:
        if not collect_sources(arm):
            print(f"{RED}✖ no .swift sources found under: {arm}{RESET}", file=sys.stderr)
            print("  (exit 2 = the check did not run. This is NOT a pass.)", file=sys.stderr)
            return 2
        decls = scan_arm(arm)
        dead = [d for d in decls if not d.writes]
        dead_total += len(dead)
        status = f"{RED}{len(dead)} DEAD{RESET}" if dead else f"{GREEN}clean{RESET}"
        print(f"{arm:<24} {len(decls):>2} declarations   {status}")
        for d in dead:
            print(f"   {RED}HIT DEAD-STATE{RESET} {d.file}:{d.line}  "
                  f"@{d.wrapper} `{d.name}`")
            print(f"        {DIM}{d.text}{RESET}")
            print(f"        {DIM}0 write points under {arm} — value is fixed at "
                  f"its initialiser for the lifetime of the view{RESET}")
        if a.verbose:
            for d in decls:
                if d.writes:
                    print(f"   {GREEN}live{RESET}  @{d.wrapper} `{d.name}` "
                          f"({d.file}:{d.line}) <- {d.writes[0]}"
                          + (f" +{len(d.writes) - 1} more" if len(d.writes) > 1 else ""))
        print()
    return 1 if dead_total else 0


if __name__ == "__main__":
    sys.exit(main())
