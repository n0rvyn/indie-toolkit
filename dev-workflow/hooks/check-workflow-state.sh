#!/bin/bash
# Check for in-progress dev-workflow state and output resume prompt

STATE_FILE=".claude/dev-workflow-state.yml"

if [ ! -f "$STATE_FILE" ]; then
  exit 0
fi

phase=$(grep '^current_phase:' "$STATE_FILE" | sed 's/current_phase: *//')
phase_name=$(grep '^phase_name:' "$STATE_FILE" | sed 's/phase_name: *//' | tr -d '"')
step=$(grep '^phase_step:' "$STATE_FILE" | sed 's/phase_step: *//')
updated=$(grep '^last_updated:' "$STATE_FILE" | sed 's/last_updated: *//' | tr -d '"')

if [ "$step" = "done" ]; then
  exit 0
fi

echo "[dev-workflow] Phase ${phase} (${phase_name}) in progress — step: ${step}, last updated: ${updated}. Run /run-phase to resume."
