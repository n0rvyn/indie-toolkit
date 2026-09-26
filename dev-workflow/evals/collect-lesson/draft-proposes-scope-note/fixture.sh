#!/bin/bash
# Seeds a fixture knowledge base in the run's $HOME, a per-run temp dir, so a real
# ~/.claude/knowledge is never touched. The run can read it; it cannot write it
# (eval runs confine writes to the workspace).
set -e
KB="$HOME/.claude/knowledge"
entry() { mkdir -p "$KB/$(dirname "$1")"; cat > "$KB/$1"; }

entry api-usage/2026-05-30-sdk-query-writes-resumable-transcripts.md <<'MD'
---
category: api-usage
keywords: [Claude Agent SDK, resume, persistSession, session transcript, query]
date: 2026-05-30
---
# Claude Agent SDK query() writes a resumable transcript

With `persistSession: true`, `query({prompt: "..."})` writes `projects/<cwd>/<id>.jsonl` on clean exit,
and `--resume <id>` continues it after the host app restarts.
MD
