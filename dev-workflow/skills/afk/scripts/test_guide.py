"""Tests for guide.py. Run: python3 -m unittest test_guide -v (from this directory).

GUIDE_PY may point at another copy of guide.py (used to prove these tests can fail —
same pattern as run-phase/scripts/test_phase.py)."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
GUIDE_PY = os.environ.get("GUIDE_PY", os.path.join(HERE, "guide.py"))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))

DONT_REPEAT_HEADING = "## ⛔ 别再跑一遍的"
CARD_FIELDS = ["Stopped at", "Why", "Next action", "Pointers", "Resume with"]


def _fixture(name):
    return os.path.join(FIXTURES, name)


def _fixture_text(name):
    with open(_fixture(name), "r", encoding="utf-8") as f:
        return f.read()


def run_guide(args, cwd=None):
    """Runs guide.py from `cwd` (default: a directory that is NOT the project
    root, so relative-path handling is exercised, never inherited from cwd)."""
    return subprocess.run([sys.executable, GUIDE_PY, *args], capture_output=True, text=True,
                          cwd=cwd or tempfile.gettempdir())


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


class TmpRoot:
    """A temp project root with a .claude dir."""

    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        os.makedirs(os.path.join(self.root, ".claude"), exist_ok=True)

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def copy_fixture(self, name, rel):
        dest = self.path(rel)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy(_fixture(name), dest)
        return dest

    def write_state(self, plan_file, current_phase=1, phase_step="execute"):
        state = json.loads(_fixture_text("state.json"))
        state["plan_file"] = plan_file
        state["current_phase"] = current_phase
        state["phase_step"] = phase_step
        with open(self.path(".claude", "dev-workflow-state.json"), "w", encoding="utf-8") as f:
            json.dump(state, f)
        return state

    def close(self):
        self.tmp.cleanup()


class GuideTests(unittest.TestCase):
    def setUp(self):
        self.roots = []

    def tearDown(self):
        for r in self.roots:
            r.close()

    def mkroot(self):
        r = TmpRoot()
        self.roots.append(r)
        return r

    # ---- sweep-dps ----

    def test_sweep_dps_plan_a_alone_one_blocking_one_recommended(self):
        out = run_guide(["sweep-dps", "--plans", _fixture("plan-a.md")])
        self.assertEqual(out.returncode, 0, out.stderr)
        data = json.loads(out.stdout)
        self.assertEqual(data["plans_swept"], 1)
        self.assertEqual(data["open_blocking"], 1)
        self.assertEqual(data["open_recommended"], 1)
        self.assertEqual(data["resolved"], 0)

    def test_sweep_dps_plan_b_fully_resolved(self):
        out = run_guide(["sweep-dps", "--plans", _fixture("plan-b.md")])
        data = json.loads(out.stdout)
        self.assertEqual(data["open_blocking"], 0)
        self.assertEqual(data["open_recommended"], 0)
        self.assertEqual(data["resolved"], 1)

    def test_sweep_dps_via_state_sweeps_a_never_c(self):
        root = self.mkroot()
        root.write_state(_fixture("plan-a.md"), current_phase=1)
        out = run_guide(["sweep-dps", "--root", root.root, "--dev-guide", _fixture("dev-guide.md")])
        data = json.loads(out.stdout)
        self.assertEqual(data["plans_swept"], 1)
        self.assertEqual(data["open_blocking"], 1)
        self.assertEqual(data["open_recommended"], 1)
        files_seen = {d["file"] for d in data["dps"]}
        self.assertEqual(files_seen, {_fixture("plan-a.md")})

    def test_sweep_dps_with_plans_flag_adds_c_too(self):
        root = self.mkroot()
        root.write_state(_fixture("plan-a.md"), current_phase=1)
        out = run_guide(["sweep-dps", "--root", root.root, "--dev-guide", _fixture("dev-guide.md"),
                          "--plans", _fixture("plan-c.md")])
        data = json.loads(out.stdout)
        self.assertEqual(data["plans_swept"], 2)
        self.assertEqual(data["open_blocking"], 2)  # A's one + C's one

    def test_sweep_dps_skips_state_plan_on_phase_mismatch(self):
        root = self.mkroot()
        # locate() resolves phase 1 (the dev-guide's first incomplete phase);
        # state parked on phase 2 must not contribute its plan_file.
        root.write_state(_fixture("plan-a.md"), current_phase=2)
        out = run_guide(["sweep-dps", "--root", root.root, "--dev-guide", _fixture("dev-guide.md")])
        data = json.loads(out.stdout)
        self.assertEqual(data["plans_swept"], 0)

    def test_sweep_dps_no_dev_guide_no_plans_is_empty(self):
        out = run_guide(["sweep-dps"])
        self.assertEqual(out.returncode, 0, out.stderr)
        data = json.loads(out.stdout)
        self.assertEqual(data, {"ok": True, "plans_swept": 0, "reports_swept": 0, "open_blocking": 0,
                                 "open_recommended": 0, "resolved": 0, "dps": [], "missing": []})

    def test_sweep_dps_plan_without_decisions_section_contributes_nothing(self):
        out = run_guide(["sweep-dps", "--plans", _fixture("plan-noverdict.md")])
        self.assertEqual(out.returncode, 0, out.stderr)
        data = json.loads(out.stdout)
        self.assertEqual(data["plans_swept"], 1)
        self.assertEqual(data["dps"], [])

    def test_sweep_dps_nonexistent_plan_is_missing_and_exit_3(self):
        out = run_guide(["sweep-dps", "--plans", _fixture("plan-a.md"), _fixture("nope.md")])
        self.assertEqual(out.returncode, 3)
        data = json.loads(out.stdout)
        self.assertEqual(data["missing"], [_fixture("nope.md")])
        self.assertFalse(data["ok"])
        # the plan that does exist is still swept — the exit code is the signal
        self.assertEqual(data["open_blocking"], 1)

    def test_sweep_dps_nonexistent_verify_report_is_missing_and_exit_3(self):
        out = run_guide(["sweep-dps", "--verify-report", _fixture("no-report.md")])
        self.assertEqual(out.returncode, 3)
        self.assertEqual(json.loads(out.stdout)["missing"], [_fixture("no-report.md")])

    def test_sweep_dps_state_plan_file_missing_on_disk_is_missing(self):
        root = self.mkroot()
        root.write_state("docs/06-plans/gone.md", current_phase=1)
        out = run_guide(["sweep-dps", "--root", root.root, "--dev-guide", _fixture("dev-guide.md")])
        self.assertEqual(out.returncode, 3)
        self.assertEqual(json.loads(out.stdout)["missing"], [root.path("docs", "06-plans", "gone.md")])

    def test_sweep_dps_relative_paths_resolve_against_root_not_cwd(self):
        root = self.mkroot()
        root.copy_fixture("dev-guide.md", "docs/06-plans/dev-guide.md")
        root.copy_fixture("plan-a.md", "docs/06-plans/plan-a.md")
        root.copy_fixture("plan-c.md", "docs/06-plans/plan-c.md")
        root.copy_fixture("report-a.md", ".claude/reviews/report-a.md")
        root.write_state("docs/06-plans/plan-a.md", current_phase=1)
        out = run_guide(["sweep-dps", "--root", root.root, "--dev-guide", "docs/06-plans/dev-guide.md",
                          "--plans", "docs/06-plans/plan-c.md",
                          "--verify-report", ".claude/reviews/report-a.md"], cwd="/")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        data = json.loads(out.stdout)
        self.assertEqual(data["plans_swept"], 2)
        self.assertEqual(data["reports_swept"], 1)
        self.assertEqual(data["missing"], [])

    def test_sweep_dps_dedups_state_plan_and_plans_flag_same_file(self):
        root = self.mkroot()
        root.copy_fixture("plan-a.md", "docs/06-plans/plan-a.md")
        root.write_state("docs/06-plans/plan-a.md", current_phase=1)
        out = run_guide(["sweep-dps", "--root", root.root, "--dev-guide", _fixture("dev-guide.md"),
                          "--plans", root.path("docs", "06-plans", "plan-a.md")])
        data = json.loads(out.stdout)
        self.assertEqual(data["plans_swept"], 1)
        self.assertEqual(data["open_blocking"], 1)

    def test_sweep_dps_dev_guide_with_no_state_file(self):
        root = self.mkroot()
        out = run_guide(["sweep-dps", "--root", root.root, "--dev-guide", _fixture("dev-guide.md")])
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["plans_swept"], 0)

    def test_sweep_dps_dev_guide_with_null_plan_file(self):
        root = self.mkroot()
        root.write_state(None, current_phase=1, phase_step="plan")
        out = run_guide(["sweep-dps", "--root", root.root, "--dev-guide", _fixture("dev-guide.md")])
        self.assertEqual(out.returncode, 0, out.stderr)
        data = json.loads(out.stdout)
        self.assertEqual(data["plans_swept"], 0)
        self.assertEqual(data["missing"], [])

    def test_sweep_dps_verify_report_blocks_are_parsed(self):
        out = run_guide(["sweep-dps", "--verify-report", _fixture("report-a.md")])
        self.assertEqual(out.returncode, 0, out.stderr)
        data = json.loads(out.stdout)
        self.assertEqual(data["reports_swept"], 1)
        # DP-001 is the "-- Already resolved" reference form: not a live DP
        self.assertEqual(sorted(d["id"] for d in data["dps"]), ["DP-003", "DP-004"])
        self.assertEqual(data["open_blocking"], 1)
        self.assertEqual(data["open_recommended"], 1)
        self.assertEqual({d["source"] for d in data["dps"]}, {"verify-report"})

    def test_sweep_dps_report_dp_resolved_by_chosen_or_by_plan_title(self):
        out = run_guide(["sweep-dps", "--plans", _fixture("plan-b.md"),
                          "--verify-report", _fixture("report-b.md")])
        data = json.loads(out.stdout)
        self.assertEqual(data["open_blocking"], 0)
        self.assertEqual(data["open_recommended"], 0)
        by_key = {(d["source"], d["id"]): d for d in data["dps"]}
        self.assertTrue(by_key[("verify-report", "DP-002")]["resolved"])   # **Chosen:** in the report
        self.assertEqual(by_key[("verify-report", "DP-001")]["resolved_via"], _fixture("plan-b.md"))

    def test_sweep_dps_new_blocking_dp_reusing_resolved_title_stays_open(self):
        plan_b = open(_fixture("plan-b.md"), encoding="utf-8").read()
        import re as _re
        m = _re.search(r"^### \[(DP-\d+)\] (.+?)(?: \((?:blocking|recommended)\))?$", plan_b, _re.M)
        title = m.group(2).strip()
        with tempfile.TemporaryDirectory() as d:
            rep = os.path.join(d, "report.md")
            with open(rep, "w", encoding="utf-8") as f:
                f.write("## Decisions\n\n### [DP-099] " + title + " (blocking)\n\n"
                        "**Context:** a different concern\n**Options:**\n- A: x\n- B: y\n"
                        "**Recommendation:** A\n")
            out = run_guide(["sweep-dps", "--plans", _fixture("plan-b.md"), "--verify-report", rep])
            data = json.loads(out.stdout)
            self.assertEqual(data["open_blocking"], 1)

    def test_sweep_dps_same_id_in_plan_and_report_are_distinct(self):
        out = run_guide(["sweep-dps", "--plans", _fixture("plan-a.md"),
                          "--verify-report", _fixture("report-b.md")])
        data = json.loads(out.stdout)
        dp1 = [d for d in data["dps"] if d["id"] == "DP-001"]
        self.assertEqual(len(dp1), 2)
        self.assertEqual({d["file"] for d in dp1}, {_fixture("plan-a.md"), _fixture("report-b.md")})

    def test_sweep_dps_real_path_run_phase_plan_resolved(self):
        plan = os.path.join(REPO, "docs", "06-plans", "2026-09-24-run-phase-state-script-plan.md")
        if not os.path.isfile(plan):
            self.skipTest("real-path plan not present in this checkout")
        out = run_guide(["sweep-dps", "--plans", plan])
        data = json.loads(out.stdout)
        self.assertEqual(data["open_blocking"], 0)
        self.assertEqual(data["open_recommended"], 0)
        dp1 = next(d for d in data["dps"] if d["id"] == "DP-001")
        self.assertTrue(dp1["resolved"])

    def test_sweep_dps_real_path_verifier_report_resolved_via_plan(self):
        plan = os.path.join(REPO, "docs", "06-plans", "2026-09-24-afk-absorbs-self-pacing-plan.md")
        report = os.path.join(REPO, ".claude", "reviews", "plan-verifier-2026-09-24-140253.md")
        if not (os.path.isfile(plan) and os.path.isfile(report)):
            self.skipTest("real-path plan/report not present in this checkout")
        out = run_guide(["sweep-dps", "--plans", plan, "--verify-report", report])
        data = json.loads(out.stdout)
        # The report still carries DP-002 with **Recommendation:** — it was answered
        # in the plan (same title), so it must not surface as open.
        self.assertEqual(data["open_blocking"], 0, data)
        rep = [d for d in data["dps"] if d["source"] == "verify-report"]
        self.assertEqual([d["id"] for d in rep], ["DP-002"])
        self.assertEqual(rep[0]["resolved_via"], plan)

    # ---- unit-signals ----

    def test_unit_signals_plan_b_verified_one_marker_no_must_fix(self):
        out = run_guide(["unit-signals", "--plan", _fixture("plan-b.md")])
        data = json.loads(out.stdout)
        self.assertTrue(data["verified"])
        self.assertEqual(data["verdict"], "approved")
        self.assertEqual(data["checkpoint_markers"], ["1"])
        self.assertIsNone(data["must_fix"])

    def test_unit_signals_must_fix_zero_is_echoed_not_null(self):
        out = run_guide(["unit-signals", "--plan", _fixture("plan-b.md"), "--must-fix", "0"])
        data = json.loads(out.stdout)
        self.assertEqual(data["must_fix"], 0)

    def test_unit_signals_plan_a_not_verified_reports_open_dps(self):
        out = run_guide(["unit-signals", "--plan", _fixture("plan-a.md")])
        data = json.loads(out.stdout)
        self.assertFalse(data["verified"])
        self.assertEqual(data["checkpoint_markers"], [])
        self.assertEqual(data["open_dps"]["open_blocking"], 1)
        self.assertEqual(data["open_dps"]["open_recommended"], 1)
        self.assertIn("src/foundation.py", data["files"])

    def test_unit_signals_revised_counts_as_verified(self):
        data = json.loads(run_guide(["unit-signals", "--plan", _fixture("plan-revised.md")]).stdout)
        self.assertEqual(data["verdict"], "revised")
        self.assertTrue(data["verified"])

    def test_unit_signals_partial_is_not_verified_and_ignores_verdict_outside_section(self):
        data = json.loads(run_guide(["unit-signals", "--plan", _fixture("plan-partial.md")]).stdout)
        self.assertEqual(data["verdict"], "partial")
        self.assertFalse(data["verified"])

    def test_unit_signals_verification_section_without_verdict(self):
        data = json.loads(run_guide(["unit-signals", "--plan", _fixture("plan-noverdict.md")]).stdout)
        self.assertIsNone(data["verdict"])
        self.assertFalse(data["verified"])
        self.assertEqual(data["open_dps"]["dps"], [])

    def test_unit_signals_files_dedup_across_tasks_in_order(self):
        data = json.loads(run_guide(["unit-signals", "--plan", _fixture("plan-revised.md")]).stdout)
        self.assertEqual(data["files"], ["src/shared.py", "src/one.py", "src/two.py"])

    def test_unit_signals_missing_plan_fails(self):
        out = run_guide(["unit-signals", "--plan", _fixture("does-not-exist.md")])
        self.assertEqual(out.returncode, 3)

    def test_unit_signals_verify_report_dps_count(self):
        out = run_guide(["unit-signals", "--plan", _fixture("plan-b.md"),
                          "--verify-report", _fixture("report-a.md")])
        self.assertEqual(out.returncode, 0, out.stderr)
        data = json.loads(out.stdout)
        self.assertEqual(data["open_dps"]["open_blocking"], 1)
        self.assertEqual(data["open_dps"]["reports_swept"], 1)

    def test_unit_signals_missing_verify_report_fails(self):
        out = run_guide(["unit-signals", "--plan", _fixture("plan-b.md"),
                          "--verify-report", _fixture("no-report.md")])
        self.assertEqual(out.returncode, 3)

    def test_unit_signals_relative_plan_resolves_against_root(self):
        root = self.mkroot()
        root.copy_fixture("plan-b.md", "docs/06-plans/plan-b.md")
        out = run_guide(["unit-signals", "--root", root.root, "--plan", "docs/06-plans/plan-b.md"], cwd="/")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertTrue(json.loads(out.stdout)["verified"])

    # ---- unit-signals: stop_rows ----

    def _rows(self, args):
        out = run_guide(["unit-signals", *args])
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        return {r["row"]: r for r in json.loads(out.stdout)["stop_rows"]}

    def test_stop_rows_clean_plan_has_none(self):
        self.assertEqual(self._rows(["--plan", _fixture("plan-revised.md"), "--must-fix", "0"]), {})

    def test_stop_rows_open_blocking_dp_fires_now(self):
        rows = self._rows(["--plan", _fixture("plan-a.md")])
        self.assertEqual(rows["blocking-dp"]["fires"], "now")
        self.assertEqual([d["id"] for d in rows["blocking-dp"]["dps"]], ["DP-001"])

    def test_stop_rows_open_recommended_dp_is_not_a_stop(self):
        rows = self._rows(["--plan", _fixture("plan-a.md")])
        self.assertEqual(set(rows), {"blocking-dp", "verify-missing"})

    def test_stop_rows_verify_missing_and_partial(self):
        self.assertIn("verify-missing", self._rows(["--plan", _fixture("plan-noverdict.md")]))
        self.assertEqual(self._rows(["--plan", _fixture("plan-partial.md")])["verify-missing"]["verdict"],
                         "partial")

    def test_stop_rows_author_checkpoint_fires_after_its_task_not_now(self):
        row = self._rows(["--plan", _fixture("plan-b.md")])["author-checkpoint"]
        self.assertEqual(row["tasks"], ["1"])
        self.assertNotEqual(row["fires"], "now")

    def test_stop_rows_must_fix_only_after_repair(self):
        self.assertNotIn("must-fix-after-repair",
                         self._rows(["--plan", _fixture("plan-revised.md"), "--must-fix", "2"]))
        rows = self._rows(["--plan", _fixture("plan-revised.md"), "--must-fix", "2", "--after-repair"])
        self.assertEqual(rows["must-fix-after-repair"]["must_fix"], 2)
        self.assertEqual(rows["must-fix-after-repair"]["fires"], "now")
        self.assertNotIn("must-fix-after-repair",
                         self._rows(["--plan", _fixture("plan-revised.md"), "--must-fix", "0", "--after-repair"]))

    def test_after_repair_without_must_fix_is_refused(self):
        out = run_guide(["unit-signals", "--plan", _fixture("plan-b.md"), "--after-repair"])
        self.assertEqual(out.returncode, 3)

    # ---- adopt-dp ----

    def test_adopt_dp_rewrites_only_that_dp_and_is_idempotent(self):
        root = self.mkroot()
        plan = root.copy_fixture("plan-a.md", "plan-a.md")
        out = run_guide(["adopt-dp", "--file", plan, "--dp", "DP-002"])
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertTrue(json.loads(out.stdout)["changed"])
        text = _read(plan)
        self.assertIn("**Chosen:** Option A — quieter default.", text)
        self.assertIn("**Recommendation:** A — simpler.", text)  # DP-001 untouched
        after_first = text
        out2 = run_guide(["adopt-dp", "--file", plan, "--dp", "DP-002"])
        self.assertEqual(out2.returncode, 0)
        self.assertFalse(json.loads(out2.stdout)["changed"])
        self.assertEqual(_read(plan), after_first)
        # the sweep now sees it resolved
        swept = json.loads(run_guide(["sweep-dps", "--plans", plan]).stdout)
        self.assertEqual(swept["open_recommended"], 0)
        self.assertEqual(swept["open_blocking"], 1)

    def test_adopt_dp_handles_unverified_recommendation_in_report(self):
        root = self.mkroot()
        rep = root.copy_fixture("report-a.md", "report-a.md")
        out = run_guide(["adopt-dp", "--file", rep, "--dp", "DP-004"])
        self.assertEqual(out.returncode, 0, out.stdout)
        text = _read(rep)
        self.assertIn("**Chosen:** Option A — no precedent in code.", text)
        self.assertNotIn("**Recommendation (unverified):**", text)

    def test_adopt_dp_unknown_dp_exit_3(self):
        root = self.mkroot()
        plan = root.copy_fixture("plan-a.md", "plan-a.md")
        before = _read(plan)
        out = run_guide(["adopt-dp", "--file", plan, "--dp", "DP-099"])
        self.assertEqual(out.returncode, 3)
        self.assertEqual(_read(plan), before)

    def test_adopt_dp_refuses_blocking_without_label(self):
        root = self.mkroot()
        plan = root.copy_fixture("plan-a.md", "plan-a.md")
        before = _read(plan)
        out = run_guide(["adopt-dp", "--file", plan, "--dp", "DP-001"])
        self.assertEqual(out.returncode, 3)
        self.assertEqual(_read(plan), before)

    def test_adopt_dp_blocking_with_user_label(self):
        root = self.mkroot()
        plan = root.copy_fixture("plan-a.md", "plan-a.md")
        out = run_guide(["adopt-dp", "--file", plan, "--dp", "DP-001", "--label", "B"])
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertIn("**Chosen:** Option B", _read(plan))
        self.assertIn("**Recommendation:** A — quieter default.", _read(plan))

    def test_adopt_dp_missing_file_exit_3(self):
        out = run_guide(["adopt-dp", "--file", _fixture("nope.md"), "--dp", "DP-001"])
        self.assertEqual(out.returncode, 3)

    # ---- goal-line ----

    def test_goal_line_starts_with_goal_command(self):
        root = self.mkroot()
        data = json.loads(run_guide(["goal-line", "--root", root.root, "--dev-guide", _fixture("dev-guide.md"),
                                      "--slug", "demo"]).stdout)
        self.assertTrue(data["line"].startswith("/goal 同时满足："), data["line"][:40])

    def test_goal_line_writes_file_and_names_judge_and_terminal(self):
        root = self.mkroot()
        out = run_guide(["goal-line", "--root", root.root, "--dev-guide", _fixture("dev-guide.md"),
                          "--slug", "demo"])
        data = json.loads(out.stdout)
        self.assertIn("phase.py locate --dev-guide", data["line"])
        self.assertIn("all_complete: true", data["line"])
        self.assertIn("## 终止", data["line"])
        self.assertIn(".claude/afk/demo.md", data["line"])
        self.assertEqual(data["dropped"], [])
        self.assertTrue(os.path.isfile(data["path"]))
        self.assertEqual(_read(data["path"]), data["line"])

    def test_goal_line_relative_dev_guide_resolves_against_root(self):
        root = self.mkroot()
        root.copy_fixture("dev-guide.md", "docs/06-plans/dev-guide.md")
        data = json.loads(run_guide(["goal-line", "--root", root.root, "--dev-guide",
                                      "docs/06-plans/dev-guide.md", "--slug", "demo"], cwd="/").stdout)
        self.assertIn("--dev-guide " + root.path("docs", "06-plans", "dev-guide.md"), data["line"])

    def test_goal_line_includes_constraints(self):
        root = self.mkroot()
        out = run_guide(["goal-line", "--root", root.root, "--dev-guide", _fixture("dev-guide.md"),
                          "--slug", "demo", "--constraint", "不 push", "--constraint", "只用 iPhone"])
        data = json.loads(out.stdout)
        self.assertIn("不 push", data["line"])
        self.assertIn("只用 iPhone", data["line"])

    def test_goal_line_over_cap_drops_constraints_lifo_never_judge_or_terminal(self):
        root = self.mkroot()
        args = ["goal-line", "--root", root.root, "--dev-guide", _fixture("dev-guide.md"), "--slug", "demo"]
        long_constraints = [f"约束{i}-" * 60 for i in range(20)]
        for c in long_constraints:
            args += ["--constraint", c]
        out = run_guide(args)
        data = json.loads(out.stdout)
        self.assertLessEqual(data["chars"], 4000)
        self.assertTrue(data["dropped"])
        # least load-bearing last: the drop order is the reverse of the pass order
        n = len(data["dropped"])
        self.assertEqual(data["dropped"], list(reversed(long_constraints))[:n])
        self.assertIn(long_constraints[0], data["line"])
        self.assertIn("phase.py locate --dev-guide", data["line"])
        self.assertIn("## 终止", data["line"])

    def test_goal_line_persists_constraints_and_reuses_them(self):
        root = self.mkroot()
        run_guide(["goal-line", "--root", root.root, "--dev-guide", _fixture("dev-guide.md"),
                   "--slug", "demo", "--constraint", "不 push", "--constraint", "只用 iPhone"])
        out = run_guide(["goal-line", "--root", root.root, "--dev-guide", _fixture("dev-guide.md"),
                          "--slug", "demo", "--reuse-constraints", "--constraint", "不动 fixtures",
                          "--constraint", "不 push"])
        self.assertEqual(out.returncode, 0, out.stderr)
        data = json.loads(out.stdout)
        self.assertEqual(data["constraints"], ["不 push", "只用 iPhone", "不动 fixtures"])
        self.assertIn("只用 iPhone", data["line"])
        self.assertIn("不动 fixtures", data["line"])
        # without --reuse-constraints the stored list is replaced, never merged silently
        data2 = json.loads(run_guide(["goal-line", "--root", root.root, "--dev-guide",
                                       _fixture("dev-guide.md"), "--slug", "demo"]).stdout)
        self.assertNotIn("只用 iPhone", data2["line"])

    def test_goal_line_reuse_without_stored_constraints_is_refused(self):
        root = self.mkroot()
        out = run_guide(["goal-line", "--root", root.root, "--dev-guide", _fixture("dev-guide.md"),
                          "--slug", "demo", "--reuse-constraints"])
        self.assertEqual(out.returncode, 3)

    # ---- crystal pointer ----

    def test_crystal_records_path_and_refuses_missing(self):
        root = self.mkroot()
        crystal = root.path("docs", "11-crystals", "2026-09-24-x-crystal.md")
        os.makedirs(os.path.dirname(crystal))
        with open(crystal, "w", encoding="utf-8") as f:
            f.write("# crystal\n")
        out = run_guide(["crystal", "--root", root.root, "--slug", "demo",
                          "--path", "docs/11-crystals/2026-09-24-x-crystal.md"], cwd="/")
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertEqual(_read(root.path(".claude", "afk", "demo-crystal.txt")).strip(), crystal)
        bad = run_guide(["crystal", "--root", root.root, "--slug", "demo", "--path", "docs/none.md"])
        self.assertEqual(bad.returncode, 3)

    # ---- card ----

    def _goal(self, root, slug="demo"):
        return json.loads(run_guide(["goal-line", "--root", root.root, "--dev-guide", _fixture("dev-guide.md"),
                                      "--slug", slug]).stdout)

    def _card(self, root, *extra, slug="demo"):
        out = run_guide(["card", "--root", root.root, "--slug", slug, "--stopped-at", "phase 1",
                          "--why", "blocking DP", "--next", "answer it", *extra])
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        return _read(root.path(".claude", "afk", f"{slug}-handoff.md")), json.loads(out.stdout)

    def test_card_refuses_without_goal_file(self):
        root = self.mkroot()
        out = run_guide(["card", "--root", root.root, "--slug", "demo", "--stopped-at", "x",
                          "--why", "y", "--next", "z"])
        self.assertNotEqual(out.returncode, 0)
        self.assertFalse(os.path.isfile(root.path(".claude", "afk", "demo-handoff.md")))

    def test_card_exact_field_set(self):
        root = self.mkroot()
        self._goal(root)
        text, _ = self._card(root)
        top_fields = [line[len("- **"):line.index(":**")] for line in text.splitlines()
                      if line.startswith("- **") and ":**" in line]
        self.assertEqual(top_fields, CARD_FIELDS)
        self.assertTrue(text.startswith("# afk handoff — demo\n"))

    def test_card_schema_pointers_only_for_existing_files(self):
        root = self.mkroot()
        self._goal(root)
        # Only the checkpoint file exists on disk; no run log, crystal, or state.
        with open(root.path(".claude", "execute-plan-checkpoint.json"), "w", encoding="utf-8") as f:
            f.write("{}")
        text, _ = self._card(root)
        self.assertIn("- **Stopped at:** phase 1", text)
        self.assertIn("- **Why:** blocking DP", text)
        self.assertIn("- **Next action:** answer it", text)
        self.assertIn("- **Pointers:**", text)
        self.assertIn("checkpoint: ", text)
        self.assertNotIn("run-log:", text)
        self.assertNotIn("crystal:", text)
        self.assertNotIn("state:", text)
        self.assertNotIn("plan:", text)
        self.assertIn("- **Resume with:**", text)
        self.assertNotIn(DONT_REPEAT_HEADING, text)

    def test_card_crystal_pointer_only_from_recorded_file_never_newest_on_disk(self):
        root = self.mkroot()
        self._goal(root)
        os.makedirs(root.path("docs", "11-crystals"))
        for name in ("2026-01-01-old-crystal.md", "2026-09-24-other-topic-crystal.md"):
            with open(root.path("docs", "11-crystals", name), "w", encoding="utf-8") as f:
                f.write("x\n")
        text, _ = self._card(root)
        self.assertNotIn("crystal:", text)
        run_guide(["crystal", "--root", root.root, "--slug", "demo",
                   "--path", root.path("docs", "11-crystals", "2026-01-01-old-crystal.md")])
        text, data = self._card(root)
        self.assertIn("  - crystal: " + root.path("docs", "11-crystals", "2026-01-01-old-crystal.md"), text)
        self.assertEqual(data["pointers"]["crystal"], root.path("docs", "11-crystals", "2026-01-01-old-crystal.md"))

    def test_card_run_log_pointer_when_present(self):
        root = self.mkroot()
        self._goal(root)
        os.makedirs(root.path(".claude", "afk"), exist_ok=True)
        with open(root.path(".claude", "afk", "demo.md"), "w", encoding="utf-8") as f:
            f.write("log\n")
        text, _ = self._card(root)
        self.assertIn("  - run-log: " + root.path(".claude", "afk", "demo.md"), text)

    def test_card_state_and_plan_pointers_resolve_relative_plan_against_root(self):
        root = self.mkroot()
        self._goal(root)
        root.write_state("docs/06-plans/p.md")
        text, _ = self._card(root)
        self.assertIn("  - state: " + root.path(".claude", "dev-workflow-state.json"), text)
        self.assertIn("  - plan: " + root.path("docs", "06-plans", "p.md"), text)

    def test_card_state_pointer_yaml_source(self):
        root = self.mkroot()
        self._goal(root)
        with open(root.path(".claude", "dev-workflow-state.yml"), "w", encoding="utf-8") as f:
            f.write("current_phase: 1\nphase_step: execute\nplan_file: null\n")
        text, _ = self._card(root)
        self.assertIn("  - state: " + root.path(".claude", "dev-workflow-state.yml"), text)
        self.assertNotIn("  - plan:", text)

    def test_card_state_pointer_unparseable_state_uses_its_path(self):
        root = self.mkroot()
        self._goal(root)
        with open(root.path(".claude", "dev-workflow-state.json"), "w", encoding="utf-8") as f:
            f.write("{not json")
        text, _ = self._card(root)
        self.assertIn("  - state: " + root.path(".claude", "dev-workflow-state.json"), text)

    def test_card_next_action_appends_doc_path(self):
        root = self.mkroot()
        self._goal(root)
        text, _ = self._card(root, "--doc", "docs/06-plans/HANDOFF-x.md")
        self.assertIn("- **Next action:** answer it — docs/06-plans/HANDOFF-x.md", text)

    def test_card_dont_repeat_is_one_optional_block(self):
        root = self.mkroot()
        self._goal(root)
        text, _ = self._card(root, "--dont-repeat", "already tried X, it fails the same way")
        self.assertEqual(text.count(DONT_REPEAT_HEADING), 1)
        self.assertIn("already tried X, it fails the same way", text)

    def test_card_resume_says_type_afk_and_quotes_last_goal_line(self):
        root = self.mkroot()
        goal = self._goal(root)
        text, data = self._card(root)
        lines = text.splitlines()
        i = next(k for k, line in enumerate(lines) if line.startswith("- **Resume with:**"))
        self.assertIn("`/afk`", lines[i])
        self.assertIn("/goal", lines[i])
        self.assertIn(goal["line"], lines[i + 1])       # last goal line, byte-identical
        self.assertTrue(lines[i + 1].startswith("  - "))
        self.assertEqual(data["last_goal_line"], goal["line"])

    def test_card_overwrites_previous(self):
        root = self.mkroot()
        self._goal(root)
        run_guide(["card", "--root", root.root, "--slug", "demo", "--stopped-at", "phase 1",
                   "--why", "first stop", "--next", "z"])
        run_guide(["card", "--root", root.root, "--slug", "demo", "--stopped-at", "phase 2",
                   "--why", "second stop", "--next", "z"])
        text = _read(root.path(".claude", "afk", "demo-handoff.md"))
        self.assertIn("second stop", text)
        self.assertNotIn("first stop", text)

    # ---- resume-point ----

    def _resume(self, root, dev_guide=None):
        out = run_guide(["resume-point", "--root", root.root, "--dev-guide", dev_guide or _fixture("dev-guide.md")])
        return out.returncode, json.loads(out.stdout)

    def test_resume_point_no_state_is_init_at_locate_phase(self):
        root = self.mkroot()
        code, data = self._resume(root)
        self.assertEqual(code, 0)
        self.assertEqual(data["branch"], "init")
        self.assertEqual(data["locate_phase"]["n"], 1)
        self.assertEqual(data["remaining_phases"], 2)

    def test_resume_point_same_phase_in_progress_is_resume(self):
        root = self.mkroot()
        root.write_state("p.md", current_phase=1, phase_step="review")
        _, data = self._resume(root)
        self.assertEqual(data["branch"], "resume")
        self.assertEqual(data["phase_step"], "review")

    def test_resume_point_other_phase_in_progress_is_mismatch(self):
        root = self.mkroot()
        root.write_state("p.md", current_phase=2, phase_step="execute")
        _, data = self._resume(root)
        self.assertEqual(data["branch"], "phase-mismatch")
        self.assertEqual(data["state_phase"], 2)

    def test_resume_point_done_but_phase_unchecked_is_check_off_never_init(self):
        root = self.mkroot()
        root.write_state("p.md", current_phase=1, phase_step="done")
        _, data = self._resume(root)
        self.assertEqual(data["branch"], "check-off")

    def test_resume_point_done_and_checked_off_is_init_next(self):
        root = self.mkroot()
        guide = root.copy_fixture("dev-guide.md", "dev-guide.md")
        run_guide(["--root", root.root, "resume-point", "--dev-guide", guide])  # smoke: global --root form
        subprocess.run([sys.executable, os.path.join(REPO, "dev-workflow", "skills", "run-phase", "scripts",
                                                     "phase.py"), "check-off", "--dev-guide", guide,
                        "--phase", "1"], check=True, capture_output=True)
        root.write_state("p.md", current_phase=1, phase_step="done")
        _, data = self._resume(root, guide)
        self.assertEqual(data["branch"], "init")
        self.assertEqual(data["locate_phase"]["n"], 2)

    def test_resume_point_unusable_state_defers_to_run_phase(self):
        root = self.mkroot()
        with open(root.path(".claude", "dev-workflow-state.json"), "w", encoding="utf-8") as f:
            f.write("{not json")
        _, data = self._resume(root)
        self.assertEqual(data["branch"], "state-error")

    def test_resume_point_lists_goal_slugs(self):
        root = self.mkroot()
        self._goal(root, slug="alpha")
        _, data = self._resume(root)
        self.assertEqual(data["slugs"], ["alpha"])

    def _state_with_report(self, root, step, verification_report):
        state = root.write_state("p.md", current_phase=1, phase_step=step)
        state["verification_report"] = verification_report
        with open(root.path(".claude", "dev-workflow-state.json"), "w", encoding="utf-8") as f:
            json.dump(state, f)

    def test_resume_point_verify_finished_enters_at_pre_execute_gate(self):
        root = self.mkroot()
        rep = root.copy_fixture("report-a.md", ".claude/reviews/plan-verifier-x.md")
        self._state_with_report(root, "verify", "must-revise — .claude/reviews/plan-verifier-x.md")
        _, data = self._resume(root)
        self.assertEqual(data["branch"], "resume")
        # verify-plan already ran: re-dispatching it would break its one-round rule and
        # re-raise the DP the user just answered in the report
        self.assertEqual(data["enter_at"], "pre-execute-gate")
        self.assertEqual(data["verify_report"], rep)

    def test_resume_point_verify_not_finished_enters_at_verify(self):
        root = self.mkroot()
        self._state_with_report(root, "verify", None)
        _, data = self._resume(root)
        self.assertEqual(data["enter_at"], "verify")
        self.assertIsNone(data["verify_report"])

    def test_resume_point_later_step_carries_verify_report(self):
        root = self.mkroot()
        rep = root.copy_fixture("report-a.md", ".claude/reviews/plan-verifier-x.md")
        self._state_with_report(root, "review", "approved — " + rep)
        _, data = self._resume(root)
        self.assertEqual(data["enter_at"], "review")
        self.assertEqual(data["verify_report"], rep)

    def test_resume_point_all_complete(self):
        root = self.mkroot()
        guide = root.copy_fixture("dev-guide.md", "dev-guide.md")
        phase_py = os.path.join(REPO, "dev-workflow", "skills", "run-phase", "scripts", "phase.py")
        for n in ("1", "2"):
            subprocess.run([sys.executable, phase_py, "check-off", "--dev-guide", guide, "--phase", n],
                           check=True, capture_output=True)
        _, data = self._resume(root, guide)
        self.assertEqual(data["branch"], "all-complete")


if __name__ == "__main__":
    unittest.main()
