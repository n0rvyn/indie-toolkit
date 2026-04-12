---
name: minimax-coding-plan
description: "查询 MiniMax coding plan 剩余额度，使用浏览器登录态中的 HERTZ-SESSION。支持从环境变量、cookie 文件或 session 刷新命令读取会话。Use when the user asks to check MiniMax coding plan quota, remains, usage, HERTZ-SESSION, or MiniMax browser-session automation. Keywords: MiniMax, minimax, coding plan, remains, quota, HERTZ-SESSION."
context: fork
model: haiku
allowed-tools: Bash(*skills/minimax-coding-plan/scripts/*)
---

# MiniMax Coding Plan

查询 MiniMax `coding_plan/remains` 接口，并把 `HERTZ-SESSION` 的读取方式收敛成统一入口。

## 认证边界

- 这个技能面向浏览器登录态，不是官方 OpenAPI token 流
- 需要 `MINIMAX_GROUP_ID`
- 需要有效的 `HERTZ-SESSION`
- 可选 `MINIMAX_SESSION_COMMAND` 用于在 cookie 失效后取回新 session

## Path Setup

```bash
BASE="${CLAUDE_PLUGIN_ROOT:-${CODEX_HOME:-$HOME/.codex}}"
SKILLS_ROOT="$BASE/skills"
[ -d "$SKILLS_ROOT/minimax-coding-plan/scripts" ] || SKILLS_ROOT="$BASE/indie-toolkit/minimax-platform/skills"
```

## 工具

```bash
${SKILLS_ROOT}/minimax-coding-plan/scripts/minimax_coding_plan.sh
```

## 常用命令

### 查看额度摘要

```bash
MINIMAX_GROUP_ID='2036327615073096267' \
MINIMAX_HERTZ_SESSION='your-session' \
${SKILLS_ROOT}/minimax-coding-plan/scripts/minimax_coding_plan.sh
```

### 输出原始 JSON

```bash
MINIMAX_GROUP_ID='2036327615073096267' \
MINIMAX_HERTZ_SESSION='your-session' \
${SKILLS_ROOT}/minimax-coding-plan/scripts/minimax_coding_plan.sh --json
```

等价写法：`MINIMAX_OUTPUT=json`。

### 从 cookie 文件读取

```bash
MINIMAX_GROUP_ID='2036327615073096267' \
MINIMAX_COOKIE_FILE="$HOME/.config/minimax/hertz-session.txt" \
${SKILLS_ROOT}/minimax-coding-plan/scripts/minimax_coding_plan.sh
```

### cookie 失效后自动拉取新 session

```bash
MINIMAX_GROUP_ID='2036327615073096267' \
MINIMAX_SESSION_COMMAND='/path/to/session-helper' \
${SKILLS_ROOT}/minimax-coding-plan/scripts/minimax_coding_plan.sh
```

`MINIMAX_SESSION_COMMAND` 必须输出以下任一格式：

- 裸 `HERTZ-SESSION` 值
- `HERTZ-SESSION=...`
- Netscape cookie 文件中的 `HERTZ-SESSION` 行

## 返回行为

- 成功时输出模型级 usage/limit 摘要
- `--json` 时输出原始响应
- cookie 缺失或失效时退出并提示重新登录

## 不做的事

- 不伪造用户名密码登录
- 不声称存在官方 refresh token
- 不自动抓浏览器密码库；如需自动取 session，由本机脚本或浏览器自动化承担
