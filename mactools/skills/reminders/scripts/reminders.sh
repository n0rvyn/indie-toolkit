#!/bin/bash
# Reminders.app CLI wrapper
# Uses compiled Swift binary (EventKit) for fast access to Reminders.
# If binary not found, auto-compiles from reminders.swift.

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BINARY="${SCRIPT_DIR}/reminders_cli"
SOURCE="${SCRIPT_DIR}/reminders.swift"

# Auto-build if binary doesn't exist or source is newer
if [ ! -x "$BINARY" ] || [ "$SOURCE" -nt "$BINARY" ]; then
    echo "Building reminders CLI..." >&2
    bash "${SCRIPT_DIR}/build_reminders.sh" >&2
fi

exec "$BINARY" "$@"
