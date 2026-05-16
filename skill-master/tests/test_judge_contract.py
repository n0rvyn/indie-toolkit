"""
Tests for the Judge agent contract + dispatch wire.

Validates:
  (a) judge.md agent file exists with correct frontmatter
  (b) judge input schema (fixture) is structurally valid
  (c) judge output schema (fixture) has correct types (approvals=list[int], rejections with reason)

Run with:
    cd skill-master && python3 -m unittest tests.test_judge_contract -v
"""

import json
import re
import unittest
from pathlib import Path

SKILL_MASTER_DIR = Path(__file__).parent.parent
AGENTS_DIR = SKILL_MASTER_DIR / "agents"
FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _parse_frontmatter(text: str) -> dict:
    """
    Minimal frontmatter parser: extract key: value lines between first two --- delimiters.
    Returns a dict with string values (list values for indented block lists).
    """
    delims = [m.start() for m in re.finditer(r"^---$", text, re.MULTILINE)]
    if len(delims) < 2:
        return {}
    fm_text = text[delims[0] + 3 : delims[1]]
    result = {}
    current_key = None
    current_list = None
    for line in fm_text.splitlines():
        if not line.strip():
            continue
        if line.startswith("  ") or line.startswith("\t"):
            # continuation / list item
            stripped = line.strip().lstrip("- ").strip()
            if current_key and current_list is not None:
                current_list.append(stripped)
        elif ":" in line:
            if current_key and current_list is not None:
                result[current_key] = current_list
            parts = line.split(":", 1)
            current_key = parts[0].strip()
            val = parts[1].strip()
            if val:
                result[current_key] = val
                current_list = None
            else:
                current_list = []
                result[current_key] = current_list
    if current_key and current_list is not None:
        result[current_key] = current_list
    return result


class TestJudgeMdExists(unittest.TestCase):
    def test_judge_md_exists(self):
        """agents/judge.md must exist."""
        judge_path = AGENTS_DIR / "judge.md"
        self.assertTrue(
            judge_path.exists(),
            f"FileNotFoundError: {judge_path} not found — run Task 7-impl first",
        )


class TestJudgeMdFrontmatter(unittest.TestCase):
    def setUp(self):
        self.judge_path = AGENTS_DIR / "judge.md"

    def test_judge_md_frontmatter(self):
        """judge.md frontmatter must contain description, model: sonnet, tools: [Read, Bash(git log:*)]."""
        self.assertTrue(
            self.judge_path.exists(),
            f"judge.md not found at {self.judge_path}",
        )
        text = self.judge_path.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)

        self.assertIn("description", fm, "frontmatter must contain 'description'")
        self.assertTrue(
            str(fm.get("description", "")).strip(),
            "frontmatter 'description' must be non-empty",
        )

        model_val = fm.get("model", "")
        self.assertEqual(
            model_val, "sonnet",
            f"frontmatter 'model' must be 'sonnet', got '{model_val}'",
        )

        tools = fm.get("tools", [])
        if isinstance(tools, str):
            tools = [tools]
        self.assertIn(
            "Read", tools,
            f"frontmatter 'tools' must include 'Read', got {tools}",
        )
        self.assertIn(
            "Bash(git log:*)", tools,
            f"frontmatter 'tools' must include 'Bash(git log:*)', got {tools}",
        )


class TestJudgeInputSchemaValid(unittest.TestCase):
    def test_judge_input_schema_valid(self):
        """Fixture judge_input_sample.json must have required structure."""
        fixture_path = FIXTURES_DIR / "judge_input_sample.json"
        self.assertTrue(fixture_path.exists(), f"Fixture not found: {fixture_path}")
        data = json.loads(fixture_path.read_text(encoding="utf-8"))

        self.assertIn("candidates", data, "input must have 'candidates' key")
        self.assertIsInstance(data["candidates"], list)
        self.assertGreater(len(data["candidates"]), 0, "candidates must be non-empty")

        candidate = data["candidates"][0]
        for key in ("candidate_index", "file_path", "change_type", "old_string", "new_string", "evidence_summary"):
            self.assertIn(key, candidate, f"candidate missing key: {key}")
        self.assertIsInstance(candidate["candidate_index"], int)

        self.assertIn("context", data, "input must have 'context' key")
        ctx = data["context"]
        self.assertIn("window_days", ctx)
        self.assertIsInstance(ctx["window_days"], int)
        self.assertIn("lag_warning", ctx)


class TestJudgeOutputApprovalsOnlyIntegers(unittest.TestCase):
    def test_judge_output_approvals_only_integers(self):
        """Fixture judge_output_sample.json: approvals must be a list of ints."""
        fixture_path = FIXTURES_DIR / "judge_output_sample.json"
        self.assertTrue(fixture_path.exists(), f"Fixture not found: {fixture_path}")
        data = json.loads(fixture_path.read_text(encoding="utf-8"))

        self.assertIn("approvals", data, "output must have 'approvals' key")
        self.assertIsInstance(data["approvals"], list)
        for item in data["approvals"]:
            self.assertIsInstance(item, int, f"approvals must contain ints, got {type(item)}: {item}")


class TestJudgeOutputRejectionRequiresReason(unittest.TestCase):
    def test_judge_output_rejection_requires_reason(self):
        """Fixture judge_output_sample.json: rejections each need candidate_index (int) and reason (non-empty str)."""
        fixture_path = FIXTURES_DIR / "judge_output_sample.json"
        self.assertTrue(fixture_path.exists(), f"Fixture not found: {fixture_path}")
        data = json.loads(fixture_path.read_text(encoding="utf-8"))

        self.assertIn("rejections", data, "output must have 'rejections' key")
        self.assertIsInstance(data["rejections"], list)
        for rejection in data["rejections"]:
            self.assertIn("candidate_index", rejection, "rejection must have 'candidate_index'")
            self.assertIsInstance(rejection["candidate_index"], int)
            self.assertIn("reason", rejection, "rejection must have 'reason'")
            self.assertIsInstance(rejection["reason"], str)
            self.assertTrue(rejection["reason"].strip(), "rejection 'reason' must be non-empty")


if __name__ == "__main__":
    unittest.main()
