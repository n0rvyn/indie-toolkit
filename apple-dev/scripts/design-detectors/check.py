#!/usr/bin/env python3
"""Driver: run N1/N2/N3 over every arm, print the verification matrix, and
assert the experiment's KNOWN ANSWERS.

  python3 check.py matrix     8 arms x 3 detectors
  python3 check.py selftest   assert known positives HIT and known negatives are CLEAN
  python3 check.py all        matrix + selftest   (exit 1 if the self-test fails)

The self-test is the acceptance gate. A detector that has not been run against a
known positive is not a detector.
"""

from __future__ import annotations

import sys
from pathlib import Path as FSPath

from common import ARMS, DIM, GREEN, RED, RESET, YELLOW, repo_root

import n1_paradigm as n1
import n2_dead_state as n2
import n3_scaffold_leak as n3

# ---------------------------------------------------------------------------
# Known answers. Provenance:
#   [spec]  stated in the experiment brief as ground truth
#   [clone] arm4t / arm4u are arm4 variants (tint / dark-only) — same code shape
# Cells not listed are genuinely unknown and are NOT asserted.
# ---------------------------------------------------------------------------
HIT, CLEAN = "HIT", "CLEAN"

KNOWN = {
    "N1": {
        "arm2-jsx-port": (HIT, "spec: 13x hand-rolled Path, 0x import Charts"),
        "arm1-contract-only": (CLEAN, "spec"),
        "arm1b-replication": (CLEAN, "spec"),
        "arm4-all-in": (CLEAN, "spec"),
    },
    "N2": {
        "arm4-all-in": (HIT, "spec: @State readiness never assigned"),
        "arm4t-tinted": (HIT, "clone of arm4"),
        "arm4u-darkonly": (HIT, "clone of arm4"),
    },
    "N3": {
        "arm2-jsx-port": (HIT, "spec: padding 64/100 + ignoresSafeArea"),
        "arm4-all-in": (HIT, "spec: padding 64/100 + ignoresSafeArea"),
        "arm1-contract-only": (CLEAN, "spec"),
        "arm1b-replication": (CLEAN, "spec"),
    },
}


def run_all() -> dict[str, dict[str, tuple[str, str]]]:
    """-> {detector: {arm: (verdict, one-line evidence)}}"""
    rules, _ = n1.compile_rules(FSPath(repo_root() / "run2" / "contract" / "DESIGN.md"))
    rule = rules[0]
    out: dict[str, dict[str, tuple[str, str]]] = {"N1": {}, "N2": {}, "N3": {}}

    for arm in ARMS:
        # N1
        fs = n1.check_arm(arm, rule)
        v = [f for f in fs if f.verdict == "VIOLATION"]
        if v:
            out["N1"][arm] = (HIT, f"`{v[0].component}` draws with Path — {v[0].cites[0]}")
        else:
            f = fs[0]
            note = "no chart component at all" if f.verdict == "NO-COMPONENT" else \
                   f"Swift Charts — {f.cites[0] if f.cites else ''}"
            out["N1"][arm] = (CLEAN, note)

        # N2
        decls = n2.scan_arm(arm)
        dead = [d for d in decls if not d.writes]
        if dead:
            out["N2"][arm] = (
                HIT,
                "; ".join(f"`{d.name}` dead ({d.file.split('/')[-1]}:{d.line})" for d in dead),
            )
        else:
            out["N2"][arm] = (CLEAN, f"{len(decls)} declarations, all written")

        # N3
        hits, _ = n3.scan_arm(arm, 48.0)
        if hits:
            h = hits[0]
            pads = "/".join(f"{p[3]:g}" for p in h.pads)
            out["N3"][arm] = (HIT, f"`{h.view}` padding {pads} + ignoresSafeArea "
                                  f"({h.file.split('/')[-1]}:{h.pads[0][0]})")
        else:
            out["N3"][arm] = (CLEAN, "no co-occurrence")
    return out


def matrix(res) -> None:
    print(f"\n{DIM}VERIFICATION MATRIX — 8 arms x 3 detectors{RESET}")
    print(f"{DIM}  * = cell has a known answer from the experiment; "
          f"(!) = detector disagrees with it{RESET}\n")
    w = 24
    print(f"{'arm':<{w}} {'N1 paradigm':<16} {'N2 dead-state':<16} {'N3 scaffold':<16}")
    print("-" * (w + 52))
    for arm in ARMS:
        row = f"{arm:<{w}} "
        for det in ("N1", "N2", "N3"):
            verdict, _ = res[det][arm]
            known = KNOWN[det].get(arm)
            star = "*" if known else " "
            bad = known and known[0] != verdict
            color = RED if verdict == HIT else GREEN
            cell = f"{verdict}{star}" + ("(!)" if bad else "")
            row += f"{color}{cell:<16}{RESET}" if not bad else f"{YELLOW}{cell:<16}{RESET}"
        print(row)

    print(f"\n{DIM}evidence{RESET}")
    for det in ("N1", "N2", "N3"):
        print(f"\n  {det}")
        for arm in ARMS:
            verdict, ev = res[det][arm]
            c = RED if verdict == HIT else DIM
            print(f"    {c}{verdict:<6}{RESET} {arm:<24} {DIM}{ev}{RESET}")


def selftest(res) -> int:
    print(f"\n{DIM}SELF-TEST — known positives must HIT, known negatives must be CLEAN{RESET}\n")
    fails = 0
    for det in ("N1", "N2", "N3"):
        for arm, (expected, why) in KNOWN[det].items():
            actual, ev = res[det][arm]
            ok = actual == expected
            if not ok:
                fails += 1
            kind = "positive" if expected == HIT else "negative"
            tag = f"{GREEN}PASS{RESET}" if ok else f"{RED}FAIL{RESET}"
            print(f"  {tag}  {det}  known {kind:<8} {arm:<24} "
                  f"expected {expected:<5} got {actual:<5} {DIM}({why}){RESET}")
            if not ok:
                print(f"        {RED}detector bug — fix the detector, not the answer{RESET}")
    n = sum(len(v) for v in KNOWN.values())
    print(f"\n  {n - fails}/{n} asserted cells pass"
          + (f"  {RED}{fails} FAILING{RESET}" if fails else f"  {GREEN}all green{RESET}"))
    return 1 if fails else 0


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    res = run_all()
    if cmd in ("matrix", "all"):
        matrix(res)
    if cmd in ("selftest", "all"):
        return selftest(res)
    return 0


if __name__ == "__main__":
    sys.exit(main())
