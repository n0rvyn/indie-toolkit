#!/usr/bin/env python3
"""PreToolUse(Edit|Write) trip-wire: surface a knowledge-base entry at the moment
the code that would trigger it is being written.

Why this exists
---------------
The knowledge base is retrievable but not *recalled*. On 2026-08-10 (CleanLabel)
`knowledge/api-misuse/2026-07-10-swift-memberwise-init-silently-erased.md` — an
entry written a month earlier, by the same author, about the same project, naming
the exact scenario ("给一个 SwiftUI View 加可选回调") — sat unread while the same
bug was re-introduced and had to be caught downstream by a plan verifier.

The existing global rule 「开局先查自己的知识库」 has a *debugging* trigger
(symptom + platform name + error code). That miss happened while **authoring new
code**, so the trigger never fired. Writing new code walks into old pits too.

Design constraints (each learned from a hook that got them wrong)
----------------------------------------------------------------
1. **Match code being written, never prose.** `xcodebuild-guard.py` denied two
   commands on 2026-08-10 because their *documentation payload* contained the
   command string. So: skip non-code paths (docs/, *.md, knowledge/), and match
   only the edit payload.
2. **Precision over recall.** ~186 entries; a general keyword search would fire
   constantly and get tuned out. A pattern earns a trip-wire only after the
   failure class has cost >=2 incidents — in practice, entries carrying a
   recurrence section. Keep this table SHORT.
3. **Never block.** Exit 0 with a stderr nudge. A false positive must cost a line
   of text, not a refused edit.
4. **Once per session per wire.** Repeating the same nudge on every edit is how
   nudges become invisible.
"""
import json
import os
import re
import sys

KB = os.path.expanduser("~/.claude/knowledge")
STATE_DIR = os.path.expanduser("~/.claude/.kb-tripwire")

# Paths whose content is prose, not code. Never trip on these.
PROSE_PATH = re.compile(r"(\.md$|\.txt$|\.rst$|/docs?/|/knowledge/|/\.claude/)", re.I)

# Each wire: (id, path_regex, payload_regex, absent_regex_or_None, kb_relpath, note)
#   absent_regex — when set, the wire fires only if this is NOT present in the
#   payload *or* the on-disk file (used for "a @Test with no enclosing suite").
TRIPWIRES = [
    (
        "swift-let-default-memberwise",
        r"\.swift$",
        r"^\s*let\s+\w+\s*:[^=\n]*=\s*(nil|\{\s*\})\s*$",
        None,
        "api-misuse/2026-07-10-swift-memberwise-init-silently-erased.md",
        "`let` + 默认值的属性**不进**合成 memberwise init（不是可省略，是不存在）——"
        "调用点会报 `extra argument`。要能显式传入就得用 `var`。",
    ),
    (
        "swift-testing-suiteless",
        r"\.swift$",
        r"^\s*@Test\b",
        r"(struct|final\s+class|class|@Suite)\s+\w*[Tt]ests?\b",
        "platform-constraints/2026-08-10-swift-testing-suiteless-tests-silently-skipped.md",
        "`@Test` 写在文件作用域（无 suite 类型）时，`-only-testing:Target/TypeName` "
        "匹配不到任何东西 → 报 `TEST SUCCEEDED` 但 `totalTestCount: 0`，静默零测试。",
    ),
    (
        "swift-testing-in-uitests",
        r"UITests?/.*\.swift$",
        r"^\s*import\s+Testing\b",
        None,
        "platform-constraints/2026-08-10-swift-testing-suiteless-tests-silently-skipped.md",
        "XCUITest 的 runner 依赖 XCTest 基础设施，Swift Testing 写的 UI 用例"
        "**不会被收集、也不报错**。UITest 一律 `XCTestCase`。",
    ),
    (
        "swiftui-lazyvstack-a11y",
        r"\.swift$",
        r"\bLazyVStack\b",
        None,
        "api-misuse/2026-07-12-swiftui-lazyvstack-drops-section-from-a11y-tree.md",
        "`LazyVStack` 会把整段内容从可访问性树里漏掉（渲染正常、VoiceOver 与 XCUITest 都够不到）。"
        "数据量不大时用 `VStack`。",
    ),
]


def _payload(tool_name, tool_input):
    """The text actually being written."""
    if tool_name == "Write":
        return tool_input.get("content") or ""
    if tool_name == "Edit":
        return tool_input.get("new_string") or ""
    if tool_name == "MultiEdit":
        return "\n".join((e or {}).get("new_string") or ""
                         for e in (tool_input.get("edits") or []))
    return ""


def _already_nudged(session, wire_id):
    """One nudge per wire per session. Returns True if it already fired."""
    if not session:
        return False
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        marker = os.path.join(STATE_DIR, f"{re.sub(r'[^A-Za-z0-9_-]', '', session)}.{wire_id}")
        if os.path.exists(marker):
            return True
        open(marker, "w").close()
    except Exception:
        return False        # state is best-effort; never let it suppress by accident
    return False


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    tool = data.get("tool_name") or ""
    if tool not in ("Edit", "Write", "MultiEdit"):
        return

    tool_input = data.get("tool_input") or {}
    path = tool_input.get("file_path") or ""
    if not path or PROSE_PATH.search(path):
        return

    payload = _payload(tool, tool_input)
    if not payload:
        return

    session = data.get("session_id") or ""

    for wire_id, path_re, hit_re, absent_re, kb_rel, note in TRIPWIRES:
        if not re.search(path_re, path):
            continue
        if not re.search(hit_re, payload, re.M):
            continue
        if absent_re:
            haystack = payload
            try:                                  # widen to the whole file if it exists
                with open(path, "r", encoding="utf-8", errors="ignore") as fh:
                    haystack += "\n" + fh.read()
            except Exception:
                pass
            if re.search(absent_re, haystack):
                continue
        if _already_nudged(session, wire_id):
            continue

        kb_path = os.path.join(KB, kb_rel)
        where = kb_path if os.path.exists(kb_path) else f"{kb_rel}（未找到，可能已改名）"
        print(f"[kb-tripwire] 这个坑知识库里有记录：{note}\n"
              f"              → {where}", file=sys.stderr)


if __name__ == "__main__":
    main()
