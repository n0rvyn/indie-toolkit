#!/bin/bash
# Check for in-progress dev-workflow state and output resume prompt.
# All reading and validation lives in phase.py (the only writer of
# .claude/dev-workflow-state.json) — this hook just calls `status --hook`
# and prints whatever it says, including the named-error lines for a
# broken or off-enum state file. No silent fallback: if phase.py itself
# is missing, that is a visible line, not nothing.

PHASE="$(cd "$(dirname "$0")/.." && pwd)/skills/run-phase/scripts/phase.py"

if [ -f "$PHASE" ]; then
  python3 "$PHASE" status --hook --root .
  exit 0
fi

echo "[dev-workflow] phase.py not found — plugin install incomplete"
exit 0
