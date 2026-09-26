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
Nothing about the query here.
MD
mkdir -p docs/09-lessons-learned
cat > docs/09-lessons-learned/2026-07-02-zebrafish-importer-drops-rows.md <<'MD'
# The zebrafish importer silently drops rows with an empty tank id
Project-local lesson: validate tank ids before import.
MD
