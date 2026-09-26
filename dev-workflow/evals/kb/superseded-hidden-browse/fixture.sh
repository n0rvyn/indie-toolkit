#!/bin/bash
# Seeds a fixture knowledge base in the run's $HOME, a per-run temp dir, so a real
# ~/.claude/knowledge is never touched. The run can read it; it cannot write it
# (eval runs confine writes to the workspace).
set -e
KB="$HOME/.claude/knowledge"
entry() { mkdir -p "$KB/$(dirname "$1")"; cat > "$KB/$1"; }

entry platform-constraints/2026-04-02-sdk-bundles-cli-binary.md <<'MD'
---
category: platform-constraints
keywords: [Claude Agent SDK, cli.js, pathToClaudeCodeExecutable, SDK binary]
date: 2026-04-02
status: superseded
superseded_by: 2026-05-17-sdk-no-longer-bundles-cli.md
---
# Claude Agent SDK bundles the full CLI as cli.js

> ⛔ 已被取代（2026-05-17）：0.2.141 起 npm 包不再包含 cli.js。现行结论见 [[2026-05-17-sdk-no-longer-bundles-cli.md]]。

The SDK npm package ships a bundled `cli.js`. Point `pathToClaudeCodeExecutable` at
`node_modules/@anthropic-ai/claude-agent-sdk/cli.js` so the app never depends on a system install.
MD

entry platform-constraints/2026-05-17-sdk-no-longer-bundles-cli.md <<'MD'
---
category: platform-constraints
keywords: [Claude Agent SDK, cli.js removed, claude binary, PATH, spawn]
date: 2026-05-17
verified_on: claude-agent-sdk 0.2.141
supersedes: [2026-04-02-sdk-bundles-cli-binary.md]
---
# Claude Agent SDK no longer bundles cli.js (0.2.141+)

From `@anthropic-ai/claude-agent-sdk@0.2.141` the package no longer ships `cli.js`.
Spawn the system `claude` binary instead: resolve it from PATH (or a CLAUDE_BIN override)
and pass that path to the SDK. A hard-coded path into node_modules now fails at startup.
MD

entry api-usage/2026-03-20-sdk-streaming-chunk-order.md <<'MD'
---
category: api-usage
keywords: [Claude Agent SDK, streaming, message order]
date: 2026-03-20
---
# SDK streaming messages arrive tool_use before text

Unrelated filler entry: when streaming, a tool_use block can arrive before the text block of the same turn.
MD
