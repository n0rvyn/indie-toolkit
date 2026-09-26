#!/bin/bash
# Seeds a fixture knowledge base in the run's $HOME, a per-run temp dir, so a real
# ~/.claude/knowledge is never touched. The run can read it; it cannot write it
# (eval runs confine writes to the workspace).
set -e
KB="$HOME/.claude/knowledge"
entry() { mkdir -p "$KB/$(dirname "$1")"; cat > "$KB/$1"; }

entry workflow/2026-05-01-unrelated.md <<'MD'
---
category: workflow
keywords: [commit, conventional commits]
date: 2026-05-01
---
# Unrelated entry
Nothing about the lesson here.
MD
