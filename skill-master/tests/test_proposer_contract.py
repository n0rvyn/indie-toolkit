"""
Tests for the Proposer agent contract + dispatch wire.

Validates:
  (a) proposer.md agent file exists with correct frontmatter
  (b) proposer input schema (fixture) is structurally valid
  (c) proposer output sample (fixture) passes validate_proposal.validate()

Run with:
    cd skill-master && python3 -m unittest tests.test_proposer_contract -v
"""

import json
import tempfile
import unittest
from pathlib import Path

SKILL_MASTER_DIR = Path(__file__).parent.parent
AGENTS_DIR = SKILL_MASTER_DIR / "agents"
FIXTURES_DIR = Path(__file__).parent / "fixtures"
REPO_ROOT = SKILL_MASTER_DIR.parent


class TestProposerMdExists(unittest.TestCase):
    def test_proposer_md_exists(self):
        """agents/proposer.md must exist."""
        proposer_path = AGENTS_DIR / "proposer.md"
        self.assertTrue(
            proposer_path.exists(),
            f"FileNotFoundError: {proposer_path} not found — run Task 4-impl first",
        )


class TestProposerMdFrontmatter(unittest.TestCase):
    def setUp(self):
        self.proposer_path = AGENTS_DIR / "proposer.md"

    def _parse_frontmatter(self, text: str) -> dict:
        """
        Minimal frontmatter parser: extract key: value lines between first two --- delimiters.
        Returns a dict with string values (list lines joined as list if indented).
        """
        import re
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

    def test_proposer_md_frontmatter(self):
        """proposer.md frontmatter must contain description, model: sonnet, tools: [Read]."""
        self.assertTrue(
            self.proposer_path.exists(),
            f"proposer.md not found at {self.proposer_path}",
        )
        text = self.proposer_path.read_text(encoding="utf-8")
        fm = self._parse_frontmatter(text)

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


class TestInputSchemaValid(unittest.TestCase):
    def test_input_schema_valid(self):
        """Fixture proposer_input_sample.json must have required keys."""
        fixture_path = FIXTURES_DIR / "proposer_input_sample.json"
        self.assertTrue(fixture_path.exists(), f"Fixture not found: {fixture_path}")
        data = json.loads(fixture_path.read_text(encoding="utf-8"))

        self.assertIn("window_days", data)
        self.assertIsInstance(data["window_days"], int)

        self.assertIn("findings", data)
        self.assertIsInstance(data["findings"], list)
        self.assertGreater(len(data["findings"]), 0)

        finding = data["findings"][0]
        for key in ("plugin", "component", "invocations", "corrections", "correction_rate", "pattern_summary"):
            self.assertIn(key, finding, f"finding missing key: {key}")

        self.assertIn("target_files", data)
        self.assertIsInstance(data["target_files"], list)
        self.assertGreater(len(data["target_files"]), 0)

        target = data["target_files"][0]
        for key in ("path", "current_description"):
            self.assertIn(key, target, f"target_file missing key: {key}")


class TestOutputPassesValidator(unittest.TestCase):
    def test_output_passes_validator(self):
        """Each candidate in proposer_output_sample.json must pass validate_proposal.validate()."""
        fixture_path = FIXTURES_DIR / "proposer_output_sample.json"
        self.assertTrue(fixture_path.exists(), f"Fixture not found: {fixture_path}")
        data = json.loads(fixture_path.read_text(encoding="utf-8"))

        self.assertIn("candidates", data)
        self.assertIsInstance(data["candidates"], list)

        # Validate required candidate keys
        for i, candidate in enumerate(data["candidates"]):
            for key in ("file_path", "change_type", "old_string", "new_string",
                        "evidence_keys", "evidence_summary", "expected_metric_change",
                        "sample_size", "confidence"):
                self.assertIn(key, candidate, f"candidate[{i}] missing key: {key}")

            # sample_size must be int
            self.assertIsInstance(
                candidate["sample_size"], int,
                f"candidate[{i}].sample_size must be int",
            )

            # confidence must be one of low/medium/high
            self.assertIn(
                candidate["confidence"], ("low", "medium", "high"),
                f"candidate[{i}].confidence must be 'low'|'medium'|'high'",
            )

            # evidence_keys must be list of str
            self.assertIsInstance(candidate["evidence_keys"], list)
            for ek in candidate["evidence_keys"]:
                self.assertIsInstance(ek, str)

        # Now run validate_proposal on each candidate using a temp SKILL.md
        # that contains the old_string so validate() can read the file
        import sys
        sys.path.insert(0, str(SKILL_MASTER_DIR))
        from scripts.validate_proposal import validate

        SKILL_TEMPLATE = (
            "---\n"
            "name: verify-plan\n"
            "description: {description}\n"
            "---\n"
            "\n"
            "## Overview\n\n"
            "This skill verifies plans.\n\n"
            "{old_string}\n"
        )

        import tempfile, os
        with tempfile.TemporaryDirectory() as tmp_dir:
            for i, candidate in enumerate(data["candidates"]):
                old_str = candidate["old_string"]
                # Build a minimal SKILL.md that contains old_string verbatim.
                # For description_update, old_string is the full "description: <value>"
                # line — embed it directly in frontmatter.
                # For append_examples_section, old_string is the last line(s) of body.
                if candidate["change_type"] == "description_update":
                    skill_content = (
                        f"---\n"
                        f"name: verify-plan\n"
                        f"{old_str}\n"
                        f"---\n\n"
                        f"## Overview\n\nThis skill verifies plans.\n"
                    )
                else:
                    skill_content = (
                        f"---\n"
                        f"name: verify-plan\n"
                        f"description: Verifies plans.\n"
                        f"---\n\n"
                        f"## Overview\n\nThis skill verifies plans.\n\n"
                        f"{old_str}\n"
                    )

                # Write temp SKILL.md inside tmp_dir (which is inside repo_root equivalent)
                skill_file = os.path.join(tmp_dir, f"SKILL_{i}.md")
                with open(skill_file, "w", encoding="utf-8") as f:
                    f.write(skill_content)

                candidate_copy = dict(candidate)
                candidate_copy["file_path"] = skill_file

                allow, reason = validate(candidate_copy, tmp_dir)
                self.assertTrue(
                    allow,
                    f"candidate[{i}] failed validate_proposal: {reason}",
                )


if __name__ == "__main__":
    unittest.main()
