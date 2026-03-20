#!/usr/bin/env bash
# run_host.sh — Local orchestrator for single-host inspection
#
# Replaces both ssh_exec.sh (individual commands) and host-connector agent (LLM orchestration).
# SCP's collector.sh + checks.conf to remote host, executes, retrieves JSON output.
#
# Usage: bash run_host.sh <host_json> <collector_path> <checks_conf_path> <output_dir>
#
# Arguments:
#   host_json        - Path to JSON file with host connection details
#   collector_path   - Path to collector.sh script
#   checks_conf_path - Path to checks.conf (bash-sourceable) for this host
#   output_dir       - Directory to write {hostname}.json result
#
# host_json format:
#   {"name":"web1","host":"192.168.1.10","port":22,"user":"deploy",
#    "key":"~/.ssh/id_rsa","password":"","become":true,"become_pass":"","timeout":30}
#
# Exit codes:
#   0 - Success (JSON written to output_dir)
#   1 - SSH/SCP failure (error JSON written to output_dir)
#   3 - Invalid arguments
#   4 - sshpass not installed (required for password auth)

set -uo pipefail

if [[ $# -lt 4 ]]; then
    echo "Usage: run_host.sh <host_json> <collector_path> <checks_conf_path> <output_dir>" >&2
    exit 3
fi

HOST_JSON="$1"
COLLECTOR="$2"
CHECKS_CONF="$3"
OUTPUT_DIR="$4"

# Validate inputs
for f in "$HOST_JSON" "$COLLECTOR" "$CHECKS_CONF"; do
    if [[ ! -f "$f" ]]; then
        echo "Error: File not found: $f" >&2
        exit 3
    fi
done
mkdir -p "$OUTPUT_DIR" 2>/dev/null

# Parse host JSON using python3 (runs locally, python3 guaranteed)
eval "$(python3 -c "
import json, sys, shlex
with open('$HOST_JSON') as f:
    h = json.load(f)
for k in ['name','host','port','user','key','password','become','become_pass','timeout']:
    v = h.get(k, '')
    if isinstance(v, bool):
        v = 'true' if v else 'false'
    print(f'H_{k.upper()}={shlex.quote(str(v))}')
")"

H_PORT="${H_PORT:-22}"
H_TIMEOUT="${H_TIMEOUT:-30}"
H_KEY="${H_KEY:-none}"
H_PASSWORD="${H_PASSWORD:-}"
H_BECOME="${H_BECOME:-false}"
H_BECOME_PASS="${H_BECOME_PASS:-}"

OUTPUT_FILE="${OUTPUT_DIR}/${H_NAME}.json"
RAND=$(head -c 8 /dev/urandom | od -An -tx1 | tr -d ' \n' | head -c 8)
REMOTE_COLLECTOR="/tmp/li-${RAND}.sh"
REMOTE_CHECKS="/tmp/li-checks-${RAND}.conf"

# ── Build SSH options ─────────────────────────────────────────────────────────

SSH_OPTS=(
    -o "ConnectTimeout=${H_TIMEOUT}"
    -o "StrictHostKeyChecking=accept-new"
    -o "LogLevel=ERROR"
    -p "$H_PORT"
)

SCP_OPTS=(
    -o "ConnectTimeout=${H_TIMEOUT}"
    -o "StrictHostKeyChecking=accept-new"
    -o "LogLevel=ERROR"
    -P "$H_PORT"
)

USE_SSHPASS=false
if [[ -n "$H_PASSWORD" && "$H_PASSWORD" != "none" ]]; then
    if ! command -v sshpass &>/dev/null; then
        echo "Error: sshpass required for password auth but not installed" >&2
        exit 4
    fi
    USE_SSHPASS=true
else
    SSH_OPTS+=(-o "BatchMode=yes")
    SCP_OPTS+=(-o "BatchMode=yes")
fi

if [[ "$H_KEY" != "none" && "$H_KEY" != "" ]]; then
    # Expand ~ in key path
    H_KEY="${H_KEY/#\~/$HOME}"
    if [[ -f "$H_KEY" ]]; then
        SSH_OPTS+=(-i "$H_KEY")
        SCP_OPTS+=(-i "$H_KEY")
    fi
fi

TARGET="${H_USER}@${H_HOST}"

# ── Helper functions ──────────────────────────────────────────────────────────

ssh_cmd() {
    if [[ "$USE_SSHPASS" == "true" ]]; then
        sshpass -p "$H_PASSWORD" ssh "${SSH_OPTS[@]}" "$TARGET" "$@"
    else
        ssh "${SSH_OPTS[@]}" "$TARGET" "$@"
    fi
}

scp_cmd() {
    if [[ "$USE_SSHPASS" == "true" ]]; then
        sshpass -p "$H_PASSWORD" scp "${SCP_OPTS[@]}" "$@"
    else
        scp "${SCP_OPTS[@]}" "$@"
    fi
}

write_error() {
    local msg="$1"
    local escaped_msg
    escaped_msg=$(printf '%s' "$msg" | sed 's/"/\\"/g' | tr '\n' ' ')
    cat > "$OUTPUT_FILE" <<EOF
{
  "timestamp": "$(date -u '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date '+%Y-%m-%dT%H:%M:%S')",
  "error": "$escaped_msg",
  "host": "$H_NAME",
  "host_ip": "$H_HOST",
  "status": "unreachable"
}
EOF
}

cleanup_remote() {
    ssh_cmd "rm -f '$REMOTE_COLLECTOR' '$REMOTE_CHECKS'" 2>/dev/null || true
}

# ── Step 1: Test connectivity ─────────────────────────────────────────────────

echo "[run_host] Testing connectivity to ${H_NAME} (${H_HOST}:${H_PORT})..." >&2
if ! ssh_cmd "echo ok" &>/dev/null; then
    write_error "SSH connection failed to ${H_HOST}:${H_PORT}"
    echo "[run_host] FAILED: Cannot connect to ${H_NAME}" >&2
    exit 1
fi

# ── Step 2: SCP files to remote ──────────────────────────────────────────────

echo "[run_host] Uploading collector to ${H_NAME}..." >&2
if ! scp_cmd "$COLLECTOR" "${TARGET}:${REMOTE_COLLECTOR}" 2>/dev/null; then
    write_error "SCP failed: could not upload collector.sh"
    echo "[run_host] FAILED: SCP collector to ${H_NAME}" >&2
    exit 1
fi

if ! scp_cmd "$CHECKS_CONF" "${TARGET}:${REMOTE_CHECKS}" 2>/dev/null; then
    cleanup_remote
    write_error "SCP failed: could not upload checks.conf"
    echo "[run_host] FAILED: SCP checks.conf to ${H_NAME}" >&2
    exit 1
fi

# ── Step 3: Execute collector ─────────────────────────────────────────────────

echo "[run_host] Running collector on ${H_NAME}..." >&2

EXEC_CMD="bash '$REMOTE_COLLECTOR' '$REMOTE_CHECKS'"

# Wrap with privilege escalation if needed
if [[ "$H_BECOME" == "true" ]]; then
    if [[ -n "$H_BECOME_PASS" && "$H_BECOME_PASS" != "none" ]]; then
        EXEC_CMD="echo '${H_BECOME_PASS}' | sudo -S bash '$REMOTE_COLLECTOR' '$REMOTE_CHECKS'"
    else
        EXEC_CMD="sudo -n bash '$REMOTE_COLLECTOR' '$REMOTE_CHECKS'"
    fi
fi

RESULT=""
EXEC_EXIT=0
RESULT=$(ssh_cmd "$EXEC_CMD" 2>/dev/null) || EXEC_EXIT=$?

# ── Step 4: Save output ──────────────────────────────────────────────────────

if [[ $EXEC_EXIT -ne 0 && -z "$RESULT" ]]; then
    cleanup_remote
    write_error "Collector execution failed with exit code $EXEC_EXIT"
    echo "[run_host] FAILED: Collector failed on ${H_NAME} (exit $EXEC_EXIT)" >&2
    exit 1
fi

# Validate JSON output
if ! echo "$RESULT" | python3 -m json.tool &>/dev/null; then
    # Output might still contain useful data; save what we got
    cleanup_remote
    write_error "Collector output is not valid JSON. Raw output: $(echo "$RESULT" | head -5 | tr '\n' ' ')"
    echo "[run_host] FAILED: Invalid JSON from ${H_NAME}" >&2
    exit 1
fi

echo "$RESULT" > "$OUTPUT_FILE"

# ── Step 5: Cleanup remote files ─────────────────────────────────────────────

cleanup_remote
echo "[run_host] OK: ${H_NAME} → ${OUTPUT_FILE}" >&2
exit 0
