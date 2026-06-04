#!/bin/bash
# SessionStart hook: cache the booted iOS Simulator's runtime version.
#
# Why: nudge-apple-version.py (PostToolUse on WebSearch/WebFetch) wants to tell
# Claude "you can reproduce this on the booted sim (iOS X.Y)". Resolving that
# version needs `xcrun simctl`, which is slow (~200-500ms) and must NOT run on
# the per-WebSearch hot path. A booted simulator is machine-global state, so a
# single global cache file is correct (not per-project).
#
# Output: $HOME/.claude/.booted-sim-cache  (one line: "26.2", or absent/empty)
# Fail-open: any error -> exit 0, leave cache untouched. Never blocks a session.

set -euo pipefail
trap 'exit 0' EXIT ERR

CACHE="$HOME/.claude/.booted-sim-cache"

# Skip silently if simctl is unavailable (no Xcode / CLT).
command -v xcrun >/dev/null 2>&1 || exit 0

mkdir -p "$HOME/.claude" 2>/dev/null || true

# `simctl list devices booted -j` returns devices keyed by runtime identifier
# (e.g. "com.apple.CoreSimulator.SimRuntime.iOS-26-2"); the runtime whose device
# list is non-empty holds the booted device. Parse its version "26.2".
ver=$(xcrun simctl list devices booted -j 2>/dev/null | python3 -c '
import sys, json, re
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for runtime, devices in (data.get("devices") or {}).items():
    if not devices:
        continue
    # A device appears here only when booted (we filtered with `booted`).
    m = re.search(r"iOS-(\d+)-(\d+)", runtime)
    if m:
        print(f"{m.group(1)}.{m.group(2)}")
        break
' 2>/dev/null || true)

# Reflect SessionStart-time truth. If a sim is booted, cache its version; if
# nothing is booted, CLEAR any prior value — leaving a stale version would make
# the nudge falsely claim a booted sim ("可直接复现") that no longer exists.
if [ -n "${ver:-}" ]; then
    printf '%s\n' "$ver" > "$CACHE" 2>/dev/null || true
else
    rm -f "$CACHE" 2>/dev/null || true
fi

exit 0
