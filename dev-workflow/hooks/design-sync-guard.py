#!/usr/bin/env python3
"""Claude Design access: deliver the convention on demand, and block the one
approach that is known to waste 25 minutes.

Two modes, one script:

  UserPromptSubmit — the prompt mentions claude.ai/design → inject the working
      convention (use the DesignSync MCP, how to get projectId, the sub-agent
      availability caveat). Costs nothing in every other session, which is why
      this moved out of ~/.claude/CLAUDE.md on 2026-08-16: it was 1,355 chars
      of unconditional context for a tool that appears in a small fraction of
      sessions.

  PreToolUse(WebFetch) — the url IS a claude.ai/design URL → deny. This is the
      documented failure (2026-07-11): WebFetch on a private design URL hangs or
      returns the SPA shell, and driving a browser to scrape the canvas is brittle
      and slow. Prose did not prevent it once; a guard does.

Decisions are emitted as JSON on exit 0 (the runtime only reads JSON from a
clean exit), so a crashed guard fails open rather than wedging every call.
"""

import json
import re
import sys

DESIGN_URL = re.compile(r"claude\.ai/design", re.I)

CONVENTION = (
    "[design-sync] 检测到 Claude Design（`claude.ai/design`）。约定：\n"
    "• **读设计稿一律用 `DesignSync` MCP** —— 不用 WebFetch，不用浏览器抠 canvas。"
    "它是 deferred 工具，先 `ToolSearch select:DesignSync` 加载再用。\n"
    "• `projectId` = URL 里 `/p/` 后那个 UUID，直接从链接取；方法签名与 256KiB 上限"
    "加载 schema 即得。\n"
    "• 产物形状：React/JSX 源码树（`src/*.jsx` + `src/tokens.css` 是设计 token 单一真源）"
    "+ 自包含 `Prototype.html`（tokens 内联，可直接跑）+ 画布版（`Lumina.html` / `design-canvas.jsx`）。\n"
    "• ⚠️ **DesignSync 的 sub-agent 可用性不是环境不变量** —— 2026-07-11 一天内实测出"
    "「Agent 派生查无」「Workflow 派生可加载」「Agent 派生可加载」三种结果（随 harness 版本 / "
    "MCP 挂载点变化）。派发批量拉取前让 agent 先自测 `ToolSearch select:DesignSync`，"
    "查无再回落主线 `get_file`。\n"
    "• 省 context 的正确做法：JSX 只读一遍就地抽成 DESIGN.md/FLOW.md，别把原始 JSX 写回盘；"
    "`get_file` 大文件自动落盘（`Prototype.html` 254KB 即是），小文件走 inline。\n"
    "• 权限：读方法需 claude.ai 登录带 design scope，首次调用弹一次授权。无登录态的 headless "
    "会话用 `/design-login`；本地组件库增量同步用 `/design-sync`。这两个是 claude.ai/design 侧的"
    "第一方入口，**不在本地 skills/plugins 目录——盘上 grep 不到不等于 phantom**。"
)

DENY = (
    "⛔ 不要对 `claude.ai/design` URL 用 WebFetch。实证 2026-07-11：私有 design URL 会卡死 / "
    "只取到 SPA 空壳，改用浏览器自动化抠 canvas 又脆又慢，一共绕了 25 分钟。\n"
    "改用 DesignSync MCP：`ToolSearch select:DesignSync` 加载后调用其读方法，"
    "`projectId` 取 URL 里 `/p/` 后那个 UUID。自家产品有一等 MCP，第一反应就用它。"
)


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    event = data.get("hook_event_name") or ""

    if event == "PreToolUse" and data.get("tool_name") == "WebFetch":
        url = (data.get("tool_input") or {}).get("url") or ""
        if DESIGN_URL.search(url):
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": DENY,
                }
            }, ensure_ascii=False))
        sys.exit(0)

    if event == "UserPromptSubmit":
        prompt = data.get("prompt") or ""
        if DESIGN_URL.search(prompt):
            print(json.dumps({
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": CONVENTION,
                }
            }, ensure_ascii=False))
        sys.exit(0)

    sys.exit(0)


if __name__ == "__main__":
    main()
