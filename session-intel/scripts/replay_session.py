#!/usr/bin/env python3
"""Parse a session JSONL file and output structured replay data."""

import argparse
import json
import os
import sys


def replay_session(filepath, detail="standard"):
    """Parse session JSONL and return structured replay data.

    Args:
        filepath: path to session JSONL file
        detail: summary | standard | verbose

    Returns:
        dict with header, turns, files, tool_sequence
    """
    records = []
    source = "claude-code"

    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                records.append(record)
            except json.JSONDecodeError:
                continue

    # Detect source format
    if records and records[0].get("type") == "session_meta":
        source = "codex"

    if source == "claude-code":
        return _replay_claude(records, detail)
    else:
        return _replay_codex(records, detail)


def _replay_claude(records, detail):
    """Build replay data from Claude Code JSONL."""
    header = {
        "session_id": None, "project": None, "project_path": None,
        "branch": None, "model": None, "duration_min": None,
    }
    turns = []
    current_turn = None
    files_touched = {}
    tool_sequence = []
    total_input = 0
    total_output = 0
    timestamps = []
    assistant_ids = set()

    for r in records:
        rtype = r.get("type")
        ts = r.get("timestamp")
        if ts:
            timestamps.append(ts)

        if not header["session_id"] and r.get("sessionId"):
            header["session_id"] = r["sessionId"]
        if not header["project_path"] and r.get("cwd"):
            header["project_path"] = r["cwd"]
            header["project"] = os.path.basename(r["cwd"])
        if not header["branch"] and r.get("gitBranch"):
            header["branch"] = r["gitBranch"]

        if rtype == "user":
            msg = r.get("message", {})
            content = msg.get("content", "")
            text = _extract_text(content)
            if text:
                current_turn = {
                    "number": len(turns) + 1,
                    "timestamp": ts,
                    "user_message": text[:2000] if detail != "verbose" else text,
                    "assistant_actions": [],
                }
                turns.append(current_turn)

        elif rtype == "assistant":
            msg = r.get("message", {})
            msg_id = msg.get("id")
            if msg_id:
                assistant_ids.add(msg_id)
            if not header["model"] and msg.get("model"):
                header["model"] = msg["model"]

            usage = msg.get("usage", {})
            total_input += usage.get("input_tokens", 0)
            total_output += usage.get("output_tokens", 0)

            for block in msg.get("content", []):
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "text" and current_turn:
                    text = block.get("text", "")
                    if text.strip():
                        truncated = text[:200] if detail == "standard" else (text[:500] if detail == "verbose" else text[:100])
                        current_turn["assistant_actions"].append({
                            "type": "text", "content": truncated
                        })
                elif block.get("type") == "tool_use" and current_turn:
                    name = block.get("name", "")
                    inp = block.get("input", {})
                    tool_sequence.append(name)
                    action = {"type": "tool", "name": name}

                    if detail == "verbose":
                        action["input"] = {k: str(v)[:500] for k, v in inp.items()} if isinstance(inp, dict) else str(inp)[:500]
                    elif detail == "standard":
                        if isinstance(inp, dict) and "file_path" in inp:
                            action["file"] = inp["file_path"]
                        elif isinstance(inp, dict) and "command" in inp:
                            action["command"] = str(inp["command"])[:100]

                    current_turn["assistant_actions"].append(action)

                    # Track files
                    if isinstance(inp, dict) and "file_path" in inp:
                        fp = inp["file_path"]
                        if fp not in files_touched:
                            files_touched[fp] = {"read": 0, "edit": 0, "create": 0}
                        if name == "Read":
                            files_touched[fp]["read"] += 1
                        elif name == "Edit":
                            files_touched[fp]["edit"] += 1
                        elif name == "Write":
                            files_touched[fp]["create"] += 1

    if timestamps:
        header["time_start"] = timestamps[0]
        header["time_end"] = timestamps[-1]
        try:
            from datetime import datetime
            start = datetime.fromisoformat(timestamps[0].replace("Z", "+00:00"))
            end = datetime.fromisoformat(timestamps[-1].replace("Z", "+00:00"))
            header["duration_min"] = round((end - start).total_seconds() / 60, 1)
        except (ValueError, TypeError):
            pass

    header["user_turns"] = len(turns)
    header["assistant_turns"] = len(assistant_ids)
    header["total_input_tokens"] = total_input
    header["total_output_tokens"] = total_output

    return {
        "header": header,
        "turns": turns if detail != "summary" else [],
        "files": files_touched,
        "tool_sequence": tool_sequence if detail != "summary" else [],
        "turn_count": len(turns),
    }


def _replay_codex(records, detail):
    """Build replay data from Codex JSONL."""
    header = {
        "session_id": None, "project": None, "project_path": None,
        "branch": None, "model": None, "duration_min": None,
    }
    turns = []
    current_turn = None
    tool_sequence = []
    timestamps = []

    for r in records:
        rtype = r.get("type")
        ts = r.get("timestamp")
        if ts:
            timestamps.append(ts)

        if rtype == "session_meta":
            p = r.get("payload", {})
            header["session_id"] = p.get("id")
            header["project_path"] = p.get("cwd")
            if header["project_path"]:
                header["project"] = os.path.basename(header["project_path"])
            git = p.get("git", {})
            if isinstance(git, dict):
                header["branch"] = git.get("branch")

        elif rtype == "turn_context":
            p = r.get("payload", {})
            if not header["model"] and p.get("model"):
                header["model"] = p["model"]

        elif rtype == "response_item":
            p = r.get("payload", {})
            ptype = p.get("type", "")

            if ptype == "message" and p.get("role") == "user":
                text = _extract_codex_text(p)
                if text:
                    current_turn = {
                        "number": len(turns) + 1,
                        "timestamp": ts,
                        "user_message": text[:2000] if detail != "verbose" else text,
                        "assistant_actions": [],
                    }
                    turns.append(current_turn)

            elif ptype == "message" and p.get("role") == "assistant" and current_turn:
                text = _extract_codex_text(p)
                if text:
                    current_turn["assistant_actions"].append({
                        "type": "text",
                        "content": text[:200] if detail == "standard" else text[:500],
                    })

            elif ptype == "function_call" and current_turn:
                name = p.get("name", "")
                tool_sequence.append(name)
                current_turn["assistant_actions"].append({
                    "type": "tool", "name": name,
                })

    if timestamps:
        header["time_start"] = timestamps[0]
        header["time_end"] = timestamps[-1]

    header["user_turns"] = len(turns)
    header["turn_count"] = len(turns)

    return {
        "header": header,
        "turns": turns if detail != "summary" else [],
        "files": {},
        "tool_sequence": tool_sequence if detail != "summary" else [],
        "turn_count": len(turns),
    }


def _extract_text(content):
    """Extract text from Claude Code message content."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                texts.append(b.get("text", ""))
        return " ".join(texts)
    return ""


def _extract_codex_text(payload):
    """Extract text from Codex message payload."""
    content = payload.get("content", [])
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts = []
        for b in content:
            if isinstance(b, dict) and b.get("type") in ("input_text", "output_text", "text"):
                texts.append(b.get("text", ""))
        return " ".join(texts)
    return ""


def main():
    parser = argparse.ArgumentParser(description="Parse session JSONL for replay")
    parser.add_argument("--input", required=True, help="Session JSONL file path")
    parser.add_argument("--detail", choices=["summary", "standard", "verbose"],
                       default="standard", help="Detail level")
    parser.add_argument("--output", default=None, help="Output JSON file")
    args = parser.parse_args()

    result = replay_session(args.input, args.detail)

    output = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
    else:
        print(output)


if __name__ == "__main__":
    main()
