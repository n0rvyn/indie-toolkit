#!/bin/bash
# Tests for scan-secrets.sh: a commit is scanned in the repository it actually
# writes to (git -C, --git-dir/--work-tree, GIT_DIR=, cd && ...), not the session cwd.
set -u

HOOK_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HOOK_SCRIPT="${HOOK_DIR}/scan-secrets.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT INT TERM

G=(git -c user.email=t@example.com -c user.name=t -c init.defaultBranch=main -c commit.gpgsign=false)
# Fake AWS key assembled at runtime so this file never holds one verbatim
# (the hook would otherwise block committing this test).
SECRET="AKIA""ABCDEFGHIJKLMNOP"

make_repo() {  # make_repo <dir> <with initial commit: yes|no>
    mkdir -p "$1"
    "${G[@]}" -C "$1" init -q
    if [ "$2" = yes ]; then
        echo ok > "$1/a.txt"
        "${G[@]}" -C "$1" add a.txt
        "${G[@]}" -C "$1" commit -qm init
    fi
}
stage_secret() {
    echo "key = ${SECRET}" > "$1/leak.txt"
    "${G[@]}" -C "$1" add leak.txt
}

LEAKY="$WORK/leaky repo"   # space in the path on purpose
CLEAN="$WORK/clean"
UNBORN="$WORK/unborn"      # no commits yet: diff --cached has no HEAD
ELSEWHERE="$WORK/elsewhere" # not a git repository
make_repo "$LEAKY" yes; stage_secret "$LEAKY"
make_repo "$CLEAN" yes
make_repo "$UNBORN" no; stage_secret "$UNBORN"
mkdir -p "$ELSEWHERE"

PASS=0
FAIL=0

run_case() {  # run_case <name> <session cwd> <command> <expected exit> [expected stderr substring]
    local name="$1" cwd="$2" command="$3" expect="$4" expect_stderr="${5:-}" input code stderr_output
    input=$(python3 -c 'import json, sys; print(json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": sys.argv[1]}, "cwd": sys.argv[2]}))' "$command" "$cwd")
    stderr_output=$(cd "$cwd" && printf '%s' "$input" | bash "$HOOK_SCRIPT" 2>&1 >/dev/null)
    code=$?
    if [ "$code" -eq "$expect" ] && { [ -z "$expect_stderr" ] || echo "$stderr_output" | grep -q "$expect_stderr"; }; then
        echo "PASS: $name"
        PASS=$((PASS+1))
    else
        echo "FAIL: $name (exit=$code, expected=$expect${expect_stderr:+/$expect_stderr}, stderr=$stderr_output)"
        FAIL=$((FAIL+1))
    fi
}

# --- must block: the target repo has a staged secret ---
run_case "plain-commit" "$LEAKY" "git commit -m x" 2
run_case "unborn-repo" "$UNBORN" "git commit -m x" 2
run_case "dash-C-from-elsewhere" "$ELSEWHERE" "git -C '$LEAKY' commit -m x" 2
run_case "dash-C-relative" "$WORK" "git -C 'leaky repo' commit -m x" 2
run_case "dash-c-then-dash-C" "$ELSEWHERE" "git -c core.quotepath=off -C '$LEAKY' commit -m x" 2
run_case "git-dir-work-tree" "$ELSEWHERE" "git --git-dir='$LEAKY/.git' --work-tree='$LEAKY' commit -m x" 2
run_case "GIT_DIR-assignment" "$ELSEWHERE" "GIT_DIR='$LEAKY/.git' GIT_WORK_TREE='$LEAKY' git commit -m x" 2
run_case "cd-and-commit" "$ELSEWHERE" "cd '$LEAKY' && git commit -m x" 2
run_case "cd-newline-commit" "$ELSEWHERE" "cd '$LEAKY'"$'\n'"git commit -m x" 2
run_case "second-of-two-commits" "$ELSEWHERE" "git -C '$CLEAN' commit -m a && git -C '$LEAKY' commit -m b" 2
run_case "redirect-and-pipe" "$ELSEWHERE" "git -C '$LEAKY' commit -m x 2>&1 | tail -1" 2
run_case "heredoc-message" "$LEAKY" "git commit -m \"\$(cat <<'EOF'"$'\n'"subject"$'\n\n'"body line"$'\n'"EOF"$'\n'")\"" 2
run_case "unparseable-falls-back-to-cwd" "$LEAKY" "git commit -m \"unclosed" 2 "could not parse"
run_case "unresolved-cd-falls-back-to-cwd" "$LEAKY" "cd \"\$REPO\" && git commit -m x" 2 "could not resolve"

# --- must pass: not a commit, or the target repo is clean ---
run_case "dash-C-clean-while-cwd-leaky" "$LEAKY" "git -C '$CLEAN' commit -m x" 0
run_case "cd-clean-while-cwd-leaky" "$LEAKY" "cd '$CLEAN' && git commit -m x" 0
run_case "git-status" "$LEAKY" "git status" 0
run_case "commit-word-as-argument" "$LEAKY" "git log --grep commit" 0
run_case "commit-inside-echo" "$LEAKY" "echo \"git commit\"" 0

echo "---"
echo "PASS: $PASS  FAIL: $FAIL"
[ "$FAIL" -eq 0 ]
