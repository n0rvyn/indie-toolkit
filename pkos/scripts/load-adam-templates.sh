#!/bin/bash
# Load PKOS task templates into Adam via REST API.
# Usage: load-adam-templates.sh [adam-url]
# Requires: Adam server running, yq installed

set -euo pipefail

ADAM_URL="${1:-http://localhost:7100}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CONFIG="$SCRIPT_DIR/../config/adam-task-templates.yaml"

if ! command -v yq &>/dev/null; then
    echo "Error: yq is required (brew install yq)" >&2
    exit 1
fi

# Check Adam is running
if ! curl -sf "$ADAM_URL/healthz" >/dev/null 2>&1; then
    echo "Error: Adam not reachable at $ADAM_URL" >&2
    echo "Start Adam first: cd /Users/norvyn/Code/Projects/Adam && pnpm start" >&2
    exit 1
fi

count=$(yq '.templates | length' "$CONFIG")
echo "Loading $count PKOS task templates into Adam..."

for i in $(seq 0 $((count - 1))); do
    id=$(yq ".templates[$i].id" "$CONFIG")
    name=$(yq ".templates[$i].name" "$CONFIG")

    # Convert YAML template to JSON for API
    json=$(yq -o=json ".templates[$i]" "$CONFIG")

    # Create or update template
    status=$(curl -sf -o /dev/null -w "%{http_code}" \
        -X POST "$ADAM_URL/task-templates" \
        -H "Content-Type: application/json" \
        -d "$json" 2>/dev/null || echo "000")

    if [ "$status" = "200" ] || [ "$status" = "201" ]; then
        echo "  ✅ $id ($name)"
    else
        echo "  ❌ $id ($name) — HTTP $status"
    fi
done

echo "Done. Verify: curl $ADAM_URL/task-templates"
