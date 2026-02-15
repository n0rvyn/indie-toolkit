#!/bin/bash
# Build ocr.swift into a compiled binary for faster execution.
# Usage: bash build_ocr.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="${SCRIPT_DIR}/ocr.swift"
OUTPUT="${SCRIPT_DIR}/ocr"

if [ ! -f "$SOURCE" ]; then
    echo "Error: Source file not found: $SOURCE" >&2
    exit 1
fi

echo "Compiling ocr.swift..."
swiftc -O -o "$OUTPUT" "$SOURCE" \
    -framework Vision \
    -framework AppKit \
    -framework CoreGraphics \
    -framework PDFKit

chmod +x "$OUTPUT"
echo "Build complete: $OUTPUT"
