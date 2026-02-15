#!/bin/bash
# Build calendar.swift into a compiled binary for faster execution.
# Usage: bash build_calendar.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="${SCRIPT_DIR}/calendar.swift"
OUTPUT="${SCRIPT_DIR}/calendar_cli"

if [ ! -f "$SOURCE" ]; then
    echo "Error: Source file not found: $SOURCE" >&2
    exit 1
fi

echo "Compiling calendar.swift..."
swiftc -O -o "$OUTPUT" "$SOURCE" \
    -framework EventKit

chmod +x "$OUTPUT"
echo "Build complete: $OUTPUT"
