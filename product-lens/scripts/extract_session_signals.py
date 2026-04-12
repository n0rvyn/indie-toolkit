#!/usr/bin/env python3
"""Read Claude/Codex session logs and derive product-lens progress signals.

This script is intentionally read-only for source session records. It reads:
- Claude project JSONL files under ~/.claude/projects/<project-dir>/
- Codex rollout JSONL files under ~/.codex/sessions/YYYY/MM/DD/

It can optionally publish a product-lens exchange artifact by calling the
existing publish_exchange.py helper.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any


THEME_KEYWORDS: dict[str, tuple[str, ...]] = {
    "planning": ("plan", "planning", "write-plan", "dev guide", "phase", "执行计划", "计划"),
    "review": ("review", "execution-review", "implementation-review", "plan-verifier", "审查", "reviewer"),
    "workflow": ("workflow", "artifact", "crystal", "crystallize", "pkos", "exchange"),
    "testing": ("test", "tests", "vitest", "playwright", "e2e", "验证"),
    "debugging": ("bug", "fix", "debug", "error", "失败", "报错"),
    "release": ("release", "deploy", "submission", "publish", "launch"),
    "research": ("research", "scan", "digest", "article", "summary", "调研", "总结"),
}

EDIT_TOOL_NAMES = {
    "Edit",
    "MultiEdit",
    "Write",
    "NotebookEditCell",
    "apply_patch",
}

NOISE_PREFIXES = (
    "warmup",
    "hook pretooluse:",
    "tool permission request failed:",
    "base directory for this skill:",
    "<local-command-caveat>",
    "<command-message>",
    "<command-name>",
    "<bash-input>",
    "<local-command-stdout>",
    "[request interrupted by user]",
    "[system context]",
    "(bash completed with no output)",
    "the file ",
    "no matches found",
    "no files found",
    "decompose this goal into ",
    "[image:",
    "[request interrupted by user",
    "<bash-stdout>",
    "the user just ",
    "analyze this task and output only a json execution plan.",
    "unknown slash command:",
    "this session is being continued from a previous conversation",
)

NOISE_EXACT = {
    "go ahead",
    "ok, go ahead",
    "okay, go ahead",
    "run phase",
    "hi",
    "hello",
    "say hi",
    "say hello",
    "test",
    "test step",
    "test task",
    "?",
    "？",
}


@dataclass
class SessionStats:
    session_id: str
    source: str
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    user_messages: int = 0
    assistant_messages: int = 0
    tool_calls: int = 0
    edit_calls: int = 0
    prompts: list[str] = field(default_factory=list)
    themes: Counter[str] = field(default_factory=Counter)

    def observe_timestamp(self, timestamp: datetime) -> None:
        if self.first_seen is None or timestamp < self.first_seen:
            self.first_seen = timestamp
        if self.last_seen is None or timestamp > self.last_seen:
            self.last_seen = timestamp


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract product-lens progress signals from session logs")
    parser.add_argument("--project-cwd", required=True, help="Absolute project cwd used by Claude/Codex sessions")
    parser.add_argument("--project-name", default=None, help="Display project name; defaults to cwd basename")
    parser.add_argument("--claude-project-dir", default=None, help="Override ~/.claude/projects/<encoded cwd>")
    parser.add_argument("--codex-sessions-root", default="~/.codex/sessions", help="Codex sessions root")
    parser.add_argument("--days", type=int, default=30, help="Lookback window in days")
    parser.add_argument("--limit-prompts", type=int, default=8, help="Max top prompts to report")
    parser.add_argument("--publish-progress-pulse", action="store_true", help="Publish progress-pulse artifact")
    parser.add_argument("--exchange-root", default="~/Obsidian/PKOS/.exchange/product-lens", help="Exchange root")
    parser.add_argument("--sync-notion", action="store_true", help="Request downstream Notion projection")
    parser.add_argument("--created", default=None, help="Artifact created date (YYYY-MM-DD)")
    return parser.parse_args()


def expand_path(raw: str | None) -> Path | None:
    if not raw:
        return None
    return Path(os.path.expanduser(raw)).resolve()


def encode_claude_project_dir(project_cwd: str) -> str:
    normalized = project_cwd.strip()
    return normalized.replace("/", "-")


def parse_timestamp(raw: str | None) -> datetime | None:
    if not raw:
        return None
    text = raw.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).astimezone(UTC)
    except ValueError:
        return None


def normalize_text(value: str) -> str:
    text = re.sub(r"\s+", " ", value.strip())
    return text


def extract_texts(content: Any) -> list[str]:
    if isinstance(content, str):
        text = normalize_text(content)
        return [text] if text else []

    texts: list[str] = []
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type in {"text", "input_text", "output_text"}:
                text = normalize_text(str(block.get("text", "")))
                if text:
                    texts.append(text)
    return texts


def classify_themes(text: str) -> set[str]:
    lowered = text.lower()
    matches = set()
    for theme, keywords in THEME_KEYWORDS.items():
        if any(keyword.lower() in lowered for keyword in keywords):
            matches.add(theme)
    return matches


def summarize_prompt(text: str) -> str:
    normalized = normalize_text(text)
    if len(normalized) <= 96:
        return normalized
    return normalized[:93].rstrip() + "..."


def is_noise_prompt(text: str) -> bool:
    lowered = normalize_text(text).lower()
    if len(lowered) < 8:
        return True
    if lowered in NOISE_EXACT:
        return True
    return any(lowered.startswith(prefix) for prefix in NOISE_PREFIXES)


def should_include(timestamp: datetime | None, cutoff: datetime) -> bool:
    return timestamp is not None and timestamp >= cutoff


def analyze_claude_project(project_dir: Path, project_cwd: str, cutoff: datetime) -> dict[str, SessionStats]:
    sessions: dict[str, SessionStats] = {}
    for path in sorted(project_dir.glob("*.jsonl")):
        if path.stat().st_size == 0:
            continue
        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    record = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                if record.get("cwd") != project_cwd:
                    continue
                if record.get("isSidechain") is True:
                    continue
                timestamp = parse_timestamp(record.get("timestamp"))
                if not should_include(timestamp, cutoff):
                    continue

                session_id = str(record.get("sessionId") or path.stem)
                stats = sessions.setdefault(session_id, SessionStats(session_id=session_id, source="claude"))
                assert timestamp is not None
                stats.observe_timestamp(timestamp)

                record_type = record.get("type")
                message = record.get("message")
                if not isinstance(message, dict):
                    continue

                role = message.get("role")
                if record_type == "user" and role == "user":
                    texts = extract_texts(message.get("content"))
                    if texts:
                        for text in texts:
                            if is_noise_prompt(text):
                                continue
                            stats.user_messages += 1
                            stats.prompts.append(text)
                            for theme in classify_themes(text):
                                stats.themes[theme] += 1
                elif record_type == "assistant" and role == "assistant":
                    stats.assistant_messages += 1
                    content = message.get("content")
                    if isinstance(content, list):
                        for block in content:
                            if not isinstance(block, dict):
                                continue
                            if block.get("type") == "tool_use":
                                stats.tool_calls += 1
                                tool_name = str(block.get("name", ""))
                                if tool_name in EDIT_TOOL_NAMES:
                                    stats.edit_calls += 1

    return sessions


def analyze_codex_sessions(root: Path, project_cwd: str, cutoff: datetime) -> dict[str, SessionStats]:
    sessions: dict[str, SessionStats] = {}
    for path in sorted(root.rglob("*.jsonl")):
        session_id: str | None = None
        session_stats: SessionStats | None = None
        matches_project = False

        with path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                raw_line = raw_line.strip()
                if not raw_line:
                    continue
                try:
                    record = json.loads(raw_line)
                except json.JSONDecodeError:
                    continue

                record_type = record.get("type")
                payload = record.get("payload")

                if record_type == "session_meta" and isinstance(payload, dict):
                    if payload.get("cwd") != project_cwd:
                        break
                    timestamp = parse_timestamp(record.get("timestamp"))
                    if not should_include(timestamp, cutoff):
                        break
                    matches_project = True
                    session_id = str(payload.get("id") or path.stem)
                    session_stats = sessions.setdefault(session_id, SessionStats(session_id=session_id, source="codex"))
                    assert timestamp is not None
                    session_stats.observe_timestamp(timestamp)
                    continue

                if not matches_project or session_stats is None:
                    continue

                timestamp = parse_timestamp(record.get("timestamp"))
                if not should_include(timestamp, cutoff):
                    continue
                assert timestamp is not None
                session_stats.observe_timestamp(timestamp)

                if record_type == "event_msg" and isinstance(payload, dict):
                    if payload.get("type") == "user_message":
                        text = normalize_text(str(payload.get("message", "")))
                        if text and not is_noise_prompt(text):
                            session_stats.user_messages += 1
                            session_stats.prompts.append(text)
                            for theme in classify_themes(text):
                                session_stats.themes[theme] += 1
                elif record_type == "response_item" and isinstance(payload, dict):
                    payload_type = payload.get("type")
                    if payload_type == "message" and payload.get("role") == "assistant":
                        session_stats.assistant_messages += 1
                    elif payload_type == "function_call":
                        session_stats.tool_calls += 1
                        name = str(payload.get("name", ""))
                        if name in EDIT_TOOL_NAMES:
                            session_stats.edit_calls += 1

    return sessions


def aggregate_summary(all_sessions: list[SessionStats], limit_prompts: int) -> dict[str, Any]:
    prompts = Counter()
    themes = Counter()
    active_days: set[str] = set()
    tool_calls = 0
    edit_calls = 0
    user_messages = 0
    assistant_messages = 0
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    by_source = Counter()

    for session in all_sessions:
        by_source[session.source] += 1
        tool_calls += session.tool_calls
        edit_calls += session.edit_calls
        user_messages += session.user_messages
        assistant_messages += session.assistant_messages
        themes.update(session.themes)
        for prompt in session.prompts:
            prompts[summarize_prompt(prompt)] += 1
        if session.first_seen:
            if first_seen is None or session.first_seen < first_seen:
                first_seen = session.first_seen
            active_days.add(session.first_seen.date().isoformat())
        if session.last_seen:
            if last_seen is None or session.last_seen > last_seen:
                last_seen = session.last_seen
            active_days.add(session.last_seen.date().isoformat())

    return {
        "session_count": len(all_sessions),
        "sessions_by_source": dict(by_source),
        "tool_calls": tool_calls,
        "edit_calls": edit_calls,
        "user_messages": user_messages,
        "assistant_messages": assistant_messages,
        "active_day_count": len(active_days),
        "first_seen": first_seen.isoformat() if first_seen else None,
        "last_seen": last_seen.isoformat() if last_seen else None,
        "top_prompts": prompts.most_common(limit_prompts),
        "top_themes": themes.most_common(),
    }


def derive_decision(summary: dict[str, Any]) -> tuple[str, list[str], str, list[str]]:
    session_count = int(summary["session_count"])
    active_days = int(summary["active_day_count"])
    tool_calls = int(summary["tool_calls"])
    edit_calls = int(summary["edit_calls"])
    top_themes = {theme: count for theme, count in summary["top_themes"]}
    dominant_theme = summary["top_themes"][0][0] if summary["top_themes"] else None
    leading_themes = [theme for theme, _count in summary["top_themes"][:3]]

    if session_count == 0:
        decision = "stalled"
    elif edit_calls == 0 and session_count >= 4 and (top_themes.get("planning", 0) + top_themes.get("review", 0)) >= session_count:
        decision = "drifting"
    elif active_days >= 3 and tool_calls >= 12:
        decision = "accelerating"
    elif session_count >= 2:
        decision = "steady"
    else:
        decision = "stalled"

    reasons = [
        f"Observed {session_count} recent Claude/Codex sessions across {active_days} active day(s).",
        f"Captured {tool_calls} tool calls, including {edit_calls} edit-like actions.",
    ]
    if dominant_theme:
        reasons.append(f"Leading recent themes were {', '.join(leading_themes)}.")

    if decision == "accelerating":
        risk = "Activity is strong, but session volume alone cannot prove shipped output."
        actions = [
            "Pair session activity with commit-level signals before upgrading the verdict.",
            "Check whether the heaviest session themes produced merged code, released features, or only analysis.",
        ]
    elif decision == "steady":
        risk = "Recent activity exists, but the session volume is not yet strong enough to prove momentum."
        actions = [
            "Check whether the most recent sessions resulted in shipped code or only discussion.",
            "Re-run the pulse after the next commit window.",
        ]
    elif decision == "drifting":
        risk = "The project shows many planning or review conversations without enough edit-like activity."
        actions = [
            "Collapse the current thread into one implementation target.",
            "Require the next review window to include concrete code changes or task completion.",
        ]
    else:
        risk = "Recent session activity is too weak to support an active progress signal."
        actions = [
            "Confirm whether work moved to another workspace or tool before stopping the track.",
            "Re-run after a fresh session window if work resumes.",
        ]

    return decision, reasons, risk, actions


def build_evidence(summary: dict[str, Any]) -> list[str]:
    evidence = [
        f"sessions={summary['session_count']}",
        f"sessions_by_source={summary['sessions_by_source']}",
        f"tool_calls={summary['tool_calls']}",
        f"edit_calls={summary['edit_calls']}",
        f"user_messages={summary['user_messages']}",
        f"assistant_messages={summary['assistant_messages']}",
        f"active_day_count={summary['active_day_count']}",
        f"last_seen={summary['last_seen']}",
    ]
    top_prompts = summary["top_prompts"]
    if top_prompts:
        evidence.append("top_prompts=" + " | ".join(f"{prompt} ({count})" for prompt, count in top_prompts[:5]))
    top_themes = summary["top_themes"]
    if top_themes:
        evidence.append("top_themes=" + ", ".join(f"{theme}:{count}" for theme, count in top_themes[:5]))
    return evidence


def publish_progress_pulse(
    args: argparse.Namespace,
    project_name: str,
    decision: str,
    reasons: list[str],
    risk: str,
    actions: list[str],
    evidence: list[str],
) -> int:
    publish_script = Path(__file__).with_name("publish_exchange.py")
    cmd = [
        "python3",
        str(publish_script),
        "--intent",
        "project_progress_pulse",
        "--decision",
        decision,
        "--confidence",
        "medium",
        "--project",
        project_name,
        "--project-root",
        args.project_cwd,
        "--window-days",
        str(args.days),
        "--risk",
        risk,
        "--exchange-root",
        args.exchange_root,
    ]
    created = args.created or datetime.now().date().isoformat()
    cmd.extend(["--created", created])
    if args.sync_notion:
        cmd.append("--sync-notion")
    for reason in reasons:
        cmd.extend(["--reason", reason])
    for action in actions:
        cmd.extend(["--action", action])
    for item in evidence:
        cmd.extend(["--evidence", item])
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip())
    return result.returncode


def main() -> int:
    args = parse_args()
    project_cwd = str(expand_path(args.project_cwd))
    project_name = args.project_name or Path(project_cwd).name

    claude_project_dir = expand_path(args.claude_project_dir)
    if claude_project_dir is None:
        claude_project_dir = Path.home() / ".claude" / "projects" / encode_claude_project_dir(project_cwd)

    codex_sessions_root = expand_path(args.codex_sessions_root)
    if codex_sessions_root is None:
        raise SystemExit("Failed to resolve Codex sessions root")

    cutoff = datetime.now(UTC) - timedelta(days=args.days)
    claude_sessions = analyze_claude_project(claude_project_dir, project_cwd, cutoff) if claude_project_dir.exists() else {}
    codex_sessions = analyze_codex_sessions(codex_sessions_root, project_cwd, cutoff)

    all_sessions = list(claude_sessions.values()) + list(codex_sessions.values())
    summary = aggregate_summary(all_sessions, args.limit_prompts)
    decision, reasons, risk, actions = derive_decision(summary)
    evidence = build_evidence(summary)

    output = {
        "project": project_name,
        "project_cwd": project_cwd,
        "window_days": args.days,
        "decision": decision,
        "summary": summary,
        "reasons": reasons,
        "risk": risk,
        "actions": actions,
        "evidence": evidence,
        "sources": {
            "claude_project_dir": str(claude_project_dir),
            "codex_sessions_root": str(codex_sessions_root),
        },
    }
    print(json.dumps(output, ensure_ascii=True, indent=2))

    if args.publish_progress_pulse:
        return publish_progress_pulse(args, project_name, decision, reasons, risk, actions, evidence)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
