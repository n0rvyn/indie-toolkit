#!/bin/bash
# Seeds a fixture knowledge base in the run's $HOME, a per-run temp dir, so a real
# ~/.claude/knowledge is never touched. The run can read it; it cannot write it
# (eval runs confine writes to the workspace).
set -e
KB="$HOME/.claude/knowledge"
entry() { mkdir -p "$KB/$(dirname "$1")"; cat > "$KB/$1"; }

entry api-usage/2026-05-31-sdk-streaming-input-not-resumable.md <<'MD'
---
category: api-usage
keywords: [Claude Agent SDK, streaming-input, resume, persistSession]
date: 2026-05-31
---
# Streaming-input sessions are not disk-resumable
A streaming-input `query()` persists no resumable transcript even with persistSession: true.
MD
entry bug-postmortem/2026-06-01-streaming-session-self-heal.md <<'MD'
---
category: bug-postmortem
keywords: [streaming-input, self-heal, restart]
date: 2026-06-01
---
# Streaming session self-heal after a restart
Postmortem: the app replays its own history into the first streaming turn after a cold start.
MD
