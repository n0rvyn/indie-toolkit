#!/usr/bin/env bash
# ssh_exec.sh — Execute a command on a remote host via SSH
#
# Usage: bash ssh_exec.sh <host> <port> <user> [key_file] [timeout] [become] [become_method] [password] [become_pass] <<< "<commands>"
#
# Arguments:
#   host           - Hostname or IP
#   port           - SSH port
#   user           - SSH user
#   key_file       - Path to SSH private key (use "none" to skip)
#   timeout        - Connection timeout in seconds (default: 30)
#   become         - "true" to use privilege escalation (default: "false")
#   become_method  - "sudo" (default: "sudo"). Only sudo is supported.
#   password       - SSH login password (optional; requires sshpass)
#   become_pass    - sudo password (optional; uses sudo -S when set)
#
# The command to execute is read from stdin.
#
# Authentication:
#   - If `password` is provided and non-empty, uses sshpass for password-based SSH.
#     sshpass must be installed; exit code 4 if missing.
#   - If `password` is empty or "none", uses key-based auth with BatchMode=yes.
#     Only key-based authentication works in this mode.
#
# NOTE: StrictHostKeyChecking=accept-new auto-trusts unknown hosts on first
# connection. This is a TOFU (trust-on-first-use) model. For high-security
# environments, pre-populate known_hosts or set StrictHostKeyChecking=yes.
#
# Exit codes:
#   0 - Success
#   1 - SSH connection failed or command failed
#   3 - Invalid arguments
#   4 - sshpass not installed (required for password auth)

set -euo pipefail

if [[ $# -lt 3 ]]; then
    echo "Usage: ssh_exec.sh <host> <port> <user> [key_file] [timeout] [become] [become_method] [password] [become_pass]" >&2
    exit 3
fi

HOST="$1"
PORT="$2"
USER="$3"
KEY_FILE="${4:-none}"
TIMEOUT="${5:-30}"
BECOME="${6:-false}"
BECOME_METHOD="${7:-sudo}"
PASSWORD="${8:-}"
BECOME_PASS="${9:-}"

# Read command from stdin
COMMAND=$(cat)

if [[ -z "$COMMAND" ]]; then
    echo "Error: No command provided on stdin" >&2
    exit 3
fi

# Build SSH options
SSH_OPTS=(
    -o "ConnectTimeout=${TIMEOUT}"
    -o "StrictHostKeyChecking=accept-new"
    -o "LogLevel=ERROR"
    -p "$PORT"
)

# Determine auth mode
USE_SSHPASS=false
if [[ -n "$PASSWORD" && "$PASSWORD" != "none" ]]; then
    if ! command -v sshpass &>/dev/null; then
        echo "Error: sshpass is not installed. Password-based SSH auth requires sshpass." >&2
        echo "Install: brew install hudochenkov/sshpass/sshpass (macOS) or apt install sshpass (Linux)" >&2
        exit 4
    fi
    USE_SSHPASS=true
else
    SSH_OPTS+=(-o "BatchMode=yes")
fi

if [[ "$KEY_FILE" != "none" && -f "$KEY_FILE" ]]; then
    SSH_OPTS+=(-i "$KEY_FILE")
fi

# Wrap command with privilege escalation if needed (sudo only).
if [[ "$BECOME" == "true" ]]; then
    if [[ -n "$BECOME_PASS" && "$BECOME_PASS" != "none" ]]; then
        # sudo -S reads password from stdin; echo password then pipe the command
        COMMAND="echo '${BECOME_PASS}' | sudo -S bash <<'INSPECT_EOF'
${COMMAND}
INSPECT_EOF"
    else
        COMMAND="sudo -n bash <<'INSPECT_EOF'
${COMMAND}
INSPECT_EOF"
    fi
fi

# Execute via stdin pipe
if [[ "$USE_SSHPASS" == "true" ]]; then
    echo "$COMMAND" | sshpass -p "$PASSWORD" ssh "${SSH_OPTS[@]}" "${USER}@${HOST}" bash -s 2>&1
else
    echo "$COMMAND" | ssh "${SSH_OPTS[@]}" "${USER}@${HOST}" bash -s 2>&1
fi
