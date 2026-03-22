#!/bin/bash
# Voice transcription wrapper — auto-compiles Swift CLI and invokes it.
# Usage: voice-transcribe.sh <audio-file>
# Language detected from filename prefix: en-* → Apple Speech, zh-* → Whisper

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SWIFT_SRC="$SCRIPT_DIR/voice-transcribe.swift"
BINARY="$SCRIPT_DIR/.voice-transcribe-bin"

# Auto-compile if binary missing or source newer
if [ ! -f "$BINARY" ] || [ "$SWIFT_SRC" -nt "$BINARY" ]; then
    echo "Compiling voice-transcribe..." >&2
    swiftc -framework Speech -framework Foundation -O -o "$BINARY" "$SWIFT_SRC" 2>&1 | head -20 >&2
    if [ $? -ne 0 ]; then
        echo "Error: Failed to compile voice-transcribe.swift" >&2
        exit 1
    fi
fi

exec "$BINARY" "$@"
