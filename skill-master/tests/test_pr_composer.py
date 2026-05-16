"""
Tests for pr_composer.py — branch management, PR body rendering, apply_candidates, rollback.

Run with:
    cd skill-master && python3 -m unittest tests.test_pr_composer -v
"""

import hashlib
import json
import os
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, call, patch

SKILL_MASTER_DIR = Path(__file__).parent.parent


def _import_pr_composer():
    import sys
    sys.path.insert(0, str(SKILL_MASTER_DIR))
    import scripts.pr_composer as pc
    return pc


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_CANDIDATES = [
    {
        "file_path": "dev-workflow/skills/verify-plan/SKILL.md",
        "change_type": "description_update",
        "old_string": "description: Verifies plans.",
        "new_string": "description: Verifies implementation plans before execution.",
        "evidence_keys": ["correction_rate"],
        "evidence_summary": "12 invocations, 33% correction rate",
        "expected_metric_change": "correction_rate should drop below 20%",
        "sample_size": 12,
        "confidence": "medium",
    }
]

SAMPLE_FINDINGS = [
    {
        "plugin": "dev-workflow",
        "component": "verify-plan",
        "invocations": 12,
        "corrections": 4,
        "correction_rate": 0.33,
        "pattern_summary": "users often followed up with skip intent",
    }
]


# ---------------------------------------------------------------------------
# Task 9 tests
# ---------------------------------------------------------------------------

class TestBranchNameFormat(unittest.TestCase):
    def test_branch_name_format(self):
        """branch_name(candidates, today) must return auto-insights/YYYY-MM-DD-{8-char-hash}."""
        pc = _import_pr_composer()
        today = date(2026, 5, 16)
        name = pc.branch_name(SAMPLE_CANDIDATES, today)
        # Format: auto-insights/YYYY-MM-DD-{8 hex chars}
        self.assertTrue(
            name.startswith("auto-insights/2026-05-16-"),
            f"branch name must start with 'auto-insights/2026-05-16-', got: {name}",
        )
        suffix = name.split("auto-insights/2026-05-16-")[-1]
        self.assertEqual(len(suffix), 8, f"hash suffix must be 8 chars, got: {repr(suffix)}")
        self.assertTrue(
            all(c in "0123456789abcdef" for c in suffix),
            f"hash suffix must be hex, got: {repr(suffix)}",
        )


class TestPrBodyContainsEvidenceTable(unittest.TestCase):
    def test_pr_body_contains_evidence_table(self):
        """render_pr_body must include evidence table with required headers."""
        pc = _import_pr_composer()
        body = pc.render_pr_body(SAMPLE_CANDIDATES, SAMPLE_FINDINGS, lag_warning=None)
        self.assertIn(
            "| plugin | component | finding | confidence |",
            body,
            "PR body must contain evidence table header",
        )


class TestPrBodyContainsExpectedMetricChange(unittest.TestCase):
    def test_pr_body_contains_expected_metric_change(self):
        """render_pr_body must include 'Expected change in next window:' section."""
        pc = _import_pr_composer()
        body = pc.render_pr_body(SAMPLE_CANDIDATES, SAMPLE_FINDINGS, lag_warning=None)
        self.assertIn(
            "Expected change in next window:",
            body,
            "PR body must contain 'Expected change in next window:' section",
        )


class TestPrBodyNoQuoteBlockInBody(unittest.TestCase):
    def test_pr_body_no_quote_block_in_body(self):
        """render_pr_body must not contain raw > quote lines outside the lag-meta sentinel."""
        pc = _import_pr_composer()
        body = pc.render_pr_body(SAMPLE_CANDIDATES, SAMPLE_FINDINGS, lag_warning=None)
        lines = body.splitlines()
        lag_meta_next = False
        for i, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped == "<!--lag-meta-->":
                lag_meta_next = True
                continue
            if stripped.startswith(">"):
                if lag_meta_next:
                    lag_meta_next = False
                    continue
                self.fail(
                    f"PR body contains disallowed quote block at line {i}: {repr(line)}"
                )
            if stripped and not stripped.startswith("<!--"):
                lag_meta_next = False


class TestPrBodySurfacesLagWarning(unittest.TestCase):
    def test_pr_body_surfaces_lag_warning_when_present(self):
        """When lag_warning is provided, first section must contain the warning text."""
        pc = _import_pr_composer()
        body = pc.render_pr_body(SAMPLE_CANDIDATES, SAMPLE_FINDINGS, lag_warning="数据滞后 36h")
        self.assertIn("⚠️", body, "PR body must contain warning emoji when lag_warning set")
        self.assertIn("36h", body, "PR body must contain lag duration when lag_warning set")


class TestPrBodySurfacesConfidencePerCandidate(unittest.TestCase):
    def test_pr_body_surfaces_confidence_per_candidate(self):
        """Each candidate must appear with Confidence and Sample count in PR body."""
        pc = _import_pr_composer()
        body = pc.render_pr_body(SAMPLE_CANDIDATES, SAMPLE_FINDINGS, lag_warning=None)
        self.assertIn("Confidence:", body, "PR body must contain 'Confidence:' per candidate")
        self.assertIn("Sample", body, "PR body must contain 'Sample' count per candidate")
        self.assertIn("12", body, "PR body must contain sample_size value (12)")


class TestBranchCleanupOnPushFailure(unittest.TestCase):
    def test_branch_cleanup_on_push_failure(self):
        """When git push fails, git branch -D must be called (not remote delete)."""
        pc = _import_pr_composer()

        call_log = []

        def mock_run(cmd, **kwargs):
            call_log.append(cmd)
            result = MagicMock()
            if "push" in cmd:
                result.returncode = 1
                result.stderr = "push failed"
            else:
                result.returncode = 0
                result.stdout = ""
                result.stderr = ""
            return result

        with patch("scripts.pr_composer.subprocess.run", side_effect=mock_run):
            try:
                pc.push("auto-insights/2026-05-16-abcd1234")
            except Exception:
                pass  # expected — push fails

        # rollback for push failure: local branch delete only
        with patch("scripts.pr_composer.subprocess.run", side_effect=mock_run):
            pc.rollback("auto-insights/2026-05-16-abcd1234", push_succeeded=False)

        branch_d_calls = [c for c in call_log if "branch" in c and "-D" in c]
        remote_delete_calls = [
            c for c in call_log if "push" in c and "--delete" in c
        ]
        self.assertTrue(
            len(branch_d_calls) > 0,
            "rollback must call 'git branch -D' when push failed",
        )
        self.assertEqual(
            len(remote_delete_calls), 0,
            "rollback must NOT call remote delete when push never succeeded",
        )


class TestBranchCleanupOnSigintAfterPushBeforePr(unittest.TestCase):
    def test_branch_cleanup_on_sigint_after_push_before_pr(self):
        """When push succeeded but PR not yet created, rollback must delete both local and remote branch."""
        pc = _import_pr_composer()

        call_log = []

        def mock_run(cmd, **kwargs):
            call_log.append(cmd)
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            return result

        with patch("scripts.pr_composer.subprocess.run", side_effect=mock_run):
            pc.rollback("auto-insights/2026-05-16-abcd1234", push_succeeded=True)

        branch_d_calls = [c for c in call_log if "branch" in c and "-D" in c]
        remote_delete_calls = [
            c for c in call_log if "push" in c and "--delete" in c
        ]
        self.assertTrue(
            len(branch_d_calls) > 0,
            "rollback must call 'git branch -D' when push succeeded but PR not created",
        )
        self.assertTrue(
            len(remote_delete_calls) > 0,
            "rollback must call 'git push origin --delete' to clean orphan remote branch",
        )


class TestPrAlreadyCreatedNoRollback(unittest.TestCase):
    def test_pr_already_created_no_rollback(self):
        """When PR already created, rollback must NOT delete local or remote branch."""
        pc = _import_pr_composer()

        call_log = []

        def mock_run(cmd, **kwargs):
            call_log.append(cmd)
            result = MagicMock()
            result.returncode = 0
            result.stdout = ""
            result.stderr = ""
            return result

        with patch("scripts.pr_composer.subprocess.run", side_effect=mock_run):
            pc.rollback(
                "auto-insights/2026-05-16-abcd1234",
                push_succeeded=True,
                pr_created=True,
            )

        branch_d_calls = [c for c in call_log if "branch" in c and "-D" in c]
        remote_delete_calls = [
            c for c in call_log if "push" in c and "--delete" in c
        ]
        self.assertEqual(
            len(branch_d_calls), 0,
            "rollback must NOT delete local branch when PR already created",
        )
        self.assertEqual(
            len(remote_delete_calls), 0,
            "rollback must NOT delete remote branch when PR already created",
        )


class TestCommitMessageUsesSafePrefix(unittest.TestCase):
    def test_commit_message_uses_safe_prefix(self):
        """commit() default message must start with chore(insights): or docs(insights):."""
        pc = _import_pr_composer()

        generated_messages = []

        def mock_run(cmd, **kwargs):
            if "commit" in cmd:
                # Find -m argument
                for j, part in enumerate(cmd):
                    if part == "-m" and j + 1 < len(cmd):
                        generated_messages.append(cmd[j + 1])
            result = MagicMock()
            result.returncode = 0
            result.stdout = "abc1234"
            result.stderr = ""
            return result

        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch("scripts.pr_composer.subprocess.run", side_effect=mock_run):
                pc.commit(Path(tmp_dir))

        self.assertTrue(
            len(generated_messages) > 0,
            "commit() must invoke git commit with -m flag",
        )
        msg = generated_messages[0]
        self.assertTrue(
            msg.startswith("chore(insights):") or msg.startswith("docs(insights):"),
            f"commit message must start with chore(insights): or docs(insights):, got: {repr(msg)}",
        )

    def test_commit_message_rejects_feat_fix_prefix(self):
        """commit() must raise ValueError when message uses feat: or fix: prefix."""
        pc = _import_pr_composer()

        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(ValueError):
                pc.commit(Path(tmp_dir), message="feat: improve skill description")

        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(ValueError):
                pc.commit(Path(tmp_dir), message="fix: correct trigger keyword")


class TestApplyCandidatesTempDirPattern(unittest.TestCase):
    def test_apply_candidates_temp_dir_pattern(self):
        """When old_string not found in a candidate, raise RuntimeError; all original files unchanged."""
        pc = _import_pr_composer()

        with tempfile.TemporaryDirectory() as repo_dir:
            repo = Path(repo_dir)
            # Create 3 target files
            files = []
            original_contents = []
            for i in range(3):
                p = repo / f"SKILL_{i}.md"
                content = f"---\nname: skill-{i}\ndescription: Skill {i}.\n---\n\n## Body {i}\n"
                p.write_text(content)
                files.append(p)
                original_contents.append(content)

            candidates = [
                {
                    "file_path": str(files[0]),
                    "old_string": "description: Skill 0.",
                    "new_string": "description: Skill 0 improved.",
                    "change_type": "description_update",
                },
                {
                    "file_path": str(files[1]),
                    "old_string": "DOES NOT EXIST IN FILE",  # will fail
                    "new_string": "description: Skill 1 improved.",
                    "change_type": "description_update",
                },
                {
                    "file_path": str(files[2]),
                    "old_string": "description: Skill 2.",
                    "new_string": "description: Skill 2 improved.",
                    "change_type": "description_update",
                },
            ]

            with self.assertRaises(RuntimeError):
                pc.apply_candidates(candidates, repo)

            # All original files must be unchanged
            for i, (p, original) in enumerate(zip(files, original_contents)):
                actual = p.read_text()
                self.assertEqual(
                    actual, original,
                    f"File {i} must be unchanged after failed apply_candidates",
                )


class TestApplyCandidatesAllOrNothingTempPhase(unittest.TestCase):
    def test_apply_candidates_all_or_nothing_temp_phase(self):
        """When all candidates succeed, all target files are updated."""
        pc = _import_pr_composer()

        with tempfile.TemporaryDirectory() as repo_dir:
            repo = Path(repo_dir)
            files = []
            for i in range(3):
                p = repo / f"SKILL_{i}.md"
                content = f"---\nname: skill-{i}\ndescription: Skill {i}.\n---\n\n## Body {i}\n"
                p.write_text(content)
                files.append(p)

            candidates = [
                {
                    "file_path": str(files[i]),
                    "old_string": f"description: Skill {i}.",
                    "new_string": f"description: Skill {i} improved.",
                    "change_type": "description_update",
                }
                for i in range(3)
            ]

            pc.apply_candidates(candidates, repo)

            for i, p in enumerate(files):
                content = p.read_text()
                self.assertIn(
                    f"description: Skill {i} improved.",
                    content,
                    f"File {i} must be updated after successful apply_candidates",
                )


class TestPrBodyLinksRevertInstructions(unittest.TestCase):
    def test_pr_body_links_revert_instructions(self):
        """PR body must contain git revert instruction and state.json reference."""
        pc = _import_pr_composer()
        body = pc.render_pr_body(
            SAMPLE_CANDIDATES, SAMPLE_FINDINGS, lag_warning=None, commit_sha="abc1234"
        )
        self.assertIn(
            "git revert",
            body,
            "PR body must contain 'git revert' revert instruction",
        )
        self.assertIn(
            "skill-master-insights-state.json",
            body,
            "PR body must reference skill-master-insights-state.json for revert guidance",
        )


if __name__ == "__main__":
    unittest.main()
