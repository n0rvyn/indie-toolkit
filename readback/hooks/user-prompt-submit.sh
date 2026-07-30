#!/usr/bin/env bash
# readback: user-prompt-submit — inject a non-blocking "state your reading" hint
# when the prompt has a genuine ambiguous referent.
#
# Schema v3 (2026-07-30). What changed and why:
#
#   v2 fired on action-verb presence (`fix` / `修` / `implement` / …) and injected a
#   BLOCKING mandate: dispatch intent-echoer, paste 3 paragraphs verbatim, STOP and
#   wait for confirmation. Two problems, both structural:
#
#   1. Wrong event. UserPromptSubmit runs before the model has looked at anything,
#      so the hook can only guess ambiguity from surface words. That is why v2 needed
#      five skip groups and nine CJK idiom-stripping sed rules and STILL fired on
#      discussion prompts ("你没有说修复建议？").
#   2. Wrong output. A blocking stop-and-confirm on every action prompt contradicts
#      the harness instruction to reserve blocking questions for cases where proceeding
#      would be unsafe or would waste the work. Cost of being wrong about a reading is
#      one correction message; cost of stopping is a round-trip on every single task.
#
#   v3 inverts both: fire only on a genuine ambiguous-referent signal, and ask for a
#   one-sentence statement of the chosen reading WITHOUT stopping. The user's stop
#   mechanism is ESC, which is always available and costs them nothing when unused.
#
# Trigger = (ambiguity signal) AND (no concrete target named) AND (not a discussion prompt).
# Emits `additionalContext`. Fails open on any error.
set -e

trap 'echo "{}"; exit 0' ERR

INPUT=$(cat)
# Claude Code stdin field is `prompt` (not `user_prompt`); verified against
# dev-workflow/hooks/suggest-skills.sh in this repo.
PROMPT=$(echo "$INPUT" | jq -r '.prompt // empty')

[ -z "$PROMPT" ] && { echo "{}"; exit 0; }

# ── Skip 1: slash commands. Flow control and explicit skill entry, not a request
# whose referent could be misread. `/readback` itself is the manual full-echo path.
if echo "$PROMPT" | grep -qE "^/"; then
  echo "{}"; exit 0
fi

# ── Skip 2: explicit bypass ───────────────────────────────────────────────────
if echo "$PROMPT" | grep -qiE "^(go|just do it|--no-questions|skip readback)\b" \
   || echo "$PROMPT" | grep -qE "^直接做"; then
  echo "{}"; exit 0
fi

# ── Skip 3: discussion / opinion / question. The deliverable is an answer, not a
# change, so there is no work to misdirect. Matches anywhere in the prompt.
# The 你(没有|没|忘了|漏了) arm is the v2 leak that fired on "你没有说修复建议？".
if echo "$PROMPT" | grep -qE "你(同意|觉得|认为|怎么看|怎么想|没有|没|忘了|漏了)" \
   || echo "$PROMPT" | grep -qE "如何(更好|改进|优化|设计|做|解决|处理|应对|界定|判断)" \
   || echo "$PROMPT" | grep -qE "我(觉得|认为|的看法|的认识|在想|想问|想了解)" \
   || echo "$PROMPT" | grep -qE "(同意我|同意吗|觉得呢|对吗|好不好|行不行|是不是应该|有没有|要不要)" \
   || echo "$PROMPT" | grep -qE "(讨论|商量|方案对比|你的建议|给个建议|怎么理解|什么意思)" \
   || echo "$PROMPT" | grep -qiE "(do you agree|what do you think|how would you|should (i|we)|thoughts\?|discuss)"; then
  echo "{}"; exit 0
fi

# ── Skip 4: a concrete target is named, so the referent is not in doubt ────────
# A file path, a backticked identifier, a call site, a CamelCase symbol, or a line
# reference all pin down what the user means. Checked BEFORE ambiguity signals so
# "把 `CardTitle` 的这个字号改小" does not fire.
if echo "$PROMPT" | grep -qE "[A-Za-z0-9_./-]+\.(swift|ts|tsx|js|jsx|py|md|json|sh|ya?ml|go|rs|java|kt|c|cpp|h|hpp|rb|php|css|html)\b" \
   || echo "$PROMPT" | grep -q '`' \
   || echo "$PROMPT" | grep -qE "[A-Za-z_][A-Za-z0-9_]*\(\)" \
   || echo "$PROMPT" | grep -qE "\b[a-z]+[A-Z][A-Za-z0-9]*\b|\b[A-Z][a-z0-9]+[A-Z][A-Za-z0-9]*\b" \
   || echo "$PROMPT" | grep -qE ":[0-9]+\b|\bL[0-9]+\b" \
   || echo "$PROMPT" | grep -qE "第\s*[0-9]+\s*(行|处|个)"; then
  echo "{}"; exit 0
fi

# ── Ambiguity signals ─────────────────────────────────────────────────────────
# Each is a case where two or more readings are genuinely available and picking the
# wrong one wastes the work. Derived from the referent-ambiguity rule in the user's
# global CLAUDE.md ("那个颜色 / 这个字号 / 那种风格" and multi-difference screenshots).
SIGNAL=""

# A locator ("顶部那个间距", "左上", "第 2 处") pins the referent down even when a
# demonstrative is present, so it suppresses A1, A2 and A2b alike.
HAS_LOCATOR=false
if echo "$PROMPT" | grep -qE "(左上|右上|左下|右下|顶部|底部|中间|靠上|靠下|第\s*[0-9]+)" \
   || echo "$PROMPT" | grep -qiE "\b(top|bottom|leftmost|rightmost|first|second|third)\b"; then
  HAS_LOCATOR=true
fi

# A1: a screenshot with no locator. "改成图里那样" — which of the differences?
if [ "$HAS_LOCATOR" = "false" ] && echo "$PROMPT" | grep -qE "\[Image"; then
  SIGNAL="截图里有多处可指对象，未指明哪一处"
fi

# A2: demonstrative + ATTRIBUTE noun. The noun list is attributes only, never
# objects: "这个字号" leaves the owning object unnamed (the real failure mode),
# whereas "这个按钮" names the object and is only ambiguous if several exist —
# object nouns here produced false positives on "只重构这个按钮的样式".
if [ -z "$SIGNAL" ] && [ "$HAS_LOCATOR" = "false" ] \
   && echo "$PROMPT" | grep -qE "(那个|这个|那种|这种|那些|这些)[ 　]*(颜色|色|字号|字体|大小|尺寸|间距|边距|圆角|阴影|样式|风格|布局|位置|排版|效果|动画)"; then
  SIGNAL="指示代词 + 属性名，未点明是哪一个对象的该属性"
fi

# A2b: bare demonstrative as the object — "改成那样" / "make it like that".
if [ -z "$SIGNAL" ] && [ "$HAS_LOCATOR" = "false" ] \
   && { echo "$PROMPT" | grep -qE "(改成那样|改成这样|像那样|像这样|按那个来|按这个来|就那样|跟那个一样|和那个一样)" \
   || echo "$PROMPT" | grep -qiE "\b(like that|like this|that one|the other one) *$"; }; then
  SIGNAL="以指示代词指代目标状态，未描述目标状态本身"
fi

# A3: broad-scope change with no target. "重构一下" / "统一样式" — which units?
if [ -z "$SIGNAL" ] && echo "$PROMPT" | grep -qE "(重构|统一|全部改|都改|整体调|整个改|全都|通通)" \
   && ! echo "$PROMPT" | grep -qE "(只|仅|限于|范围是)"; then
  SIGNAL="要求大范围变更，未界定范围边界"
fi

if [ -z "$SIGNAL" ]; then
  echo "{}"; exit 0
fi

# ── Minimal state check: an explicitly confirmed readback is already in force ──
# fix-bug Step pre-0 and write-plan Step 2.5 write this file and own the strict
# blocking flow. Do not add a second voice on top of theirs.
STATE_FILE=".claude/readback-state.json"
if [ -r "$STATE_FILE" ]; then
  CONFIRMED=$(jq -r '.user_confirmed // false' "$STATE_FILE" 2>/dev/null || echo "false")
  [ "$CONFIRMED" = "true" ] && { echo "{}"; exit 0; }
fi

HINT=$(cat <<HINT_EOF
[readback-hint] This request has an ambiguous referent: ${SIGNAL}.

Open your reply with ONE sentence naming the reading you picked and the one you ruled out, in the user's own words. Example: "我理解你指的是卡片标题的字号（不是正文），按这个改。"

Then keep working in the same turn. Do NOT dispatch an agent for this, and do NOT stop to wait for confirmation — the user interrupts with ESC if the reading is wrong, and a wrong reading costs one correction message while stopping costs a round-trip on every task.

Stop and ask only if the work you would do before any feedback is destructive, irreversible, or a real scope change.
HINT_EOF
)

jq -n --arg ctx "$HINT" '{
  hookSpecificOutput: {
    hookEventName: "UserPromptSubmit",
    additionalContext: $ctx
  }
}'
exit 0
