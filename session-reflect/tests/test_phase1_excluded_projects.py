#!/usr/bin/env python3
"""Phase 1: excluded_projects path-prefix matching + ignore_patterns back-compat."""

import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent / "scripts"


def load_extract_sessions():
    spec = importlib.util.spec_from_file_location(
        "extract_sessions", SCRIPT_DIR / "extract-sessions.py"
    )
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class TestExcludedProjects(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.projects_dir = Path(self.tmpdir) / "projects"
        self.projects_dir.mkdir()
        # Create a few project dirs with one fake jsonl each
        for name in (".adam", "indie-toolkit", "other-automation", "team-adam-tool"):
            d = self.projects_dir / name
            d.mkdir()
            (d / "session1.jsonl").write_text(
                '{"sessionId": "s-' + name + '", "cwd": "/Users/u/Code/' + name + '", "timestamp": "2026-04-10T00:00:00Z"}\n'
            )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_excluded_projects_filters_by_prefix(self):
        m = load_extract_sessions()
        sessions = m.discover_claude_sessions(
            str(self.projects_dir),
            cutoff_ts=0,
            excluded_projects=[".adam"],
        )
        names = {s["project_dir"] for s in sessions}
        self.assertNotIn(".adam", names)
        self.assertIn("indie-toolkit", names)
        self.assertIn("other-automation", names)
        self.assertIn("team-adam-tool", names)

    def test_excluded_projects_matches_path_component_prefix_not_substring(self):
        m = load_extract_sessions()
        sessions = m.discover_claude_sessions(
            str(self.projects_dir),
            cutoff_ts=0,
            excluded_projects=[".adam"],
        )
        project_paths = {s["project_dir"]: s["project_path"] for s in sessions}
        self.assertNotIn(".adam", project_paths)
        self.assertEqual(
            project_paths["other-automation"],
            "/Users/u/Code/other-automation",
        )
        self.assertEqual(
            project_paths["team-adam-tool"],
            "/Users/u/Code/team-adam-tool",
        )

    def test_ignore_patterns_back_compat_emits_deprecation_warning(self):
        # Run extract-sessions.py with --ignore-patterns; capture stderr
        # NOTE: existing flag in extract-sessions.py is --claude-projects, NOT --projects-dir
        result = subprocess.run(
            [
                sys.executable, str(SCRIPT_DIR / "extract-sessions.py"),
                "--claude-projects", str(self.projects_dir),
                "--ignore-patterns", "adam",
                "--source", "claude-code",
                "--format", "json",
                "--days", "0",  # no time filter; fixture files have current mtime but be explicit
            ],
            capture_output=True, text=True, check=False,
        )
        self.assertIn("DEPRECATION WARNING", result.stderr,
                      "Should warn when ignore_patterns is used without excluded_projects")

    def test_ignore_patterns_substring_match_still_works(self):
        m = load_extract_sessions()
        sessions = m.discover_claude_sessions(
            str(self.projects_dir),
            cutoff_ts=0,
            ignore_patterns=["adam"],
        )
        names = {s["project_dir"] for s in sessions}
        # "adam" substring matches both .adam and other-automation? No — substring is "adam"
        # which matches ".adam" and "other-automation" (no "adam" in "other-automation")
        # Actually "other-automation" does not contain "adam" — only ".adam" does.
        self.assertNotIn(".adam", names)
        self.assertIn("indie-toolkit", names)
        self.assertIn("other-automation", names)
        self.assertNotIn("team-adam-tool", names)

    def test_load_config_includes_default_adam_exclusion(self):
        m = load_extract_sessions()
        excluded, legacy = m._load_config()
        self.assertIn(".adam", excluded)
        self.assertEqual(legacy, [])


if __name__ == "__main__":
    unittest.main()
