#!/bin/zsh
# shoot.sh <AppPath.app> <out.png> [ENV=val ...]
# Quit, relaunch the binary (so launch env vars apply), activate, capture the main window by id.
# Run `xcodebuild build` first so the relaunched .app contains your change.
APP="$1"; OUT="${2:-shot.png}"
shift 2 2>/dev/null
NAME="$(basename "$APP" .app)"
DIR="${0:A:h}"
osascript -e "tell application \"$NAME\" to quit" 2>/dev/null
osascript -e 'delay 2' 2>/dev/null
env "$@" "$APP/Contents/MacOS/$NAME" >/dev/null 2>&1 &
osascript -e 'delay 5' 2>/dev/null
osascript -e "tell application \"$NAME\" to activate" 2>/dev/null
osascript -e 'delay 1' 2>/dev/null
id=$(swift "$DIR/winlist.swift" "$NAME" 2>/dev/null | awk '$2=="layer=0"{print $1; exit}')
if [ -z "$id" ]; then echo "NO_WINDOW"; exit 1; fi
/bin/rm -f "$OUT"
screencapture -x -o -l "$id" "$OUT"
echo "SHOT_OK $OUT (window $id)"
