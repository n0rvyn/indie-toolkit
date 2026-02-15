#!/bin/bash
# Calendar CLI wrapper
# Uses compiled Swift binary (EventKit) for fast access to Calendar.
# If binary not found, auto-compiles from calendar.swift.

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BINARY="${SCRIPT_DIR}/calendar_cli"
SOURCE="${SCRIPT_DIR}/calendar.swift"

# Auto-build if binary doesn't exist or source is newer
if [ ! -x "$BINARY" ] || [ "$SOURCE" -nt "$BINARY" ]; then
    echo "Building calendar CLI..." >&2
    bash "${SCRIPT_DIR}/build_calendar.sh" >&2
fi

exec "$BINARY" "$@"
