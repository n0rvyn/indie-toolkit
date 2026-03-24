#!/bin/bash
# SessionStart hook: detect changes in Xcode's built-in AI documentation.
# Compares hash of file listing against stored hash. Notifies on change.

DOCS_DIR="/Applications/Xcode.app/Contents/PlugIns/IDEIntelligenceChat.framework/Versions/A/Resources/AdditionalDocumentation"
HASH_FILE="$HOME/.claude/xcode-docs-hash"

# Skip if Xcode not installed or directory doesn't exist
if [ ! -d "$DOCS_DIR" ]; then
  exit 0
fi

# Compute hash of sorted file listing (names + sizes for content-change sensitivity)
current_hash=$(ls -lS "$DOCS_DIR" 2>/dev/null | shasum -a 256 | cut -d' ' -f1)

if [ -z "$current_hash" ]; then
  exit 0
fi

# First run: store hash, silent
if [ ! -f "$HASH_FILE" ]; then
  mkdir -p "$(dirname "$HASH_FILE")"
  echo "$current_hash" > "$HASH_FILE"
  exit 0
fi

stored_hash=$(cat "$HASH_FILE" 2>/dev/null)

if [ "$current_hash" = "$stored_hash" ]; then
  exit 0
fi

# Hash differs: report change
file_count=$(ls "$DOCS_DIR" 2>/dev/null | wc -l | tr -d ' ')
echo "[xcode-docs] Xcode AI documentation changed (${file_count} files in AdditionalDocumentation/). Review with: ls \"$DOCS_DIR\""

# Update stored hash
echo "$current_hash" > "$HASH_FILE"
exit 0
