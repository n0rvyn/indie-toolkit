#!/usr/bin/env python3
"""PostToolUse(Agent) hook: verify sub-agent file-write claims.

When a Task agent reports it wrote/saved/created files, check those paths
exist on disk and are non-empty. If any claimed file is missing or empty,
inject a system-reminder into the next turn so the main session knows the
sub-agent's stdout is unreliable.

This addresses the fabrication pattern: "agent claimed to write X, main
session marks task complete, file never landed on disk."

Silent on success — no output if all claimed files exist.
"""

import json
import os
import re
import sys


# Verb form: "wrote PATH", "saved (to) PATH", "created PATH", with up to ~80
# chars of noun phrase between verb and path (e.g., "wrote the report to PATH").
# Bounded by sentence-ending punctuation so we don't cross sentence boundaries.
VERB_PATTERN = re.compile(
    r"(?i)\b(?:saved|wrote|written|created)(?:\s+to)?\b"
    r"[^.\n!?]{0,80}?"
    r"(?<![A-Za-z0-9_./-])"
    r"([/~][/A-Za-z0-9_.-]+|[A-Za-z0-9_./-]+\.[a-z]{2,6})"
)

# If any of these words appear between the verb and the captured path, the
# match is descriptive prose ("wrote a function named MyClass.swift"), not a
# real file-write claim. Skip such matches to avoid spurious warnings.
FILLER_BEFORE_PATH = re.compile(
    r"(?i)\b(?:function|method|class|variable|component|view|struct|"
    r"enum|protocol|named|called|module|symbol|type|property|"
    r"helper|test|case|fixture|test\s+case)\b"
)

# Label form: "Output: PATH", "Wrote: PATH", "→ PATH"
LABEL_PATTERN = re.compile(
    r"(?:Output|Wrote|Saved|Result|→)[:=]\s+"
    r"[`\"']?"
    r"([/~]?[A-Za-z0-9_./-]+\.[a-z]{2,6})"
    r"[`\"']?"
)

# Strip punctuation off the tail of captured paths
TRAILING = ".,;:)]}>`\"'"


def extract_response_text(response):
    if isinstance(response, str):
        return response
    if isinstance(response, list):
        parts = []
        for block in response:
            if isinstance(block, dict):
                # tool_response blocks may carry text under 'text' or 'content'
                text = block.get("text") or block.get("content") or ""
                if isinstance(text, list):
                    text = " ".join(
                        b.get("text", "") if isinstance(b, dict) else str(b)
                        for b in text
                    )
                parts.append(str(text))
            else:
                parts.append(str(block))
        return "\n".join(parts)
    if isinstance(response, dict):
        # Sometimes nested under 'output' or 'content'
        for key in ("output", "content", "text", "result"):
            if key in response:
                return extract_response_text(response[key])
        return json.dumps(response)
    return str(response)


def collect_paths(text):
    paths = set()
    for match in VERB_PATTERN.finditer(text):
        between = text[match.start() : match.start(1)]
        if FILLER_BEFORE_PATH.search(between):
            continue
        path = match.group(1).rstrip(TRAILING)
        if path:
            paths.add(path)
    for match in LABEL_PATTERN.finditer(text):
        path = match.group(1).rstrip(TRAILING)
        if path:
            paths.add(path)
    return paths


def resolve(path, cwd):
    expanded = os.path.expanduser(path)
    if not os.path.isabs(expanded):
        expanded = os.path.normpath(os.path.join(cwd, expanded))
    return expanded


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if data.get("tool_name") != "Agent":
        sys.exit(0)

    response_text = extract_response_text(data.get("tool_response", ""))
    if not response_text:
        sys.exit(0)

    cwd = data.get("cwd") or os.getcwd()
    subagent = (
        data.get("tool_input", {}).get("subagent_type")
        or data.get("tool_input", {}).get("description")
        or "agent"
    )

    claimed = collect_paths(response_text)
    if not claimed:
        sys.exit(0)

    missing = []
    for path in sorted(claimed):
        resolved = resolve(path, cwd)
        try:
            if not os.path.exists(resolved):
                missing.append(f"- {path} (not found)")
            elif os.path.isfile(resolved) and os.path.getsize(resolved) == 0:
                missing.append(f"- {path} (empty)")
        except OSError:
            missing.append(f"- {path} (stat failed)")

    if not missing:
        sys.exit(0)

    warning = (
        f"[verify-agent-output] Sub-agent '{subagent}' reported writing files "
        f"that are NOT on disk:\n"
        + "\n".join(missing)
        + "\n\nDo NOT mark the task complete based on agent stdout. Either "
        f"(a) re-write the content yourself from the agent's output, "
        f"(b) re-dispatch the agent with explicit Write tool requirement, or "
        f"(c) report failure to the user."
    )

    output = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": warning,
        }
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
