#!/bin/bash
# UserPromptSubmit hook: match user input and suggest relevant skills.
# Injects suggestions as context. Audit-hint and skill-hint can coexist.

input=$(cat)

# Extract user prompt
prompt=$(echo "$input" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('prompt', ''))
except:
    print('')
" 2>/dev/null)

# Skip if user is already invoking a slash command
if echo "$prompt" | grep -q '^/'; then
  exit 0
fi

# Skip very short prompts (greetings, yes/no)
if [ ${#prompt} -lt 6 ]; then
  exit 0
fi

# Audit staleness check (non-blocking; falls through to skill suggestions)
_audit_lower=$(echo "$prompt" | tr '[:upper:]' '[:lower:]')
if echo "$_audit_lower" | grep -qE 'commit|提交|write.*plan|计划|dev.?guide|开发指南'; then
  _audit_file=".claude/last-audit-commit"
  if [ -f "$_audit_file" ]; then
    _stored_sha=$(head -1 "$_audit_file" 2>/dev/null)
    if [ -n "$_stored_sha" ] && git rev-parse HEAD >/dev/null 2>&1; then
      _count=$(git rev-list --count "$_stored_sha"..HEAD 2>/dev/null)
      if [ -n "$_count" ] && [ "$_count" -ge 20 ]; then
        echo "[audit-hint] 距上次代码审计已有 ${_count} 个 commit，建议运行 /code-audit"
      fi
    fi
  fi
fi

# Lowercase for matching
lower=$(echo "$prompt" | tr '[:upper:]' '[:lower:]')

# Project health hint (bounded, non-blocking; at most one line)
if echo "$lower" | grep -qE 'commit|提交|write.*plan|计划|dev.?guide|开发指南|bug|报错|crash|fix.*error|error.*fix'; then
  _hook_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
  _scanner="${_hook_dir}/../scripts/project_health_scan.py"
  if [ -f "$_scanner" ]; then
    _reason="plan"
    if echo "$lower" | grep -qE 'commit|提交'; then
      _reason="commit"
    elif echo "$lower" | grep -qE 'dev.?guide|开发指南'; then
      _reason="dev-guide"
    elif echo "$lower" | grep -qE 'bug|报错|crash|fix.*error|error.*fix'; then
      _reason="fix"
    fi
    _health=$(python3 "$_scanner" --project-root "$(pwd)" --mode light --reason "$_reason" --format json --max-ms 250 2>/dev/null)
    _hint=$(printf '%s' "$_health" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(0)
signals = data.get("signals", {})
bad = [(name, info) for name, info in signals.items() if info.get("status") in {"red", "yellow"}]
if bad:
    name, info = bad[0]
    ev = (info.get("evidence") or ["check project health"])[0]
    status = info.get("status")
    print(f"[health-hint] {name}: {status} — {ev}")
' 2>/dev/null)
    if [ -n "$_hint" ]; then
      echo "$_hint"
    fi
  fi
fi

# Pattern → skill mapping (first match wins)
if echo "$lower" | grep -qE 'commit|提交|save progress'; then
  echo "[skill-hint] Related: /commit — analyzes changes and commits with conventional format"
elif echo "$lower" | grep -qE 'bug|报错|crash|stack.?trace|fix.*error|error.*fix'; then
  echo "[skill-hint] Related: /fix-bug — systematic diagnosis through reproduction and hypothesis"
elif echo "$lower" | grep -qE 'write.*plan|计划|implementation plan'; then
  echo "[skill-hint] Related: /write-plan — creates implementation plan with bite-size tasks"
elif echo "$lower" | grep -qE 'brainstorm|创意|explore.*idea|头脑风暴'; then
  echo "[skill-hint] Related: /brainstorm — explores intent, requirements and design before implementation"
elif echo "$lower" | grep -qE 'design.*prompt|stitch.*prompt|figma.*prompt|generate.*prompt.*design|设计提示词|生成.*prompt'; then
  echo "[skill-hint] Related: /generate-design-prompt — generates Stitch/Figma prompts from project features"
elif echo "$lower" | grep -qE 'design.*prototype|prototype.*design|understand.*design|analyze.*design|stitch.*design|figma.*design|design.*analysis|设计原型|分析设计|理解设计'; then
  echo "[skill-hint] Related: /understand-design — analyzes design prototypes with dual-channel image+code understanding"
elif echo "$lower" | grep -qE 'phase|阶段|next phase|run.phase'; then
  echo "[skill-hint] Related: /run-phase — orchestrates plan-execute-review cycle"
elif echo "$lower" | grep -qE 'crystal|crystallize|固化.*决策|决策.*结晶|结晶|settle.*decision|lock.*decision'; then
  echo "[skill-hint] Related: /crystallize — locks settled decisions into a crystal file before planning"
elif echo "$lower" | grep -qE 'design.*decision|设计决策|tradeoff|trade.off'; then
  echo "[skill-hint] Related: /design-decision — analyzes trade-offs between approaches"
elif echo "$lower" | grep -qE 'search.*knowledge|知识库|past.*lesson|之前.*遇到|find.*lesson|记得.*问题|similar.*bug|seen.*before|how.*last.*time|以前怎么'; then
  echo "[skill-hint] Related: /kb — search cross-project knowledge base"
elif echo "$lower" | grep -qE 'lesson|教训|踩坑|pitfall'; then
  echo "[skill-hint] Related: /collect-lesson — extracts and saves a lesson to the knowledge base"
elif echo "$lower" | grep -qE 'kickoff|新项目|init.*project|project.*init'; then
  echo "[skill-hint] Related: /project-kickoff — guided iOS project initialization"
elif echo "$lower" | grep -qE 'dev.?guide|开发指南|development guide'; then
  echo "[skill-hint] Related: /write-dev-guide — creates phased development guide"
elif echo "$lower" | grep -qE 'review.*(code|impl)|代码审查|审查.*实现'; then
  if echo "$lower" | grep -qE 'phase|plan|计划|阶段|执行'; then
    echo "[skill-hint] Related: /run-phase — orchestrates plan-execute-review cycle"
  else
    echo "[skill-hint] Related: /review-before-commit — semantic diff review before commit"
  fi
fi

exit 0
