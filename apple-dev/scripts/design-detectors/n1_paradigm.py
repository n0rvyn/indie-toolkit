#!/usr/bin/env python3
"""N1 — Paradigm compliance (catches D1: hand-rolled Path instead of Swift Charts).

The assertion is NOT hardcoded. It is compiled from the contract's
`## Platform Mapping` table in DESIGN.md. A row of the form

    | Spark / MiniBars / charts | **Swift Charts** — never hand-rolled `Path` |
      ^ component lexicon         ^ required API      ^ forbidden mechanism

compiles into:  any type whose CamelCase name matches the component lexicon
                MUST use the required API and MUST NOT use the forbidden symbol.

Rows whose left cell names no component (CSS-concept rows such as
"flex / grid + `gap` | … — not `GeometryReader`") are not mechanizable by this
rule and are reported as SKIPPED, never silently dropped.

Verdicts, per arm:
  VIOLATION  a lexicon-named component uses the forbidden mechanism
  COMPLIANT  the component (or an inline chart) uses the required API, no forbidden use
  NO-COMPONENT  no chart component exists at all (an omission, not a paradigm breach)

Usage:  python3 n1_paradigm.py [--arm ARM ...] [--contract DIR]
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path as FSPath

from common import (
    ARMS, DIM, GREEN, RED, RESET, YELLOW,
    Block, arm_sources, camel_tokens, line_of, rel, repo_root, scrub,
    token_subsequence, type_blocks,
)

# ---------------------------------------------------------------------------
# 1. Compile assertions from the contract
# ---------------------------------------------------------------------------

ROW_RE = re.compile(r"^\|(?P<lhs>[^|]+)\|(?P<rhs>[^|]+)\|\s*$", re.M)
NEGATION_RE = re.compile(r"\b(?:never|not)\b(?P<tail>[^|]*)", re.I)
BOLD_RE = re.compile(r"\*\*(?P<api>[^*]+)\*\*")
TICK_RE = re.compile(r"`([^`]+)`")
IDENT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]*$")


@dataclass
class Rule:
    components: list[str]          # e.g. ['Spark', 'MiniBars', 'charts']
    required_api: str              # e.g. 'Swift Charts'
    required_module: str           # e.g. 'Charts'
    forbidden: list[str]           # e.g. ['Path']
    source: str                    # 'DESIGN.md:132'
    row: str

    @property
    def component_tokens(self) -> list[list[str]]:
        return [camel_tokens(c) for c in self.components]


@dataclass
class SkippedRow:
    source: str
    row: str
    reason: str


def compile_rules(design_md: FSPath) -> tuple[list[Rule], list[SkippedRow]]:
    text = design_md.read_text(encoding="utf-8")
    # Restrict to the Platform Mapping section.
    start = text.find("## Platform Mapping")
    if start == -1:
        return [], []
    nxt = text.find("\n## ", start + 1)
    section = text[start: nxt if nxt != -1 else len(text)]
    base_line = text.count("\n", 0, start) + 1

    rules: list[Rule] = []
    skipped: list[SkippedRow] = []

    for m in ROW_RE.finditer(section):
        lhs, rhs = m.group("lhs").strip(), m.group("rhs").strip()
        if set(lhs) <= {"-", " ", ":"} or lhs.lower().startswith(("web /", "react paradigm")):
            continue  # header / separator
        neg = NEGATION_RE.search(rhs)
        if not neg:
            continue
        forbidden = [t.strip() for t in TICK_RE.findall(neg.group("tail"))]
        forbidden = [f for f in forbidden if IDENT_RE.match(f)]
        if not forbidden:
            continue

        src = f"{design_md.name}:{base_line + section.count(chr(10), 0, m.start())}"

        # Component lexicon = left cell, split on '/'. Must name components, not
        # CSS concepts: at least one term must be a capitalised bare identifier.
        comps = [c.strip().strip("`") for c in lhs.split("/")]
        comps = [c for c in comps if c and IDENT_RE.match(c)]
        if not any(c[:1].isupper() for c in comps):
            skipped.append(SkippedRow(
                src, m.group(0).strip(),
                "left cell names no component type (CSS-concept row) — the "
                "forbidden symbol cannot be scoped to a component, so this row "
                "is not mechanizable by N1",
            ))
            continue

        bold = BOLD_RE.search(rhs)
        if not bold:
            skipped.append(SkippedRow(
                src, m.group(0).strip(),
                "no bolded required API in the right cell — nothing to assert as mandatory",
            ))
            continue
        api = bold.group("api").strip()
        module = api.split()[-1]  # 'Swift Charts' -> 'Charts'

        rules.append(Rule(comps, api, module, forbidden, src, m.group(0).strip()))

    return rules, skipped


# ---------------------------------------------------------------------------
# 2. Apply to Swift sources
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    verdict: str
    component: str
    cites: list[str] = field(default_factory=list)
    note: str = ""


def mark_hits(body: str, module: str) -> list[int]:
    """Offsets of required-API usage: `Chart(`/`Chart {` or any `…Mark(`."""
    root = re.escape(module.rstrip("s"))  # Charts -> Chart
    pat = re.compile(rf"\b{root}\s*[({{]|\b\w+Mark\s*\(")
    return [m.start() for m in pat.finditer(body)]


def forbidden_hits(body: str, symbols: list[str]) -> list[int]:
    offs = []
    for sym in symbols:
        # `Path()` / `Path {` constructions and `-> Path` return types
        pat = re.compile(rf"\b{re.escape(sym)}\s*[({{]|->\s*{re.escape(sym)}\b")
        offs += [m.start() for m in pat.finditer(body)]
    return sorted(offs)


def is_chart_component(block: Block, rule: Rule) -> bool:
    toks = camel_tokens(block.name)
    return any(token_subsequence(t, toks) for t in rule.component_tokens)


def check_arm(arm: str, rule: Rule) -> list[Finding]:
    findings: list[Finding] = []
    named_any = False
    api_any: list[str] = []
    imported = False

    for path in arm_sources(arm):
        raw = path.read_text(encoding="utf-8", errors="replace")
        s = scrub(raw)
        if re.search(rf"^\s*import\s+{re.escape(rule.required_module)}\s*$", s, re.M):
            imported = True

        for b in type_blocks(path):
            named = is_chart_component(b, rule)
            bad = forbidden_hits(b.body, rule.forbidden)
            good = mark_hits(b.body, rule.required_module)

            if named:
                named_any = True
                if bad:
                    lines = sorted({b.start_line + b.body.count("\n", 0, o) for o in bad})
                    findings.append(Finding(
                        "VIOLATION", b.name,
                        [f"{rel(path)}:{ln}" for ln in lines[:6]],
                        f"component `{b.name}` matches the contract lexicon "
                        f"{rule.components} but draws with `{'/'.join(rule.forbidden)}`; "
                        f"required API `{rule.required_api}` "
                        f"{'absent' if not good else 'also present'} in this type",
                    ))
                elif good:
                    findings.append(Finding(
                        "COMPLIANT", b.name,
                        [f"{rel(path)}:{b.start_line + b.body.count(chr(10), 0, good[0])}"],
                        f"uses {rule.required_api}",
                    ))
                else:
                    findings.append(Finding(
                        "UNKNOWN-MECHANISM", b.name,
                        [f"{rel(path)}:{b.decl_line}"],
                        "neither required API nor forbidden symbol found — inspect",
                    ))
            elif good and b.is_view:
                # Inline chart in a View that is not lexicon-named (arm1b/arm1c).
                ln = b.start_line + b.body.count("\n", 0, good[0])
                api_any.append(f"{rel(path)}:{ln} ({b.name})")

    if not findings:
        if api_any:
            findings.append(Finding(
                "COMPLIANT", "(inline)", api_any[:3],
                f"no lexicon-named component; chart rendered inline with {rule.required_api}",
            ))
        else:
            findings.append(Finding(
                "NO-COMPONENT", "—", [],
                f"no component matching {rule.components} and no {rule.required_api} usage "
                f"anywhere — the chart is absent (an omission, not a paradigm breach)",
            ))
    if named_any and not imported:
        for f in findings:
            if f.verdict == "VIOLATION":
                f.note += f"; `import {rule.required_module}` absent from the module"
    return findings


# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", action="append", default=None)
    ap.add_argument("--contract", default=str(repo_root() / "run2" / "contract"))
    a = ap.parse_args()
    arms = a.arm or ARMS

    rules, skipped = compile_rules(FSPath(a.contract) / "DESIGN.md")
    print(f"{DIM}N1 — paradigm compliance. Assertions compiled from the contract.{RESET}")
    for r in rules:
        print(f"\n  rule <- {r.source}")
        print(f"    {r.row}")
        print(f"    components : {r.components}")
        print(f"    required   : {r.required_api}  (import {r.required_module}, "
              f"`{r.required_module.rstrip('s')}(`/`…Mark(`)")
        print(f"    forbidden  : {r.forbidden}")
    for s in skipped:
        print(f"\n  {YELLOW}SKIPPED{RESET} <- {s.source}")
        print(f"    {s.row}")
        print(f"    reason: {s.reason}")
    if not rules:
        print("no mechanizable paradigm rules found in the contract", file=sys.stderr)
        return 2

    print()
    exit_code = 0
    for rule in rules:
        for arm in arms:
            for f in check_arm(arm, rule):
                color = {"VIOLATION": RED, "COMPLIANT": GREEN}.get(f.verdict, YELLOW)
                mark = "HIT " if f.verdict == "VIOLATION" else "    "
                print(f"{mark}{color}{f.verdict:<18}{RESET} {arm:<24} {f.component}")
                for c in f.cites:
                    print(f"         {DIM}{c}{RESET}")
                if f.note:
                    print(f"         {DIM}{f.note}{RESET}")
                if f.verdict == "VIOLATION":
                    exit_code = 1
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
