#!/usr/bin/env python3
"""
Standalone backfill orchestrator for session-reflect.

Drives the full pipeline (discover -> parse -> heuristic audit -> persist) over historical
sessions, with per-session checkpointing for resume after interruption and version-aware
re-analysis.

Architecture C: LLM-based enrichment (dimensions, task_summary, session_dna) is NOT run
here. Backfill populates rule-based `ai_behavior_audit` rows and marks each session
`enrichment_pending = 1`. Users finish LLM enrichment incrementally via `/reflect --enrich`,
which dispatches the session-parser agent in the host Claude Code session.

Can be invoked directly (cron / launchd / external scheduler) or via /reflect --backfill.
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# Make sibling scripts importable
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import sessions_db  # noqa: E402
from analyzer_version import ANALYZER_VERSION  # noqa: E402
from compute_baselines import compute_baselines  # noqa: E402
from link_sessions import recompute_session_links  # noqa: E402

# Backfill runs rule-based audit only (no LLM calls, no network). Cost is the
# local CPU work of parsing JSONL + running regex-based audit. LLM enrichment
# cost is incurred later by /reflect --enrich on a per-session basis.
DEFAULT_BASELINE_WINDOW = "60d"


def _load_config():
    """Read session-reflect config.yaml for excluded_projects + back-compat ignore_patterns."""
    cfg_path = SCRIPT_DIR.parent / "config.yaml"
    excluded = []
    legacy = []
    if not cfg_path.exists():
        return excluded, legacy
    # Tolerant micro-parser to avoid yaml dependency
    in_excluded = False
    in_legacy = False
    for line in cfg_path.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if stripped.startswith("excluded_projects:"):
            in_excluded = True
            in_legacy = False
            continue
        if stripped.startswith("ignore_patterns:"):
            in_legacy = True
            in_excluded = False
            continue
        if line.startswith("  - ") or line.startswith("- "):
            value = stripped.lstrip("- ").strip()
            if in_excluded:
                excluded.append(value)
            elif in_legacy:
                legacy.append(value)
        else:
            in_excluded = False
            in_legacy = False
    return excluded, legacy


def discover_all(days=None, excluded=None, legacy=None):
    """Invoke extract-sessions.py to enumerate all candidate sessions.

    days=None means all-time. We pass --days 0 sentinel because extract-sessions.py's
    own --days default is 7 (not all-time); without an explicit value here, /reflect
    AND backfill default windows would diverge.
    """
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / "extract-sessions.py"),
        "--source", "all",
        "--format", "json",
    ]
    # Always pass --days: 0 means no time filter; otherwise the integer
    cmd += ["--days", str(days if days is not None else 0)]
    if excluded:
        cmd += ["--excluded-projects", *excluded]
    if legacy:
        cmd += ["--ignore-patterns", *legacy]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        print(f"extract-sessions.py failed: {proc.stderr}", file=sys.stderr)
        return []
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []


def resolve_discovery_days(days=None, full=False):
    """Translate CLI flags into the extract-sessions window argument."""
    if full:
        return None
    return days


def filter_to_pending(sessions, force_all=False):
    """Filter the candidate list to sessions that need analysis.

    A session is pending if any of:
    - No sessions row exists yet (never analyzed)
    - analysis_checkpoints row exists with re_analyze_pending = 1
    - No analysis_checkpoints row exists for an analyzed session
    """
    if force_all:
        return sessions
    pending_ids = set(sessions_db.get_pending_session_ids())
    # Sessions never seen by sessions.db are also pending
    known_ids = set(sessions_db.get_session_ids())
    out = []
    for s in sessions:
        sid = s.get("session_id")
        if sid in pending_ids or sid not in known_ids:
            out.append(s)
    return out


def parse_one(session_meta):
    """Run the appropriate parser on one session and upsert via --sqlite-db.

    Passes --enrich so the parser runs the local rule-based audit and marks
    the session `enrichment_pending=1`. No LLM call happens here.
    """
    src = session_meta.get("source")
    file_path = session_meta.get("file_path")
    if not file_path or not src:
        return False, "missing file_path or source"
    parser = "parse_claude_session.py" if src == "claude-code" else "parse_codex_session.py"
    cmd = [
        sys.executable,
        str(SCRIPT_DIR / parser),
        "--input", file_path,
        "--sqlite-db", str(sessions_db.DB_PATH),
        "--enrich",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        return False, proc.stderr.strip().splitlines()[-1] if proc.stderr else "parser failed"
    return True, None


def build_backfill_report(summary):
    """Render one backfill run summary as markdown."""
    lines = [
        "# session-reflect backfill report",
        "",
        f"- date: {summary['report_date']}",
        f"- analyzer_version: {summary['analyzer_version']}",
        f"- discovered: {summary['discovered']}",
        f"- pending: {summary['pending']}",
        f"- succeeded: {summary['succeeded']}",
        f"- failed: {summary['failed']}",
        f"- links_written: {summary['links_written']}",
        f"- baseline_rows_written: {summary['baseline_rows_written']}",
        f"- baseline_window: {summary['baseline_window']}",
        f"- pending_enrichment: {summary.get('pending_enrichment', 0)}",
        f"- duration_min: {summary['duration_min']:.2f}",
        "",
        "## Failures",
        "",
    ]
    if summary["failures"]:
        for item in summary["failures"]:
            lines.append(f"- {item['session_id']}: {item['error']}")
    else:
        lines.append("- none")
    lines.extend(["", "## Anomalies", ""])
    if summary["anomalies"]:
        for item in summary["anomalies"]:
            missing = ", ".join(item.get("missing", [])) or "none"
            invalid = ", ".join(item.get("invalid", [])) or "none"
            lines.append(f"- {item['session_id']}: missing={missing}; invalid={invalid}")
    else:
        lines.append("- none")
    lines.append("")
    return "\n".join(lines)


def write_backfill_report(summary, report_root=None, now=None):
    """Append a markdown report and return the written path."""
    report_dt = now or datetime.now()
    if report_root:
        root = Path(report_root).expanduser()
    else:
        default_db_path = Path("~/.claude/session-reflect/sessions.db").expanduser()
        if Path(sessions_db.DB_PATH).expanduser() == default_db_path:
            root = Path("~/.claude/session-reflect/backfill-reports").expanduser()
        else:
            root = Path(sessions_db.DB_PATH).expanduser().parent / "backfill-reports"
    root.mkdir(parents=True, exist_ok=True)
    report_path = root / f"{report_dt.strftime('%Y-%m-%d')}.md"
    content = build_backfill_report(summary)
    if report_path.exists():
        existing = report_path.read_text()
        if existing.strip():
            content = f"{existing.rstrip()}\n\n---\n\n{content}"
    report_path.write_text(content)
    return report_path


def main():
    parser = argparse.ArgumentParser(description="session-reflect backfill orchestrator")
    parser.add_argument("--days", type=int, default=None,
                        help="Lookback window in days (default: all-time)")
    parser.add_argument("--full", action="store_true",
                        help="Explicit all-time alias for historical backfill")
    parser.add_argument("--dry-run", action="store_true",
                        help="Report session count + cost estimate, no work")
    parser.add_argument("--resume", action="store_true",
                        help="Continue from analysis_checkpoints (default behavior; explicit flag for clarity)")
    parser.add_argument("--force-all", action="store_true",
                        help="Re-analyze ALL discovered sessions, ignoring checkpoints")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process at most N sessions this run (useful for batch chunks)")
    parser.add_argument("--bump-version", action="store_true",
                        help="Mark all checkpoints as re_analyze_pending=1 (use after analyzer changes)")
    args = parser.parse_args()

    # Ensure DB ready
    sessions_db.init_db()

    if args.bump_version:
        n = sessions_db.mark_re_analyze_pending(ANALYZER_VERSION)
        print(f"[backfill] Marked {n} sessions as re_analyze_pending (analyzer version: {ANALYZER_VERSION})")
        return

    excluded, legacy = _load_config()
    discovery_days = resolve_discovery_days(days=args.days, full=args.full)
    candidates = discover_all(days=discovery_days, excluded=excluded, legacy=legacy)
    pending = filter_to_pending(candidates, force_all=args.force_all)

    if args.limit:
        pending = pending[: args.limit]

    n = len(pending)
    if args.dry_run:
        print(f"[backfill] Discovered: {len(candidates)} candidates")
        print(f"[backfill] Pending (will be analyzed): {n}")
        print("[backfill] Cost: local rule-based audit only (no LLM calls).")
        print("[backfill] Run `/reflect --enrich` after backfill to finish LLM enrichment incrementally.")
        return

    if n == 0:
        print("[backfill] No pending sessions; nothing to do.")
        return

    print(f"[backfill] Starting: {n} sessions, analyzer_version={ANALYZER_VERSION}")
    started = time.time()
    ok = 0
    fail = 0
    failures = []
    succeeded_ids = []
    for i, s in enumerate(pending, start=1):
        sid = s.get("session_id")
        success, err = parse_one(s)
        if success:
            sessions_db.upsert_checkpoint(sid, ANALYZER_VERSION)
            ok += 1
            succeeded_ids.append(sid)
        else:
            fail += 1
            failures.append({"session_id": sid, "error": err})
            print(f"[backfill] FAIL {sid}: {err}", file=sys.stderr)
        # Progress every 25 sessions
        if i % 25 == 0:
            elapsed = time.time() - started
            rate = i / elapsed if elapsed > 0 else 0
            remaining = (n - i) / rate if rate > 0 else 0
            print(f"[backfill] {i}/{n} ({ok} ok, {fail} fail) -- eta {remaining/60:.1f}min")
    link_summary = recompute_session_links(
        target_session_ids=[s.get("session_id") for s in pending],
        db_path=sessions_db.DB_PATH,
    )
    print(
        "[backfill] Linking: "
        f"{link_summary['source_sessions']} source sessions, "
        f"{link_summary['links_written']} links written"
    )
    baseline_summary = compute_baselines(
        db_path=str(sessions_db.DB_PATH),
        window_spec=DEFAULT_BASELINE_WINDOW,
    )
    print(
        "[backfill] Baselines: "
        f"{baseline_summary['rows_written']} rows written "
        f"for window {baseline_summary['window_spec']}"
    )
    anomalies = sessions_db.get_backfill_anomalies(succeeded_ids)
    pending_enrichment = sessions_db.count_pending_enrichment()
    elapsed = time.time() - started
    report_summary = {
        "report_date": datetime.now().date().isoformat(),
        "analyzer_version": ANALYZER_VERSION,
        "discovered": len(candidates),
        "pending": n,
        "succeeded": ok,
        "failed": fail,
        "links_written": link_summary["links_written"],
        "baseline_rows_written": baseline_summary["rows_written"],
        "baseline_window": baseline_summary["window_spec"],
        "pending_enrichment": pending_enrichment,
        "failures": failures,
        "anomalies": anomalies,
        "duration_min": elapsed / 60,
    }
    report_path = write_backfill_report(report_summary)
    print(f"[backfill] Report: {report_path}")
    print(f"[backfill] Done: {ok} succeeded, {fail} failed in {elapsed/60:.1f}min")
    if pending_enrichment:
        print(
            f"[backfill] {pending_enrichment} sessions pending LLM enrichment — "
            "run `/reflect --enrich` to process incrementally."
        )


if __name__ == "__main__":
    main()
