#!/bin/bash
# Seeds a fixture knowledge base in the run's $HOME, a per-run temp dir, so a real
# ~/.claude/knowledge is never touched. The run can read it; it cannot write it
# (eval runs confine writes to the workspace).
set -e
KB="$HOME/.claude/knowledge"
entry() { mkdir -p "$KB/$(dirname "$1")"; cat > "$KB/$1"; }

entry api-usage/2026-08-26-ark-responses-api-sse-usage-tokens.md <<'MD'
---
category: api-usage
keywords: [Volcengine Ark, responses API, SSE, usage tokens]
date: 2026-08-26
---
# Volcengine Ark responses API reports usage only in the final SSE event
The `usage` block arrives in the last event of the stream; intermediate events carry none.
MD
entry api-usage/2026-08-20-ark-seed-vision-thinking-on-by-default.md <<'MD'
---
category: api-usage
keywords: [Volcengine Ark, seed vision, thinking, default]
date: 2026-08-20
---
# Ark seed vision models think by default
Pass `thinking: {type: "disabled"}` to turn it off; otherwise latency doubles.
MD
