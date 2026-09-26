# asc-listing Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "ASC listing"
- "Help me fill out the ASC fields for submission"
- "检查隐私标签应该怎么填"
- "app store listing"
- "What data types do I need to declare in App Privacy?"
- "ASC 现在填的关键词是什么"
- "我改的 ASC 字段存进去了吗"
- "提交出去了吗"
- "is it actually submitted"
- "read back what ASC holds"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Review my code quality"
- "Write a plan for this feature"
- "Fix this bug"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output correctly identifies review mode (full fill / privacy labels / pre-submit audit / specific section)
- [ ] Output loads appropriate reference files based on mode
- [ ] Mode A: Output walks through fields in order, confirming each major section before proceeding
- [ ] Mode B: Output dispatches `apple-dev:app-review-auditor` (mode=guidelines, scope=privacy-only) and renders its code-evidence table and produces privacy label recommendation table with evidence
- [ ] Mode A Step 3.5: Output passes the description/promo text verbatim per locale to `apple-dev:app-review-auditor` (mode=claims) and lists every missing/stub/wrong_target claim as a blocker
- [ ] If the auditor dispatch fails or returns blocked, Output says the check did not run — no privacy table / claims table fabricated inline, not reported as "no issues"
- [ ] Mode C: Output answers specific questions with reference citations
- [ ] Does NOT run code-compliance commands (those belong to /asc-submit-preview)

## Redundancy Risk
Baseline comparison: Base model cannot access Apple's submission requirements without reference documents; this skill provides structured guidance
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
