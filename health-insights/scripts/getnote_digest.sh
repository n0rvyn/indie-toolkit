#!/bin/bash
# Thin wrapper: save health digest to Get笔记
# Usage: getnote_digest.sh "<content>" "<tag>"
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# Resolve getnote.sh via env var, then via repo-relative fallback.
# This script lives at <repo>/health-insights/scripts/, so getnote is at
# ../../pkos/skills/getnote/scripts/getnote.sh.
GETNOTE_SH="${GETNOTE_SH:-$SCRIPT_DIR/../../pkos/skills/getnote/scripts/getnote.sh}"

CONTENT="${1:-}"
TAG="${2:-health-weekly-digest}"

if [[ -z "$CONTENT" ]]; then
  echo "Usage: getnote_digest.sh \"<content>\" [\"<tag>\"]" >&2
  exit 1
fi

if [[ ! -x "$GETNOTE_SH" ]]; then
  echo "getnote_digest: getnote.sh not found or not executable at: $GETNOTE_SH" >&2
  echo "Set \$GETNOTE_SH to override the default path." >&2
  exit 2
fi

TITLE="健康周报 $(date +%Y-%m-%d)"
"$GETNOTE_SH" save_note "$TITLE" "$CONTENT" "$TAG"
