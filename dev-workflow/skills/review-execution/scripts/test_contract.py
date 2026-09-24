#!/usr/bin/env python3
"""Tracked contract test — supersedes the local, untracked heading checker
`.claude/skills/call-graph/scripts/check_section_contract.py`.

    reviewer agent  --Return block-->  review.workflow.js CONTRACT  --passthrough-->  run-phase

`review.workflow.js` schemas make the reviewer -> workflow hop fail loudly (a required
schema field the agent drops makes StructuredOutput reject the return). What is still
unchecked at runtime is FIELD NAMES: whether the `CONTRACT` object's headings still
match what each producer agent actually emits in its **Return** block, and whether
every `passthrough['<agentType>'].<field>` citation in the consumer docs (run-phase,
afk, review-execution/eval.md) names a field CONTRACT actually has.

This test proves the three ends agree on names. It does not prove the chain runs end
to end — the Apple half only actually executes in an Apple project with a
`*View.swift` change (see the plan's Pre-flight risks / CLAUDE.md Refactor Closure #3).

Checks:
  (a) every CONTRACT heading appears in its producer's **Return** fenced block
      (same return_block rule as check_section_contract.py:46-57)
  (b) every `passthrough['<agentType>'].<field>` citation in the consumer docs names
      a field that exists in CONTRACT for that reviewer (or a common field every
      named reviewer's schema always carries: verdict, report_path, findings)
  (c) minimum-citation floor — every CONTRACT field run-phase actually consumes is
      cited at least once, in that exact form, in run-phase/SKILL.md. Zero citations
      must be reported red, never clean (the exact failure
      check_section_contract.py:100-104 exists to prevent).

Run: python3 -m unittest test_contract -v
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]

WORKFLOW_SCRIPT = ROOT / "dev-workflow/skills/review-execution/review.workflow.js"

PRODUCERS = {
    "dev-workflow:implementation-reviewer": ROOT / "dev-workflow/agents/implementation-reviewer.md",
    "apple-dev:ui-reviewer": ROOT / "apple-dev/agents/ui-reviewer.md",
    "apple-dev:design-reviewer": ROOT / "apple-dev/agents/design-reviewer.md",
    "apple-dev:feature-reviewer": ROOT / "apple-dev/agents/feature-reviewer.md",
    "apple-dev:apple-reviewer": ROOT / "apple-dev/agents/apple-reviewer.md",
}

RUN_PHASE_SKILL = ROOT / "dev-workflow/skills/run-phase/SKILL.md"

CONSUMER_FILES = {
    "run-phase/SKILL.md": RUN_PHASE_SKILL,
    "run-phase/eval.md": ROOT / "dev-workflow/skills/run-phase/eval.md",
    "afk/SKILL.md": ROOT / "dev-workflow/skills/afk/SKILL.md",
    "review-execution/eval.md": ROOT / "dev-workflow/skills/review-execution/eval.md",
}

# Every named reviewer's schema (namedReviewerSchema() in review.workflow.js) always
# carries these three on top of whatever CONTRACT adds — citing them is not citing an
# unknown field even though they are not spelled out per-reviewer in CONTRACT.
COMMON_FIELDS = {"verdict", "report_path", "findings"}

# What run-phase actually consumes today (plan Task 4 / Expected outcome), used only
# by the citation-floor check (c). apple-reviewer has no CONTRACT fields and is not
# part of the floor.
FLOOR_FIELDS = {
    "apple-dev:ui-reviewer": {"part_c_human_verification"},
    "apple-dev:design-reviewer": {"part_a_red", "part_b_device_verification"},
    "apple-dev:feature-reviewer": {"part_c_device_verification"},
    "dev-workflow:implementation-reviewer": {"tests_line", "decisions_line", "pre_existing_line", "gaps_line"},
}

CITATION_RE = re.compile(r"passthrough\[['\"]([^'\"]+)['\"]\]\.(\w+)")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def load_contract(text: str) -> dict:
    m = re.search(r"// CONTRACT:BEGIN\s*(.*?)// CONTRACT:END", text, re.S)
    if not m:
        raise AssertionError(
            "review.workflow.js: CONTRACT:BEGIN / CONTRACT:END markers not found — "
            "the contract must be readable without executing the script."
        )
    body = m.group(1).strip()
    body = re.sub(r"^const\s+CONTRACT\s*=\s*", "", body)
    body = body.rstrip()
    if body.endswith(";"):
        body = body[:-1]
    return json.loads(body)


def return_block(text: str) -> str:
    """The fenced block under the agent's **Return** step — same rule as
    check_section_contract.py's `return_block()`: sections that live only in the
    report format further down the file do NOT count."""
    m = re.search(r"\*\*Return\*\*", text)
    if not m:
        return ""
    rest = text[m.end():]
    fence = re.search(r"```(.*?)```", rest, re.S)
    return fence.group(1) if fence else ""


def heading_present(block: str, heading: str) -> bool:
    if heading.startswith("###"):
        return any(line.strip() == heading for line in block.splitlines())
    # A bare key line (e.g. "Tests:") must start a line, not just appear mid-text.
    return re.search(rf"^{re.escape(heading)}", block, re.M) is not None


def citations_in(text: str):
    return [(m.group(1), m.group(2)) for m in CITATION_RE.finditer(text)]


class ContractMarkersParse(unittest.TestCase):
    def test_markers_present_and_json_valid(self):
        contract = load_contract(read(WORKFLOW_SCRIPT))
        self.assertEqual(set(contract.keys()), set(PRODUCERS.keys()))

    def test_load_contract_fails_loudly_without_markers(self):
        with self.assertRaises(AssertionError):
            load_contract("no markers here")


def producer_problems(contract: dict, producers: dict[str, Path]) -> list[str]:
    """The one loop both the real-file check and the mutation fixtures run — a
    mutation that bypasses this function is not testing what (a) checks."""
    problems = []
    for agent_type, fields in contract.items():
        path = producers[agent_type]
        if not path.is_file():
            problems.append(f"{agent_type}: missing producer file {path}")
            continue
        block = return_block(read(path))
        if fields and not block:
            problems.append(f"{agent_type}: no **Return** fenced block found in {path}")
            continue
        for field, heading in fields.items():
            if not heading_present(block, heading):
                problems.append(
                    f"{agent_type}.{field}: heading {heading!r} not found in {path}'s Return block"
                )
    return problems


def _ui_reviewer_counts_only_mutation() -> tuple[str, str]:
    """Mutate a real copy of ui-reviewer.md: drop `### Part C: 人工验证清单` from the
    Return fence only, replacing it with counts-only lines (the exact 2026-09-04
    failure shape). The SAME heading text is duplicated verbatim further down in the
    report format (`ui-reviewer.md:315`), untouched — that duplicate is what makes
    this fixture distinguish "checks only the Return fence" from "scans the whole
    file". Returns (original_text, mutated_text)."""
    text = read(PRODUCERS["apple-dev:ui-reviewer"])
    m = re.search(r"\*\*Return\*\*", text)
    rest = text[m.end():]
    fence = re.search(r"```(.*?)```", rest, re.S)
    counts_only_block = "```\nReport: x.md\nVerdict: pass\n视觉规范: 🔴 0 / 🟡 0\n交互完整性: 🔴 0 / 🟡 0\n人工验证项: 0\n检查文件数: 0\n```"
    mutated = text[:m.end()] + rest[:fence.start()] + counts_only_block + rest[fence.end():]
    return text, mutated


class ProducerReturnsContractHeadings(unittest.TestCase):
    """(a) every CONTRACT heading appears in its producer's Return block."""

    def test_real_producers(self):
        contract = load_contract(read(WORKFLOW_SCRIPT))
        problems = producer_problems(contract, PRODUCERS)
        self.assertEqual(problems, [], "\n" + "\n".join(problems))

    def test_red_on_counts_only_return_block(self):
        """Mutation fixture — the exact 2026-09-04 failure shape: a Return block that
        reports counts only, dropping the heading CONTRACT requires, while the SAME
        heading still exists verbatim further down in the report format.
        `return_block()` must see only the Return fence, not the report copy — a
        checker that scanned the whole file would stay green here and miss the bug."""
        contract = load_contract(read(WORKFLOW_SCRIPT))
        field = "part_c_human_verification"
        heading = contract["apple-dev:ui-reviewer"][field]
        _, mutated = _ui_reviewer_counts_only_mutation()

        # Precondition: the heading this mutation drops from the Return block still
        # survives elsewhere in the file (the report format) — otherwise this fixture
        # would trivially pass for the wrong reason (heading gone everywhere, not just
        # from the Return block).
        self.assertIn(heading, mutated, f"precondition failed: {heading!r} should survive in the report body")

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td) / "ui-reviewer.md"
            tmp_path.write_text(mutated, encoding="utf-8")
            problems = producer_problems(contract, {**PRODUCERS, "apple-dev:ui-reviewer": tmp_path})

        self.assertEqual(
            problems,
            [f"apple-dev:ui-reviewer.{field}: heading {heading!r} not found in {tmp_path}'s Return block"],
        )

    def test_return_block_restriction_is_what_makes_the_mutation_detectable(self):
        """If return_block() did not exclude the report-format copy, the counts-only
        mutation above would go undetected. Prove that by removing the restriction
        (scan the whole file) and showing the same mutation then reports clean —
        confirms the red case above is discriminating on the Return-vs-report split,
        not on something else."""
        contract = load_contract(read(WORKFLOW_SCRIPT))
        field = "part_c_human_verification"
        heading = contract["apple-dev:ui-reviewer"][field]
        _, mutated = _ui_reviewer_counts_only_mutation()

        # Whole-file scan (no Return-fence restriction) still finds the heading,
        # because it survives in the report body further down the file.
        self.assertTrue(
            heading_present(mutated, heading),
            "a whole-file scan should stay green on this fixture — that's exactly why "
            "return_block()'s restriction to the Return fence is load-bearing",
        )


class BareKeyHeadings(unittest.TestCase):
    """The bare-key branch of heading_present() (implementation-reviewer's `Tests:` /
    `Decisions:` / `Pre-existing:` / `Plan-vs-Code gaps:` lines), which the ui-reviewer
    fixture above never reaches — its heading is a `###` one."""

    def test_bare_key_must_start_a_line(self):
        self.assertTrue(heading_present("Report: x.md\nTests: 3 required", "Tests:"))
        self.assertFalse(heading_present("Report: x.md\n- Tests: 3 required", "Tests:"))
        self.assertFalse(heading_present("Report: x.md\nno tests here", "Tests:"))

    def test_red_when_tests_line_dropped_from_real_return_block(self):
        """Mutate a real copy of implementation-reviewer.md: drop the `Tests:` line from
        the Return fence only. The file still says `- Tests: …` in its report format
        further down — mid-line, so the start-of-line rule must not count it."""
        contract = load_contract(read(WORKFLOW_SCRIPT))
        path = PRODUCERS["dev-workflow:implementation-reviewer"]
        text = read(path)
        m = re.search(r"\*\*Return\*\*", text)
        rest = text[m.end():]
        fence = re.search(r"```(.*?)```", rest, re.S)
        block = fence.group(0)
        self.assertRegex(block, r"(?m)^Tests:", "precondition: the real Return fence carries a Tests: line")
        mutated_block = re.sub(r"(?m)^Tests:.*\n", "", block)
        mutated = text[:m.end()] + rest[:fence.start()] + mutated_block + rest[fence.end():]
        self.assertIn("Tests:", mutated, "precondition: Tests: survives mid-line in the report format")

        with tempfile.TemporaryDirectory() as td:
            tmp_path = Path(td) / "implementation-reviewer.md"
            tmp_path.write_text(mutated, encoding="utf-8")
            problems = producer_problems(contract, {**PRODUCERS, "dev-workflow:implementation-reviewer": tmp_path})

        self.assertEqual(
            problems,
            [f"dev-workflow:implementation-reviewer.tests_line: heading 'Tests:' not found in {tmp_path}'s Return block"],
        )


class ConsumerCitationsAreKnownFields(unittest.TestCase):
    """(b) every passthrough['<agentType>'].<field> citation names a real field."""

    def _problems_for(self, contract: dict, label: str, text: str) -> list[str]:
        problems = []
        for agent_type, field in citations_in(text):
            if agent_type not in contract:
                problems.append(f"{label}: cites unknown agentType {agent_type!r}")
                continue
            known = set(contract[agent_type].keys()) | COMMON_FIELDS
            if field not in known:
                problems.append(f"{label}: cites unknown field {agent_type}.{field}")
        return problems

    def test_real_consumers(self):
        contract = load_contract(read(WORKFLOW_SCRIPT))
        problems = []
        for label, path in CONSUMER_FILES.items():
            if not path.is_file():
                continue
            problems += self._problems_for(contract, label, read(path))
        self.assertEqual(problems, [], "\n" + "\n".join(problems))

    def test_red_on_unknown_field_citation(self):
        contract = load_contract(read(WORKFLOW_SCRIPT))
        fixture = "See `passthrough['dev-workflow:implementation-reviewer'].nonexistent_field` for details."
        problems = self._problems_for(contract, "fixture", fixture)
        self.assertEqual(
            problems,
            ["fixture: cites unknown field dev-workflow:implementation-reviewer.nonexistent_field"],
        )


class RunPhaseCitationFloor(unittest.TestCase):
    """(c) every field run-phase consumes must be cited at least once, in that exact
    form, in run-phase/SKILL.md. Zero citations is red, never reported clean."""

    @staticmethod
    def _uncited(text: str) -> set[tuple[str, str]]:
        cited = set(citations_in(text))
        want = {(agent, field) for agent, fields in FLOOR_FIELDS.items() for field in fields}
        return want - cited

    def test_checker_goes_green_on_a_fully_cited_fixture(self):
        """Proves the floor check CAN pass — without this, a green run-phase result
        would be indistinguishable from a checker that can never fail."""
        fixture = "\n".join(
            f"passthrough['{agent}'].{field}"
            for agent, fields in FLOOR_FIELDS.items() for field in fields
        )
        self.assertEqual(self._uncited(fixture), set())

    def test_checker_goes_red_when_citations_are_removed(self):
        """Red on a copy of the REAL run-phase/SKILL.md with every passthrough citation
        stripped — not on an empty string, which would pass even if the checker only
        ever looked at file length."""
        want = {(agent, field) for agent, fields in FLOOR_FIELDS.items() for field in fields}
        stripped = CITATION_RE.sub("", read(RUN_PHASE_SKILL))
        self.assertGreater(len(stripped), 1000, "precondition: the rest of the real file survives")
        self.assertEqual(self._uncited(stripped), want)

    def test_checker_names_exactly_the_one_citation_removed(self):
        target = "passthrough['dev-workflow:implementation-reviewer'].gaps_line"
        real = read(RUN_PHASE_SKILL)
        self.assertIn(target, real, "precondition: run-phase cites gaps_line today")
        self.assertEqual(
            self._uncited(real.replace(target, "")),
            {("dev-workflow:implementation-reviewer", "gaps_line")},
        )

    def test_real_run_phase_skill(self):
        uncited = self._uncited(read(RUN_PHASE_SKILL))
        self.assertEqual(
            uncited, set(),
            f"run-phase/SKILL.md never cites (in the exact `passthrough['agent'].field` "
            f"form): {sorted(uncited)}",
        )


if __name__ == "__main__":
    unittest.main()
