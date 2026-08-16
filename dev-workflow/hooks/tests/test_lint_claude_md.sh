#!/bin/bash
# Test harness for lint-claude-md.py PostToolUse hook
set -u

HOOK_DIR="$(cd "$(dirname "$0")/.." && pwd)"
HOOK_SCRIPT="${HOOK_DIR}/lint-claude-md.py"
TMPROOT="$(mktemp -d)"

cleanup() { rm -rf "$TMPROOT" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

PASS=0
FAIL=0

# run_case <name> <project-subdir> <file-basename> <expect-substring|EMPTY>
run_case() {
    local name="$1" proj="$2" fname="$3" expect="$4"
    local path="${TMPROOT}/${proj}/${fname}"
    local input
    input=$(python3 -c "
import json,sys
print(json.dumps({'tool_name':'Edit','tool_input':{'file_path':sys.argv[1]},'hook_event_name':'PostToolUse'}))
" "$path")
    local out __err
    __err=$(mktemp)
    out=$(printf '%s' "$input" | python3 "$HOOK_SCRIPT" 2>"$__err")
    if grep -q 'Traceback\|SyntaxError\|IndentationError' "$__err" 2>/dev/null; then
        echo "  FAIL: $name — hook crashed: $(head -1 "$__err")"; FAIL=$((FAIL+1)); rm -f "$__err"; return
    fi
    rm -f "$__err"

    if [ "$expect" = "EMPTY" ]; then
        if [ -z "$out" ]; then
            echo "  PASS: $name (silent)"; PASS=$((PASS+1))
        else
            echo "  FAIL: $name — expected silence, got: $out"; FAIL=$((FAIL+1))
        fi
    else
        if printf '%s' "$out" | grep -q "$expect"; then
            echo "  PASS: $name"; PASS=$((PASS+1))
        else
            echo "  FAIL: $name — expected '$expect', got: ${out:-<empty>}"; FAIL=$((FAIL+1))
        fi
    fi
}

mk() { mkdir -p "$(dirname "$1")"; cat > "$1"; }

echo "=== lint-claude-md.py ==="

# --- check 1: phantom compound slash reference -------------------------------
mk "${TMPROOT}/p1/CLAUDE.md" <<'EOF'
# p1
Run `/verify-dev-guide` after writing the guide.
EOF
run_case "phantom compound slash is reported" p1 CLAUDE.md "verify-dev-guide"

# real skill must not be reported
mk "${TMPROOT}/p2/CLAUDE.md" <<'EOF'
# p2
Use `/write-dev-guide` then `/run-phase`.
EOF
run_case "existing skills stay silent" p2 CLAUDE.md EMPTY

# --- check 1 exclusions: paths and routes ------------------------------------
mk "${TMPROOT}/p3/CLAUDE.md" <<'EOF'
# p3
Logs go to /tmp/device_crashes and the route is `POST /v1/vision`.
Docs live in `/docs`. Deploy path `/var/www/app`.
Call `POST /api/pages` then `/:id/publish`.
EOF
run_case "paths and routes are not phantoms" p3 CLAUDE.md EMPTY

# --- check 2: dead doc path --------------------------------------------------
mk "${TMPROOT}/p4/CLAUDE.md" <<'EOF'
# p4
See `docs/09-lessons-learned/` for known traps.
EOF
run_case "missing docs path is reported" p4 CLAUDE.md "09-lessons-learned"

mkdir -p "${TMPROOT}/p5/docs/09-lessons-learned"
mk "${TMPROOT}/p5/CLAUDE.md" <<'EOF'
# p5
See `docs/09-lessons-learned/` for known traps.
EOF
run_case "existing docs path stays silent" p5 CLAUDE.md EMPTY

# placeholder paths describe where a file SHOULD go; not a defect
mk "${TMPROOT}/p6/CLAUDE.md" <<'EOF'
# p6
留档位置：`docs/05-features/功能名.md`
变更历史：`docs/07-changelog/YYYY-MM-DD.md`
决策：`docs/03-decisions/ADR-xxx.md`
EOF
run_case "template placeholders are not dead paths" p6 CLAUDE.md EMPTY

# an author who already flagged the path keeps it silent
mk "${TMPROOT}/p7/CLAUDE.md" <<'EOF'
# p7
| 项目概览 | `docs/00-AI-CONTEXT.md` ⚠️ 尚未创建 |
EOF
run_case "acknowledged missing path stays silent" p7 CLAUDE.md EMPTY

# an author's own hedge counts as acknowledgement too
mk "${TMPROOT}/p7b/CLAUDE.md" <<'EOF'
# p7b
1. 更新 `docs/04-implementation/file-structure.md`（如有）
2. 阶段开发指南 `docs/04-dev-guide/dev-guide.md`（待生成）
EOF
run_case "author hedges (如有 / 待生成) stay silent" p7b CLAUDE.md EMPTY

# ... but an unhedged missing path on a similar line still reports
mk "${TMPROOT}/p7c/CLAUDE.md" <<'EOF'
# p7c
1. 更新 `docs/04-implementation/file-structure.md`
EOF
run_case "same path without a hedge still reports" p7c CLAUDE.md "file-structure"

# --- check 3: model-uninvocable skill written as an instruction ---------------
mk "${TMPROOT}/p8/CLAUDE.md" <<'EOF'
# p8
完成后用 `/handoff` 或主动询问用户。
EOF
run_case "disable-model-invocation skill is flagged" p8 CLAUDE.md "disable-model-invocation"

# a sentence recording where the file came from is not an instruction
mk "${TMPROOT}/p8b/CLAUDE.md" <<'EOF'
# p8b
> 由 `/apple-dev:project-kickoff` skill 在 2026-05-07 立项时生成；从未运行 /init。
EOF
run_case "provenance mention is not an instruction" p8b CLAUDE.md EMPTY

# the corrected wording must also stay silent
mk "${TMPROOT}/p8c/CLAUDE.md" <<'EOF'
# p8c
**触发方式**：完成后主动询问用户；需要整会话交接时，提示用户运行 `/handoff`（该 skill 标了 `disable-model-invocation`，模型不能自行调用）
EOF
run_case "wording that routes the skill to the user stays silent" p8c CLAUDE.md EMPTY

# --- scope: non-CLAUDE.md files are ignored ----------------------------------
mk "${TMPROOT}/p9/README.md" <<'EOF'
# p9
Run `/verify-dev-guide` and see `docs/nope/`.
EOF
run_case "non-CLAUDE.md file is ignored" p9 README.md EMPTY

# --- robustness --------------------------------------------------------------
run_case "missing file does not crash" p-nonexistent CLAUDE.md EMPTY

echo ""
echo "PASS: $PASS  FAIL: $FAIL"
[ "$FAIL" -eq 0 ] || exit 1
