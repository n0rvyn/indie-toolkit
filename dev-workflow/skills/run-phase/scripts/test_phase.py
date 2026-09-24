"""Tests for phase.py. Each case runs in a throwaway temp dir standing in for a project
root. Run: python3 -m unittest test_phase -v (from this directory).

PHASE_PY may point at another copy of phase.py (used to prove these tests can fail —
same pattern as review-execution/scripts/test_route.py)."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
_spec = importlib.util.spec_from_file_location("phase", os.environ.get("PHASE_PY", os.path.join(HERE, "phase.py")))
phase = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(phase)
# Subprocess tests added with the review fixes run this path, so PHASE_PY also
# redirects them (the older CLI tests always run the working copy).
PHASE_SCRIPT = os.environ.get("PHASE_PY", os.path.join(HERE, "phase.py"))


def _fixture(name):
    with open(os.path.join(FIXTURES, name), "r", encoding="utf-8") as f:
        return f.read()


class TmpRoot:
    """A temp project root with a .claude dir, optionally seeded from a fixture."""

    def __init__(self, fixture=None, as_name=None):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        os.makedirs(os.path.join(self.root, ".claude"), exist_ok=True)
        if fixture:
            dest_name = as_name or fixture
            shutil.copy(os.path.join(FIXTURES, fixture), os.path.join(self.root, ".claude", dest_name))

    def state_path(self):
        return os.path.join(self.root, ".claude", "dev-workflow-state.json")

    def yaml_path(self):
        return os.path.join(self.root, ".claude", "dev-workflow-state.yml")

    def read_state(self):
        with open(self.state_path(), "r", encoding="utf-8") as f:
            return json.load(f)

    def close(self):
        self.tmp.cleanup()


class PhaseTests(unittest.TestCase):
    def setUp(self):
        self.roots = []

    def tearDown(self):
        for r in self.roots:
            r.close()

    def mk(self, fixture=None, as_name=None):
        r = TmpRoot(fixture, as_name)
        self.roots.append(r)
        return r

    # -- no state file -----------------------------------------------------

    def test_no_state_file_status(self):
        r = self.mk()
        out = phase.status(r.root)
        self.assertEqual(out, {"ok": True, "exists": False})

    def test_no_state_file_hook_prints_nothing(self):
        r = self.mk()
        out = subprocess.run([sys.executable, os.path.join(HERE, "phase.py"),
                              "--root", r.root, "status", "--hook"],
                              capture_output=True, text=True)
        self.assertEqual(out.returncode, 0)
        self.assertEqual(out.stdout, "")

    def test_no_state_file_step_refused(self):
        r = self.mk()
        out, code = phase.cmd_step(r.root, "plan")
        self.assertFalse(out["ok"])
        self.assertEqual(code, 3)

    # -- sanctioned transitions ---------------------------------------------

    def test_self_transition_bumps_last_updated(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        before = r.read_state()["last_updated"]
        out, code = phase.cmd_step(r.root, "review")
        self.assertTrue(out["ok"], out)
        self.assertEqual(code, 0)
        after = r.read_state()
        self.assertEqual(after["phase_step"], "review")
        self.assertNotEqual(after["last_updated"], before)

    def test_init_then_step_plan_noop(self):
        r = self.mk()
        out, code = phase.cmd_init(r.root, 1, "Phase One", "docs/06-plans/x-dev-guide.md")
        self.assertTrue(out["ok"], out)
        out, code = phase.cmd_step(r.root, "plan")
        self.assertTrue(out["ok"], out)
        self.assertEqual(r.read_state()["phase_step"], "plan")

    def test_init_preserves_adhoc_keys_from_prior_state(self):
        r = self.mk("adhoc-keys.json", "dev-workflow-state.json")
        state = r.read_state()
        state["phase_step"] = "done"  # init must refuse otherwise
        with open(r.state_path(), "w") as f:
            json.dump(state, f)
        out, code = phase.cmd_init(r.root, 2, "Phase Two", "docs/06-plans/x-dev-guide.md")
        self.assertTrue(out["ok"], out)
        after = r.read_state()
        self.assertEqual(after["deploy_notes"], "TestFlight build 42 sent")
        self.assertEqual(after["blocked_by"], "waiting on Apple review")
        self.assertEqual(after["current_phase"], 2)
        self.assertEqual(after["phase_step"], "plan")

    def test_review_to_test_sanctioned(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        out, code = phase.cmd_step(r.root, "test")
        self.assertTrue(out["ok"], out)
        self.assertEqual(code, 0)
        self.assertEqual(r.read_state()["phase_step"], "test")

    def test_fix_to_fix_noop(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        state = r.read_state()
        state["phase_step"] = "fix"
        with open(r.state_path(), "w") as f:
            json.dump(state, f)
        out, code = phase.cmd_step(r.root, "fix")
        self.assertTrue(out["ok"], out)
        self.assertEqual(r.read_state()["phase_step"], "fix")

    def test_reset_to_plan_with_reason_from_execute(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        state = r.read_state()
        state["phase_step"] = "execute"
        with open(r.state_path(), "w") as f:
            json.dump(state, f)
        out, code = phase.cmd_step(r.root, "plan", reason="scope drift")
        self.assertTrue(out["ok"], out)
        after = r.read_state()
        self.assertEqual(after["phase_step"], "plan")
        self.assertTrue(any("scope drift" in n["text"] for n in after["notes"]))

    def test_done_to_plan_refused(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        state = r.read_state()
        state["phase_step"] = "done"
        with open(r.state_path(), "w") as f:
            json.dump(state, f)
        out, code = phase.cmd_step(r.root, "plan", reason="anything")
        self.assertFalse(out["ok"])
        self.assertEqual(code, 3)

    def test_finalized_from_review_requires_override_and_reason(self):
        r = self.mk("valid.json", "dev-workflow-state.json")  # phase_step: review
        out, code = phase.cmd_step(r.root, "finalized")
        self.assertFalse(out["ok"])
        out, code = phase.cmd_step(r.root, "finalized", reason="finalize override")
        self.assertFalse(out["ok"])
        out, code = phase.cmd_step(r.root, "finalized", reason="finalize override", override=True)
        self.assertTrue(out["ok"], out)
        self.assertEqual(r.read_state()["phase_step"], "finalized")

    def test_finalized_from_done_no_reason_needed(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        state = r.read_state()
        state["phase_step"] = "done"
        with open(r.state_path(), "w") as f:
            json.dump(state, f)
        out, code = phase.cmd_step(r.root, "finalized")
        self.assertTrue(out["ok"], out)

    def test_generic_illegal_transition_refused_then_allowed_with_reason(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        state = r.read_state()
        state["phase_step"] = "verify"
        with open(r.state_path(), "w") as f:
            json.dump(state, f)
        out, code = phase.cmd_step(r.root, "fix")
        self.assertFalse(out["ok"])
        # verify -> fix skips execute/test/review: a forward skip needs --override too.
        out, code = phase.cmd_step(r.root, "fix", reason="manual jump")
        self.assertFalse(out["ok"], out)
        out, code = phase.cmd_step(r.root, "fix", reason="manual jump", override=True)
        self.assertTrue(out["ok"], out)
        after = r.read_state()
        self.assertEqual(after["phase_step"], "fix")
        self.assertTrue(any("manual jump" in n["text"] for n in after["notes"]))

    # -- quarantine -----------------------------------------------------------

    def test_quarantine_then_init(self):
        r = self.mk("broken.json", "dev-workflow-state.json")
        out, code = phase.cmd_quarantine(r.root)
        self.assertTrue(out["ok"], out)
        self.assertTrue(os.path.isfile(out["quarantined"]))
        self.assertFalse(os.path.isfile(r.state_path()))
        out, code = phase.cmd_init(r.root, 1, "Phase One", "docs/06-plans/x-dev-guide.md")
        self.assertTrue(out["ok"], out)

    def test_quarantine_refuses_healthy_file_by_default(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        out, code = phase.cmd_quarantine(r.root)
        self.assertFalse(out["ok"])
        self.assertEqual(code, 3)
        self.assertTrue(os.path.isfile(r.state_path()))  # untouched

    def test_quarantine_explicit_target_quarantines_anyway(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        out, code = phase.cmd_quarantine(r.root, target=r.state_path())
        self.assertTrue(out["ok"], out)
        self.assertFalse(os.path.isfile(r.state_path()))

    # -- step done + completion gate ------------------------------------------

    def test_step_done_override_on_gaps_leaves_test_report_untouched(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        state = r.read_state()
        state.update({
            "review_reports": ["review-execution:consolidated"],
            "review_findings": {"must_fix": 2, "nice_to_have": 0},
            "test_report": "existing-report.md",
            "gaps_remaining": 3,
        })
        with open(r.state_path(), "w") as f:
            json.dump(state, f)
        out, code = phase.cmd_step(r.root, "done")
        self.assertFalse(out["ok"])
        self.assertEqual(out["block"], "gaps")
        out, code = phase.cmd_step(r.root, "done", override=True)
        self.assertTrue(out["ok"], out)
        after = r.read_state()
        self.assertEqual(after["test_report"], "existing-report.md")
        self.assertEqual(after["review_reports"], ["review-execution:consolidated"])
        self.assertTrue(any("gaps accepted as known issues: 3" in n["text"] for n in after["notes"]))

    def test_step_done_no_reports_block_and_override(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        state = r.read_state()
        state.update({"review_reports": [], "test_report": None})
        with open(r.state_path(), "w") as f:
            json.dump(state, f)
        out, code = phase.cmd_step(r.root, "done")
        self.assertFalse(out["ok"])
        self.assertEqual(out["block"], "no-reports")
        out, code = phase.cmd_step(r.root, "done", override=True)
        self.assertTrue(out["ok"], out)
        after = r.read_state()
        self.assertEqual(after["review_reports"], ["user-override"])
        self.assertEqual(after["test_report"], "user-override")

    # -- legacy_leftover / migrate -----------------------------------------

    def test_both_json_and_yaml_present_legacy_leftover(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        shutil.copy(os.path.join(FIXTURES, "legacy.yml"), r.yaml_path())
        out = phase.status(r.root)
        self.assertTrue(out.get("legacy_leftover"))
        out, code = phase.cmd_migrate(r.root)
        self.assertTrue(out["ok"], out)
        self.assertTrue(out["archived"])
        self.assertFalse(os.path.isfile(r.yaml_path()))
        self.assertTrue(os.path.isfile(r.yaml_path() + ".archive"))

    def test_migrate_yaml_only(self):
        r = self.mk()
        shutil.copy(os.path.join(FIXTURES, "legacy.yml"), r.yaml_path())
        out, code = phase.cmd_migrate(r.root)
        self.assertTrue(out["ok"], out)
        self.assertTrue(out["migrated"])
        self.assertFalse(os.path.isfile(r.yaml_path()))
        state = r.read_state()
        self.assertEqual(state["project"], "LegacyProj")
        self.assertEqual(state["review_reports"], ["review-execution:consolidated"])

    # -- round trip / ad-hoc keys --------------------------------------------

    def test_round_trip_keeps_adhoc_keys(self):
        r = self.mk("adhoc-keys.json", "dev-workflow-state.json")
        out, code = phase.cmd_note(r.root, "checked in")
        self.assertTrue(out["ok"], out)
        after = r.read_state()
        self.assertEqual(after["deploy_notes"], "TestFlight build 42 sent")
        self.assertEqual(after["blocked_by"], "waiting on Apple review")

    # -- broken JSON ----------------------------------------------------------

    def test_broken_json_refused_no_write(self):
        r = self.mk("broken.json", "dev-workflow-state.json")
        before = _fixture("broken.json")
        out, code = phase.cmd_step(r.root, "test")
        self.assertFalse(out["ok"])
        self.assertEqual(code, 3)
        with open(r.state_path(), "r", encoding="utf-8") as f:
            after = f.read()
        self.assertEqual(before, after)

    def test_status_broken_json(self):
        r = self.mk("broken.json", "dev-workflow-state.json")
        out = phase.status(r.root)
        self.assertFalse(out["ok"])
        self.assertTrue(any("unparseable" in e for e in out["errors"]))

    # -- off-enum step ----------------------------------------------------------

    def test_offenum_step_named_and_repaired(self):
        r = self.mk("offenum.json", "dev-workflow-state.json")
        out = phase.status(r.root)
        self.assertFalse(out["ok"])
        self.assertTrue(any("verified-iphone" in e for e in out["errors"]))
        out, code = phase.cmd_step(r.root, "review")
        self.assertFalse(out["ok"])  # no --reason yet
        out, code = phase.cmd_step(r.root, "review", reason="x")
        self.assertTrue(out["ok"], out)
        self.assertEqual(r.read_state()["phase_step"], "review")

    # -- legacy aliases -----------------------------------------------------

    def test_legacy_alias_spec_maps_to_review(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        state = r.read_state()
        state["phase_step"] = "spec"
        with open(r.state_path(), "w") as f:
            json.dump(state, f)
        out = phase.status(r.root)
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["step"], "review")
        self.assertTrue(out["legacy_alias_applied"])

    def test_legacy_alias_build_test_maps_to_test(self):
        r = self.mk("legacy.yml", "dev-workflow-state.yml")
        out = phase.status(r.root)
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["step"], "test")
        self.assertTrue(out["legacy_alias_applied"])

    # -- YAML parsing with / without PyYAML ----------------------------------

    def test_yaml_migration_with_pyyaml(self):
        r = self.mk()
        shutil.copy(os.path.join(FIXTURES, "legacy.yml"), r.yaml_path())
        with mock.patch.object(phase, "_flat_yaml_parse", wraps=phase._flat_yaml_parse) as spy:
            state = phase._parse_yaml(r.yaml_path())
            spy.assert_not_called()  # PyYAML path taken, fallback never invoked
        self.assertEqual(state["review_reports"], ["review-execution:consolidated"])
        self.assertEqual(state["current_phase"], 1)

    def test_yaml_migration_without_pyyaml(self):
        r = self.mk()
        shutil.copy(os.path.join(FIXTURES, "legacy.yml"), r.yaml_path())
        with mock.patch.dict(sys.modules, {"yaml": None}):  # forces `import yaml` -> ImportError
            with mock.patch.object(phase, "_flat_yaml_parse", wraps=phase._flat_yaml_parse) as spy:
                state = phase._parse_yaml(r.yaml_path())
                spy.assert_called_once()  # proves the fallback branch actually ran
        self.assertEqual(state["review_reports"], ["review-execution:consolidated"])
        self.assertEqual(state["current_phase"], 1)
        self.assertEqual(state["phase_step"], "build-test")

    def test_migrate_without_pyyaml_via_cmd(self):
        r = self.mk()
        shutil.copy(os.path.join(FIXTURES, "legacy.yml"), r.yaml_path())
        with mock.patch.dict(sys.modules, {"yaml": None}):
            out, code = phase.cmd_migrate(r.root)
        self.assertTrue(out["ok"], out)
        self.assertTrue(out["migrated"])
        state = r.read_state()
        self.assertEqual(state["project"], "LegacyProj")
        self.assertEqual(state["review_reports"], ["review-execution:consolidated"])

    # -- set --------------------------------------------------------------

    def test_set_unknown_key_refused(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        out, code = phase.cmd_set(r.root, ["some_random_key=1"])
        self.assertFalse(out["ok"])
        self.assertEqual(code, 3)
        self.assertTrue(any("use `note`" in e for e in out["errors"]))

    def test_set_owned_key(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        out, code = phase.cmd_set(r.root, ["gaps_remaining=2"])
        self.assertTrue(out["ok"], out)
        self.assertEqual(r.read_state()["gaps_remaining"], 2)

    # -- hook output ----------------------------------------------------------

    def test_hook_line_in_progress(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        line = phase.hook_line(r.root)
        self.assertIn("Phase 2", line)
        self.assertIn("in progress", line)
        self.assertIn("review", line)

    def test_hook_line_done_is_none(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        state = r.read_state()
        state["phase_step"] = "done"
        with open(r.state_path(), "w") as f:
            json.dump(state, f)
        self.assertIsNone(phase.hook_line(r.root))

    def test_hook_line_broken(self):
        r = self.mk("broken.json", "dev-workflow-state.json")
        line = phase.hook_line(r.root)
        self.assertIn("state file unreadable", line)

    def test_hook_line_offenum(self):
        r = self.mk("offenum.json", "dev-workflow-state.json")
        line = phase.hook_line(r.root)
        self.assertIn("verified-iphone", line)

    # -- atomic write ----------------------------------------------------------

    def test_atomic_write_leaves_no_temp_file(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        phase.cmd_note(r.root, "note")
        leftovers = [f for f in os.listdir(os.path.join(r.root, ".claude")) if f.endswith(".tmp")]
        self.assertEqual(leftovers, [])

    def test_atomic_write_removes_temp_file_on_exception(self):
        r = self.mk()

        class Unserializable:
            pass

        with self.assertRaises(TypeError):
            phase._write(r.root, {"phase_step": "plan", "bad": Unserializable()})
        leftovers = [f for f in os.listdir(os.path.join(r.root, ".claude")) if f.endswith(".tmp")]
        self.assertEqual(leftovers, [])
        self.assertFalse(os.path.isfile(r.state_path()))  # never replaced the real file

    def test_unquoted_yaml_date_does_not_crash_write(self):
        r = self.mk()
        with open(r.yaml_path(), "w") as f:
            f.write(
                "project: X\ncurrent_phase: 1\nphase_name: P\nphase_step: review\n"
                "dev_guide: docs/x.md\nplan_file: null\nreview_reports: []\n"
                "test_report: null\ngaps_remaining: 0\n"
                'last_updated: "2026-05-14T13:01:09Z"\n'
                "some_ad_hoc_date: 2026-05-14\n"  # unquoted -> PyYAML parses as datetime.date
            )
        out, code = phase.cmd_migrate(r.root)
        self.assertTrue(out["ok"], out)
        after = r.read_state()
        self.assertEqual(after["some_ad_hoc_date"], "2026-05-14")

    def test_append_note_preserves_non_list_notes_value(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        state = r.read_state()
        state["notes"] = "legacy free-text note"
        with open(r.state_path(), "w") as f:
            json.dump(state, f)
        out, code = phase.cmd_note(r.root, "new note")
        self.assertTrue(out["ok"], out)
        after = r.read_state()
        self.assertEqual(after["notes"][0], "legacy free-text note")
        self.assertEqual(after["notes"][1]["text"], "new note")


class DevGuideTests(unittest.TestCase):
    """Task 2: guide / phases / locate / check-off / scope-mode."""

    def setUp(self):
        self.roots = []

    def tearDown(self):
        for r in self.roots:
            r.close()

    def mk_root(self):
        r = TmpRoot()
        self.roots.append(r)
        return r

    def _fixture_path(self, name):
        return os.path.join(FIXTURES, name)

    # -- guide --------------------------------------------------------------

    def test_guide_single_candidate(self):
        r = self.mk_root()
        plans = os.path.join(r.root, "docs", "06-plans")
        os.makedirs(plans)
        shutil.copy(self._fixture_path("dev-guide.md"), os.path.join(plans, "x-dev-guide.md"))
        out, code = phase.cmd_guide(r.root)
        self.assertTrue(out["ok"], out)
        self.assertEqual(code, 0)
        self.assertTrue(out["path"].endswith("x-dev-guide.md"))

    def test_guide_multiple_prefers_current_true(self):
        r = self.mk_root()
        plans = os.path.join(r.root, "docs", "06-plans")
        os.makedirs(plans)
        shutil.copy(self._fixture_path("dev-guide.md"), os.path.join(plans, "a-dev-guide.md"))
        # A second dev-guide without current:true
        with open(os.path.join(plans, "b-dev-guide.md"), "w", encoding="utf-8") as f:
            f.write("---\ntype: dev-guide\n---\n\n# B\n")
        out, code = phase.cmd_guide(r.root)
        self.assertTrue(out["ok"], out)
        self.assertTrue(out["path"].endswith("a-dev-guide.md"))

    def test_guide_multiple_none_marked_asks(self):
        r = self.mk_root()
        plans = os.path.join(r.root, "docs", "06-plans")
        os.makedirs(plans)
        for name in ("a-dev-guide.md", "b-dev-guide.md"):
            with open(os.path.join(plans, name), "w", encoding="utf-8") as f:
                f.write("---\ntype: dev-guide\n---\n\n# X\n")
        out, code = phase.cmd_guide(r.root)
        self.assertFalse(out["ok"])
        self.assertEqual(code, 3)
        self.assertEqual(len(out["candidates"]), 2)

    def test_guide_none_found(self):
        r = self.mk_root()
        out, code = phase.cmd_guide(r.root)
        self.assertFalse(out["ok"])
        self.assertEqual(code, 3)

    # -- phases ---------------------------------------------------------------

    def test_phases_counts(self):
        out = phase.phases(self._fixture_path("dev-guide.md"))
        self.assertTrue(out["ok"], out)
        ps = {p["n"]: p for p in out["phases"]}
        self.assertEqual(ps[1]["total"], 2)
        self.assertEqual(ps[1]["checked"], 2)
        self.assertTrue(ps[1]["complete"])
        self.assertEqual(ps[2]["total"], 3)
        self.assertEqual(ps[2]["checked"], 1)
        self.assertFalse(ps[2]["complete"])
        self.assertEqual(ps[3]["total"], 2)
        self.assertEqual(ps[3]["checked"], 0)
        self.assertFalse(ps[3]["complete"])

    def test_phases_zh_label(self):
        out = phase.phases(self._fixture_path("dev-guide-zh.md"))
        self.assertTrue(out["ok"], out)
        p = out["phases"][0]
        self.assertEqual(p["total"], 2)
        self.assertEqual(p["checked"], 1)

    def test_phases_unparseable(self):
        out = phase.phases(self._fixture_path("dev-guide-unparseable.md"))
        self.assertFalse(out["ok"])
        self.assertIn("unparseable_reason", out)

    def test_phases_cashie_real_dev_guide(self):
        cashie = "/Users/norvyn/Code/Projects/Cashie/docs/06-plans/2026-09-12-multi-currency-dev-guide.md"
        if not os.path.isfile(cashie):
            self.skipTest("Cashie project not present on this machine")
        out = phase.phases(cashie)
        self.assertTrue(out["ok"], out)
        counts = [p["total"] for p in out["phases"]]
        self.assertEqual(counts, [4, 3, 5, 2, 3, 2])

    # -- locate -----------------------------------------------------------

    def test_locate_first_incomplete(self):
        out, code = phase.cmd_locate(self._fixture_path("dev-guide.md"))
        self.assertTrue(out["ok"], out)
        self.assertEqual(code, 0)
        self.assertEqual(out["phase"]["n"], 2)
        self.assertFalse(out["all_complete"])

    def test_locate_all_complete(self):
        r = self.mk_root()
        dest = os.path.join(r.root, "dev-guide.md")
        with open(dest, "w", encoding="utf-8") as f:
            f.write("## Phase 1: A\n**Acceptance criteria:**\n- [x] one\n")
        out, code = phase.cmd_locate(dest)
        self.assertTrue(out["ok"], out)
        self.assertIsNone(out["phase"])
        self.assertTrue(out["all_complete"])

    # -- check-off -------------------------------------------------------

    def test_check_off_ticks_only_target_phase(self):
        r = self.mk_root()
        dest = os.path.join(r.root, "dev-guide.md")
        shutil.copy(self._fixture_path("dev-guide.md"), dest)
        with open(dest, "r", encoding="utf-8") as f:
            before = f.read()
        out, code = phase.cmd_check_off(dest, 2, date="2026-09-24")
        self.assertTrue(out["ok"], out)
        self.assertEqual(code, 0)
        self.assertEqual(out["ticked"], 2)  # phase 2 had 2 unchecked criteria
        self.assertTrue(out["status_inserted"])
        with open(dest, "r", encoding="utf-8") as f:
            after = f.read()
        before_lines = before.split("\n")
        after_lines = after.split("\n")
        # Byte-diff: only checkbox chars inside phase 2's block change, plus one
        # inserted status line. Compare via difflib to isolate the changed lines.
        import difflib
        diff = list(difflib.unified_diff(before_lines, after_lines, lineterm=""))
        changed_from = [l[1:] for l in diff if l.startswith("-") and not l.startswith("---")]
        changed_to = [l[1:] for l in diff if l.startswith("+") and not l.startswith("+++")]
        for line in changed_from:
            self.assertIn("- [ ]", line)
        for line in changed_to:
            self.assertTrue("- [x]" in line or line.startswith("**Status:**"))
        # Phase 1 and Phase 3 criteria untouched
        self.assertIn("- [x] criterion one\n- [x] criterion two", after)  # phase 1
        self.assertIn("- [ ] criterion one\n- [ ] criterion two", after)  # phase 3

    def test_check_off_no_reinsert_when_status_present(self):
        r = self.mk_root()
        dest = os.path.join(r.root, "dev-guide.md")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(
                "## Phase 1: A\n**Status:** ✅ Completed — 2026-01-01\n"
                "**Acceptance criteria:**\n- [ ] one\n"
            )
        out, code = phase.cmd_check_off(dest, 1)
        self.assertTrue(out["ok"], out)
        self.assertFalse(out["status_inserted"])
        with open(dest, "r", encoding="utf-8") as f:
            after = f.read()
        self.assertEqual(after.count("**Status:**"), 1)

    def test_check_off_all_phases_complete_flag(self):
        r = self.mk_root()
        dest = os.path.join(r.root, "dev-guide.md")
        with open(dest, "w", encoding="utf-8") as f:
            f.write("## Phase 1: A\n**Acceptance criteria:**\n- [ ] one\n")
        out, code = phase.cmd_check_off(dest, 1)
        self.assertTrue(out["ok"], out)
        self.assertTrue(out["all_phases_complete"])

    def test_check_off_phase_not_found(self):
        out, code = phase.cmd_check_off(self._fixture_path("dev-guide.md"), 99)
        self.assertFalse(out["ok"])
        self.assertEqual(code, 3)

    # -- scope-mode -------------------------------------------------------

    def test_scope_mode_lightweight_within_60_min(self):
        out, code = phase.cmd_scope_mode(
            self._fixture_path("dev-guide.md"), now="2026-09-24T10:30:00")
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["mode"], "lightweight")

    def test_scope_mode_full_after_60_min(self):
        out, code = phase.cmd_scope_mode(
            self._fixture_path("dev-guide.md"), now="2026-09-24T12:00:00")
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["mode"], "full")

    def test_scope_mode_no_confirmed_at_is_full(self):
        r = self.mk_root()
        dest = os.path.join(r.root, "dev-guide.md")
        with open(dest, "w", encoding="utf-8") as f:
            f.write("---\ntype: dev-guide\n---\n\n## Phase 1: A\n")
        out, code = phase.cmd_scope_mode(dest)
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["mode"], "full")


class DevGuideCliTests(unittest.TestCase):
    """CLI wiring for the Task 2 subcommands."""

    def test_phases_cli(self):
        out = subprocess.run(
            [sys.executable, os.path.join(HERE, "phase.py"), "phases",
             "--dev-guide", os.path.join(FIXTURES, "dev-guide.md")],
            capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        parsed = json.loads(out.stdout)
        self.assertTrue(parsed["ok"])
        self.assertEqual(len(parsed["phases"]), 3)

    def test_locate_cli(self):
        out = subprocess.run(
            [sys.executable, os.path.join(HERE, "phase.py"), "locate",
             "--dev-guide", os.path.join(FIXTURES, "dev-guide.md")],
            capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        parsed = json.loads(out.stdout)
        self.assertEqual(parsed["phase"]["n"], 2)

    def test_guide_cli(self):
        with tempfile.TemporaryDirectory() as root:
            plans = os.path.join(root, "docs", "06-plans")
            os.makedirs(plans)
            shutil.copy(os.path.join(FIXTURES, "dev-guide.md"), os.path.join(plans, "x-dev-guide.md"))
            out = subprocess.run(
                [sys.executable, os.path.join(HERE, "phase.py"), "--root", root, "guide"],
                capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            parsed = json.loads(out.stdout)
            self.assertTrue(parsed["path"].endswith("x-dev-guide.md"))

    def test_check_off_cli(self):
        with tempfile.TemporaryDirectory() as root:
            dest = os.path.join(root, "dev-guide.md")
            shutil.copy(os.path.join(FIXTURES, "dev-guide.md"), dest)
            out = subprocess.run(
                [sys.executable, os.path.join(HERE, "phase.py"), "check-off",
                 "--dev-guide", dest, "--phase", "3", "--date", "2026-09-24"],
                capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            parsed = json.loads(out.stdout)
            self.assertTrue(parsed["ok"])
            self.assertEqual(parsed["ticked"], 2)

    def test_scope_mode_cli(self):
        out = subprocess.run(
            [sys.executable, os.path.join(HERE, "phase.py"), "scope-mode",
             "--dev-guide", os.path.join(FIXTURES, "dev-guide.md"),
             "--now", "2026-09-24T10:15:00"],
            capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        parsed = json.loads(out.stdout)
        self.assertEqual(parsed["mode"], "lightweight")


class CliTests(unittest.TestCase):
    """A couple of subprocess-level checks that the CLI wiring matches the module API."""

    def test_status_cli_exit_code_and_json(self):
        r = TmpRoot("valid.json", "dev-workflow-state.json")
        try:
            out = subprocess.run([sys.executable, os.path.join(HERE, "phase.py"),
                                  "--root", r.root, "status"], capture_output=True, text=True)
            self.assertEqual(out.returncode, 0)
            parsed = json.loads(out.stdout)
            self.assertTrue(parsed["ok"])
            self.assertEqual(parsed["step"], "review")
        finally:
            r.close()

    def test_broken_cli_exit_3_never_traceback(self):
        r = TmpRoot("broken.json", "dev-workflow-state.json")
        try:
            out = subprocess.run([sys.executable, os.path.join(HERE, "phase.py"),
                                  "--root", r.root, "status"], capture_output=True, text=True)
            self.assertEqual(out.returncode, 3)
            self.assertEqual(out.stderr, "")
            json.loads(out.stdout)  # must still be valid JSON
        finally:
            r.close()

    def test_root_after_subcommand_plan_form(self):
        """The plan's own real-path verify uses `status --root <path>` (--root AFTER
        the subcommand). Run from HERE (not the tmp root) so a silent fallback to cwd
        shows up as exists:false instead of accidentally reading the right file."""
        r = TmpRoot("valid.json", "dev-workflow-state.json")
        try:
            out = subprocess.run([sys.executable, "phase.py", "status", "--root", r.root],
                                  capture_output=True, text=True, cwd=HERE)
            self.assertEqual(out.returncode, 0, out.stderr)
            parsed = json.loads(out.stdout)
            self.assertTrue(parsed["ok"])
            self.assertEqual(parsed["step"], "review")
        finally:
            r.close()

    def test_root_after_subcommand_hook_form(self):
        """Task 5's exact hook invocation: `status --hook --root .` (called with --root
        as the last argument, after --hook)."""
        r = TmpRoot("valid.json", "dev-workflow-state.json")
        try:
            out = subprocess.run([sys.executable, "phase.py", "status", "--hook", "--root", r.root],
                                  capture_output=True, text=True, cwd=HERE)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertIn("Phase 2", out.stdout)
            self.assertIn("in progress", out.stdout)
        finally:
            r.close()

    def test_root_before_subcommand_still_works(self):
        r = TmpRoot("valid.json", "dev-workflow-state.json")
        try:
            out = subprocess.run([sys.executable, "phase.py", "--root", r.root, "status"],
                                  capture_output=True, text=True, cwd=HERE)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(json.loads(out.stdout)["step"], "review")
        finally:
            r.close()

    def test_unquoted_yaml_date_status_via_cli_does_not_crash(self):
        r = TmpRoot()
        try:
            with open(r.yaml_path(), "w") as f:
                f.write(
                    "project: X\ncurrent_phase: 1\nphase_name: P\nphase_step: review\n"
                    "dev_guide: docs/x.md\nplan_file: null\nreview_reports: []\n"
                    "test_report: null\ngaps_remaining: 0\n"
                    'last_updated: "2026-05-14T13:01:09Z"\n'
                    "some_ad_hoc_date: 2026-05-14\n"
                )
            out = subprocess.run([sys.executable, "phase.py", "status", "--root", r.root],
                                  capture_output=True, text=True, cwd=HERE)
            self.assertEqual(out.returncode, 0, out.stderr)
            parsed = json.loads(out.stdout)
            self.assertTrue(parsed["ok"], parsed)
            self.assertNotIn("internal error", out.stdout)
        finally:
            r.close()


class PlanFactsTests(unittest.TestCase):
    """Task 3: plan-facts."""

    def _fixture_path(self, name):
        return os.path.join(FIXTURES, name)

    def test_small_plan_auto_approve(self):
        out, code = phase.cmd_plan_facts(self._fixture_path("plan-small.md"))
        self.assertTrue(out["ok"], out)
        self.assertEqual(code, 0)
        self.assertEqual(out["tasks"], 3)
        self.assertTrue(out["fast"])
        self.assertTrue(out["auto_approve"])
        self.assertTrue(out["lint"]["ok"])

    def test_design_doc_blocks_auto_approve(self):
        out, code = phase.cmd_plan_facts(
            self._fixture_path("plan-small.md"), design_doc=self._fixture_path("design-ux.md"))
        self.assertTrue(out["ok"], out)
        self.assertFalse(out["auto_approve"])
        self.assertTrue(out["fast"])  # still fast — only auto_approve is blocked

    def test_crystal_blocks_auto_approve(self):
        out, code = phase.cmd_plan_facts(self._fixture_path("plan-small.md"), crystal="docs/11-crystals/x-crystal.md")
        self.assertFalse(out["auto_approve"])

    def test_design_doc_literal_none_does_not_block(self):
        out, code = phase.cmd_plan_facts(self._fixture_path("plan-small.md"), design_doc="none", crystal="none")
        self.assertTrue(out["auto_approve"])

    def test_plan_facts_missing_file(self):
        out, code = phase.cmd_plan_facts("/no/such/plan.md")
        self.assertFalse(out["ok"])
        self.assertEqual(code, 3)

    def test_real_plan_own_task_count(self):
        this_plan = os.path.join(HERE, "..", "..", "..", "..",
                                  "docs", "06-plans", "2026-09-24-run-phase-state-script-plan.md")
        if not os.path.isfile(this_plan):
            self.skipTest("plan file not present (unexpected outside this repo checkout)")
        out, code = phase.cmd_plan_facts(this_plan)
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["tasks"], 7)
        self.assertFalse(out["fast"])  # 7 >= 5
        self.assertFalse(out["auto_approve"])  # 7 > 3


class UxMapTests(unittest.TestCase):
    """Task 3: ux-map."""

    def _fixture_path(self, name):
        return os.path.join(FIXTURES, name)

    def test_triggered_and_rows_mapped(self):
        out, code = phase.cmd_ux_map(self._fixture_path("plan-ux.md"), self._fixture_path("design-ux.md"))
        self.assertTrue(out["ok"], out)
        self.assertTrue(out["triggered"])
        rows = {r["ux_id"]: r for r in out["rows"]}
        self.assertEqual(rows["UX-001"]["tasks"], ["Task 1"])
        self.assertTrue(rows["UX-001"]["mapped"])
        self.assertIn("Sign In", rows["UX-001"]["user_interaction"])
        self.assertEqual(rows["UX-002"]["tasks"], ["Task 2"])
        self.assertEqual(rows["UX-003"]["tasks"], ["Task 2"])

    def test_unmapped_ui_task_flagged(self):
        out, code = phase.cmd_ux_map(self._fixture_path("plan-ux.md"), self._fixture_path("design-ux.md"))
        self.assertEqual(out["unmapped_ui_tasks"], ["Task 3"])

    def test_header_only_table_not_triggered(self):
        r = tempfile.TemporaryDirectory()
        try:
            dd = os.path.join(r.name, "design.md")
            with open(dd, "w", encoding="utf-8") as f:
                f.write("## UX Assertions\n\n| ID | Assertion | Verification |\n|----|-----------|---------------|\n")
            out, code = phase.cmd_ux_map(self._fixture_path("plan-ux.md"), dd)
            self.assertTrue(out["ok"], out)
            self.assertFalse(out["triggered"])
            self.assertEqual(out["rows"], [])
        finally:
            r.cleanup()

    def test_no_ux_assertions_heading_not_triggered(self):
        r = tempfile.TemporaryDirectory()
        try:
            dd = os.path.join(r.name, "design.md")
            with open(dd, "w", encoding="utf-8") as f:
                f.write("# Design Doc\n\nNo UX section here.\n")
            out, code = phase.cmd_ux_map(self._fixture_path("plan-ux.md"), dd)
            self.assertFalse(out["triggered"])
        finally:
            r.cleanup()

    def test_missing_files(self):
        out, code = phase.cmd_ux_map("/no/such/plan.md", self._fixture_path("design-ux.md"))
        self.assertFalse(out["ok"])
        self.assertEqual(code, 3)


class VisualFactsTests(unittest.TestCase):
    """Task 3: visual-facts."""

    def setUp(self):
        # A real /tmp/design-screenshot-*.png on this machine would otherwise win
        # path (a) and make these tests depend on machine state.
        patcher = mock.patch.object(phase, "DESIGN_SCREENSHOT_GLOB", "/no/such/dir/design-screenshot-*.png")
        patcher.start()
        self.addCleanup(patcher.stop)

    def _fixture_path(self, name):
        return os.path.join(FIXTURES, name)

    def test_card_and_view_suffix_detected_store_excluded(self):
        out, code = phase.cmd_visual_facts(self._fixture_path("plan-swift.md"))
        self.assertTrue(out["ok"], out)
        self.assertIn("HomeCard.swift", out["views"])
        self.assertIn("ProfileView.swift", out["views"])
        self.assertNotIn("Store.swift", out["views"])

    def test_apple_dev_missing_via_env_override(self):
        with mock.patch.dict(os.environ, {"PHASE_PLUGINS_CACHE": "/no/such/cache-dir"}):
            out, code = phase.cmd_visual_facts(self._fixture_path("plan-swift.md"))
        self.assertFalse(out["apple_dev_installed"])
        self.assertEqual(out["skip_reason"], "apple-dev not installed")

    def test_apple_dev_present_via_env_override(self):
        r = tempfile.TemporaryDirectory()
        try:
            os.makedirs(os.path.join(r.name, "some-plugin", "apple-dev"))
            with mock.patch.dict(os.environ, {"PHASE_PLUGINS_CACHE": r.name}):
                out, code = phase.cmd_visual_facts(self._fixture_path("plan-swift.md"))
            self.assertTrue(out["apple_dev_installed"])
        finally:
            r.cleanup()

    def test_non_ui_phase_skip_reason(self):
        r = tempfile.TemporaryDirectory()
        try:
            plan = os.path.join(r.name, "plan.md")
            with open(plan, "w", encoding="utf-8") as f:
                f.write("### Task 1: Backend only\n**Files:**\n- Modify: `server.py`\n\n"
                         "**Verify:**\nRun: `true`\nExpected: ok\n")
            with mock.patch.object(phase, "_apple_dev_installed", return_value=True):
                out, code = phase.cmd_visual_facts(plan, root=r.name)
            self.assertEqual(out["views"], [])
            self.assertEqual(out["skip_reason"], "non-UI phase")
        finally:
            r.cleanup()

    def test_design_image_resolved_from_design_analysis(self):
        r = tempfile.TemporaryDirectory()
        try:
            plans = os.path.join(r.name, "docs", "06-plans")
            os.makedirs(plans)
            img = os.path.join(plans, "shot.png")
            open(img, "wb").close()
            da = os.path.join(plans, "x-design-analysis.md")
            with open(da, "w", encoding="utf-8") as f:
                f.write("See ![shot](shot.png) for reference.\n")
            plan = os.path.join(r.name, "plan.md")
            shutil.copy(self._fixture_path("plan-swift.md"), plan)
            with mock.patch.object(phase, "_apple_dev_installed", return_value=True):
                out, code = phase.cmd_visual_facts(plan, root=r.name)
            self.assertEqual(out["design_image"], img)
            self.assertEqual(out["skip_reason"], "no #Preview blocks")
        finally:
            r.cleanup()

    def test_preview_views_and_ok_when_all_gates_pass(self):
        r = tempfile.TemporaryDirectory()
        try:
            plans = os.path.join(r.name, "docs", "06-plans")
            os.makedirs(plans)
            img = os.path.join(plans, "shot.png")
            open(img, "wb").close()
            da = os.path.join(plans, "x-design-analysis.md")
            with open(da, "w", encoding="utf-8") as f:
                f.write("See ![shot](shot.png) for reference.\n")
            with open(os.path.join(r.name, "HomeCard.swift"), "w", encoding="utf-8") as f:
                f.write("struct HomeCard: View {}\n#Preview { HomeCard() }\n")
            plan = os.path.join(r.name, "plan.md")
            with open(plan, "w", encoding="utf-8") as f:
                f.write("### Task 1: Home\n**Files:**\n- Create: `HomeCard.swift`\n\n"
                         "**Verify:**\nRun: `true`\nExpected: ok\n")
            with mock.patch.object(phase, "_apple_dev_installed", return_value=True):
                out, code = phase.cmd_visual_facts(plan, root=r.name)
            self.assertEqual(out["preview_views"], ["HomeCard.swift"])
            self.assertIsNone(out["skip_reason"])
        finally:
            r.cleanup()

    def test_missing_plan_file(self):
        out, code = phase.cmd_visual_facts("/no/such/plan.md")
        self.assertFalse(out["ok"])
        self.assertEqual(code, 3)


class CompleteGateTests(unittest.TestCase):
    """Task 3: complete-gate CLI wrapper around the Task 1 gate."""

    def setUp(self):
        self.roots = []

    def tearDown(self):
        for r in self.roots:
            r.close()

    def mk(self, fixture=None, as_name=None):
        r = TmpRoot(fixture, as_name)
        self.roots.append(r)
        return r

    def test_ok_when_gate_passes(self):
        r = self.mk("valid.json", "dev-workflow-state.json")  # has review_reports
        out, code = phase.cmd_complete_gate(r.root)
        self.assertEqual(out, {"ok": True})
        self.assertEqual(code, 0)

    def test_no_reports_block(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        state = r.read_state()
        state.update({"review_reports": [], "test_report": None})
        with open(r.state_path(), "w") as f:
            json.dump(state, f)
        out, code = phase.cmd_complete_gate(r.root)
        self.assertFalse(out["ok"])
        self.assertEqual(out["block"], "no-reports")
        self.assertEqual(code, 3)

    def test_gaps_block(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        state = r.read_state()
        state.update({
            "review_reports": ["review-execution:consolidated"],
            "review_findings": {"must_fix": 1, "nice_to_have": 0},
            "gaps_remaining": 2,
        })
        with open(r.state_path(), "w") as f:
            json.dump(state, f)
        out, code = phase.cmd_complete_gate(r.root)
        self.assertFalse(out["ok"])
        self.assertEqual(out["block"], "gaps")

    def test_no_state_file(self):
        r = self.mk()
        out, code = phase.cmd_complete_gate(r.root)
        self.assertFalse(out["ok"])
        self.assertEqual(code, 3)


class Task3CliTests(unittest.TestCase):
    """CLI wiring for the Task 3 subcommands."""

    def test_plan_facts_cli(self):
        out = subprocess.run(
            [sys.executable, os.path.join(HERE, "phase.py"), "plan-facts",
             "--plan", os.path.join(FIXTURES, "plan-small.md")],
            capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        parsed = json.loads(out.stdout)
        self.assertEqual(parsed["tasks"], 3)
        self.assertTrue(parsed["auto_approve"])

    def test_ux_map_cli(self):
        out = subprocess.run(
            [sys.executable, os.path.join(HERE, "phase.py"), "ux-map",
             "--plan", os.path.join(FIXTURES, "plan-ux.md"),
             "--design-doc", os.path.join(FIXTURES, "design-ux.md")],
            capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        parsed = json.loads(out.stdout)
        self.assertTrue(parsed["triggered"])

    def test_visual_facts_cli(self):
        out = subprocess.run(
            [sys.executable, os.path.join(HERE, "phase.py"), "visual-facts",
             "--plan", os.path.join(FIXTURES, "plan-swift.md")],
            capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stderr)
        parsed = json.loads(out.stdout)
        self.assertIn("HomeCard.swift", parsed["views"])

    def test_complete_gate_cli(self):
        r = TmpRoot("valid.json", "dev-workflow-state.json")
        try:
            out = subprocess.run(
                [sys.executable, os.path.join(HERE, "phase.py"), "--root", r.root, "complete-gate"],
                capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            parsed = json.loads(out.stdout)
            self.assertTrue(parsed["ok"])
        finally:
            r.close()


class DuplicateKeyTests(unittest.TestCase):
    def test_duplicate_keys_block_writes_and_are_named(self):
        import tempfile, json as _j
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, ".claude"))
            with open(os.path.join(root, ".claude", "dev-workflow-state.json"), "w") as f:
                f.write('{"phase_step": "review", "current_phase": 2, "review_reports": [], "test_report": null, "test_report": "x"}')
            res = phase.load(root)
            self.assertFalse(res["ok"])
            self.assertIn("duplicate keys: test_report", res["errors"][0])
            self.assertIn("duplicate keys", phase.hook_line(root))


# ===========================================================================
# Review fixes (items numbered as in the review; each test names its item).


class _RootCase(unittest.TestCase):
    def setUp(self):
        self.roots = []

    def tearDown(self):
        for r in self.roots:
            r.close()

    def mk(self, fixture=None, as_name=None):
        r = TmpRoot(fixture, as_name)
        self.roots.append(r)
        return r

    def write_raw(self, r, text, name="dev-workflow-state.json", binary=False):
        path = os.path.join(r.root, ".claude", name)
        with open(path, "wb" if binary else "w", **({} if binary else {"encoding": "utf-8"})) as f:
            f.write(text)
        return path

    def write_state(self, r, state):
        with open(r.state_path(), "w", encoding="utf-8") as f:
            json.dump(state, f)

    def valid_state(self, **over):
        with open(os.path.join(FIXTURES, "valid.json"), "r", encoding="utf-8") as f:
            st = json.load(f)
        st.update(over)
        return st

    def cli(self, *args):
        return subprocess.run([sys.executable, PHASE_SCRIPT, *args], capture_output=True, text=True)


class Item1NoCriteriaTests(_RootCase):
    def _guide(self, text):
        r = self.mk()
        path = os.path.join(r.root, "dev-guide.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return path

    def test_check_off_no_criteria_phase_then_locate_moves_on(self):
        g = self._guide("## Phase 1: Spike\n**Goal:** explore\n\n## Phase 2: Build\n"
                        "**Acceptance criteria:**\n- [ ] one\n")
        before = phase.phases(g)["phases"][0]
        self.assertTrue(before.get("no_criteria"))
        self.assertFalse(before["complete"])
        out, code = phase.cmd_check_off(g, 1, date="2026-09-24")
        self.assertTrue(out["ok"], out)
        self.assertFalse(out["all_phases_complete"])
        loc, _ = phase.cmd_locate(g)
        self.assertEqual(loc["phase"]["n"], 2)  # used to stay stuck on phase 1 forever
        out, code = phase.cmd_check_off(g, 2, date="2026-09-24")
        self.assertTrue(out["all_phases_complete"], out)
        loc, _ = phase.cmd_locate(g)
        self.assertTrue(loc["all_complete"])

    def test_single_no_criteria_phase_all_complete(self):
        g = self._guide("## Phase 1: Only\n**Goal:** x\n")
        out, code = phase.cmd_check_off(g, 1, date="2026-09-24")
        self.assertTrue(out["all_phases_complete"], out)

    def test_status_line_without_completed_mark_is_not_complete(self):
        g = self._guide("## Phase 1: A\n**Status:** 🟡 In Progress\n**Goal:** x\n")
        p = phase.phases(g)["phases"][0]
        self.assertTrue(p["no_criteria"])
        self.assertFalse(p["complete"])

    def test_label_case_insensitive_and_fullwidth_colon(self):
        g = self._guide("## Phase 1: A\n**Acceptance Criteria:**\n- [x] one\n- [ ] two\n\n"
                        "## Phase 2: B\n**验收标准：**\n- [x] 一\n\n"
                        "## Phase 3: C\n**验收标准:**\n- [ ] 一\n")
        ps = phase.phases(g)["phases"]
        self.assertEqual([(p["total"], p["checked"]) for p in ps], [(2, 1), (1, 1), (1, 0)])
        self.assertNotIn("no_criteria", ps[0])


class Item2QuarantineTests(_RootCase):
    def _assert_quarantine_then_init(self, r, expect_ext=".json"):
        line = phase.hook_line(r.root)
        self.assertIn("phase.py quarantine", line)
        out, code = phase.cmd_quarantine(r.root)
        self.assertTrue(out["ok"], out)
        self.assertTrue(out["quarantined"].endswith(expect_ext), out)
        self.assertTrue(os.path.isfile(out["quarantined"]))
        out, code = phase.cmd_init(r.root, 1, "Phase One", "docs/06-plans/x-dev-guide.md")
        self.assertTrue(out["ok"], out)
        self.assertEqual(code, 0)

    def test_duplicate_keys_quarantine_then_init(self):
        r = self.mk()
        self.write_raw(r, '{"phase_step": "review", "current_phase": 2, "test_report": null, "test_report": "x"}')
        self._assert_quarantine_then_init(r)

    def test_broken_yml_quarantine_then_init(self):
        r = self.mk()
        self.write_raw(r, "phase_step: [unclosed\ncurrent_phase: 1\n", name="dev-workflow-state.yml")
        self.assertFalse(phase.load(r.root)["ok"])
        self._assert_quarantine_then_init(r, expect_ext=".yml")
        self.assertFalse(os.path.isfile(r.yaml_path()))

    def test_non_utf8_quarantine(self):
        r = self.mk()
        self.write_raw(r, b'{"phase_step": "review", "x": "\xff\xfe"}', binary=True)
        self._assert_quarantine_then_init(r)

    def test_json_null_and_list_quarantine(self):
        for text in ("null", "[]"):
            r = self.mk()
            self.write_raw(r, text)
            self._assert_quarantine_then_init(r)

    def test_quarantine_twice_same_second_does_not_overwrite(self):
        r = self.mk()
        with mock.patch.object(phase.time, "strftime", return_value="20260924-120000"):
            self.write_raw(r, "{broken")
            first, _ = phase.cmd_quarantine(r.root)
            self.write_raw(r, "{broken again")
            second, _ = phase.cmd_quarantine(r.root)
        self.assertTrue(first["ok"] and second["ok"], (first, second))
        self.assertNotEqual(first["quarantined"], second["quarantined"])
        with open(first["quarantined"], encoding="utf-8") as f:
            self.assertEqual(f.read(), "{broken")

    def test_quarantine_no_state_file(self):
        r = self.mk()
        out, code = phase.cmd_quarantine(r.root)
        self.assertFalse(out["ok"])
        self.assertEqual(code, 3)
        self.assertIn("no state file", out["errors"][0])


class Item3FinishedSilentTests(_RootCase):
    SOCRATIC_YML = ('project: Socratic\ncurrent_phase: D\nphase_name: "LearningOrchestrator 拆分"\n'
                    "phase_step: done\ndev_guide: docs/06-plans/x-dev-guide.md\nreview_reports:\n"
                    '  - .claude/reviews/r.md\ngaps_remaining: 0\nlast_updated: "2026-03-13T00:10:00"\n')

    def test_socratic_done_yml_with_letter_phase_is_silent(self):
        r = self.mk()
        self.write_raw(r, self.SOCRATIC_YML, name="dev-workflow-state.yml")
        self.assertIsNone(phase.hook_line(r.root))

    def test_socratic_status_does_not_block(self):
        r = self.mk()
        self.write_raw(r, self.SOCRATIC_YML, name="dev-workflow-state.yml")
        out = phase.status(r.root)
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["step"], "done")
        self.assertIn("current_phase is not an int", out["warnings"])
        out, code = phase.cmd_init(r.root, 1, "Next", "docs/06-plans/x-dev-guide.md")
        self.assertTrue(out["ok"], out)  # a finished project can start the next phase

    def test_delphi_duplicate_keys_finalized_is_silent(self):
        r = self.mk()
        self.write_raw(r, '{"current_phase": 4, "phase_step": "finalized", "review_reports": ["a"], '
                          '"review_reports": [], "gaps_remaining": 0, "gaps_remaining": 0}')
        self.assertIsNone(phase.hook_line(r.root))
        self.assertFalse(phase.status(r.root)["ok"])  # still unwritable: a write would drop data

    def test_duplicate_keys_in_progress_still_named(self):
        r = self.mk()
        self.write_raw(r, '{"phase_step": "review", "test_report": null, "test_report": "x"}')
        self.assertIn("duplicate keys: test_report", phase.hook_line(r.root))


class Item4StatusExistsTests(_RootCase):
    def test_status_exists_true_for_valid(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        self.assertIs(phase.status(r.root)["exists"], True)

    def test_status_exists_true_for_broken_and_yaml(self):
        r = self.mk("broken.json", "dev-workflow-state.json")
        self.assertIs(phase.status(r.root)["exists"], True)
        r2 = self.mk("legacy.yml", "dev-workflow-state.yml")
        out = phase.status(r2.root)
        self.assertIs(out["exists"], True)
        self.assertEqual(out["source"], "yaml")

    def test_status_cli_exists_true(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        out = self.cli("status", "--root", r.root)
        self.assertIs(json.loads(out.stdout)["exists"], True)


class Item5WriteValidationTests(_RootCase):
    def test_set_current_phase_abc_refused_file_untouched(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        before = r.read_state()
        out, code = phase.cmd_set(r.root, ["current_phase=abc"])
        self.assertFalse(out["ok"], out)
        self.assertEqual(code, 3)
        self.assertIn("current_phase is not an int", out["errors"])
        self.assertEqual(r.read_state(), before)

    def test_set_free_text_key_is_not_json_coerced(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        out, code = phase.cmd_set(r.root, ["verification_report=true", "task_progress=3", "phase_name=[x]"])
        self.assertTrue(out["ok"], out)
        st = r.read_state()
        self.assertEqual(st["verification_report"], "true")
        self.assertEqual(st["task_progress"], "3")
        self.assertEqual(st["phase_name"], "[x]")

    def test_set_free_text_null_clears(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        out, code = phase.cmd_set(r.root, ["plan_file=null"])
        self.assertTrue(out["ok"], out)
        self.assertIsNone(r.read_state()["plan_file"])

    def test_set_typed_keys_json_parsed(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        out, code = phase.cmd_set(r.root, ['review_reports=["a"]', 'review_findings={"must_fix": 1}',
                                           "gaps_remaining=4", "current_phase=3"])
        self.assertTrue(out["ok"], out)
        st = r.read_state()
        self.assertEqual((st["review_reports"], st["review_findings"], st["gaps_remaining"], st["current_phase"]),
                         (["a"], {"must_fix": 1}, 4, 3))

    def test_set_bool_is_not_an_int(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        out, code = phase.cmd_set(r.root, ["gaps_remaining=true"])
        self.assertFalse(out["ok"], out)
        self.assertIn("gaps_remaining is not an int", out["errors"])

    def test_set_review_reports_string_refused(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        out, code = phase.cmd_set(r.root, ['review_reports="consolidated"'])
        self.assertFalse(out["ok"], out)
        self.assertIn("review_reports is not a list", out["errors"])

    def test_set_repairs_bad_current_phase(self):
        r = self.mk()
        self.write_state(r, self.valid_state(current_phase="abc"))
        out, code = phase.cmd_set(r.root, ["current_phase=2"])
        self.assertTrue(out["ok"], out)
        self.assertEqual(r.read_state()["current_phase"], 2)
        self.assertNotIn("remaining_errors", out)

    def test_repair_of_double_breakage_is_not_deadlocked(self):
        r = self.mk()
        self.write_state(r, self.valid_state(current_phase="abc", phase_step="verified-iphone"))
        out, code = phase.cmd_set(r.root, ["current_phase=2"])
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["remaining_errors"], ["unknown step 'verified-iphone'"])
        out, code = phase.cmd_step(r.root, "review", reason="repair")
        self.assertTrue(out["ok"], out)
        self.assertEqual(phase.validate(r.read_state()), [])

    def test_set_that_does_not_repair_is_refused_on_invalid_state(self):
        r = self.mk()
        self.write_state(r, self.valid_state(current_phase="abc"))
        out, code = phase.cmd_set(r.root, ["plan_file=x.md"])
        self.assertFalse(out["ok"], out)

    def test_note_on_invalid_state_refused(self):
        r = self.mk()
        self.write_state(r, self.valid_state(gaps_remaining="many"))
        out, code = phase.cmd_note(r.root, "hello")
        self.assertFalse(out["ok"], out)
        self.assertEqual(code, 3)
        self.assertIn("gaps_remaining is not an int", out["errors"])

    def test_set_without_equals_refused(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        out, code = phase.cmd_set(r.root, ["plan_file"])
        self.assertFalse(out["ok"])
        self.assertIn("expected KEY=VALUE", out["errors"][0])

    def test_set_phase_step_refused(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        out, code = phase.cmd_set(r.root, ["phase_step=done"])
        self.assertFalse(out["ok"])
        self.assertIn("only by `step`", out["errors"][0])
        self.assertEqual(r.read_state()["phase_step"], "review")

    def test_set_cli_multiple_pairs(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        out = self.cli("--root", r.root, "set", "gaps_remaining=2", "test_report=true", 'review_reports=["x"]')
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        st = r.read_state()
        self.assertEqual((st["gaps_remaining"], st["test_report"], st["review_reports"]), (2, "true", ["x"]))

    def test_set_cli_refusal_exit_3(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        out = self.cli("--root", r.root, "set", "current_phase=abc")
        self.assertEqual(out.returncode, 3)
        self.assertFalse(json.loads(out.stdout)["ok"])
        self.assertEqual(out.stderr, "")


class Item6TransitionTests(_RootCase):
    def _at(self, step, **over):
        r = self.mk()
        self.write_state(r, self.valid_state(phase_step=step, **over))
        return r

    def test_plan_to_execute_reason_only_refused(self):
        r = self._at("plan")
        out, code = phase.cmd_step(r.root, "execute", reason="skip verify")
        self.assertFalse(out["ok"], out)
        self.assertEqual(r.read_state()["phase_step"], "plan")

    def test_plan_to_execute_override_and_reason_allowed(self):
        r = self._at("plan")
        out, code = phase.cmd_step(r.root, "execute", reason="skip verify", override=True)
        self.assertTrue(out["ok"], out)
        st = r.read_state()
        self.assertEqual(st["phase_step"], "execute")
        self.assertTrue(any("skip verify" in n["text"] for n in st["notes"]))

    def test_plan_to_execute_override_without_reason_refused(self):
        r = self._at("plan")
        out, code = phase.cmd_step(r.root, "execute", override=True)
        self.assertFalse(out["ok"], out)

    def test_review_to_plan_reason_allowed(self):
        r = self._at("review")
        out, code = phase.cmd_step(r.root, "plan", reason="scope drift")
        self.assertTrue(out["ok"], out)

    def test_backward_move_reason_allowed(self):
        r = self._at("fix")
        out, code = phase.cmd_step(r.root, "execute", reason="re-run a task")
        self.assertTrue(out["ok"], out)

    def test_step_cli_override_reason_wiring(self):
        r = self._at("plan")
        out = self.cli("--root", r.root, "step", "execute", "--reason", "cli skip")
        self.assertEqual(out.returncode, 3, out.stdout)
        out = self.cli("--root", r.root, "step", "execute", "--override", "--reason", "cli skip")
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(r.read_state()["phase_step"], "execute")

    def test_done_gate_not_fooled_by_truthy_string(self):
        # review_reports as a string used to satisfy `not review_reports`.
        self.assertEqual(phase.complete_gate({"review_reports": "yes", "test_report": None}),
                         {"ok": False, "block": "no-reports"})
        self.assertEqual(phase.complete_gate({"review_reports": [], "test_report": True}),
                         {"ok": False, "block": "no-reports"})

    def test_step_done_on_mistyped_state_refused_before_gate(self):
        r = self._at("review", review_reports="consolidated", test_report=None)
        out, code = phase.cmd_step(r.root, "done")
        self.assertFalse(out["ok"], out)
        self.assertIn("review_reports is not a list", out["errors"])
        self.assertEqual(r.read_state()["phase_step"], "review")

    def test_gate_must_fix_without_gaps_does_not_block(self):
        st = self.valid_state(review_findings={"must_fix": 3, "nice_to_have": 0}, gaps_remaining=0)
        self.assertEqual(phase.complete_gate(st), {"ok": True})

    def test_gate_gaps_without_must_fix_does_not_block(self):
        st = self.valid_state(review_findings={"must_fix": 0, "nice_to_have": 2}, gaps_remaining=2)
        self.assertEqual(phase.complete_gate(st), {"ok": True})

    def test_user_override_sentinels_pass_gate(self):
        st = self.valid_state(review_reports=["user-override"], test_report="user-override")
        self.assertEqual(phase.complete_gate(st), {"ok": True})
        r = self._at("review", review_reports=[], test_report=None)
        out, code = phase.cmd_step(r.root, "done", reason="skip", override=True)
        self.assertTrue(out["ok"], out)
        out, code = phase.cmd_complete_gate(r.root)
        self.assertEqual(out, {"ok": True})


class Item7RobustnessTests(_RootCase):
    def test_list_phase_step_is_a_validation_error(self):
        errs = phase.validate(self.valid_state(phase_step=["review"]))
        self.assertEqual(errs, ["phase_step is not a string (got list)"])

    def test_dict_phase_step_status_hook_and_step_do_not_crash(self):
        r = self.mk()
        self.write_state(r, self.valid_state(phase_step={"x": 1}))
        out = phase.status(r.root)
        self.assertFalse(out["ok"])
        self.assertIn("phase_step is not a string (got dict)", out["errors"])
        self.assertIn("phase_step is not a string", phase.hook_line(r.root))
        out, code = phase.cmd_step(r.root, "review")
        self.assertFalse(out["ok"])
        out, code = phase.cmd_step(r.root, "review", reason="repair")
        self.assertTrue(out["ok"], out)
        self.assertEqual(r.read_state()["phase_step"], "review")

    def test_non_object_state_refused_everywhere(self):
        for text in ("null", "[]", '"x"'):
            r = self.mk()
            self.write_raw(r, text)
            st = phase.status(r.root)
            self.assertFalse(st["ok"])
            self.assertIn("state is not an object", st["errors"])
            for out, code in (phase.cmd_step(r.root, "review", reason="x"),
                              phase.cmd_set(r.root, ["gaps_remaining=1"]),
                              phase.cmd_note(r.root, "x"),
                              phase.cmd_init(r.root, 1, "P", "g.md")):
                self.assertFalse(out["ok"], (text, out))
                self.assertEqual(code, 3)
                self.assertIn("state is not an object", out["errors"])

    def test_non_utf8_is_unparseable(self):
        r = self.mk()
        self.write_raw(r, b"\xff\xfe{", binary=True)
        st = phase.status(r.root)
        self.assertFalse(st["ok"])
        self.assertTrue(st["errors"][0].startswith("unparseable"), st)
        self.assertIn("state file unreadable", phase.hook_line(r.root))

    def test_cli_never_prints_traceback_on_bad_states(self):
        for text in ("null", "[]", '{"phase_step": ["x"]}'):
            r = self.mk()
            self.write_raw(r, text)
            for args in (("status",), ("status", "--hook"), ("step", "review", "--reason", "r"),
                         ("set", "gaps_remaining=1"), ("note", "n"), ("complete-gate",)):
                out = self.cli("--root", r.root, *args)
                self.assertNotIn("Traceback", out.stderr + out.stdout, (text, args))
                self.assertIn(out.returncode, (0, 3), (text, args, out.stdout))


class Item8ScopeModeTzTests(_RootCase):
    def _guide(self, confirmed):
        r = self.mk()
        path = os.path.join(r.root, "g.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f'---\nconfirmed_at: "{confirmed}"\n---\n\n## Phase 1: A\n')
        return path

    def test_trailing_z_against_offset_now(self):
        g = self._guide("2026-09-24T02:00:00Z")
        out, code = phase.cmd_scope_mode(g, now="2026-09-24T10:30:00+08:00")  # same instant + 30 min
        self.assertEqual(out["mode"], "lightweight", out)
        out, code = phase.cmd_scope_mode(g, now="2026-09-24T12:30:00+08:00")  # + 2.5 h
        self.assertEqual(out["mode"], "full", out)

    def test_offset_confirmed_against_z_now(self):
        g = self._guide("2026-09-24T10:00:00+08:00")
        out, code = phase.cmd_scope_mode(g, now="2026-09-24T02:20:00Z")
        self.assertEqual(out["mode"], "lightweight", out)

    def test_aware_confirmed_against_real_now_does_not_crash(self):
        g = self._guide("2000-01-01T00:00:00Z")
        out, code = phase.cmd_scope_mode(g)
        self.assertEqual(code, 0, out)
        self.assertEqual(out["mode"], "full")

    def test_unparseable_confirmed_at_is_full_with_error(self):
        g = self._guide("yesterday-ish")
        out, code = phase.cmd_scope_mode(g)
        self.assertEqual(out["mode"], "full")
        self.assertEqual(out["error"], "unparseable confirmed_at")


class Item9DesignImageTests(_RootCase):
    def _plan(self, root):
        plan = os.path.join(root, "plan.md")
        shutil.copy(os.path.join(FIXTURES, "plan-swift.md"), plan)
        return plan

    def test_path_a_newest_screenshot_by_mtime(self):
        r = self.mk()
        shots = os.path.join(r.root, "shots")
        os.makedirs(shots)
        a = os.path.join(shots, "design-screenshot-a.png")
        b = os.path.join(shots, "design-screenshot-b.png")
        for p_ in (a, b):
            open(p_, "wb").close()
        os.utime(a, (2_000_000_000, 2_000_000_000))  # a is newest, though sorted()[0] is also a...
        os.utime(b, (1_000_000_000, 1_000_000_000))
        pattern = os.path.join(shots, "design-screenshot-*.png")
        with mock.patch.object(phase, "DESIGN_SCREENSHOT_GLOB", pattern), \
                mock.patch.object(phase, "_apple_dev_installed", return_value=True):
            self.assertEqual(phase.cmd_visual_facts(self._plan(r.root), root=r.root)[0]["design_image"], a)
            os.utime(b, (3_000_000_000, 3_000_000_000))  # ...so make b newest: sorted()[0] would still say a
            self.assertEqual(phase.cmd_visual_facts(self._plan(r.root), root=r.root)[0]["design_image"], b)

    def test_path_c_image_referenced_in_design_doc(self):
        r = self.mk()
        docs = os.path.join(r.root, "docs", "02-design")
        os.makedirs(docs)
        img = os.path.join(docs, "mock.png")
        open(img, "wb").close()
        dd = os.path.join(docs, "design.md")
        with open(dd, "w", encoding="utf-8") as f:
            f.write("# Design\n\n![home](mock.png)\n")
        with mock.patch.object(phase, "DESIGN_SCREENSHOT_GLOB", os.path.join(r.root, "none-*.png")), \
                mock.patch.object(phase, "_apple_dev_installed", return_value=True):
            out, code = phase.cmd_visual_facts(self._plan(r.root), design_doc=dd, root=r.root)
        self.assertEqual(out["design_image"], img)

    def test_content_based_view_detection(self):
        r = self.mk()
        with open(os.path.join(r.root, "Home.swift"), "w", encoding="utf-8") as f:
            f.write("struct Home { }\n#Preview { Home() }\n")
        with open(os.path.join(r.root, "Store.swift"), "w", encoding="utf-8") as f:
            f.write("final class Store { }\n")
        plan = os.path.join(r.root, "plan.md")
        with open(plan, "w", encoding="utf-8") as f:
            f.write("### Task 1: Home\n**Files:**\n- Create: `Home.swift`\n- Modify: `Store.swift`\n\n"
                    "**Verify:**\nRun: `true`\nExpected: ok\n")
        with mock.patch.object(phase, "DESIGN_SCREENSHOT_GLOB", os.path.join(r.root, "none-*.png")):
            out, code = phase.cmd_visual_facts(plan, root=r.root)
        self.assertEqual(out["views"], ["Home.swift"])
        self.assertEqual(out["preview_views"], ["Home.swift"])


class Item10CriteriaScanTests(_RootCase):
    GUIDE = ("## Phase 1: A\n**Acceptance criteria:**\n- [x] one\n\n- [ ] two\n"
             "  - a nested plain bullet\n      continuation prose\n- [ ] three\n\n"
             "**Review checklist:**\n- [ ] not a criterion\n\n---\n\n## Phase 2: B\n"
             "**Acceptance criteria:**\n- [ ] only\n")

    def test_blank_line_between_criteria_counted(self):
        r = self.mk()
        g = os.path.join(r.root, "g.md")
        with open(g, "w", encoding="utf-8") as f:
            f.write(self.GUIDE)
        ps = phase.phases(g)["phases"]
        self.assertEqual((ps[0]["total"], ps[0]["checked"]), (3, 1))
        self.assertEqual(ps[1]["total"], 1)

    def test_check_off_ticks_past_blank_line_and_stops_at_label(self):
        r = self.mk()
        g = os.path.join(r.root, "g.md")
        with open(g, "w", encoding="utf-8") as f:
            f.write(self.GUIDE)
        out, code = phase.cmd_check_off(g, 1, date="2026-09-24")
        self.assertEqual(out["ticked"], 2, out)
        with open(g, encoding="utf-8") as f:
            text = f.read()
        self.assertIn("- [x] two", text)
        self.assertIn("- [x] three", text)
        self.assertIn("- [ ] not a criterion", text)
        self.assertIn("- [ ] only", text)

    def test_bold_criterion_does_not_stop_scan(self):
        r = self.mk()
        g = os.path.join(r.root, "g.md")
        with open(g, "w", encoding="utf-8") as f:
            f.write("## Phase 1: A\n**Acceptance criteria:**\n- [ ] **bold:** first\n- [ ] second\n### Notes\n- [ ] no\n")
        self.assertEqual(phase.phases(g)["phases"][0]["total"], 2)


class Item11FallbackYamlTests(_RootCase):
    YML = ("project: X\ncurrent_phase: 3\nphase_name: \"P\"\nphase_step: review\n"
           "review_reports: []\nreview_findings:\n  must_fix: 2\n  nice_to_have: 1\n"
           "notes:\n  - \"first\"\ntest_report: null\ngaps_remaining: 0\n")

    def test_nested_mapping_without_pyyaml(self):
        r = self.mk()
        self.write_raw(r, self.YML, name="dev-workflow-state.yml")
        with mock.patch.dict(sys.modules, {"yaml": None}):
            with mock.patch.object(phase, "_flat_yaml_parse", wraps=phase._flat_yaml_parse) as spy:
                state = phase._parse_yaml(r.yaml_path())
                spy.assert_called_once()
        self.assertEqual(state["review_findings"], {"must_fix": 2, "nice_to_have": 1})
        self.assertEqual(state["review_reports"], [])
        self.assertEqual(state["notes"], ["first"])
        self.assertEqual(state["gaps_remaining"], 0)
        self.assertEqual(phase.validate(state), [])

    def test_nested_mapping_matches_pyyaml(self):
        r = self.mk()
        self.write_raw(r, self.YML, name="dev-workflow-state.yml")
        with_yaml = phase._parse_yaml(r.yaml_path())
        with mock.patch.dict(sys.modules, {"yaml": None}):
            without = phase._parse_yaml(r.yaml_path())
        self.assertEqual(with_yaml, without)


class Item17GapTests(_RootCase):
    def test_init_refused_without_force_then_forced(self):
        r = self.mk("valid.json", "dev-workflow-state.json")  # phase_step: review
        out, code = phase.cmd_init(r.root, 3, "Three", "g.md")
        self.assertFalse(out["ok"])
        self.assertEqual(code, 3)
        self.assertIn("--force", out["errors"][0])
        self.assertEqual(r.read_state()["current_phase"], 2)
        out, code = phase.cmd_init(r.root, 3, "Three", "g.md", force=True)
        self.assertTrue(out["ok"], out)
        st = r.read_state()
        self.assertEqual((st["current_phase"], st["phase_step"]), (3, "plan"))

    def test_migrate_without_yml(self):
        r = self.mk("valid.json", "dev-workflow-state.json")
        out, code = phase.cmd_migrate(r.root)
        self.assertFalse(out["ok"])
        self.assertEqual(code, 3)
        self.assertIn("no legacy .yml", out["errors"][0])

    def test_migrate_reports_validation_errors_but_keeps_data(self):
        r = self.mk()
        self.write_raw(r, "project: X\ncurrent_phase: D\nphase_step: review\n", name="dev-workflow-state.yml")
        out, code = phase.cmd_migrate(r.root)
        self.assertTrue(out["ok"], out)
        self.assertEqual(out["validation_errors"], ["current_phase is not an int"])
        self.assertEqual(r.read_state()["current_phase"], "D")

    def test_validate_specific_error_strings(self):
        errs = phase.validate({"current_phase": "1", "review_reports": "x", "gaps_remaining": 1.5,
                               "review_findings": [1]})
        self.assertEqual(errs, ["missing phase_step", "current_phase is not an int",
                                "gaps_remaining is not an int", "review_reports is not a list",
                                "review_findings is not an object"])
        self.assertEqual(phase.validate({"phase_step": "nope"}), ["unknown step 'nope'"])
        self.assertEqual(phase.validate(None), ["state is not an object"])
        self.assertEqual(phase.validate({"phase_step": "spec"}), [])

    def test_plan_facts_when_lint_fails(self):
        r = self.mk()
        plan = os.path.join(r.root, "plan.md")
        with open(plan, "w", encoding="utf-8") as f:
            f.write("### Task 1: No files or verify\nJust prose.\n\n### Task 2.5: bad id\n")
        out, code = phase.cmd_plan_facts(plan)
        self.assertTrue(out["ok"], out)  # plan-facts itself succeeds; it reports the lint result
        self.assertFalse(out["lint"]["ok"])
        msgs = " ".join(e["msg"] for e in out["lint"]["errors"])
        self.assertIn("missing `**Files:**`", msgs)
        self.assertIn("looks like a task heading", msgs)


if __name__ == "__main__":
    unittest.main()
