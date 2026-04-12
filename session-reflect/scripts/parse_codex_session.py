#!/usr/bin/env python3
"""Parse a Codex session JSONL file into unified session summary JSON."""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from analyzer_version import ANALYZER_VERSION
from session_enrichment import apply_enrichment


def parse_codex_session(filepath):
    """Parse a Codex JSONL file and return unified session summary dict."""
    session_id = None
    cwd = None
    branch = None
    model = None
    timestamps = []
    user_turns = 0
    assistant_turns = 0
    tool_calls = Counter()
    tool_sequence = []
    user_prompts = []
    last_token_usage = None

    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            rtype = record.get("type")
            ts = record.get("timestamp")
            if ts:
                timestamps.append(ts)

            if rtype == "session_meta":
                payload = record.get("payload") or {}
                session_id = payload.get("id")
                cwd = payload.get("cwd")
                git_info = payload.get("git") or {}
                if isinstance(git_info, dict):
                    branch = git_info.get("branch")

            elif rtype == "turn_context":
                payload = record.get("payload") or {}
                if not model and payload.get("model"):
                    model = payload["model"]

            elif rtype == "response_item":
                payload = record.get("payload") or {}
                ptype = payload.get("type", "")

                if ptype == "message":
                    role = payload.get("role", "")
                    if role == "user":
                        user_turns += 1
                        text = _extract_codex_user_text(payload)
                        if text and len(user_prompts) < 10:
                            user_prompts.append(text[:500])
                    elif role in ("assistant", "developer"):
                        assistant_turns += 1

                elif ptype == "function_call":
                    tool_name = payload.get("name", "")
                    tool_calls[tool_name] += 1
                    tool_sequence.append(tool_name)

                elif ptype == "custom_tool_call":
                    tool_name = payload.get("name", "")
                    tool_calls[tool_name] += 1
                    tool_sequence.append(tool_name)

            elif rtype == "event_msg":
                payload = record.get("payload") or {}
                if payload.get("type") == "token_count":
                    info = payload.get("info") or {}
                    total = info.get("total_token_usage")
                    if total:
                        last_token_usage = total

    if not session_id:
        session_id = os.path.splitext(os.path.basename(filepath))[0]

    time_start = timestamps[0] if timestamps else None
    time_end = timestamps[-1] if timestamps else None
    duration_min = _calc_duration_min(time_start, time_end)

    tokens = _build_token_info(last_token_usage)

    return {
        "session_id": session_id,
        "source": "codex",
        "project": os.path.basename(cwd) if cwd else None,
        "project_path": cwd,
        "branch": branch,
        "model": model,
        "time": {
            "start": time_start,
            "end": time_end,
            "duration_min": duration_min,
        },
        "turns": {
            "user": user_turns,
            "assistant": assistant_turns,
        },
        "tokens": tokens,
        "tools": {
            "distribution": dict(tool_calls),
            "total_calls": sum(tool_calls.values()),
            "sequence": tool_sequence,
        },
        "files": {
            "read": [],
            "edited": [],
            "created": [],
        },
        "quality": {
            "repeated_edits": {},
            "bash_errors": 0,
            "build_attempts": 0,
            "build_failures": 0,
        },
        "assistant_turns": [],
        "plugin_events": [],
        "ai_behavior_audit": [],
        "analyzer_version": ANALYZER_VERSION,
        "session_dna": "mixed",
        "user_prompts": user_prompts,
        "task_summary": "",
        "corrections": [],
        "prompt_assessments": [],
        "process_gaps": [],
    }


def _extract_codex_user_text(payload):
    """Extract text from a Codex user message payload."""
    content = payload.get("content", [])
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for block in content:
            if isinstance(block, dict):
                if block.get("type") in ("input_text", "text"):
                    texts.append(block.get("text", ""))
            elif isinstance(block, str):
                texts.append(block)
        return " ".join(texts)
    return ""


def _build_token_info(last_token_usage):
    """Build unified token info from Codex cumulative token_count event."""
    if not last_token_usage:
        return {
            "input": None,
            "output": None,
            "cache_read": None,
            "cache_create": None,
            "cache_hit_rate": None,
        }

    input_tokens = last_token_usage.get("input_tokens", 0)
    cached = last_token_usage.get("cached_input_tokens", 0)
    output_tokens = last_token_usage.get("output_tokens", 0)
    reasoning = last_token_usage.get("reasoning_output_tokens", 0)

    cache_hit_rate = None
    if input_tokens > 0:
        cache_hit_rate = round(cached / input_tokens, 3)

    return {
        "input": input_tokens,
        "output": output_tokens + reasoning,
        "cache_read": cached,
        "cache_create": input_tokens - cached if input_tokens > cached else 0,
        "cache_hit_rate": cache_hit_rate,
    }


def _calc_duration_min(start_str, end_str):
    """Calculate duration in minutes between two ISO timestamps."""
    if not start_str or not end_str:
        return None
    try:
        start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        end = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        delta = (end - start).total_seconds() / 60
        return round(delta, 1)
    except (ValueError, TypeError):
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Parse a Codex session JSONL file into unified JSON"
    )
    parser.add_argument(
        "--input", required=True, help="Path to Codex session JSONL file"
    )
    parser.add_argument(
        "--output", default=None, help="Output JSON file (default: stdout)"
    )
    parser.add_argument(
        "--sqlite-db",
        default=None,
        help="Path to sessions.db to upsert results",
    )
    parser.add_argument(
        "--enrich",
        action="store_true",
        help="Invoke session-parser agent for dimension enrichment",
    )
    args = parser.parse_args()

    result = parse_codex_session(args.input)

    if args.sqlite_db:
        sys.path.insert(0, str(Path(__file__).parent))
        import sessions_db
        sessions_db.DB_PATH = Path(args.sqlite_db)
        sessions_db.init_db()
        # Flatten session data for upsert
        flat = dict(result)
        flat["time_start"] = result.get("time", {}).get("start")
        flat["time_end"] = result.get("time", {}).get("end")
        flat["duration_min"] = result.get("time", {}).get("duration_min")
        flat["turns_user"] = result.get("turns", {}).get("user")
        flat["turns_asst"] = result.get("turns", {}).get("assistant")
        flat["tokens_in"] = result.get("tokens", {}).get("input")
        flat["tokens_out"] = result.get("tokens", {}).get("output")
        flat["cache_read"] = result.get("tokens", {}).get("cache_read")
        flat["cache_create"] = result.get("tokens", {}).get("cache_create")
        flat["cache_hit_rate"] = result.get("tokens", {}).get("cache_hit_rate")
        flat["analyzer_version"] = result.get("analyzer_version", ANALYZER_VERSION)
        sessions_db.upsert_session(result["session_id"], flat)
        # Build tool call list with tool_name and file_path
        tool_list = []
        for name in result.get("tools", {}).get("sequence", []):
            tool_list.append({"tool_name": name, "file_path": None, "is_error": 0})
        sessions_db.upsert_tool_calls(result["session_id"], tool_list)

    if args.enrich:
        result, warning = apply_enrichment(result, db_path=args.sqlite_db)
        if warning:
            print(f"Warning: {warning}", file=sys.stderr)

    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
