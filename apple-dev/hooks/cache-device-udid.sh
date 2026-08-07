#!/bin/bash
# SessionStart hook: cache the connected physical iOS device's hardware UDID.
#
# Why: the xcodebuild destination SOP says "跑 tests → 真机优先", which needs the
# HARDWARE UDID (00008140-…) that `-destination "platform=iOS,id=…"` expects —
# not the CoreDevice id (3C55BC5F-…) that `xcrun devicectl` reports. Resolving it
# means `xcrun xctrace list devices`, which is slow and must not sit on a hot
# path. Before this hook the UDID was hardcoded into the user's global CLAUDE.md
# with a note to "rescan and update this line when the device changes" — machine
# state maintained by hand, guaranteed to go stale. Same reasoning (and the same
# machine-global-so-one-cache-file conclusion) as cache-booted-sim.sh.
#
# Output: $HOME/.claude/.device-udid-cache — ONE LINE PER connected device,
#         "00008140-0001546401FB001C|iPhone". Every eligible device is listed on
#         purpose: this machine routinely has an iPhone and an iPad attached at
#         once, and picking one of them here would be the tool silently choosing
#         a test target for the user. Consumers with 2+ lines must ask (or read
#         the project's own pinned UDID), never take the first line.
#         Absent when no device is connected.
# Fail-open: any error -> exit 0, leave cache untouched. Never blocks a session.

set -euo pipefail
trap 'exit 0' EXIT ERR

CACHE="$HOME/.claude/.device-udid-cache"

command -v xcrun >/dev/null 2>&1 || exit 0
mkdir -p "$HOME/.claude" 2>/dev/null || true

# `xctrace list devices` sections: "== Devices ==" holds physical devices plus
# this Mac; "== Simulators ==" follows. Take iPhone/iPad lines from the first
# section only, skip the Mac, skip anything still "(Connecting)".
entry=$(xcrun xctrace list devices 2>/dev/null | python3 -c '
import sys, re
in_devices = False
for line in sys.stdin:
    s = line.strip()
    if s.startswith("== Devices =="):
        in_devices = True
        continue
    if s.startswith("=="):          # any later section ends the device block
        in_devices = False
        continue
    if not in_devices or not s:
        continue
    if "Connecting" in s or s.startswith("My Mac"):
        continue
    if not re.search(r"\b(iPhone|iPad)\b", s):
        continue
    # "Name (26.6) (00008140-0001546401FB001C)" -> last parenthesised group
    ids = re.findall(r"\(([^)]+)\)", s)
    if not ids:
        continue
    udid = ids[-1]
    # Hardware UDIDs are 8+16 hex with a dash, or 40-hex on older devices.
    if not re.fullmatch(r"[0-9A-Fa-f]{8}-[0-9A-Fa-f]{16}|[0-9A-Fa-f]{40}", udid):
        continue
    name = s.split("(")[0].strip()
    print(f"{udid}|{name}")
' 2>/dev/null || true)

# Reflect SessionStart-time truth: no device connected -> clear, never keep a
# stale UDID (a stale one sends `xcodebuild test` at a device that is not there,
# and the SOP's fallback to a booted sim would never trigger).
if [ -n "${entry:-}" ]; then
    printf '%s\n' "$entry" > "$CACHE" 2>/dev/null || true
else
    rm -f "$CACHE" 2>/dev/null || true
fi

exit 0
