#!/usr/bin/env python3
"""phase.py — the only writer of .claude/dev-workflow-state.json for run-phase.

Replaces the hand-written JSON/YAML reads and writes that run-phase/SKILL.md used to
instruct the model to do directly. Deterministic parts only (schema, transitions,
legacy migration, atomic writes); judgment (whether to resume, how to compare scopes,
what to present to the user) stays with the model in SKILL.md.

Subcommands (each prints one JSON object on stdout):
    status [--hook]                          read + validate the state file
    init --phase N --name S --dev-guide P    start a phase (refuses unless done/finalized)
    step TARGET [--reason S] [--override]    move phase_step along TRANSITIONS (back: --reason;
                                             skip forward: --override --reason)
    set KEY=VALUE ...                        write an owned key (not phase_step / notes /
                                             last_updated); only typed keys are JSON-parsed
    note TEXT                                append a free-text note
    migrate                                  legacy .yml -> .json (or archive the leftover)
    quarantine [--target PATH]               rename a state file load() rejects out of the way
    guide                                    pick the dev-guide (docs/06-plans/*-dev-guide.md)
    phases --dev-guide P                     list `## Phase N:` blocks + criteria counts
    locate --dev-guide P                     first incomplete phase
    check-off --dev-guide P --phase N        tick a phase's criteria + insert Status line
    scope-mode --dev-guide P                 full/lightweight from frontmatter confirmed_at
    plan-facts --plan P                      task count, fast/auto-approve flags, lint result
    ux-map --plan P --design-doc P           UX Assertions <-> plan task coverage table
    visual-facts --plan P                    Gate 1/2 + #Preview filter for the visual loop
    complete-gate                            Step 8.0 block reasons from state

Usage: python3 phase.py [--root DIR] <subcommand> ...
Exit codes: 0 success, 3 refused/invalid (state unreadable, illegal transition, bad args).
Every write path except `migrate` validates the resulting state and refuses to write
an invalid one (a `set` / `step` that strictly reduces the errors is allowed: repair).
Never raises a traceback for a state-file problem — errors always come back as JSON.
"""

import argparse
import glob
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "execute-plan", "scripts"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "write-plan", "scripts"))
from compute_checkpoints import parse_tasks  # noqa: E402
from lint_plan import lint as lint_plan_lint  # noqa: E402

STEPS = ["plan", "ux-review", "verify", "execute", "test", "visual", "review", "fix", "done", "finalized"]
ALIASES = {"spec": "review", "build-test": "test"}

OWNED_KEYS = {
    "project", "current_phase", "phase_name", "phase_step", "dev_guide",
    "plan_file", "verification_report", "task_progress", "review_reports",
    "review_findings", "test_report", "gaps_remaining", "last_updated", "notes",
}

TRANSITIONS = {
    "plan": {"ux-review", "verify"},
    "ux-review": {"verify"},
    "verify": {"execute"},
    "execute": {"test"},
    "test": {"visual", "review"},
    "visual": {"review"},
    "review": {"test", "fix", "done"},
    "fix": {"test", "review", "done"},
    "done": {"finalized"},
    "finalized": set(),
}

_BLOCK_MESSAGES = {
    "no-reports": "no test or review reports found — run Step 5 and Step 6 before marking phase as done",
    "gaps": "unresolved gaps remain — fix them or mark as known issues",
}

_NO_STATE_ERROR = "no state — run `init`"
_UNPARSEABLE_WRITE_ERROR = "refusing to overwrite unparseable state — run `phase.py quarantine` or fix the file by hand"


# ---------------------------------------------------------------------------
# paths + low-level read/write


def _json_path(root):
    return os.path.join(root, ".claude", "dev-workflow-state.json")


def _yaml_path(root):
    return os.path.join(root, ".claude", "dev-workflow-state.yml")


def _now():
    return datetime.now().isoformat()


def _canonical(step_name):
    # A hand-edited file can hold a list/dict here; dict lookups on those raise
    # "unhashable" — only strings are ever aliased.
    if not isinstance(step_name, str):
        return step_name
    return ALIASES.get(step_name, step_name)


def _is_finished(state):
    """True when a parsed state's phase_step canonicalises to done/finalized —
    a finished project stays silent whatever else is wrong with the file."""
    return isinstance(state, dict) and _canonical(state.get("phase_step")) in ("done", "finalized")


def _flat_yaml_value(val):
    val = val.strip()
    if val in ("null", "~", ""):
        return None
    if val in ("true", "True"):
        return True
    if val in ("false", "False"):
        return False
    if len(val) >= 2 and ((val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'"))):
        return val[1:-1]
    if (val.startswith("[") and val.endswith("]")) or (val.startswith("{") and val.endswith("}")):
        # Inline flow collections: `[]`, `{}`, `["a", "b"]`, `{"must_fix": 1}`.
        if val in ("[]", "{}"):
            return [] if val == "[]" else {}
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return val
    try:
        return int(val)
    except ValueError:
        pass
    try:
        return float(val)
    except ValueError:
        pass
    return val


def _flat_yaml_parse(path):
    """Minimal parser for top-level `key: value`, quoted strings, null, ints, inline
    `[]`/`{}`, block lists (`  - "x"`) and one level of nested mapping
    (`review_findings:` followed by indented `  must_fix: 2`). A key with an empty
    value and no indented lines after it is null, as in PyYAML. Used only when
    PyYAML is not importable."""
    result = {}
    open_key = None  # top-level key whose value is an indented block
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for raw in lines:
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indented = line[:1] in (" ", "\t")
        if indented or stripped.startswith("- "):
            if open_key is None:
                continue
            block = result[open_key]
            if stripped.startswith("- ") or stripped == "-":
                if block is None:
                    block = result[open_key] = []
                if isinstance(block, list):
                    block.append(_flat_yaml_value(stripped[1:].strip()))
                continue
            nm = re.match(r"^([A-Za-z0-9_\-]+):\s*(.*)$", stripped)
            if nm:
                if block is None:
                    block = result[open_key] = {}
                if isinstance(block, dict):
                    block[nm.group(1)] = _flat_yaml_value(nm.group(2))
            continue
        m = re.match(r"^([A-Za-z0-9_\-]+):\s*(.*)$", line)
        if not m:
            open_key = None
            continue
        key, val = m.group(1), m.group(2)
        if val.strip() == "":
            result[key] = None  # filled in by the indented block, if any
            open_key = key
        else:
            result[key] = _flat_yaml_value(val)
            open_key = None
    return result


def _parse_yaml(path):
    try:
        import yaml
    except ImportError:
        return _flat_yaml_parse(path)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load(root):
    """Read the state file (JSON preferred, legacy YAML fallback).

    Returns {ok, exists:False} when there is nothing to read; {ok:False, exists:True,
    source, path, state:None, errors} when the file is unusable (unparseable, not
    UTF-8, duplicate keys, top level not an object); or {ok:True, exists:True, source,
    path, state, errors:[], legacy_leftover?}.

    A duplicate-key failure also carries `last_wins` — the dict a plain json.load
    would have produced — so the SessionStart hook can tell a finished project
    (stay silent) from an in-progress one. It is never written back.
    """
    jpath = _json_path(root)
    ypath = _yaml_path(root)
    has_json = os.path.isfile(jpath)
    has_yaml = os.path.isfile(ypath)
    if not has_json and not has_yaml:
        return {"ok": True, "exists": False}
    if has_json:
        base = {"exists": True, "source": "json", "path": jpath}
        dups = []

        def _pairs(pairs, _dups=dups):
            seen = {}
            for k, v in pairs:
                if k in seen and k not in _dups:
                    _dups.append(k)
                seen[k] = v
            return seen

        try:
            with open(jpath, "r", encoding="utf-8") as f:
                text = f.read()
            state = json.loads(text, object_pairs_hook=_pairs)
        except json.JSONDecodeError as e:
            return {**base, "ok": False, "state": None,
                    "errors": [f"unparseable: {e.msg} (line {e.lineno} col {e.colno})"]}
        except UnicodeDecodeError as e:
            return {**base, "ok": False, "state": None, "errors": [f"unparseable: not UTF-8 ({e.reason})"]}
        if not isinstance(state, dict):
            return {**base, "ok": False, "state": None, "errors": ["state is not an object"]}
        if dups:
            # A hand-merged file: any write would silently keep only the last value of each.
            # (Nested duplicate keys are counted too — the hook sees every object.)
            return {**base, "ok": False, "state": None, "last_wins": state,
                    "errors": [f"duplicate keys: {', '.join(dups)} (a write would keep only the last value of each)"]}
        result = {**base, "ok": True, "state": state, "errors": []}
        if has_yaml:
            result["legacy_leftover"] = True
        return result
    base = {"exists": True, "source": "yaml", "path": ypath}
    try:
        state = _parse_yaml(ypath)
    except Exception as e:  # yaml.YAMLError, UnicodeDecodeError, OSError
        return {**base, "ok": False, "state": None, "errors": [f"unparseable: {e}"]}
    if not isinstance(state, dict):
        return {**base, "ok": False, "state": None, "errors": ["state is not an object"]}
    return {**base, "ok": True, "state": state, "errors": []}


def validate(state):
    """Return a list of error strings; empty means the state is usable."""
    errors = []
    if not isinstance(state, dict):
        return ["state is not an object"]
    if "phase_step" not in state:
        errors.append("missing phase_step")
    elif not isinstance(state["phase_step"], str):
        errors.append(f"phase_step is not a string (got {type(state['phase_step']).__name__})")
    else:
        step = _canonical(state["phase_step"])
        if step not in STEPS:
            errors.append(f"unknown step '{state['phase_step']}'")
    for key, want in _TYPED_KEYS.items():
        if key in state and not _type_ok(state[key], want):
            errors.append(f"{key} is not {_TYPE_NAMES[want]}")
    return errors


# Owned keys whose values are typed (and JSON-parsed by `set`). Every other
# settable owned key is free text. bool is excluded from int on purpose:
# isinstance(True, int) is True in Python.
_TYPED_KEYS = {
    "current_phase": int,
    "gaps_remaining": int,
    "review_reports": list,
    "review_findings": dict,
}
_TYPE_NAMES = {int: "an int", list: "a list", dict: "an object"}


def _type_ok(value, want):
    if want is int:
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, want)


def _write_errors(prior_state, new_state, allow_repair):
    """Validation for every write path. Returns None when the write may proceed,
    else the list of errors the resulting state would carry.

    allow_repair (set / step only): a write onto an already-invalid state is let
    through when it strictly shrinks the error set without adding a new one — the
    repair path. Without it, a state with both an off-enum step and a bad field
    type deadlocks: `set` fails on the step, `step` fails on the field."""
    after = validate(new_state)
    if not after:
        return None
    if allow_repair and isinstance(prior_state, dict):
        before = set(validate(prior_state))
        if set(after) < before:
            return None
    return after


def _refuse_invalid(errors):
    return {"ok": False, "refused": "invalid-result",
            "errors": ["refusing to write an invalid state — the result would have these errors:"] + list(errors)}, 3


def _write(root, state):
    """Atomic read-modify-write: keeps every key the caller didn't remove, drops
    `_comment_*` keys, stamps `last_updated`, writes to a temp file then os.replace."""
    state = {k: v for k, v in state.items() if not k.startswith("_comment_")}
    state["last_updated"] = _now()
    jpath = _json_path(root)
    os.makedirs(os.path.dirname(jpath), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(jpath), prefix=".dev-workflow-state.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            # default=_json_default: a legacy YAML file can hand us an unquoted date/
            # datetime (PyYAML auto-parses those); stringify rather than lose the write.
            json.dump(state, f, indent=2, ensure_ascii=False, default=_json_default)
            f.write("\n")
        os.replace(tmp, jpath)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return state


def _json_default(obj):
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _load_for_write(root):
    """(load result, None) when there is a readable state to modify, else
    (None, refusal) — no state file, or one load() rejects (unparseable, not UTF-8,
    duplicate keys, not an object). The load errors are passed through."""
    res = load(root)
    if res.get("ok") and not res.get("exists", True):
        return None, ({"ok": False, "errors": [_NO_STATE_ERROR]}, 3)
    if not res.get("ok"):
        return None, ({"ok": False, "errors": [_UNPARSEABLE_WRITE_ERROR] + list(res.get("errors", []))}, 3)
    return res, None


def _append_note(state, text):
    notes = state.get("notes")
    if notes is None:
        notes = []
    elif not isinstance(notes, list):
        notes = [notes]  # preserve whatever was there instead of discarding it
    notes.append({"at": _now(), "text": text})
    state["notes"] = notes


# ---------------------------------------------------------------------------
# completion gate (Task 3 exposes this as `complete-gate`; `step done` uses it directly)


def complete_gate(state):
    """Type-checked: a report counts only when it is really there — review_reports a
    non-empty list, test_report a non-empty string (a truthy string in
    review_reports, or `true` in test_report, is not a report)."""
    review_reports = state.get("review_reports")
    test_report = state.get("test_report")
    has_reviews = isinstance(review_reports, list) and len(review_reports) > 0
    has_test = isinstance(test_report, str) and test_report.strip() != ""
    if not has_reviews and not has_test:
        return {"ok": False, "block": "no-reports"}
    review_findings = state.get("review_findings")
    must_fix = review_findings.get("must_fix", 0) if isinstance(review_findings, dict) else 0
    if must_fix is None:
        must_fix = 0
    elif not _type_ok(must_fix, int):
        must_fix = 1  # present but not a count: treat as unresolved rather than as zero
    gaps_remaining = state.get("gaps_remaining", 0)
    if not _type_ok(gaps_remaining, int):
        gaps_remaining = 0 if gaps_remaining is None else 1
    if must_fix > 0 and gaps_remaining > 0:
        return {"ok": False, "block": "gaps"}
    return {"ok": True}


# ---------------------------------------------------------------------------
# status / hook line


def status(root):
    res = load(root)
    if res.get("ok") and not res.get("exists", True):
        return {"ok": True, "exists": False}
    if not res.get("ok"):
        out = {k: v for k, v in res.items() if k != "last_wins"}
        return {**out, "exists": True, "step": None, "resume_step": None, "next_allowed": [],
                "legacy_alias_applied": False}
    state = res["state"]
    errors = validate(state)
    raw_step = state.get("phase_step")
    warnings = []
    if errors and _is_finished(state):
        # A finished phase with a bad field (e.g. a letter `current_phase: "D"`) must
        # not block: nothing is in progress, and `init` replaces every owned key.
        warnings, errors = errors, []
    step = _canonical(raw_step) if not errors else None
    out = {
        "ok": len(errors) == 0,
        "exists": True,
        "source": res["source"],
        "state": state,
        "errors": errors,
        "step": step,
        "resume_step": step,
        "next_allowed": sorted(TRANSITIONS.get(step, set()) | {step}) if step in TRANSITIONS else [],
        "legacy_alias_applied": isinstance(raw_step, str) and raw_step in ALIASES,
    }
    if warnings:
        out["warnings"] = warnings
    if res.get("legacy_leftover"):
        out["legacy_leftover"] = True
    return out


def _hook_value(v):
    if v is None:
        return "?"
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v


def hook_line(root):
    """One line for the SessionStart hook, or None to print nothing."""
    res = load(root)
    if res.get("ok") and not res.get("exists", True):
        return None
    if not res.get("ok"):
        if _is_finished(res.get("last_wins")):
            return None  # duplicate keys, but the last-wins step says the work is finished
        errs = "; ".join(res.get("errors", []))
        return (f"[dev-workflow] state file unreadable: {errs} — run /run-phase: it offers to "
                "fix the file by hand or move it aside with `phase.py quarantine`")
    state = res["state"]
    if _is_finished(state):
        return None  # finished projects stay silent even when other fields fail validation
    errors = validate(state)
    if errors:
        return f"[dev-workflow] {'; '.join(errors)} — run /run-phase to repair"
    step = _canonical(state.get("phase_step"))
    n = _hook_value(state.get("current_phase"))
    name = _hook_value(state.get("phase_name"))
    updated = _hook_value(state.get("last_updated"))
    return (f"[dev-workflow] Phase {n} ({name}) in progress — step: {step}, "
            f"last updated: {updated}. Run /run-phase to resume.")


# ---------------------------------------------------------------------------
# init


def cmd_init(root, phase, name, dev_guide, project=None, force=False):
    res = load(root)
    if not res.get("ok"):
        return {"ok": False, "errors": [_UNPARSEABLE_WRITE_ERROR] + list(res.get("errors", []))}, 3
    prior_state = {}
    if res.get("exists", True):
        prior_state = res["state"]
        current_raw = _canonical(prior_state.get("phase_step"))
        if current_raw not in ("done", "finalized") and not force:
            return {"ok": False, "errors": [
                f"current phase_step '{current_raw}' is not done/finalized — pass --force to override"]}, 3
    # Preserve every ad-hoc (non-owned) key from the prior state — "unknown keys
    # survive every write" applies to init too, not just step/set/note.
    new_state = {k: v for k, v in prior_state.items() if k not in OWNED_KEYS}
    new_state.update({
        "project": project or prior_state.get("project") or os.path.basename(os.path.abspath(root)),
        "current_phase": phase,
        "phase_name": name,
        "phase_step": "plan",
        "dev_guide": dev_guide,
        "plan_file": None,
        "verification_report": None,
        "task_progress": None,
        "review_reports": [],
        "test_report": None,
        "gaps_remaining": 0,
    })
    errs = _write_errors(prior_state, new_state, allow_repair=False)
    if errs:
        return _refuse_invalid(errs)
    new_state = _write(root, new_state)
    return {"ok": True, "state": new_state}, 0


# ---------------------------------------------------------------------------
# step


def transition_check(current_raw, target_raw, reason, override):
    """Return (allowed, errors, note_text). note_text (or None) is what to append to
    `notes` when the transition is not a plain sanctioned move."""
    target = _canonical(target_raw)
    if target not in STEPS:
        return False, [f"unknown target step '{target_raw}'"], None

    current_valid = isinstance(current_raw, str) and current_raw in STEPS

    if current_valid and target == current_raw:
        return True, [], None  # X -> X no-op

    if not current_valid:
        if not reason:
            return False, [f"current step '{current_raw}' is invalid/unknown — pass --reason to repair"], None
        return True, [], f"repair: {current_raw} -> {target}: {reason}"

    if target == "finalized" and current_raw != "done":
        if override and reason:
            return True, [], f"finalized override from {current_raw}: {reason}"
        return False, ["finalized from a step other than done requires --override and --reason"], None

    if target == "plan" and current_raw in ("done", "finalized"):
        return False, [f"illegal transition {current_raw} -> plan — start the next phase with `init`"], None

    if target in TRANSITIONS.get(current_raw, set()):
        return True, [], None

    if STEPS.index(target) > STEPS.index(current_raw):
        # Forward move that skips steps (e.g. plan -> execute skips verify): the
        # skipped step is a gate, so a reason alone is not enough.
        if override and reason:
            return True, [], f"override: skipped forward {current_raw} -> {target}: {reason}"
        return False, [f"illegal transition {current_raw} -> {target} skips steps — "
                       "pass --override and --reason to skip forward"], None

    # Backward move (including the reset to plan): a reason is enough.
    if reason:
        return True, [], f"transition {current_raw} -> {target}: {reason}"
    return False, [f"illegal transition {current_raw} -> {target} — pass --reason to go back"], None


def cmd_step(root, target_raw, reason=None, override=False):
    res, refusal = _load_for_write(root)
    if refusal:
        return refusal

    prior = res["state"]
    state = dict(prior)
    raw_step = state.get("phase_step")
    current_raw = _canonical(raw_step)

    allowed, errors, note_text = transition_check(current_raw, target_raw, reason, override)
    if not allowed:
        return {"ok": False, "errors": errors}, 3

    target = _canonical(target_raw)
    state["phase_step"] = target

    # Validate before the done-gate: the gate reads review_reports / gaps_remaining,
    # and on a mistyped state its answer would be meaningless.
    errs = _write_errors(prior, state, allow_repair=True)
    if errs:
        return _refuse_invalid(errs)

    gate_note = None
    if target == "done" and current_raw != "done":
        gate = complete_gate(state)
        if not gate["ok"]:
            if not override:
                return {"ok": False, "block": gate["block"], "errors": [_BLOCK_MESSAGES[gate["block"]]]}, 3
            if gate["block"] == "no-reports":
                state["review_reports"] = ["user-override"]
                state["test_report"] = "user-override"
                gate_note = "override: no test/review reports — user chose to skip and complete"
            elif gate["block"] == "gaps":
                gate_note = f"gaps accepted as known issues: {state.get('gaps_remaining', 0)}"

    if note_text:
        _append_note(state, note_text)
    if gate_note:
        _append_note(state, gate_note)
    _write(root, state)
    out = {"ok": True, "step": target}
    remaining = validate(state)
    if remaining:
        out["remaining_errors"] = remaining
    return out, 0


# ---------------------------------------------------------------------------
# set / note


# `set` JSON-parses only the typed keys; every other settable key is free text and
# is stored verbatim (so `verification_report=true` stays the string "true"). The one
# exception is the literal `null`, which clears a free-text key back to None — the
# value `init` writes there, and what `set plan_file=null` in run-phase Step 1 means.
_STRING_KEYS = {"project", "phase_name", "dev_guide", "plan_file", "verification_report",
                "task_progress", "test_report"}
_SETTABLE_KEYS = _STRING_KEYS | set(_TYPED_KEYS)


def cmd_set(root, pairs):
    res, refusal = _load_for_write(root)
    if refusal:
        return refusal

    prior = res["state"]
    state = dict(prior)
    errors = []
    updates = {}
    for pair in pairs:
        if "=" not in pair:
            errors.append(f"invalid set argument '{pair}' — expected KEY=VALUE")
            continue
        key, raw_val = pair.split("=", 1)
        if key == "phase_step":
            errors.append("phase_step is written only by `step` (it checks the transition)")
            continue
        if key == "notes":
            errors.append("notes is appended only by `note`")
            continue
        if key == "last_updated":
            errors.append("last_updated is stamped automatically on every write")
            continue
        if key not in _SETTABLE_KEYS:
            errors.append(f"unknown key '{key}' — use `note`")
            continue
        if key in _TYPED_KEYS:
            try:
                val = json.loads(raw_val)
            except json.JSONDecodeError:
                val = raw_val  # validate() names the type error below
        else:
            val = None if raw_val == "null" else raw_val
        updates[key] = val
    if errors:
        return {"ok": False, "errors": errors}, 3

    state.update(updates)
    errs = _write_errors(prior, state, allow_repair=True)
    if errs:
        return _refuse_invalid(errs)
    _write(root, state)
    out = {"ok": True, "updated": updates}
    remaining = validate(state)
    if remaining:
        out["remaining_errors"] = remaining  # a partial repair: more to fix
    return out, 0


def cmd_note(root, text):
    res, refusal = _load_for_write(root)
    if refusal:
        return refusal

    prior = res["state"]
    state = dict(prior)
    _append_note(state, text)
    errs = _write_errors(prior, state, allow_repair=False)
    if errs:
        return _refuse_invalid(errs)
    _write(root, state)
    return {"ok": True}, 0


# ---------------------------------------------------------------------------
# migrate / quarantine


def cmd_migrate(root):
    jpath = _json_path(root)
    ypath = _yaml_path(root)
    if not os.path.isfile(ypath):
        return {"ok": False, "errors": ["no legacy .yml file found"]}, 3
    if os.path.isfile(jpath):
        archive = ypath + ".archive"
        os.replace(ypath, archive)
        return {"ok": True, "archived": True, "path": archive}, 0
    try:
        state = _parse_yaml(ypath)
    except Exception as e:
        return {"ok": False, "errors": [f"unparseable: {e}"]}, 3
    if not isinstance(state, dict):
        return {"ok": False, "errors": ["state is not an object"]}, 3
    # migrate is the one write path that does not refuse an invalid result: it
    # carries legacy data over as-is (refusing would strand it in the .yml) and
    # reports what is wrong so Step 1 can repair it with `set` / `step --reason`.
    _write(root, state)
    os.remove(ypath)
    out = {"ok": True, "migrated": True}
    validation_errors = validate(state)
    if validation_errors:
        out["validation_errors"] = validation_errors
    return out, 0


# ---------------------------------------------------------------------------
# dev-guide operations (Task 2): picking the dev-guide, parsing `## Phase N:`
# blocks and their acceptance criteria, checking criteria off, and the
# scope-mode freshness check. No rewrite of dev-guide prose — only checkbox
# characters and the one inserted status line ever change.


FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
PHASE_HEADING_RE = re.compile(r"^## Phase (\d+):\s*(.*)$")
CRITERIA_LABEL_RE = re.compile(r"\*\*(?:Acceptance criteria|验收标准)\s*[:：]\*\*", re.IGNORECASE)
# What ends a criteria block: the next `**Label:**` line, a markdown heading, or a
# horizontal rule. Blank lines, nested plain bullets and prose do not — a
# `- [ ] **bold** text` criterion starts with `- `, so it never matches LABEL_LINE_RE.
LABEL_LINE_RE = re.compile(r"^\*\*[^*\n]+?\s*[:：]\s*\*\*")
HEADING_LINE_RE = re.compile(r"^#{1,6}\s")
HR_LINE_RE = re.compile(r"^\s{0,3}(?:(?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,})$")
COMPLETED_MARK = "✅ Completed"
CHECKBOX_RE = re.compile(r"^(\s*)- \[([ xX])\](.*)$")
STATUS_LINE_RE = re.compile(r"^\*\*Status:\*\*")


def _read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _frontmatter(text):
    """Minimal `key: value` frontmatter reader — good enough for `current:` and
    `confirmed_at:`, the only two fields any subcommand here reads."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        km = re.match(r"^([A-Za-z0-9_]+):\s*(.*)$", line)
        if km:
            fm[km.group(1)] = km.group(2).strip().strip('"').strip("'")
    return fm


def _parse_iso(s):
    """ISO-8601 -> naive local datetime. Accepts a trailing `Z` and `+08:00`-style
    offsets: an aware value is converted to local time before its tzinfo is dropped,
    so it compares correctly with a naive local `now`."""
    s = s.strip()
    if s.endswith("Z") or s.endswith("z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is not None:
        dt = dt.astimezone().replace(tzinfo=None)
    return dt


def _phase_slices(lines):
    """[(n, name, start_line_idx, end_line_idx)] — end is exclusive (next heading
    or EOF). `lines` has no trailing newlines (split on "\\n")."""
    heads = []
    for i, line in enumerate(lines):
        m = PHASE_HEADING_RE.match(line)
        if m:
            heads.append((int(m.group(1)), m.group(2).strip(), i))
    out = []
    for idx, (n, name, start) in enumerate(heads):
        end = heads[idx + 1][2] if idx + 1 < len(heads) else len(lines)
        out.append((n, name, start, end))
    return out


def _criteria_block(lines, start, end):
    """Find the acceptance-criteria label inside lines[start:end] and every
    checkbox line after it up to the block's end (next `**Label:**`, heading or
    horizontal rule). Returns ([(line_idx, checked_bool)], label_idx); label_idx
    is None when the phase has no recognized criteria label. Shared by `phases`
    and `check-off` so the two can never disagree on what the criteria are."""
    label_idx = None
    for i in range(start, end):
        if CRITERIA_LABEL_RE.search(lines[i]):
            label_idx = i
            break
    if label_idx is None:
        return [], None
    boxes = []
    for i in range(label_idx + 1, end):
        line = lines[i]
        stripped = line.strip()
        if LABEL_LINE_RE.match(stripped) or HEADING_LINE_RE.match(line) or HR_LINE_RE.match(line):
            break
        m = CHECKBOX_RE.match(line)
        if m:
            boxes.append((i, m.group(2).lower() == "x"))
    return boxes, label_idx


def _status_line_idx(lines, start, end):
    for i in range(start, end):
        if STATUS_LINE_RE.match(lines[i].strip()):
            return i
    return None


def cmd_guide(root):
    pattern = os.path.join(root, "docs", "06-plans", "*-dev-guide.md")
    candidates = sorted(glob.glob(pattern))
    if not candidates:
        return {"ok": False, "errors": ["no dev-guide found"], "candidates": []}, 3
    if len(candidates) == 1:
        return {"ok": True, "path": candidates[0]}, 0
    current = []
    for c in candidates:
        fm = _frontmatter(_read_text(c))
        if fm.get("current") == "true":
            current.append(c)
    if len(current) == 1:
        return {"ok": True, "path": current[0]}, 0
    return {"ok": False, "candidates": candidates}, 3


def phases(dev_guide):
    """Core parser: `{ok, phases:[{n,name,total,checked,complete,status_line}]}`
    or `{ok:False, unparseable_reason}`."""
    if not os.path.isfile(dev_guide):
        return {"ok": False, "unparseable_reason": f"no such file: {dev_guide}"}
    text = _read_text(dev_guide)
    lines = text.split("\n")
    slices = _phase_slices(lines)
    if not slices:
        return {"ok": False, "unparseable_reason": "no `## Phase N:` headings found"}
    out = []
    for n, name, start, end in slices:
        boxes, _ = _criteria_block(lines, start, end)
        total = len(boxes)
        checked = sum(1 for _, c in boxes if c)
        status_idx = _status_line_idx(lines, start, end)
        status_line = lines[status_idx].strip() if status_idx is not None else None
        # Complete = every criterion ticked, OR the Status line check-off writes. The
        # second clause is what lets a phase with no criteria list ever complete.
        complete = (total > 0 and checked == total) or (
            status_line is not None and COMPLETED_MARK in status_line)
        entry = {
            "n": n, "name": name, "total": total, "checked": checked,
            "complete": complete, "status_line": status_line,
        }
        if total == 0:
            entry["no_criteria"] = True
        out.append(entry)
    return {"ok": True, "phases": out}


def cmd_locate(dev_guide):
    res = phases(dev_guide)
    if not res["ok"]:
        return res, 3
    for p in res["phases"]:
        if not p["complete"]:
            return {"ok": True, "phase": p, "all_complete": False}, 0
    return {"ok": True, "phase": None, "all_complete": True}, 0


def cmd_check_off(dev_guide, phase_n, date=None):
    if not os.path.isfile(dev_guide):
        return {"ok": False, "errors": [f"no such file: {dev_guide}"]}, 3
    text = _read_text(dev_guide)
    trailing_newline = text.endswith("\n")
    lines = text.split("\n")
    if trailing_newline:
        lines = lines[:-1]
    slices = _phase_slices(lines)
    target = next((s for s in slices if s[0] == phase_n), None)
    if target is None:
        return {"ok": False, "errors": [f"phase {phase_n} not found"]}, 3
    _, _, start, end = target

    boxes, _ = _criteria_block(lines, start, end)
    ticked = 0
    for i, checked in boxes:
        if not checked:
            m = CHECKBOX_RE.match(lines[i])
            lines[i] = m.group(1) + "- [x]" + m.group(3)
            ticked += 1

    status_idx = _status_line_idx(lines, start, end)
    inserted = False
    if status_idx is None:
        d = date or time.strftime("%Y-%m-%d")
        lines.insert(start + 1, f"**Status:** ✅ Completed — {d}")
        inserted = True

    new_text = "\n".join(lines) + ("\n" if trailing_newline else "")
    with open(dev_guide, "w", encoding="utf-8") as f:
        f.write(new_text)

    all_res = phases(dev_guide)
    all_complete = all(p["complete"] for p in all_res["phases"]) if all_res["ok"] else False
    return {"ok": True, "ticked": ticked, "status_inserted": inserted, "all_phases_complete": all_complete}, 0


def cmd_scope_mode(dev_guide, now=None):
    if not os.path.isfile(dev_guide):
        return {"ok": False, "errors": [f"no such file: {dev_guide}"]}, 3
    text = _read_text(dev_guide)
    fm = _frontmatter(text)
    raw = fm.get("confirmed_at")
    if not raw:
        return {"ok": True, "mode": "full", "confirmed_at": None}, 0
    try:
        confirmed = _parse_iso(raw)
    except ValueError:
        return {"ok": True, "mode": "full", "confirmed_at": raw, "error": "unparseable confirmed_at"}, 0
    try:
        now_dt = _parse_iso(now) if now else datetime.now()
    except ValueError:
        return {"ok": False, "errors": [f"unparseable --now: {now}"]}, 3
    delta = abs((now_dt - confirmed).total_seconds())
    mode = "lightweight" if delta <= 3600 else "full"
    return {"ok": True, "mode": mode, "confirmed_at": raw}, 0


# ---------------------------------------------------------------------------
# rule-based gates (Task 3): plan-facts, ux-map, visual-facts, complete-gate.
# No rendering, no image comparison, no review, no test runner — those stay
# with the model. `parse_tasks` is imported from execute-plan's own parser
# (same trick as write-plan/scripts/lint_plan.py) so run-phase and
# execute-plan never disagree on what a "task" is.

FILE_PATH_RE = re.compile(r"`([^`]+)`")
UX_REF_RE = re.compile(r"\*\*UX ref:\*\*\s*(.*)")
USER_INTERACTION_RE = re.compile(r"\*\*User interaction:\*\*\s*(.*)")
UX_ID_RE = re.compile(r"UX-\d+")
VIEW_SUFFIX_RE = re.compile(r"(?:View|Card|Row|Cell|Tab|Screen|Sheet|Banner)$")
IMG_REF_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)|([^\s()`]+\.(?:png|jpg|jpeg))", re.IGNORECASE)
UX_ASSERTIONS_HEADING_RE = re.compile(r"^##\s+UX Assertions\s*$")

# understand-design's screenshot output path — a module-level constant (not
# inlined into _resolve_design_image) so tests can monkeypatch it instead of
# writing into the real system /tmp.
DESIGN_SCREENSHOT_GLOB = "/tmp/design-screenshot-*.png"


def _files_section_lines(body):
    """The `- ` bullet lines directly under a task's `**Files:**` label."""
    lines = body.split("\n")
    label_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith("**Files:**"):
            label_idx = i
            break
    if label_idx is None:
        return []
    out = []
    started = False
    for i in range(label_idx + 1, len(lines)):
        line = lines[i]
        if line.strip().startswith("- "):
            started = True
            out.append(line)
            continue
        if started:
            break
        if line.strip() == "":
            continue
        break
    return out


def _task_file_paths(body):
    paths = []
    for line in _files_section_lines(body):
        paths.extend(FILE_PATH_RE.findall(line))
    return paths


def _task_ux_refs(body):
    m = UX_REF_RE.search(body)
    if not m:
        return []
    return UX_ID_RE.findall(m.group(1))


def _task_user_interaction(body):
    m = USER_INTERACTION_RE.search(body)
    if not m:
        return None
    text = m.group(1).strip()
    return text or None


def cmd_plan_facts(plan_path, design_doc=None, crystal=None):
    if not os.path.isfile(plan_path):
        return {"ok": False, "errors": [f"no such file: {plan_path}"]}, 3
    text = _read_text(plan_path)
    tasks = parse_tasks(text)
    n = len(tasks)
    has_design_doc = design_doc not in (None, "none")
    has_crystal = crystal not in (None, "none")
    return {
        "ok": True,
        "tasks": n,
        "fast": n < 5,
        "auto_approve": n <= 3 and not has_design_doc and not has_crystal,
        "lint": lint_plan_lint(text),
    }, 0


def _ux_assertions_table(design_doc_text):
    """Parse the `## UX Assertions` markdown table -> [{ux_id, assertion}].
    [] when the heading is absent or the table has no data rows (header-only)."""
    lines = design_doc_text.split("\n")
    heading_idx = None
    for i, line in enumerate(lines):
        if UX_ASSERTIONS_HEADING_RE.match(line.strip("\n")):
            heading_idx = i
            break
    if heading_idx is None:
        return []
    table_rows = []
    for i in range(heading_idx + 1, len(lines)):
        line = lines[i]
        if line.startswith("## "):
            break
        if line.strip().startswith("|"):
            table_rows.append(line.strip())
    if len(table_rows) < 3:  # header + separator + >=1 data row
        return []
    out = []
    for row in table_rows[2:]:
        cells = [c.strip() for c in row.strip("|").split("|")]
        if len(cells) < 2 or not cells[0]:
            continue
        out.append({"ux_id": cells[0], "assertion": cells[1]})
    return out


def cmd_ux_map(plan_path, design_doc):
    if not os.path.isfile(plan_path):
        return {"ok": False, "errors": [f"no such file: {plan_path}"]}, 3
    if not os.path.isfile(design_doc):
        return {"ok": False, "errors": [f"no such file: {design_doc}"]}, 3
    tasks = parse_tasks(_read_text(plan_path))
    assertions = _ux_assertions_table(_read_text(design_doc))
    triggered = len(assertions) > 0

    rows = []
    for a in assertions:
        matching = [t for t in tasks if a["ux_id"] in _task_ux_refs(t["body"])]
        user_interaction = None
        for t in matching:
            user_interaction = _task_user_interaction(t["body"])
            if user_interaction:
                break
        rows.append({
            "ux_id": a["ux_id"],
            "assertion": a["assertion"],
            "tasks": [f"Task {t['id']}" for t in matching],
            "user_interaction": user_interaction,
            "mapped": bool(matching),
        })

    unmapped_ui_tasks = []
    for t in tasks:
        has_swift = any(p.endswith(".swift") for p in _task_file_paths(t["body"]))
        if has_swift and not _task_ux_refs(t["body"]):
            unmapped_ui_tasks.append(f"Task {t['id']}")

    return {"ok": True, "triggered": triggered, "rows": rows, "unmapped_ui_tasks": unmapped_ui_tasks}, 0


def _apple_dev_installed():
    base = os.environ.get("PHASE_PLUGINS_CACHE", os.path.expanduser("~/.claude/plugins/cache"))
    return bool(glob.glob(os.path.join(base, "*", "apple-dev")))


def _read_text_or_none(path):
    try:
        return _read_text(path)
    except OSError:
        return None


def _is_view_path(root, path):
    """A `.swift` path is a view when its stem ends with a view-shaped suffix,
    or — for a path that actually exists under root — its content has a
    `#Preview` block or a `: View` conformance. Do NOT narrow this to `*View`
    only: SwiftUI views are frequently named `Card`/`Row`/`Tab`/`Screen`."""
    if not path.endswith(".swift"):
        return False
    stem = os.path.basename(path)[: -len(".swift")]
    if VIEW_SUFFIX_RE.search(stem):
        return True
    full = path if os.path.isabs(path) else os.path.join(root, path)
    text = _read_text_or_none(full) if os.path.isfile(full) else None
    return text is not None and ("#Preview" in text or ": View" in text)


def _has_preview_block(root, path):
    full = path if os.path.isabs(path) else os.path.join(root, path)
    text = _read_text_or_none(full) if os.path.isfile(full) else None
    return text is not None and "#Preview" in text


def _first_image_ref(text):
    m = IMG_REF_RE.search(text)
    if not m:
        return None
    return m.group(1) or m.group(2)


def _resolve_ref_relative_to(ref, source_path):
    full = ref if os.path.isabs(ref) else os.path.join(os.path.dirname(source_path), ref)
    return full if os.path.isfile(full) else None


def _resolve_design_image(root, design_analysis, design_doc):
    # (a) understand-design's screenshot output — already an image path.
    # Several runs leave several screenshots; the newest is the current design.
    shots = glob.glob(DESIGN_SCREENSHOT_GLOB)
    if shots:
        return max(shots, key=os.path.getmtime)
    # (b) the design-analysis doc Step 2 chose, or the single auto-detected one.
    da_path = design_analysis if design_analysis not in (None, "none") else None
    if da_path is None:
        candidates = sorted(glob.glob(os.path.join(root, "docs", "06-plans", "*-design-analysis.md")))
        if len(candidates) == 1:
            da_path = candidates[0]
    if da_path and os.path.isfile(da_path):
        ref = _first_image_ref(_read_text(da_path))
        if ref:
            found = _resolve_ref_relative_to(ref, da_path)
            if found:
                return found
    # (c) the design doc itself.
    if design_doc not in (None, "none") and os.path.isfile(design_doc):
        ref = _first_image_ref(_read_text(design_doc))
        if ref:
            found = _resolve_ref_relative_to(ref, design_doc)
            if found:
                return found
    return None


def cmd_visual_facts(plan_path, design_analysis=None, design_doc=None, root="."):
    if not os.path.isfile(plan_path):
        return {"ok": False, "errors": [f"no such file: {plan_path}"]}, 3
    tasks = parse_tasks(_read_text(plan_path))

    all_paths = []
    for t in tasks:
        all_paths.extend(_task_file_paths(t["body"]))

    views = []
    seen = set()
    for p in all_paths:
        if p in seen:
            continue
        seen.add(p)
        if _is_view_path(root, p):
            views.append(p)

    preview_views = [p for p in views if _has_preview_block(root, p)]
    apple_dev_installed = _apple_dev_installed()
    design_image = _resolve_design_image(root, design_analysis, design_doc)

    if not apple_dev_installed:
        skip_reason = "apple-dev not installed"
    elif not views:
        skip_reason = "non-UI phase"
    elif not design_image:
        skip_reason = "no design reference image"
    elif not preview_views:
        skip_reason = "no #Preview blocks"
    else:
        skip_reason = None

    return {
        "ok": True,
        "apple_dev_installed": apple_dev_installed,
        "views": views,
        "preview_views": preview_views,
        "design_image": design_image,
        "skip_reason": skip_reason,
    }, 0


def cmd_complete_gate(root):
    res, refusal = _load_for_write(root)
    if refusal:
        return refusal
    state = res["state"]
    errors = validate(state)
    if errors:
        # The gate's answer on a mistyped state would be meaningless — repair first.
        return {"ok": False, "errors": errors}, 3
    gate = complete_gate(state)
    return gate, (0 if gate["ok"] else 3)


# ---------------------------------------------------------------------------
# migrate / quarantine


def cmd_quarantine(root, target=None):
    if target is None:
        # Default path: only quarantine a file load() rejects (unparseable, not
        # UTF-8, duplicate keys, not an object — JSON or legacy .yml), and take
        # whichever state file it failed on. An explicit --target is the user
        # naming a file by hand and is trusted as-is.
        res = load(root)
        if not res.get("exists", True):
            return {"ok": False, "errors": ["no state file to quarantine"]}, 3
        if res.get("ok"):
            return {"ok": False, "errors": [
                "state file loads fine — quarantine only takes a file load() rejects "
                "(bad field values are repaired with `set` / `step --reason`); "
                "pass --target to quarantine a specific file anyway"]}, 3
        path = res["path"]
        reasons = list(res.get("errors", []))
    else:
        path = target
        reasons = []
        if not os.path.isfile(path):
            return {"ok": False, "errors": [f"no file at {path}"]}, 3
    ext = os.path.splitext(path)[1] or ".json"
    ts = time.strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(os.path.dirname(path), f"dev-workflow-state.broken-{ts}{ext}")
    n = 1
    while os.path.exists(dest):  # two quarantines in one second must not overwrite the first
        dest = os.path.join(os.path.dirname(path), f"dev-workflow-state.broken-{ts}-{n}{ext}")
        n += 1
    os.replace(path, dest)
    out = {"ok": True, "quarantined": dest}
    if reasons:
        out["reasons"] = reasons
    return out, 0


# ---------------------------------------------------------------------------
# CLI


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_root(parser):
        # Both `phase.py --root X status` (plan's own usage) and
        # `phase.py status --root X` (plan's real-path verify + the hook) must work.
        # default=SUPPRESS: if the subcommand's own --root is absent, don't touch
        # args.root at all, so the top-level value (or its default) survives.
        parser.add_argument("--root", default=argparse.SUPPRESS)

    p_status = sub.add_parser("status")
    add_root(p_status)
    p_status.add_argument("--hook", action="store_true")

    p_init = sub.add_parser("init")
    add_root(p_init)
    p_init.add_argument("--phase", type=int, required=True)
    p_init.add_argument("--name", required=True)
    p_init.add_argument("--dev-guide", required=True, dest="dev_guide")
    p_init.add_argument("--project")
    p_init.add_argument("--force", action="store_true")

    p_step = sub.add_parser("step")
    add_root(p_step)
    p_step.add_argument("target")
    p_step.add_argument("--reason")
    p_step.add_argument("--override", action="store_true")

    p_set = sub.add_parser("set")
    add_root(p_set)
    p_set.add_argument("pairs", nargs="+")

    p_note = sub.add_parser("note")
    add_root(p_note)
    p_note.add_argument("text")

    p_migrate = sub.add_parser("migrate")
    add_root(p_migrate)

    p_q = sub.add_parser("quarantine")
    add_root(p_q)
    p_q.add_argument("--target")

    p_guide = sub.add_parser("guide")
    add_root(p_guide)

    p_phases = sub.add_parser("phases")
    p_phases.add_argument("--dev-guide", required=True, dest="dev_guide")

    p_locate = sub.add_parser("locate")
    p_locate.add_argument("--dev-guide", required=True, dest="dev_guide")

    p_checkoff = sub.add_parser("check-off")
    p_checkoff.add_argument("--dev-guide", required=True, dest="dev_guide")
    p_checkoff.add_argument("--phase", type=int, required=True)
    p_checkoff.add_argument("--date")

    p_scopemode = sub.add_parser("scope-mode")
    p_scopemode.add_argument("--dev-guide", required=True, dest="dev_guide")
    p_scopemode.add_argument("--now")

    p_planfacts = sub.add_parser("plan-facts")
    p_planfacts.add_argument("--plan", required=True, dest="plan")
    p_planfacts.add_argument("--design-doc", dest="design_doc")
    p_planfacts.add_argument("--crystal", dest="crystal")

    p_uxmap = sub.add_parser("ux-map")
    p_uxmap.add_argument("--plan", required=True, dest="plan")
    p_uxmap.add_argument("--design-doc", required=True, dest="design_doc")

    p_visualfacts = sub.add_parser("visual-facts")
    add_root(p_visualfacts)
    p_visualfacts.add_argument("--plan", required=True, dest="plan")
    p_visualfacts.add_argument("--design-analysis", dest="design_analysis")
    p_visualfacts.add_argument("--design-doc", dest="design_doc")

    p_completegate = sub.add_parser("complete-gate")
    add_root(p_completegate)

    args = ap.parse_args(argv)
    root = os.path.abspath(args.root)

    try:
        if args.cmd == "status":
            if args.hook:
                line = hook_line(root)
                if line:
                    print(line)
                return 0
            out = status(root)
            print(json.dumps(out, ensure_ascii=False, default=_json_default))
            return 0 if out.get("ok") else 3

        if args.cmd == "init":
            out, code = cmd_init(root, args.phase, args.name, args.dev_guide, args.project, args.force)
        elif args.cmd == "step":
            out, code = cmd_step(root, args.target, args.reason, args.override)
        elif args.cmd == "set":
            out, code = cmd_set(root, args.pairs)
        elif args.cmd == "note":
            out, code = cmd_note(root, args.text)
        elif args.cmd == "migrate":
            out, code = cmd_migrate(root)
        elif args.cmd == "quarantine":
            out, code = cmd_quarantine(root, args.target)
        elif args.cmd == "guide":
            out, code = cmd_guide(root)
        elif args.cmd == "phases":
            out = phases(args.dev_guide)
            code = 0 if out.get("ok") else 3
        elif args.cmd == "locate":
            out, code = cmd_locate(args.dev_guide)
        elif args.cmd == "check-off":
            out, code = cmd_check_off(args.dev_guide, args.phase, args.date)
        elif args.cmd == "scope-mode":
            out, code = cmd_scope_mode(args.dev_guide, args.now)
        elif args.cmd == "plan-facts":
            out, code = cmd_plan_facts(args.plan, args.design_doc, args.crystal)
        elif args.cmd == "ux-map":
            out, code = cmd_ux_map(args.plan, args.design_doc)
        elif args.cmd == "visual-facts":
            out, code = cmd_visual_facts(args.plan, args.design_analysis, args.design_doc, root)
        elif args.cmd == "complete-gate":
            out, code = cmd_complete_gate(root)
        else:
            return 1
    except Exception as e:  # never let a state-file problem escape as a traceback
        print(json.dumps({"ok": False, "errors": [f"internal error: {e}"]}, ensure_ascii=False))
        return 3

    print(json.dumps(out, ensure_ascii=False, default=_json_default))
    return code


if __name__ == "__main__":
    sys.exit(main())
