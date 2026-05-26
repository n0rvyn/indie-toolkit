#!/bin/bash
# Check for in-progress dev-workflow state and output resume prompt.
# Supports both .json (canonical, run-phase writes this) and .yml (legacy,
# auto-migrated by run-phase on first encounter).

JSON_STATE=".claude/dev-workflow-state.json"
YAML_STATE=".claude/dev-workflow-state.yml"

if [ -f "$JSON_STATE" ]; then
  fields=$(python3 -c "
import json, sys
try:
    with open('$JSON_STATE') as f:
        d = json.load(f)
    step = d.get('phase_step', '')
    if step in ('done', 'finalized'):
        sys.exit(0)
    phase = d.get('current_phase', '?')
    name = d.get('phase_name', '?')
    updated = d.get('last_updated', '?')
    print(f'{phase}|{name}|{step}|{updated}')
except Exception:
    pass
" 2>/dev/null)

  if [ -n "$fields" ]; then
    IFS='|' read -r phase phase_name step updated <<< "$fields"
    echo "[dev-workflow] Phase ${phase} (${phase_name}) in progress — step: ${step}, last updated: ${updated}. Run /run-phase to resume."
  fi
  exit 0
fi

if [ -f "$YAML_STATE" ]; then
  # Legacy YAML path — preserved so pre-migration projects still surface resume prompt
  phase=$(grep '^current_phase:' "$YAML_STATE" | sed 's/current_phase: *//')
  phase_name=$(grep '^phase_name:' "$YAML_STATE" | sed 's/phase_name: *//' | tr -d '"')
  step=$(grep '^phase_step:' "$YAML_STATE" | sed 's/phase_step: *//')
  updated=$(grep '^last_updated:' "$YAML_STATE" | sed 's/last_updated: *//' | tr -d '"')

  if [ "$step" = "done" ] || [ "$step" = "finalized" ]; then
    exit 0
  fi
  echo "[dev-workflow] Phase ${phase} (${phase_name}) in progress — step: ${step}, last updated: ${updated}. Run /run-phase to resume."
fi

exit 0
