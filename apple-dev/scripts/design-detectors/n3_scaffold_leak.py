#!/usr/bin/env python3
"""N3 — Scaffold leak (catches D2: the prototype's fake-device inset, transliterated).

The design source has `padding: '64px 20px 100px'` on the page shell
(screens-today.jsx:115). That inset is the PROTOTYPE'S FAKE DEVICE BEZEL — the
netting that keeps the mock content clear of a drawn notch and a drawn home bar.
On a real device the platform supplies that inset via the safe area. Copying the
numbers AND switching the safe area off is the leak: the scaffold's geometry
replaces the platform's.

CO-OCCURRENCE RULE — both, inside the SAME View scope (brace-matched):
    1. `.ignoresSafeArea(…)`                        the platform inset is switched off
    2. `.padding(.top|.bottom, N)` with N a LITERAL and N >= 48   it is re-hardcoded

Neither half is a defect alone: a wallpaper SHOULD ignore the safe area, and a
big bottom padding to clear a floating tab bar is fine when the safe area is
live. Only together do they mean "I replaced the platform inset with the
prototype's."

Why not "N is off the spacing scale": 64 IS a legal step on the scale. The
number is innocent. Only the co-occurrence is guilty.

Usage:  python3 n3_scaffold_leak.py [--arm ARM ...] [--threshold 48]
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field

from common import (
    ARMS, DIM, GREEN, RED, RESET, YELLOW,
    Block, arm_sources, body_lines, chain_head, rel, type_blocks,
)

IGNORE_RE = re.compile(r"\.ignoresSafeArea\s*\(")
# LITERAL only: `.padding(.top, 64)` matches; `.padding(.top, RLayout.pageGutter)` does not.
PAD_RE = re.compile(r"\.padding\(\s*\.(?P<edge>top|bottom)\s*,\s*(?P<n>\d+(?:\.\d+)?)\s*\)")


@dataclass
class Hit:
    view: str
    file: str
    ignores: list[tuple[int, str]] = field(default_factory=list)
    pads: list[tuple[int, str, str, float]] = field(default_factory=list)
    # line -> head of the modifier chain the .ignoresSafeArea() hangs off.
    # Informational: it tells you WHETHER the safe area was switched off on a
    # background (legitimate) or on the content container (the actual leak).
    # The verdict does not depend on it.
    receivers: dict[int, str] = field(default_factory=dict)


def receiver_hint(block: Block, line: int) -> str:
    """Head of the modifier chain the `.ignoresSafeArea()` on `line` hangs off.

    Informational only — the verdict does NOT depend on it. Brace-aware
    (see common.chain_head), so a modifier applied to a whole `ZStack { … }`
    reports `ZStack`, not the last view inside it.
    """
    for off in (m.start() for m in IGNORE_RE.finditer(block.body)):
        if block.start_line + block.body.count("\n", 0, off) == line:
            return chain_head(block.body, off)
    return "?"


def scan_arm(arm: str, threshold: float) -> tuple[list[Hit], list[Hit]]:
    hits: list[Hit] = []
    near: list[Hit] = []  # one half present, not the other — for honest reporting

    for path in arm_sources(arm):
        blocks = type_blocks(path)  # compute ONCE: the nested check below is identity-based
        for b in blocks:
            if not b.is_view:
                continue
            # Lines belonging to THIS view only: exclude lines owned by a nested type.
            nested = [
                x for x in blocks
                if x is not b
                and (x.start_line, x.end_line) != (b.start_line, b.end_line)
                and b.start_line <= x.start_line and x.end_line <= b.end_line
            ]

            def mine(ln: int) -> bool:
                return not any(x.start_line <= ln <= x.end_line for x in nested)

            h = Hit(view=b.name, file=rel(path))
            for ln, txt in body_lines(b):
                if not mine(ln):
                    continue
                if IGNORE_RE.search(txt):
                    h.ignores.append((ln, txt.strip()))
                for m in PAD_RE.finditer(txt):
                    n = float(m.group("n"))
                    if n >= threshold:
                        h.pads.append((ln, txt.strip(), m.group("edge"), n))

            if h.ignores and h.pads:
                for ln, _ in h.ignores:
                    h.receivers[ln] = receiver_hint(b, ln)
                hits.append(h)
            elif h.ignores or h.pads:
                near.append(h)
    return hits, near


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", action="append", default=None)
    ap.add_argument("--threshold", type=float, default=48.0)
    ap.add_argument("--show-near", action="store_true",
                    help="also show views where only one half of the rule is present")
    a = ap.parse_args()

    print(f"{DIM}N3 — scaffold leak. HIT = .ignoresSafeArea() AND a literal "
          f".padding(.top|.bottom, N>={a.threshold:g}) in the SAME View.{RESET}\n")
    total = 0
    for arm in a.arm or ARMS:
        hits, near = scan_arm(arm, a.threshold)
        total += len(hits)
        print(f"{arm:<24} " + (f"{RED}{len(hits)} HIT{RESET}" if hits else f"{GREEN}clean{RESET}"))
        for h in hits:
            print(f"   {RED}HIT SCAFFOLD-LEAK{RESET} {h.file}  View `{h.view}`")
            for ln, txt, edge, n in h.pads:
                print(f"        {DIM}{h.file}:{ln}{RESET}  {txt}   "
                      f"{YELLOW}<- literal {n:g}pt >= {a.threshold:g}{RESET}")
            for ln, txt in h.ignores:
                print(f"        {DIM}{h.file}:{ln}{RESET}  {txt}   "
                      f"{DIM}<- on: {h.receivers.get(ln, '?')}{RESET}")
            print(f"        {DIM}the platform inset is switched off and a "
                  f"prototype-frame inset is hardcoded in its place{RESET}")
        if a.show_near:
            for h in near:
                half = "ignoresSafeArea only" if h.ignores else "big literal padding only"
                loc = (h.ignores or [(x[0], x[1]) for x in h.pads])[0]
                print(f"   {DIM}near-miss  View `{h.view}` — {half} "
                      f"({h.file}:{loc[0]}) -> not a leak{RESET}")
        print()
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
