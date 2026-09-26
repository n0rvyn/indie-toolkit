#!/bin/bash
# Seeds a fixture knowledge base in the run's $HOME, a per-run temp dir, so a real
# ~/.claude/knowledge is never touched. The run can read it; it cannot write it
# (eval runs confine writes to the workspace).
set -e
KB="$HOME/.claude/knowledge"
entry() { mkdir -p "$KB/$(dirname "$1")"; cat > "$KB/$1"; }

entry platform-constraints/2026-06-01-hook-stderr-reaches-model.md <<'MD'
---
category: platform-constraints
keywords: [Claude Code, hooks, PreToolUse, stderr, exit code]
date: 2026-06-01
verified_on: Claude Code 2.1.100
---
# A PreToolUse hook's stderr on exit 0 is shown to the model

Print guidance to stderr and exit 0; the model sees it as a hint without the tool call being blocked.
MD
