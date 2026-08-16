#!/usr/bin/env python3
"""PreToolUse(Edit|Write|MultiEdit) detector delivery for the Swift rule sections.

Why a hook and not a skill / not `paths:` — all three measured on 2026-08-16:

  * `.claude/rules/` `paths:` is a real conditional loader, but it triggers on
    READ only. Creating a new .swift file with Write does not load it, and
    "写或改任何 SwiftUI 视图时" is exactly the create case.
  * SKILL.md `paths:` is a LIMITER, not a trigger. The official frontmatter
    reference says it "limit[s] when this skill is activated … loads
    automatically only when working with files matching the patterns."
    Description-based relevance routing still decides whether it loads at all.
  * `apple-dev:apple-swift-context` therefore never fired on its own: measured
    across 6 headless runs (control / Read / Edit / Write on haiku, Read+Write
    on sonnet) — zero Skill invocations, zero forks, zero rule content. Its
    description ("Internal context loader … Not user-invocable") gives the
    router nothing to match. Its only real caller in the marketplace is
    dev-workflow:fix-bug.

A PreToolUse hook is tool-level, so it fires on Write of a brand-new file, in
any session, and costs nothing in non-Swift work. It also sees the content being
written, so it delivers the ONE section that applies instead of six standing
pointers.

Trigger conditions are copied from the reference's own section headers, not
invented here — e.g. 容器宽度意图 defines its trigger as "有 .background() /
.clipShape() / .shadow() / .border() / .overlay(strokeBorder) 中任一".

Noise control: each detector fires at most once per session. Editing twenty
SwiftUI files must not produce twenty identical nudges (see
dev-workflow/hooks/check-repeated-edit.py's 2026-07-11 noise fix).

Never blocks: stderr only, always exit 0.
"""

import json
import os
import re
import sys
import tempfile

REF = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "references", "apple-swift-rules.md",
)

# (key, section name, content predicate, why-it-matters one-liner)
DETECTORS = [
    (
        "container-width",
        "容器宽度意图（条件触发）",
        re.compile(r"\.background\(|\.clipShape\(|\.shadow\(|\.border\(|strokeBorder"),
        "这个 View 是视觉容器，宽度意图要显式写。这类缺陷纯代码审计抓不到——每处单看都没错，"
        "必须并排看多屏渲染，所以「我看着没问题」不构成跳过理由。同节含「按钮组同宽（强制）」。",
    ),
    (
        "testing",
        "测试框架与文件放置",
        re.compile(r"@Test\b|import Testing\b|XCTestCase|import XCTest"),
        "Swift Testing 而非 XCTest；Xcode 26+ 用同步文件夹，禁止写「要手动改 pbxproj」/「要拖进 Xcode」。",
    ),
    (
        "repeated-action-control",
        "同一动作的控件形制一致（条件触发）",
        re.compile(
            r"dismiss\(\)|presentationMode|navigationBarBackButtonHidden"
            r"|[\"'](返回|关闭|取消|完成|Back|Close|Cancel|Done)[\"']"
        ),
        "必须把系统控件也数进去——NavigationLink push 自带的返回键在代码里根本不出现，"
        "只 grep 自绘代码必漏；且不得为统一长相 navigationBarBackButtonHidden(true) 掉系统那颗"
        "（会连带掐掉边缘返回手势）。",
    ),
    (
        "orientation",
        "设计稿没有横屏 ≠ 锁方向（强制）",
        re.compile(r"supportedInterfaceOrientations|UIRequiresFullScreen"),
        "⛔ 设计稿只有竖屏不构成锁方向的理由——那描述的是画布，不是产品要求。"
        "自检：是产品要求它只能竖着用，还是我只是没有横版设计图？",
    ),
]

# The button-group half of 容器宽度意图 has its own shape: siblings in one row.
BUTTON_GROUP = re.compile(r"(HStack|Grid)\b[\s\S]{0,400}?Button\([\s\S]{0,400}?Button\(")


def written_text(tool_name, tool_input):
    """The text this call is about to put on disk."""
    if tool_name == "Write":
        return tool_input.get("content") or ""
    if tool_name == "Edit":
        return tool_input.get("new_string") or ""
    if tool_name == "MultiEdit":
        return "\n".join(
            (e or {}).get("new_string") or "" for e in (tool_input.get("edits") or [])
        )
    return ""


def already_fired(session_id, key):
    """One nudge per detector per session; without a session id, do not repeat-guard."""
    if not session_id:
        return False
    path = os.path.join(tempfile.gettempdir(), f".swift-detector-{session_id}-{key}")
    if os.path.exists(path):
        return True
    try:
        open(path, "w").close()
    except OSError:
        pass
    return False


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name") or ""
    tool_input = data.get("tool_input") or {}
    path = tool_input.get("file_path") or ""
    if not path.endswith(".swift"):
        sys.exit(0)

    text = written_text(tool_name, tool_input)
    if not text:
        sys.exit(0)

    is_test_path = re.search(r"Tests?\.swift$", path) is not None
    session_id = data.get("session_id")

    for key, section, pattern, why in DETECTORS:
        hit = bool(pattern.search(text))
        if key == "testing" and is_test_path:
            hit = True
        if key == "container-width" and not hit:
            hit = bool(BUTTON_GROUP.search(text))
        if not hit or already_fired(session_id, key):
            continue
        print(
            f"[swift-rules] 本次写入触发「{section}」。判据全文："
            f"{REF} 的该节。{why}",
            file=sys.stderr,
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
