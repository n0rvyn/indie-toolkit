#!/usr/bin/env python3
"""
PreToolUse hook for Edit / Write / MultiEdit / NotebookEdit.

Goal: prevent the model from jumping to a code change on a reported bug
without first articulating the user-visible 现状 (current state) and 预期
(expected state). The block format is enforced by /fix-bug skill template;
this hook is the runtime check.

Two modes:
  - HARD (exit 2 → blocks Edit): /fix-bug skill is active in recent history,
    bug-shaped message present, no 现状/预期 block in subsequent assistant text.
  - SOFT (exit 0 + stderr): bug-shaped message present, /fix-bug NOT active,
    no 现状/预期 block.

Skip rule: if at least one Edit/Write/MultiEdit/NotebookEdit has already
fired since the bug message, the hook silently exits 0 (model is in
execution; only gate the FIRST Edit per bug message).
"""
import json
import os
import re
import sys

MAX_RECORDS = 50
FIXBUG_LOOKBACK = 10
GATED_TOOLS = {'Edit', 'Write', 'MultiEdit', 'NotebookEdit'}

# Bug-shape signals. Tuned to high-confidence patterns; false positives are
# costly because hard mode blocks. False negatives are tolerable because the
# soft mode is just a stderr suggestion.
BUG_PATTERNS = [
    re.compile(r'(?:^|\s)at [\w$.]+\([\w./]+:\d+\)', re.M),      # stack trace
    re.compile(r'Traceback \(most recent call last\)'),
    # CJK-safe: no \W boundary (CJK chars are \w, fail boundary on 崩溃/闪退). List composites explicitly.
    re.compile(r'(崩溃|崩了|闪退|崩死|崩|crashed?|crash)', re.I),
    re.compile(r'(?:不|没)(?:能|可以)?\s*work\b', re.I),
    re.compile(r"doesn'?t work|doesn'?t fire"),
    re.compile(r'为什么.{0,30}(错|失败|不|没)'),
    # Broader repair-verb family: bare "fix", Chinese 修/修复 with optional object, common error words.
    # SOFT mode tolerates false-positives (cost = single stderr); HARD mode only fires when /fix-bug active.
    re.compile(r'(?:\bfix\b|修\s*(?:这个|一下|个|下)\s*(?:bug|问题|这|这里|它)?|修复|\bbroken\b|出错|失败)', re.I),
    re.compile(r'\[Image[^\]]*\].{0,200}(?:错|崩|fail|error|失败|wrong|不对|bug)', re.I | re.S),
    # Restrict to line-start so casual mentions ("讲讲 /fix-bug 的逻辑") don't trigger
    re.compile(r'(?:^|\n)\s*/(?:[\w.-]+:)?fix-bug\b'),
    re.compile(r'<command-name>/(?:[\w.-]+:)?fix-bug</command-name>'),
]

# Format detection for 现状/预期 anchor.
# Strict pattern: matches the format the /fix-bug skill template prescribes,
# plus English variant for international use.
# Colon: accept both ASCII `:` and CJK full-width `：` (U+FF1A). In Chinese
# context, models naturally write full-width colons. Without this, HARD mode
# would falsely block when the user has actually complied.
BLOCK_PATTERN_ZH = re.compile(
    r'\*\*现状\*\*\s*[:：].{0,400}\*\*预期\*\*\s*[:：]', re.S
)
BLOCK_PATTERN_EN = re.compile(
    r'\*\*Current\*\*\s*:.{0,400}\*\*Expected\*\*\s*:', re.S | re.I
)

SKIP_PREFIXES = (
    '<system-reminder>', '<bash-input>', '<bash-output>',
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


def extract_assistant_text(record: dict) -> str:
    msg = record.get('message') or {}
    content = msg.get('content', [])
    if not isinstance(content, list):
        return ''
    parts = []
    for c in content:
        if isinstance(c, dict) and c.get('type') == 'text':
            parts.append(c.get('text', ''))
    return '\n'.join(parts)


def is_bug_shaped(text: str) -> bool:
    head = text[:1500]
    for pat in BUG_PATTERNS:
        if pat.search(head):
            return True
    return False


# The namespace is optional: a plugin skill records as `/dev-workflow:fix-bug`, but a
# `context: fork` skill or a user-level copy records the bare `/fix-bug`.
_FIXBUG_INVOKE_RE = re.compile(
    r'<command-name>/(?:[\w.-]+:)?fix-bug</command-name>'   # explicit slash-command wrap
    r'|(?:^|\n)\s*/(?:[\w.-]+:)?fix-bug\b',                 # or line-start mention (real invocation)
)


def fixbug_active(records: list, since_idx: int) -> bool:
    """Detect if /fix-bug skill was actually invoked (not just casually mentioned)
    in the last FIXBUG_LOOKBACK turns. Restricted to real invocations to avoid
    false-positive HARD blocks during meta-discussion of the skill itself."""
    lookback_start = max(since_idx, len(records) - FIXBUG_LOOKBACK)
    for r in records[lookback_start:]:
        msg = r.get('message') or {}
        content = msg.get('content', '')
        if isinstance(content, str):
            if _FIXBUG_INVOKE_RE.search(content):
                return True
        elif isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and c.get('type') == 'text':
                    if _FIXBUG_INVOKE_RE.search(c.get('text', '')):
                        return True
    return False


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if data.get('isSidechain'):
        sys.exit(0)

    tool_name = data.get('tool_name', '')
    if tool_name not in GATED_TOOLS:
        sys.exit(0)

    tx_path = data.get('transcript_path')
    if not tx_path or not os.path.isfile(tx_path):
        sys.exit(0)

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

    # Find most recent typed user message
    last_user_idx = None
    for i in range(len(records) - 1, -1, -1):
        r = records[i]
        if r.get('type') != 'user':
            continue
        if r.get('agentId') or r.get('isSidechain'):
            continue
        msg = r.get('message') or {}
        content = msg.get('content', '')
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
    if not is_bug_shaped(user_text):
        sys.exit(0)

    # Skip rule: if any GATED_TOOLS Edit already happened since the bug message,
    # silently exit (model is in execution mode)
    for r in records[last_user_idx + 1:]:
        if r.get('type') != 'assistant':
            continue
        msg = r.get('message') or {}
        content = msg.get('content', [])
        if not isinstance(content, list):
            continue
        for c in content:
            if isinstance(c, dict) and c.get('type') == 'tool_use':
                if c.get('name') in GATED_TOOLS:
                    sys.exit(0)

    # Check assistant text outputs for 现状/预期 block
    has_block = False
    for r in records[last_user_idx + 1:]:
        if r.get('type') != 'assistant':
            continue
        text = extract_assistant_text(r)
        if not text:
            continue
        if BLOCK_PATTERN_ZH.search(text) or BLOCK_PATTERN_EN.search(text):
            has_block = True
            break

    if has_block:
        sys.exit(0)

    # No block. Decide mode.
    if fixbug_active(records, last_user_idx):
        sys.stderr.write(
            '[fix-gate] /fix-bug 流程要求在 Edit 前显式写出'
            '「**现状**: ... / **预期**: ...」两行（用人话，不要写代码层术语）。'
            '当前未检测到，阻断本次 Edit。\n'
        )
        sys.exit(2)
    else:
        sys.stderr.write(
            '[fix-suggest] 检测到 bug 报告，建议先写'
            '「**现状**（用户实际看到的）/ **预期**（修完用户应该看到的）」两行再 Edit；'
            '或调 /fix-bug 走完整流程。\n'
        )
        sys.exit(0)


if __name__ == '__main__':
    main()
