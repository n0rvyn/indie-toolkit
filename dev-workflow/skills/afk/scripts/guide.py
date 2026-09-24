#!/usr/bin/env python3
"""guide.py — the fixed parts of afk's dev-guide mode.

Holds the resume-point decision, the blocking-DP sweep, the unit signals and
mechanical stop rows afk's Stop Policy reads, the recommended-DP write-back,
the crystal pointer, the stop card, and the `/goal` line for dev-guide mode.
Judgment (severity calls, whether a repair stays inside the declared Files,
what to tell the user) stays in afk/SKILL.md — this script is deterministic.

Every relative path argument (and state.plan_file) resolves against --root,
never against the caller's cwd.

Subcommands (each prints one JSON object on stdout):
    resume-point --dev-guide P [--root .]
        Which Setup item 1 branch applies: resume | phase-mismatch | init |
        check-off (state says `done` but the dev-guide still shows that phase
        unfinished — a crash between `step done` and `check-off`; never `init`
        here, it wipes plan_file/task_progress) | all-complete | state-error
        (state file unusable — follow run-phase Step 1 item 1). Also lists the
        slugs that already have a goal file, the per-phase step to enter at
        (`enter_at`: `pre-execute-gate` when the phase is at `verify` and
        verify-plan already ran), and the verify-plan report path parsed from
        state.verification_report ("<verdict> — <Report path>").
    sweep-dps [--dev-guide P] [--plans P ...] [--verify-report R ...] [--root .]
        Every open/resolved DP in the plans in scope — state.plan_file (only
        when its phase equals `phase.py locate`'s phase) plus every --plans
        path — and in every verify-plan report named with --verify-report
        (verify-plan writes its DPs into `.claude/reviews/plan-verifier-*.md`,
        not into the plan). A report DP is resolved by its own `**Chosen:**`,
        or by a resolved DP with the same id AND title in a swept plan. Never globs
        docs/06-plans/. A named file that does not exist → `missing`, exit 3.
    unit-signals --plan P [--verify-report R ...] [--must-fix N]
                 [--after-repair] [--root .]
        One plan's signals: verdict (approved | revised | partial | null, read
        from the plan's `## Verification` section only), verified
        (approved or revised), open_dps, checkpoint_markers, must_fix (echoed,
        never defaulted to 0), files, and stop_rows — the mechanical Stop
        Policy rows that fire: blocking-dp, verify-missing, author-checkpoint
        (fires at the segment boundary after its tasks, not now),
        must-fix-after-repair (only with --after-repair, i.e. the one REPAIR
        ONCE cycle already ran).
    adopt-dp --file P --dp DP-xxx [--label X] [--root .]
        Rewrites that one DP's `**Recommendation:**` /
        `**Recommendation (unverified):**` line to `**Chosen:** Option X …`.
        Without --label it adopts the recommendation and refuses a blocking DP
        (a blocking DP needs the user's answer, passed as --label).
        Idempotent: a DP that already has `**Chosen:**` is left alone.
        Exit 3 when the file or the DP is not found.
    goal-line --dev-guide P --slug S [--constraint C ...] [--reuse-constraints]
              [--root .]
        Composes the single `/goal` line dev-guide mode hands the user and
        writes it to .claude/afk/<slug>-goal.txt; the constraints go to
        .claude/afk/<slug>-constraints.json so a resume can re-pass them
        (--reuse-constraints: stored ones first, then new ones, deduped).
        The 4,000-character cap applies to the condition (the text after
        `/goal `). Pass constraints most → least load-bearing: over the cap
        they are dropped from the end, and `dropped` names them.
    crystal --slug S --path P [--root .]
        Records the crystal crystallize wrote for this run in
        .claude/afk/<slug>-crystal.txt; `card` points at it. Exit 3 when P
        does not exist.
    card --slug S --stopped-at X --why Y --next Z [--doc PATH]
         [--dont-repeat TEXT] [--root .]
        Writes/overwrites .claude/afk/<slug>-handoff.md: exactly the five
        schema fields plus at most one optional dont-repeat block. Resume with
        tells the user to type `/afk` (dev-guide mode resumes from state and
        hands back a fresh `/goal` line) and quotes the last goal line for
        reference.

Usage: python3 guide.py [--root DIR] <subcommand> ...
Exit codes: 0 success, 3 refused/invalid (bad args, no such file, missing
goal file for `card`).

Imports phase.py for dev-guide/state reads (never re-parses them) and
compute_checkpoints.py for task bodies/checkpoint markers — the same way
lint_plan.py imports compute_checkpoints.py. Read-only over phase.py's state
file: this script never writes .claude/dev-workflow-state.json.
"""

import argparse
import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "run-phase", "scripts"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "execute-plan", "scripts"))
import phase  # noqa: E402
from compute_checkpoints import parse_tasks  # noqa: E402

GOAL_CONDITION_CAP = 4000
GOAL_PREFIX = "/goal "
DONT_REPEAT_HEADING = "## ⛔ 别再跑一遍的"

DECISIONS_HEADING_RE = re.compile(r"^## Decisions\s*$", re.MULTILINE)
VERIFICATION_HEADING_RE = re.compile(r"^## Verification\s*$", re.MULTILINE)
HEADING2_RE = re.compile(r"^## ", re.MULTILINE)
# `### [DP-001] … -- Already resolved` (the verifier's reference form) has no
# severity suffix and is deliberately not matched: it is not a live DP.
DP_HEADING_RE = re.compile(r"^### \[(DP-\d+)\] (.+) \((blocking|recommended)\)\s*$", re.MULTILINE)
ANY_H3_OR_H2_RE = re.compile(r"^#{2,3} ", re.MULTILINE)
CHOSEN_RE = re.compile(r"^\*\*Chosen:\*\*", re.MULTILINE)
RECOMMENDATION_LINE_RE = re.compile(r"^\*\*Recommendation(?: \(unverified\))?:\*\*[ \t]*(.*)$", re.MULTILINE)
OPTION_LABEL_RE = re.compile(r"^(?:Option\s+)?([A-Z][A-Z+]*)\b\s*(.*)$")
# verify-plan Step 4 writes `- **Verdict:** Approved`; its completion criteria
# add `Verdict: Revised` and a "partial" verdict. Real plans carry both the
# bulleted-bold and the plain form.
VERDICT_RE = re.compile(r"^\s*(?:-\s*)?(?:\*\*)?Verdict:(?:\*\*)?\s*(Approved|Revised|partial)\b",
                        re.MULTILINE | re.IGNORECASE)


def _section_after(text, heading_re):
    """Text from a heading match to the next `## ` heading (or EOF). None when
    the heading itself is absent."""
    m = heading_re.search(text)
    if not m:
        return None
    tail = text[m.end():]
    m2 = HEADING2_RE.search(tail)
    return tail[: m2.start()] if m2 else tail


def _read_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _abs(root, path):
    """Resolve a path argument against the project root, never against cwd."""
    if path is None:
        return None
    return os.path.normpath(path if os.path.isabs(path) else os.path.join(root, path))


def _afk_path(root, name):
    return os.path.join(root, ".claude", "afk", name)


def _norm_title(title):
    return " ".join(title.split()).casefold()


# ---------------------------------------------------------------------------
# DP parsing (shared by sweep-dps, unit-signals, adopt-dp)


def _dp_blocks(text):
    """[(match, body_start, body_end)] for every live DP heading inside the
    `## Decisions` section (offsets into `text`). [] when there is no such
    section. A block ends at the next `##`/`###` heading."""
    m = DECISIONS_HEADING_RE.search(text)
    if not m:
        return []
    sec_start = m.end()
    m2 = HEADING2_RE.search(text, sec_start)
    sec_end = m2.start() if m2 else len(text)
    out = []
    for hm in DP_HEADING_RE.finditer(text, sec_start, sec_end):
        nxt = ANY_H3_OR_H2_RE.search(text, hm.end(), sec_end)
        out.append((hm, hm.end(), nxt.start() if nxt else sec_end))
    return out


def _parse_decisions(text):
    """[{id, title, severity, resolved}] from a `## Decisions` section."""
    dps = []
    for hm, b0, b1 in _dp_blocks(text):
        dps.append({
            "id": hm.group(1),
            "title": hm.group(2).strip(),
            "severity": hm.group(3),
            "resolved": bool(CHOSEN_RE.search(text, b0, b1)),
        })
    return dps


# ---------------------------------------------------------------------------
# sweep-dps


def _state_plan_path(root, dev_guide):
    """state.plan_file (absolute), only when its phase equals `locate`'s phase."""
    st = phase.status(root)
    state = st.get("state") if isinstance(st.get("state"), dict) else None
    if not state or not state.get("plan_file"):
        return None
    loc, _code = phase.cmd_locate(dev_guide)
    if loc.get("ok") and loc.get("phase") and loc["phase"].get("n") == state.get("current_phase"):
        return _abs(root, state["plan_file"])
    return None


def _sweep(root, dev_guide=None, plans=None, reports=None):
    missing = []
    plan_paths = []
    if dev_guide:
        dg = _abs(root, dev_guide)
        if not os.path.isfile(dg):
            missing.append(dg)
        else:
            sp = _state_plan_path(root, dg)
            if sp:
                plan_paths.append(sp)
    for p in plans or []:
        ap = _abs(root, p)
        if ap not in plan_paths:
            plan_paths.append(ap)
    report_paths = []
    for r in reports or []:
        ar = _abs(root, r)
        if ar not in report_paths:
            report_paths.append(ar)

    dps = []
    # (id, normalized title) -> plan path that resolved it. Title alone is not
    # enough: a new blocking DP that reuses an old title must stay open.
    resolved_titles = {}
    plans_swept = 0
    for p in plan_paths:
        if not os.path.isfile(p):
            missing.append(p)
            continue
        plans_swept += 1
        for d in _parse_decisions(_read_text(p)):
            dps.append({**d, "file": p, "source": "plan"})
            if d["resolved"]:
                resolved_titles.setdefault((d["id"], _norm_title(d["title"])), p)

    reports_swept = 0
    for r in report_paths:
        if not os.path.isfile(r):
            missing.append(r)
            continue
        reports_swept += 1
        for d in _parse_decisions(_read_text(r)):
            entry = {**d, "file": r, "source": "verify-report"}
            key = (d["id"], _norm_title(d["title"]))
            if not d["resolved"] and key in resolved_titles:
                entry["resolved"] = True
                entry["resolved_via"] = resolved_titles[key]
            dps.append(entry)

    return {
        "ok": not missing,
        "plans_swept": plans_swept,
        "reports_swept": reports_swept,
        "open_blocking": sum(1 for d in dps if d["severity"] == "blocking" and not d["resolved"]),
        "open_recommended": sum(1 for d in dps if d["severity"] == "recommended" and not d["resolved"]),
        "resolved": sum(1 for d in dps if d["resolved"]),
        "dps": dps,
        "missing": missing,
    }


def cmd_sweep_dps(root, dev_guide=None, plans=None, reports=None):
    out = _sweep(root, dev_guide, plans, reports)
    return out, (3 if out["missing"] else 0)


# ---------------------------------------------------------------------------
# unit-signals


def _verdict(text):
    section = _section_after(text, VERIFICATION_HEADING_RE)
    if section is None:
        return None
    m = VERDICT_RE.search(section)
    return m.group(1).lower() if m else None


def cmd_unit_signals(root, plan, reports=None, must_fix=None, after_repair=False):
    if after_repair and must_fix is None:
        return {"ok": False, "errors": ["--after-repair needs --must-fix N (the re-review's count)"]}, 3
    plan_abs = _abs(root, plan)
    if not os.path.isfile(plan_abs):
        return {"ok": False, "errors": [f"no such file: {plan_abs}"], "missing": [plan_abs]}, 3
    text = _read_text(plan_abs)
    verdict = _verdict(text)
    verified = verdict in ("approved", "revised")

    sweep = _sweep(root, dev_guide=None, plans=[plan_abs], reports=reports)
    if sweep["missing"]:
        return {"ok": False, "errors": [f"no such file: {m}" for m in sweep["missing"]],
                "missing": sweep["missing"]}, 3
    open_dps = {k: sweep[k] for k in ("plans_swept", "reports_swept", "open_blocking",
                                      "open_recommended", "resolved", "dps")}

    tasks = parse_tasks(text)
    checkpoint_markers = [t["id"] for t in tasks if t["has_marker"]]
    files = []
    for t in tasks:
        for f in phase._task_file_paths(t["body"]):
            if f not in files:
                files.append(f)

    stop_rows = []
    blocking = [{"file": d["file"], "id": d["id"], "title": d["title"]}
                for d in sweep["dps"] if d["severity"] == "blocking" and not d["resolved"]]
    if blocking:
        stop_rows.append({"row": "blocking-dp", "fires": "now", "dps": blocking})
    if not verified:
        stop_rows.append({"row": "verify-missing", "fires": "before execute", "verdict": verdict})
    if checkpoint_markers:
        stop_rows.append({"row": "author-checkpoint", "tasks": checkpoint_markers,
                          "fires": "at the segment boundary after these tasks' batch completes"})
    if after_repair and must_fix and must_fix > 0:
        stop_rows.append({"row": "must-fix-after-repair", "fires": "now", "must_fix": must_fix})

    return {
        "ok": True,
        "verdict": verdict,
        "verified": verified,
        "open_dps": open_dps,
        "checkpoint_markers": checkpoint_markers,
        "must_fix": must_fix,
        "files": files,
        "stop_rows": stop_rows,
    }, 0


# ---------------------------------------------------------------------------
# adopt-dp


def cmd_adopt_dp(root, file, dp_id, label=None):
    path = _abs(root, file)
    if not os.path.isfile(path):
        return {"ok": False, "errors": [f"no such file: {path}"]}, 3
    text = _read_text(path)
    block = next(((hm, b0, b1) for hm, b0, b1 in _dp_blocks(text) if hm.group(1) == dp_id), None)
    if block is None:
        return {"ok": False, "errors": [f"{dp_id} not found in the `## Decisions` section of {path}"]}, 3
    hm, b0, b1 = block
    severity = hm.group(3)
    if CHOSEN_RE.search(text, b0, b1):
        return {"ok": True, "file": path, "dp": dp_id, "changed": False, "already_chosen": True}, 0

    rec = RECOMMENDATION_LINE_RE.search(text, b0, b1)
    if label is None:
        if severity == "blocking":
            return {"ok": False, "errors": [
                f"{dp_id} is blocking — it needs the user's answer; pass --label"]}, 3
        if rec is None:
            return {"ok": False, "errors": [f"{dp_id} has no **Recommendation:** line to adopt"]}, 3
        body = rec.group(1).strip()
        lm = OPTION_LABEL_RE.match(body)
        chosen = f"**Chosen:** Option {lm.group(1)}" + (f" {lm.group(2)}" if lm.group(2) else "") \
            if lm else f"**Chosen:** {body}"
        chosen += " (adopted recommendation — afk dev-guide mode)"
    else:
        chosen = f"**Chosen:** Option {label}"

    if rec is not None:
        new_text = text[:rec.start()] + chosen + text[rec.end():]
    else:  # user answer on a DP with no recommendation line: append to the block
        insert_at = b1
        prefix = "" if text[:insert_at].endswith("\n") else "\n"
        new_text = text[:insert_at] + prefix + chosen + "\n" + text[insert_at:]
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_text)
    return {"ok": True, "file": path, "dp": dp_id, "changed": True, "chosen_line": chosen}, 0


# ---------------------------------------------------------------------------
# goal-line


def _phase_py_abs():
    return os.path.abspath(os.path.join(HERE, "..", "..", "run-phase", "scripts", "phase.py"))


def _compose_condition(abs_phase_py, abs_dev_guide, slug, constraints):
    constraint_seg = "；".join(constraints)
    cond = (
        "同时满足：(1) python3 " + abs_phase_py + " locate --dev-guide " + abs_dev_guide +
        " 输出 all_complete: true；(2) 最后一个 phase 的 review-execution gated 返回无 must-fix；"
        "证据是这两条命令/返回的原始输出，逐条贴全，不接受摘要"
    )
    if constraint_seg:
        cond += "；" + constraint_seg
    cond += (
        "；或本轮回复里逐字给出 ## 终止：{原因} 一节并贴出该轮原始输出"
        "（同一份内容同时写进 .claude/afk/" + slug + ".md）"
    )
    return cond


def cmd_goal_line(root, dev_guide, slug, constraints=None, reuse=False):
    constraints_path = _afk_path(root, f"{slug}-constraints.json")
    given = []
    if reuse:
        if not os.path.isfile(constraints_path):
            return {"ok": False, "errors": [
                f"--reuse-constraints: no stored constraints at {constraints_path}"]}, 3
        with open(constraints_path, "r", encoding="utf-8") as f:
            given = list(json.load(f))
    for c in constraints or []:
        if c not in given:
            given.append(c)

    abs_phase_py = _phase_py_abs()
    abs_dev_guide = _abs(root, dev_guide)
    remaining = list(given)
    dropped = []
    cond = _compose_condition(abs_phase_py, abs_dev_guide, slug, remaining)
    while len(cond) > GOAL_CONDITION_CAP and remaining:
        dropped.append(remaining.pop())
        cond = _compose_condition(abs_phase_py, abs_dev_guide, slug, remaining)
    line = GOAL_PREFIX + cond

    os.makedirs(os.path.dirname(constraints_path), exist_ok=True)
    path = _afk_path(root, f"{slug}-goal.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write(line)
    with open(constraints_path, "w", encoding="utf-8") as f:
        json.dump(given, f, ensure_ascii=False, indent=2)

    return {"ok": True, "line": line, "chars": len(cond), "constraints": given,
            "dropped": dropped, "path": path, "constraints_path": constraints_path}, 0


# ---------------------------------------------------------------------------
# crystal


def cmd_crystal(root, slug, path):
    p = _abs(root, path)
    if not os.path.isfile(p):
        return {"ok": False, "errors": [f"no such file: {p}"]}, 3
    rec = _afk_path(root, f"{slug}-crystal.txt")
    os.makedirs(os.path.dirname(rec), exist_ok=True)
    with open(rec, "w", encoding="utf-8") as f:
        f.write(p + "\n")
    return {"ok": True, "crystal": p, "path": rec}, 0


def _recorded_crystal(root, slug):
    rec = _afk_path(root, f"{slug}-crystal.txt")
    if not os.path.isfile(rec):
        return None
    p = _read_text(rec).strip()
    return p or None


# ---------------------------------------------------------------------------
# card


def _state_file_path(root, st):
    if st.get("path"):
        return st["path"]
    if st.get("source") == "yaml":
        return phase._yaml_path(root)
    return phase._json_path(root)


def cmd_card(root, slug, stopped_at, why, next_action, doc=None, dont_repeat=None):
    goal_path = _afk_path(root, f"{slug}-goal.txt")
    if not os.path.isfile(goal_path):
        return {"ok": False, "errors": [
            f"no goal file at {goal_path} — run `guide.py goal-line` first"]}, 3
    last_goal_line = _read_text(goal_path).strip()

    next_text = next_action
    if doc:
        next_text = f"{next_action} — {doc}"

    pointers = []
    run_log = _afk_path(root, f"{slug}.md")
    if os.path.isfile(run_log):
        pointers.append(("run-log", run_log))
    crystal = _recorded_crystal(root, slug)
    if crystal:
        pointers.append(("crystal", crystal))
    checkpoint = os.path.join(root, ".claude", "execute-plan-checkpoint.json")
    if os.path.isfile(checkpoint):
        pointers.append(("checkpoint", checkpoint))
    st = phase.status(root)
    if st.get("exists"):
        pointers.append(("state", _state_file_path(root, st)))
        state = st.get("state") if isinstance(st.get("state"), dict) else None
        plan_file = state.get("plan_file") if state else None
        if plan_file:
            pointers.append(("plan", _abs(root, plan_file)))

    lines = [f"# afk handoff — {slug}", ""]
    lines.append(f"- **Stopped at:** {stopped_at}")
    lines.append(f"- **Why:** {why}")
    lines.append(f"- **Next action:** {next_text}")
    lines.append("- **Pointers:**")
    for label, p in pointers:
        lines.append(f"  - {label}: {p}")
    lines.append("- **Resume with:** type `/afk` — dev-guide mode resumes from "
                 "`.claude/dev-workflow-state.json` and hands back a fresh `/goal` line; paste that line.")
    lines.append(f"  - last goal line (reference only — paste the fresh one): {last_goal_line}")
    if dont_repeat:
        lines.append("")
        lines.append(DONT_REPEAT_HEADING)
        lines.append(dont_repeat)

    card_path = _afk_path(root, f"{slug}-handoff.md")
    os.makedirs(os.path.dirname(card_path), exist_ok=True)
    with open(card_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    return {"ok": True, "path": card_path, "last_goal_line": last_goal_line,
            "pointers": {label: p for label, p in pointers}}, 0


# ---------------------------------------------------------------------------
# resume-point


def cmd_resume_point(root, dev_guide):
    dg = _abs(root, dev_guide)
    slugs = sorted(os.path.basename(p)[: -len("-goal.txt")]
                   for p in glob.glob(_afk_path(root, "*-goal.txt")))
    out = {"ok": True, "dev_guide": dg, "slugs": slugs}

    st = phase.status(root)
    if st.get("exists") and not st.get("ok"):
        return {**out, "branch": "state-error", "errors": st.get("errors", [])}, 0
    if st.get("source") == "yaml" or st.get("legacy_leftover"):
        out["migrate_first"] = True  # run-phase Step 1 item 1: `phase.py migrate`

    ph = phase.phases(dg)
    if not ph.get("ok"):
        return {**out, "ok": False, "branch": "no-target",
                "errors": [ph.get("unparseable_reason", "dev-guide unreadable")]}, 3
    remaining = [p for p in ph["phases"] if not p["complete"]]
    out["remaining_phases"] = len(remaining)
    if not remaining:
        return {**out, "branch": "all-complete", "locate_phase": None}, 0
    loc = remaining[0]
    out["locate_phase"] = {k: loc[k] for k in ("n", "name", "checked", "total")}

    state = st.get("state") if st.get("exists") else None
    if not state:
        return {**out, "branch": "init"}, 0
    step = st.get("step")
    out["state_phase"] = state.get("current_phase")
    out["phase_step"] = step
    same_phase = state.get("current_phase") == loc["n"]
    if step in ("done", "finalized"):
        if step == "done" and same_phase:
            return {**out, "branch": "check-off"}, 0
        return {**out, "branch": "init"}, 0
    vr = state.get("verification_report")
    out["verify_report"] = _report_path_from(root, vr)
    # verify-plan already ran for this phase (item 2 records "<verdict> — <Report path>"):
    # enter at the pre-execute gate, not at verify — a second verify round breaks
    # verify-plan's one-round rule, and a fresh verifier re-raises the DP the user
    # just answered in the report (it reads resolved DPs from the plan only).
    out["enter_at"] = "pre-execute-gate" if step == "verify" and vr else step
    return {**out, "branch": "resume" if same_phase else "phase-mismatch"}, 0


def _report_path_from(root, verification_report):
    """The Report path afk writes into state.verification_report as
    "<verdict> — <path>"; None when absent or not on disk."""
    if not isinstance(verification_report, str) or " — " not in verification_report:
        return None
    p = _abs(root, verification_report.rsplit(" — ", 1)[1].strip().strip("`"))
    return p if os.path.isfile(p) else None


# ---------------------------------------------------------------------------
# CLI


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=".")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_root(parser):
        parser.add_argument("--root", default=argparse.SUPPRESS)

    p_res = sub.add_parser("resume-point")
    add_root(p_res)
    p_res.add_argument("--dev-guide", required=True, dest="dev_guide")

    p_sweep = sub.add_parser("sweep-dps")
    add_root(p_sweep)
    p_sweep.add_argument("--dev-guide", dest="dev_guide")
    p_sweep.add_argument("--plans", nargs="*", action="extend", default=[])
    p_sweep.add_argument("--verify-report", dest="reports", action="append", default=[])

    p_unit = sub.add_parser("unit-signals")
    add_root(p_unit)
    p_unit.add_argument("--plan", required=True)
    p_unit.add_argument("--verify-report", dest="reports", action="append", default=[])
    p_unit.add_argument("--must-fix", type=int, dest="must_fix", default=None)
    p_unit.add_argument("--after-repair", action="store_true", dest="after_repair")

    p_adopt = sub.add_parser("adopt-dp")
    add_root(p_adopt)
    p_adopt.add_argument("--file", required=True)
    p_adopt.add_argument("--dp", required=True)
    p_adopt.add_argument("--label")

    p_goal = sub.add_parser("goal-line")
    add_root(p_goal)
    p_goal.add_argument("--dev-guide", required=True, dest="dev_guide")
    p_goal.add_argument("--slug", required=True)
    p_goal.add_argument("--constraint", dest="constraints", action="append", default=[])
    p_goal.add_argument("--reuse-constraints", action="store_true", dest="reuse")

    p_cry = sub.add_parser("crystal")
    add_root(p_cry)
    p_cry.add_argument("--slug", required=True)
    p_cry.add_argument("--path", required=True)

    p_card = sub.add_parser("card")
    add_root(p_card)
    p_card.add_argument("--slug", required=True)
    p_card.add_argument("--stopped-at", required=True, dest="stopped_at")
    p_card.add_argument("--why", required=True)
    p_card.add_argument("--next", required=True, dest="next_action")
    p_card.add_argument("--doc")
    p_card.add_argument("--dont-repeat", dest="dont_repeat")

    args = ap.parse_args(argv)
    root = os.path.abspath(args.root)

    try:
        if args.cmd == "resume-point":
            out, code = cmd_resume_point(root, args.dev_guide)
        elif args.cmd == "sweep-dps":
            out, code = cmd_sweep_dps(root, args.dev_guide, args.plans, args.reports)
        elif args.cmd == "unit-signals":
            out, code = cmd_unit_signals(root, args.plan, args.reports, args.must_fix, args.after_repair)
        elif args.cmd == "adopt-dp":
            out, code = cmd_adopt_dp(root, args.file, args.dp, args.label)
        elif args.cmd == "goal-line":
            out, code = cmd_goal_line(root, args.dev_guide, args.slug, args.constraints, args.reuse)
        elif args.cmd == "crystal":
            out, code = cmd_crystal(root, args.slug, args.path)
        elif args.cmd == "card":
            out, code = cmd_card(root, args.slug, args.stopped_at, args.why, args.next_action,
                                  args.doc, args.dont_repeat)
        else:
            return 1
    except Exception as e:  # never let a bad input escape as a traceback
        print(json.dumps({"ok": False, "errors": [f"internal error: {e}"]}, ensure_ascii=False))
        return 3

    print(json.dumps(out, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
