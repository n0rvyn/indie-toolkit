#!/bin/bash
# domain-intel SessionStart hook
# Checks if CWD is an initialized domain-intel directory and reports unread insight count

# If CWD doesn't have config.yaml, this isn't a domain-intel directory — silent exit
if [ ! -f "./config.yaml" ]; then
  exit 0
fi

# Check state file for last scan
state_file="./state.yaml"
last_scan="never"
if [ -f "$state_file" ]; then
  last_scan=$(grep '^last_scan:' "$state_file" | sed 's/last_scan: *//' | tr -d '"')
fi

if [ "$last_scan" = "never" ]; then
  echo "[domain-intel] Ready but no scans yet. Run /scan to start collecting."
  exit 0
fi

# Count unread insights
insights_dir="./insights"
if [ ! -d "$insights_dir" ]; then
  exit 0
fi

unread_count=$(grep -rl 'read: false' "$insights_dir/" 2>/dev/null | wc -l | tr -d ' ')

if [ "$unread_count" -gt 0 ]; then
  echo "[domain-intel] $unread_count unread insight(s). Last scan: $last_scan. Use /intel for a briefing."
fi
