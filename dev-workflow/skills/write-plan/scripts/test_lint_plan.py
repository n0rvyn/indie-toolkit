#!/usr/bin/env python3
"""Tests for lint_plan.py. Run: python3 -m unittest test_lint_plan (from this directory).

LINT_PY may point at another copy of lint_plan.py (used to prove these tests can fail)."""

import importlib.util
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("lint_plan", os.environ.get("LINT_PY", os.path.join(HERE, "lint_plan.py")))
L = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(L)


def task(head, depends=None, files=True, verify=True):
    body = [f"### {head}", ""]
    if depends is not None:
        body.append(f"**Depends on:** {depends}")
    if files:
        body.append("**Files:**\n- Modify: `a.py`")
    if verify:
        body.append("**Verify:**\nRun: `true`\nExpected: exit 0")
    return "\n".join(body) + "\n\n"


def msgs(result):
    return " | ".join(e["msg"] for e in result["errors"])


class LintPlanTests(unittest.TestCase):
    def test_clean_plan_passes(self):
        plan = "# Plan\n\n" + task("Task 1-tests: t") + task("Task 1-impl: i", "Task 1-tests") + task("Task 2: x", "None")
        r = L.lint(plan)
        self.assertTrue(r["ok"], msgs(r))
        self.assertEqual(r["tasks"], 3)

    def test_unparseable_task_heading_is_an_error(self):
        r = L.lint(task("Task 1: a") + task("Task 2b-tests: b"))
        self.assertFalse(r["ok"])
        self.assertIn("execute-plan will not see it", msgs(r))

    def test_notes_heading_mentioning_a_task_is_not_flagged(self):
        r = L.lint(task("Task 1: a") + "### Task 1 改动后（复测）\n\n结果正常。\n")
        self.assertTrue(r["ok"], msgs(r))

    def test_no_tasks_is_an_error(self):
        r = L.lint("# Plan\n\nJust prose.\n")
        self.assertFalse(r["ok"])
        self.assertEqual(r["tasks"], 0)

    def test_missing_verify_and_files(self):
        r = L.lint(task("Task 1: a", files=False, verify=False))
        self.assertIn("missing `**Files:**`", msgs(r))
        self.assertIn("missing `**Verify:**`", msgs(r))

    def test_plural_depends_is_flagged_as_ignored(self):
        r = L.lint(task("Task 1: a") + task("Task 2: b") + task("Task 3: c", "Tasks 1 through 2."))
        self.assertIn("dependency is ignored", msgs(r))

    def test_explicit_no_dependency_values_pass(self):
        for v in ("None", "none", "—", "—（先写，应 FAIL）", ""):
            r = L.lint(task("Task 1: a", v))
            self.assertTrue(r["ok"], f"{v!r}: {msgs(r)}")

    def test_dependency_on_missing_task(self):
        r = L.lint(task("Task 1-tests: t") + task("Task 1-impl: i") + task("Task 2: x", "Task 1"))
        self.assertIn("depends on Task 1, which does not exist", msgs(r))

    def test_unpaired_tests_task(self):
        r = L.lint(task("Task 1-tests: t") + task("Task 2: x"))
        self.assertIn("no matching `Task 1-impl`", msgs(r))

    def test_duplicate_ids(self):
        r = L.lint(task("Task 1: a") + task("Task 1: again"))
        self.assertIn("duplicate task id", msgs(r))

    def test_examples_inside_code_fences_are_ignored(self):
        plan = task("Task 1: a") + "```markdown\n### Task 9 - example\n**Depends on:** Tasks 1-8\n```\n"
        r = L.lint(plan)
        self.assertTrue(r["ok"], msgs(r))


if __name__ == "__main__":
    unittest.main()
