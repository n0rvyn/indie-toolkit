#!/usr/bin/env python3
"""Tests for route.py. Each case builds a throwaway git repo, changes files, and asserts
which reviewers get routed. Run: python3 -m unittest test_route (from this directory).

ROUTE_PY may point at another copy of route.py (used to prove these tests can fail)."""

import importlib.util
import json
import os
import subprocess
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("route", os.environ.get("ROUTE_PY", os.path.join(HERE, "route.py")))
route = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(route)


def sh(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


class Repo:
    def __init__(self, apple=False):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        sh(self.root, "git", "init", "-q")
        sh(self.root, "git", "config", "user.email", "t@t")
        sh(self.root, "git", "config", "user.name", "t")
        if apple:
            os.makedirs(os.path.join(self.root, "App.xcodeproj"))
            self.write("App.xcodeproj/project.pbxproj", "// base\n")
        self.write("App/HomeView.swift", "struct HomeView {}\n")
        self.write("App/Store.swift", "final class Store {}\n")
        self.write("App/Info.plist", "<plist/>\n")
        sh(self.root, "git", "add", "-A")
        sh(self.root, "git", "commit", "-q", "-m", "base")

    def write(self, rel, text):
        p = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)

    def close(self):
        self.tmp.cleanup()


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.plugins = tempfile.TemporaryDirectory()
        os.makedirs(os.path.join(self.plugins.name, "indie-toolkit", "apple-dev"))
        os.environ["ROUTE_PLUGINS_CACHE"] = self.plugins.name
        self.repos = []

    def tearDown(self):
        for r in self.repos:
            r.close()
        self.plugins.cleanup()
        os.environ.pop("ROUTE_PLUGINS_CACHE", None)

    def repo(self, apple=False):
        r = Repo(apple)
        self.repos.append(r)
        return r

    def agents(self, out):
        return [r["agent"] for r in out.get("apple_reviewers", [])]

    def test_no_changes_stops(self):
        out = route.route(self.repo(apple=True).root)
        self.assertEqual(out["stop"], "no uncommitted changes")

    def test_non_apple_routes_no_apple_reviewer(self):
        r = self.repo(apple=False)
        r.write("App/HomeView.swift", "struct HomeView { var x = 1 }\n")
        out = route.route(r.root)
        self.assertFalse(out["apple_project"])
        self.assertEqual(self.agents(out), [])

    def test_modified_view_routes_ui_reviewer_only(self):
        r = self.repo(apple=True)
        r.write("App/HomeView.swift", "struct HomeView { var x = 1 }\n")
        out = route.route(r.root)
        self.assertEqual(self.agents(out), ["apple-dev:ui-reviewer", "apple-dev:feature-reviewer"])
        self.assertEqual(out["apple_reviewers"][-1]["when"], "only if SPANS_LAYERS")

    def test_logic_only_change_routes_no_ui_reviewer(self):
        r = self.repo(apple=True)
        r.write("App/Store.swift", "final class Store { var n = 0 }\n")
        out = route.route(r.root)
        self.assertNotIn("apple-dev:ui-reviewer", self.agents(out))
        self.assertNotIn("apple-dev:design-reviewer", self.agents(out))

    def test_untracked_new_view_routes_design_reviewer(self):
        r = self.repo(apple=True)
        r.write("App/ProfileView.swift", "struct ProfileView {}\n")  # never git-added
        out = route.route(r.root)
        self.assertIn("apple-dev:design-reviewer", self.agents(out))
        design = [x for x in out["apple_reviewers"] if x["agent"] == "apple-dev:design-reviewer"][0]
        self.assertEqual(design["files"], ["App/ProfileView.swift"])

    def test_plist_routes_apple_reviewer(self):
        r = self.repo(apple=True)
        r.write("App/Info.plist", "<plist><dict/></plist>\n")
        out = route.route(r.root)
        self.assertIn("apple-dev:apple-reviewer", self.agents(out))
        self.assertNotIn("apple-dev:ui-reviewer", self.agents(out))

    def test_feature_spec_makes_feature_reviewer_unconditional(self):
        r = self.repo(apple=True)
        r.write("docs/05-features/home.md", "# Home\n")
        r.write("App/Store.swift", "final class Store { var n = 0 }\n")
        out = route.route(r.root)
        feature = [x for x in out["apple_reviewers"] if x["agent"] == "apple-dev:feature-reviewer"][0]
        self.assertEqual(feature["when"], "always")

    def test_apple_dev_missing_routes_nothing(self):
        os.environ["ROUTE_PLUGINS_CACHE"] = os.path.join(self.plugins.name, "empty")
        r = self.repo(apple=True)
        r.write("App/HomeView.swift", "struct HomeView { var x = 1 }\n")
        out = route.route(r.root)
        self.assertFalse(out["apple_dev_installed"])
        self.assertEqual(self.agents(out), [])

    def test_scope_files_intersection_empty_stops(self):
        r = self.repo(apple=True)
        r.write("App/HomeView.swift", "struct HomeView { var x = 1 }\n")
        out = route.route(r.root, scope_files=["App/Store.swift"])
        self.assertEqual(out["stop"], "scope_files intersect no changed file")

    def test_cli_prints_json(self):
        r = self.repo(apple=True)
        r.write("App/HomeView.swift", "struct HomeView { var x = 1 }\n")
        out = subprocess.run(["python3", os.path.join(HERE, "route.py"), "--root", r.root],
                             capture_output=True, text=True, env=os.environ)
        self.assertEqual(out.returncode, 0)
        self.assertTrue(json.loads(out.stdout)["flags"]["HAS_VIEW_MODIFIED"])


if __name__ == "__main__":
    unittest.main()
