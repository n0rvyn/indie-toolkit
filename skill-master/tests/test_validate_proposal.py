"""
Tests for validate_proposal.py — mechanical whitelist enforcement.

Run with:
    cd skill-master && python3 -m unittest tests.test_validate_proposal -v
"""

import os
import tempfile
import unittest
from pathlib import Path


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_skill_file(content: str, dir: str | None = None) -> str:
    """Write content to a temp SKILL.md and return its path."""
    tmp = tempfile.NamedTemporaryFile(
        suffix=".md", mode="w", delete=False, encoding="utf-8", dir=dir
    )
    tmp.write(content)
    tmp.close()
    return tmp.name


# Sample SKILL.md with body horizontal rule (for frontmatter boundary test)
SKILL_WITH_HR = """\
---
name: verify-plan
description: Verifies implementation plans for correctness.
allowed-tools:
  - Read
  - Bash
---

## Overview

This skill verifies plans.

---

## Process

1. Read the plan file.
2. Check for gaps.

## Examples

- Example 1: basic usage
"""

SKILL_SIMPLE = """\
---
name: verify-plan
description: Verifies implementation plans for correctness.
allowed-tools:
  - Read
---

## Process

1. Read the plan.

## Examples

- Example 1
"""


class TestAllowDescriptionChange(unittest.TestCase):
    def test_allow_description_change(self):
        from scripts.validate_proposal import validate
        repo_root = tempfile.mkdtemp()
        skill_path = _make_skill_file(SKILL_SIMPLE, dir=repo_root)
        try:
            proposal = {
                "file_path": skill_path,
                "old_string": "description: Verifies implementation plans for correctness.",
                "new_string": "description: Verifies implementation plans, checking scope and feasibility.",
                "change_type": "description_update",
            }
            allow, reason = validate(proposal, repo_root=repo_root)
            self.assertTrue(allow, f"Expected allow but got deny: {reason}")
        finally:
            os.unlink(skill_path)
            os.rmdir(repo_root)


class TestAllowAppendExamplesSection(unittest.TestCase):
    def test_allow_append_examples_section(self):
        from scripts.validate_proposal import validate
        repo_root = tempfile.mkdtemp()
        skill_path = _make_skill_file(SKILL_SIMPLE, dir=repo_root)
        try:
            proposal = {
                "file_path": skill_path,
                "old_string": "- Example 1",
                "new_string": "- Example 1\n- Example 2: advanced usage with --focus flag",
                "change_type": "append_examples_section",
            }
            allow, reason = validate(proposal, repo_root=repo_root)
            self.assertTrue(allow, f"Expected allow but got deny: {reason}")
        finally:
            os.unlink(skill_path)
            os.rmdir(repo_root)


class TestDenyFrontmatterAllowedTools(unittest.TestCase):
    def test_deny_frontmatter_allowed_tools(self):
        from scripts.validate_proposal import validate
        skill_path = _make_skill_file(SKILL_SIMPLE)
        try:
            repo_root = tempfile.mkdtemp()
            proposal = {
                "file_path": skill_path,
                "old_string": "  - Read",
                "new_string": "  - Read\n  - Write",
                "change_type": "description_update",
            }
            allow, reason = validate(proposal, repo_root=repo_root)
            self.assertFalse(allow, "Expected deny for frontmatter allowed-tools change")
        finally:
            os.unlink(skill_path)
            os.rmdir(repo_root)


class TestDenyProcessSectionChange(unittest.TestCase):
    def test_deny_process_section_change(self):
        from scripts.validate_proposal import validate
        skill_path = _make_skill_file(SKILL_SIMPLE)
        try:
            repo_root = tempfile.mkdtemp()
            proposal = {
                "file_path": skill_path,
                "old_string": "1. Read the plan.",
                "new_string": "1. Read the plan.\n2. Run validation.",
                "change_type": "append_examples_section",
            }
            allow, reason = validate(proposal, repo_root=repo_root)
            self.assertFalse(allow, "Expected deny for ## Process section change")
        finally:
            os.unlink(skill_path)
            os.rmdir(repo_root)


class TestDenyDeleteExistingContent(unittest.TestCase):
    def test_deny_delete_existing_content(self):
        from scripts.validate_proposal import validate
        skill_path = _make_skill_file(SKILL_SIMPLE)
        try:
            repo_root = tempfile.mkdtemp()
            proposal = {
                "file_path": skill_path,
                # old_string is non-empty, new_string is empty → deletion
                "old_string": "- Example 1",
                "new_string": "",
                "change_type": "append_examples_section",
            }
            allow, reason = validate(proposal, repo_root=repo_root)
            self.assertFalse(allow, "Expected deny for deletion of existing content")
        finally:
            os.unlink(skill_path)
            os.rmdir(repo_root)


class TestDenyPathOutsideRepo(unittest.TestCase):
    def test_deny_path_outside_repo(self):
        from scripts.validate_proposal import validate
        repo_root = tempfile.mkdtemp()
        try:
            proposal = {
                "file_path": "/etc/passwd",
                "old_string": "root",
                "new_string": "hacked",
                "change_type": "description_update",
            }
            allow, reason = validate(proposal, repo_root=repo_root)
            self.assertFalse(allow, "Expected deny for path outside repo")
            self.assertIn("path", reason.lower())
        finally:
            os.rmdir(repo_root)

    def test_deny_path_traversal(self):
        from scripts.validate_proposal import validate
        repo_root = tempfile.mkdtemp()
        try:
            proposal = {
                "file_path": repo_root + "/../../../etc/passwd",
                "old_string": "root",
                "new_string": "hacked",
                "change_type": "description_update",
            }
            allow, reason = validate(proposal, repo_root=repo_root)
            self.assertFalse(allow, "Expected deny for path traversal")
        finally:
            os.rmdir(repo_root)


class TestDenyPrBodyWithQuoteBlock(unittest.TestCase):
    def test_deny_pr_body_with_raw_quote(self):
        from scripts.validate_proposal import validate_pr_body
        body = "## Findings\n> This is a raw quote from the user prompt\n\nSome text."
        allow, reason = validate_pr_body(body)
        self.assertFalse(allow, "Expected deny for PR body with quote block")
        self.assertIn("quote block", reason.lower())


class TestLagMetaAllowlistPassesQuoteCheck(unittest.TestCase):
    def test_lag_meta_sentinel_allows_quote_line(self):
        """A > line immediately after <!--lag-meta--> sentinel should pass."""
        from scripts.validate_proposal import validate_pr_body
        body = (
            "<!--lag-meta-->\n"
            "> Warning: Session-reflect data has 36h lag\n"
            "\n"
            "## Findings\n"
            "> raw quote from user prompt\n"
        )
        allow, reason = validate_pr_body(body)
        self.assertFalse(allow, "Expected deny because Findings section has a raw quote")
        # The lag-meta line should NOT be cited; only the Findings quote should be
        self.assertIn("quote block", reason.lower())
        # The reason should reference a line number in the Findings section (line 5+)
        # not the lag-meta quote line (line 2)
        import re
        line_match = re.search(r"line (\d+)", reason)
        if line_match:
            cited_line = int(line_match.group(1))
            self.assertGreater(cited_line, 2, "Lag-meta sentinel line should not be cited")


class TestBodyWithHorizontalRuleNotConfused(unittest.TestCase):
    """
    Verify frontmatter boundary detection uses anchored ^---$ regex,
    not simple .split('---'), so body horizontal rules don't confuse it.
    """

    def test_allow_edit_after_body_horizontal_rule(self):
        """Edit to content after body --- should be allowed (not in frontmatter)."""
        from scripts.validate_proposal import validate
        repo_root = tempfile.mkdtemp()
        skill_path = _make_skill_file(SKILL_WITH_HR, dir=repo_root)
        try:
            # Edit is to the Examples section, which is after the body --- rule
            proposal = {
                "file_path": skill_path,
                "old_string": "- Example 1: basic usage",
                "new_string": "- Example 1: basic usage\n- Example 2: with --focus flag",
                "change_type": "append_examples_section",
            }
            allow, reason = validate(proposal, repo_root=repo_root)
            self.assertTrue(allow, f"Expected allow for post-HR edit but got deny: {reason}")
        finally:
            os.unlink(skill_path)
            os.rmdir(repo_root)

    def test_deny_edit_to_frontmatter_content(self):
        """Edit to frontmatter fields should be denied."""
        from scripts.validate_proposal import validate
        skill_path = _make_skill_file(SKILL_WITH_HR)
        try:
            repo_root = tempfile.mkdtemp()
            # Try to change allowed-tools in frontmatter
            proposal = {
                "file_path": skill_path,
                "old_string": "  - Read\n  - Bash",
                "new_string": "  - Read\n  - Bash\n  - Write",
                "change_type": "description_update",
            }
            allow, reason = validate(proposal, repo_root=repo_root)
            self.assertFalse(allow, "Expected deny for frontmatter edit in HR-containing SKILL.md")
        finally:
            os.unlink(skill_path)
            os.rmdir(repo_root)


if __name__ == "__main__":
    unittest.main()
