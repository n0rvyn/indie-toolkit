#!/usr/bin/env python3
"""Tests for skill_usage.py.

Run: cd dev-workflow/scripts && python3 -m unittest test_skill_usage -v
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import skill_usage

FIXTURES = Path(__file__).with_name("fixtures") / "skill_usage"
SCRIPT = Path(__file__).with_name("skill_usage.py")


class TestBuildPatterns(unittest.TestCase):
    def test_typed_bare_matches(self):
        typed, _ = skill_usage.build_patterns("self-pacing")
        self.assertTrue(typed.search("<command-name>/self-pacing</command-name>"))

    def test_typed_namespaced_matches(self):
        typed, _ = skill_usage.build_patterns("self-pacing")
        self.assertTrue(typed.search("<command-name>/dev-workflow:self-pacing</command-name>"))

    def test_typed_does_not_match_prose(self):
        typed, _ = skill_usage.build_patterns("self-pacing")
        self.assertIsNone(
            typed.search("I read about self-pacing in the docs but haven't run /self-pacing yet")
        )

    def test_skill_tool_bare_matches(self):
        _, skill_pat = skill_usage.build_patterns("self-pacing")
        self.assertTrue(skill_pat.search('"name":"Skill","input":{"skill":"self-pacing","args":"x"}'))

    def test_skill_tool_namespaced_matches(self):
        _, skill_pat = skill_usage.build_patterns("self-pacing")
        self.assertTrue(
            skill_pat.search('"name":"Skill","input":{"skill":"dev-workflow:self-pacing","args":"x"}')
        )

    def test_skill_tool_does_not_match_different_skill(self):
        _, skill_pat = skill_usage.build_patterns("self-pacing")
        self.assertIsNone(
            skill_pat.search('"name":"Skill","input":{"skill":"kb","args":"self-pacing 0 times"}')
        )


class TestScanFixtures(unittest.TestCase):
    def test_typed_bare_counts(self):
        result = skill_usage.scan(["self-pacing"], None, FIXTURES)
        self.assertGreaterEqual(result["self-pacing"]["invocations_typed"], 1)

    def test_typed_and_namespaced_and_skill_tool_all_count(self):
        result = skill_usage.scan(["self-pacing"], None, FIXTURES)
        bucket = result["self-pacing"]
        # sess-bare, sess-namespaced, sess-old, sess-multi(x2) = 5 typed invocations
        self.assertEqual(bucket["invocations_typed"], 5)
        # sess-skill-tool = 1 skill-tool invocation
        self.assertEqual(bucket["invocations_skill_tool"], 1)

    def test_prose_mention_does_not_count(self):
        result = skill_usage.scan(["self-pacing"], None, FIXTURES)
        # sess-prose must not contribute; verified indirectly via the exact
        # invocation count above (which would be 6, not 5, if it counted).
        self.assertEqual(result["self-pacing"]["invocations_typed"], 5)

    def test_dedupe_by_session(self):
        result = skill_usage.scan(["self-pacing"], None, FIXTURES)
        # sess-multi fires twice but is one session; bare/namespaced/
        # skill-tool/old add four more distinct sessions = 5 sessions total.
        self.assertEqual(result["self-pacing"]["sessions"], 5)

    def test_days_window_excludes_old_record(self):
        result = skill_usage.scan(["self-pacing"], 60, FIXTURES)
        # sess-old is dated 2020-01-01, well outside any 60-day window from
        # today, so both its session and its invocation drop out.
        self.assertEqual(result["self-pacing"]["invocations_typed"], 4)
        self.assertEqual(result["self-pacing"]["sessions"], 4)

    def test_last_use_is_the_most_recent_matching_date(self):
        result = skill_usage.scan(["self-pacing"], None, FIXTURES)
        self.assertEqual(result["self-pacing"]["last_use"], "2026-09-21")

    def test_unrelated_skill_name_is_unaffected(self):
        result = skill_usage.scan(["afk"], None, FIXTURES)
        self.assertEqual(result["afk"]["invocations_typed"], 1)
        self.assertEqual(result["afk"]["sessions"], 1)

    def test_control_skill_counts_independently(self):
        result = skill_usage.scan(["self-pacing", "kb"], None, FIXTURES)
        self.assertGreaterEqual(result["kb"]["invocations_skill_tool"], 1)
        # the "kb" bucket must not pick up the "self-pacing" mention inside
        # the kb call's own args string.
        self.assertEqual(result["kb"]["invocations_typed"], 0)


class TestMain(unittest.TestCase):
    def test_main_prints_json_with_skills_and_control(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = skill_usage.main(
                ["--projects", str(FIXTURES), "--control", "kb", "self-pacing", "afk"]
            )
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertIn("self-pacing", payload["skills"])
        self.assertIn("afk", payload["skills"])
        self.assertIn("kb", payload["control"])

    def test_cli_subprocess_real_path(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--projects", str(FIXTURES), "--days", "60", "self-pacing"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["skills"]["self-pacing"]["invocations_typed"], 4)


EDGE = Path(__file__).with_name("fixtures") / "skill_usage_edge"


class TestEdgeCases(unittest.TestCase):
    """Shapes seen in real transcripts (2026-09-24 survey of ~/.claude/projects):
    tool_result lines that echo `<command-name>` markup, isMeta peer/skill-load
    lines, fork-skill launches recorded only as `system`/`local_command`, and
    records with a missing or unparseable timestamp."""

    def test_only_genuine_typed_messages_count(self):
        # sess-echo (tool_result echo), sess-peer (isMeta x2 + prose mid-string)
        # must add nothing; nots/badts/nosid/junk are the four genuine ones.
        bucket = skill_usage.scan(["self-pacing"], None, EDGE)["self-pacing"]
        self.assertEqual(bucket["invocations_typed"], 4)
        self.assertEqual(bucket["sessions"], 4)

    def test_tool_result_echo_alone_counts_zero(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d) / "p"
            proj.mkdir()
            (proj / "s.jsonl").write_text((EDGE / "proj" / "sess-echo.jsonl").read_text(), encoding="utf-8")
            self.assertEqual(skill_usage.scan(["self-pacing"], None, Path(d))["self-pacing"]["invocations_typed"], 0)

    def test_days_excludes_missing_and_unparseable_timestamps(self):
        bucket = skill_usage.scan(["self-pacing"], 60, EDGE)["self-pacing"]
        self.assertEqual(bucket["invocations_typed"], 2)  # nosid + junk (2099 dates)
        self.assertEqual(bucket["sessions"], 2)

    def test_missing_session_id_falls_back_to_file_stem(self):
        with tempfile.TemporaryDirectory() as d:
            proj = Path(d) / "p"
            proj.mkdir()
            line = (EDGE / "proj" / "nosid.jsonl").read_text()
            (proj / "one.jsonl").write_text(line + line, encoding="utf-8")
            (proj / "two.jsonl").write_text(line, encoding="utf-8")
            bucket = skill_usage.scan(["self-pacing"], None, Path(d))["self-pacing"]
            self.assertEqual(bucket["invocations_typed"], 3)
            self.assertEqual(bucket["sessions"], 2)  # stems "one" and "two"

    def test_malformed_and_non_dict_lines_are_skipped(self):
        bucket = skill_usage.scan(["self-pacing"], 60, EDGE)["self-pacing"]
        # sess-junk's valid record after three junk lines still counts
        self.assertGreaterEqual(bucket["invocations_typed"], 1)

    def test_fork_skill_launch_counts_bare_and_namespaced(self):
        bucket = skill_usage.scan(["commit"], None, EDGE)["commit"]
        self.assertEqual(bucket["invocations_fork"], 2)
        # the plain "/dev-workflow:commit" user line is the same launch, not a second one
        self.assertEqual(bucket["invocations_typed"], 0)
        self.assertEqual(bucket["sessions"], 1)

    def test_fork_channel_does_not_match_other_skill_containing_the_name(self):
        bucket = skill_usage.scan(["review-before-commit"], None, EDGE)["review-before-commit"]
        self.assertEqual(bucket["invocations_fork"], 1)

    def test_nonexistent_projects_root_is_all_zero(self):
        bucket = skill_usage.scan(["afk"], None, Path("/nonexistent/skill-usage-root"))["afk"]
        self.assertEqual(bucket, {"sessions": 0, "invocations_typed": 0, "invocations_skill_tool": 0,
                                  "invocations_fork": 0, "last_use": None})

    def test_main_without_control_has_no_control_key(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            skill_usage.main(["--projects", str(FIXTURES), "afk"])
        self.assertNotIn("control", json.loads(buf.getvalue()))

    def test_main_duplicate_names_reported_once(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            skill_usage.main(["--projects", str(FIXTURES), "self-pacing", "self-pacing", "--control",
                              "self-pacing"])
        payload = json.loads(buf.getvalue())
        self.assertEqual(list(payload["skills"]), ["self-pacing"])
        self.assertEqual(payload["skills"]["self-pacing"]["invocations_typed"], 5)
        self.assertEqual(payload["control"]["self-pacing"], payload["skills"]["self-pacing"])


class TestMutation(unittest.TestCase):
    """Confirms the fixtures actually exercise the matcher: weakening the
    typed-command regex to plain substring search must make a test fail."""

    def test_regex_boundary_is_load_bearing(self):
        loose_typed = re.compile(re.escape("self-pacing"))
        content = "I read about self-pacing in the docs but haven't run /self-pacing yet"
        # The real (tag-bounded) pattern must NOT match prose ...
        typed, _ = skill_usage.build_patterns("self-pacing")
        self.assertIsNone(typed.search(content))
        # ... while a naive substring pattern WOULD match it, proving the
        # tag boundary in build_patterns is the thing doing the work.
        self.assertIsNotNone(loose_typed.search(content))


if __name__ == "__main__":
    unittest.main()
