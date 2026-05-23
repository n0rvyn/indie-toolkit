#!/usr/bin/env python3
"""
PreToolUse hook for Edit / Write / Grep / Bash.

When the user's most recent typed message contains a file path (existing on
disk) or http(s) URL, and no assistant tool call since has read it, AND the
current tool call isn't reading it → emit stderr nudge.

Always exit 0 (soft). Never blocks.
"""
import json
import os
import re
import sys

# Performance cap: never scan more than this many records from the tail.
MAX_RECORDS = 50

PATH_RE = re.compile(r'(/[A-Za-z0-9._/\\-]+)')
URL_RE = re.compile(r'(https?://\S+)')

SKIP_PREFIXES = (
    '<system-reminder>', '<command-message>', '<command-name>',
    '<command-args>', '<bash-input>', '<bash-output>',
    'Base directory for this skill:', 'Caveat:', '[Request interrupted',
    'tool_use_id',
)


def is_real_user_text(text: str) -> bool:
    if not text or not text.strip():
        return False
    s = text.lstrip()
    return not s.startswith(SKIP_PREFIXES)


def extract_user_text(record: dict) -> str:
    msg = record.get('message') or {}
    content = msg.get('content', '')
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if not isinstance(c, dict):
                continue
            if c.get('type') == 'tool_result':
                return ''
            if c.get('type') == 'text':
                parts.append(c.get('text', ''))
        return '\n'.join(parts)
    return ''


def extract_paths_and_urls(text: str) -> list:
    """Return list of unique resources mentioned in the user text."""
    found = []
    seen = set()
    for m in PATH_RE.finditer(text):
        p = m.group(1)
        # Require absolute + exists on disk to avoid false positives
        if p.startswith('/') and os.path.exists(p) and p not in seen:
            found.append(p)
            seen.add(p)
    for m in URL_RE.finditer(text):
        u = m.group(1).rstrip('.,;:!?)')
        if u not in seen:
            found.append(u)
            seen.add(u)
    return found


def tool_call_touches(tool_use: dict, target: str) -> bool:
    """Check whether a single assistant tool_use call references the target."""
    if not isinstance(tool_use, dict):
        return False
    name = tool_use.get('name', '')
    ti = tool_use.get('input', {})
    if not isinstance(ti, dict):
        return False
    if name in ('Read', 'Edit', 'Write', 'MultiEdit', 'NotebookEdit'):
        if ti.get('file_path') == target:
            return True
    if name == 'WebFetch':
        if ti.get('url') == target:
            return True
    if name == 'Bash':
        cmd = ti.get('command', '')
        # Word-boundary check to avoid prefix false-positive
        # (e.g., target=/tmp/foo.log should NOT match cmd containing /tmp/foo.log.bak)
        if re.search(r'(?:^|[\s\'"=<>|;&(])' + re.escape(target) + r'(?:$|[\s\'"<>|;&)])', cmd):
            return True
    if name == 'Grep':
        path = ti.get('path', '')
        if target in path:
            return True
    return False


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    # Sidechain (subagent) guard
    if data.get('isSidechain'):
        sys.exit(0)

    tx_path = data.get('transcript_path')
    if not tx_path or not os.path.isfile(tx_path):
        sys.exit(0)

    tool_name = data.get('tool_name', '')
    tool_input = data.get('tool_input', {}) or {}

    # Read tail of transcript
    try:
        with open(tx_path, errors='ignore') as fh:
            lines = fh.readlines()
    except Exception:
        sys.exit(0)

    tail = lines[-MAX_RECORDS:] if len(lines) > MAX_RECORDS else lines
    records = []
    for line in tail:
        try:
            records.append(json.loads(line))
        except Exception:
            continue

    # Walk backwards to find the most recent typed user message
    last_user_idx = None
    for i in range(len(records) - 1, -1, -1):
        r = records[i]
        if r.get('type') != 'user':
            continue
        if r.get('agentId') or r.get('isSidechain'):
            continue
        msg = r.get('message') or {}
        content = msg.get('content', '')
        # Skip tool_result records
        if isinstance(content, list) and any(
            isinstance(c, dict) and c.get('type') == 'tool_result' for c in content
        ):
            continue
        text = extract_user_text(r)
        if is_real_user_text(text):
            last_user_idx = i
            break

    if last_user_idx is None:
        sys.exit(0)

    user_text = extract_user_text(records[last_user_idx])
    targets = extract_paths_and_urls(user_text)
    if not targets:
        sys.exit(0)

    # Check which targets have been read since the user message
    read = set()
    for r in records[last_user_idx + 1:]:
        if r.get('type') != 'assistant':
            continue
        msg = r.get('message') or {}
        content = msg.get('content', [])
        if not isinstance(content, list):
            continue
        for c in content:
            if isinstance(c, dict) and c.get('type') == 'tool_use':
                for tg in targets:
                    if tg not in read and tool_call_touches(c, tg):
                        read.add(tg)

    # Check if the CURRENT tool call is reading one of the unread targets
    unread = [t for t in targets if t not in read]
    if not unread:
        sys.exit(0)

    pseudo_call = {'name': tool_name, 'input': tool_input}
    for t in unread:
        if tool_call_touches(pseudo_call, t):
            sys.exit(0)  # Current call IS the read — allow

    # Nudge first unread (multi-path policy: don't spam)
    first = unread[0]
    sys.stderr.write(
        f'[source-hint] 用户上一条消息提到了 {first}，但你还没读它。'
        f'优先读它再做其它工具调用。\n'
    )
    sys.exit(0)


if __name__ == '__main__':
    main()
