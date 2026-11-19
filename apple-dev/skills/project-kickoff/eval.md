# project-kickoff Eval

Cases: `evals/project-kickoff/` — run with `claude plugin eval <plugin-dir> --tag project-kickoff --no-publish`. Bundled generator checks: `scripts/test_project_instruction_reference.py`.

## Output Assertions
Not observable: interactive, cross-plugin, host-env
<!-- What must be true in the skill's output -->
- [ ] Output clarifies requirements through iterative questions (problem, users, angle)
- [ ] Output performs "AI era check" before market research (can existing AI tools solve this?)
- [ ] Output assesses AI replacement risk and identifies irreplaceable value
- [ ] Output keeps the full CP1 展示内容 block (concept table + 领域研究摘要 + Expectation Recap + the AskUserQuestion options) within 20 lines when step 2.5 does not fire, and within 28 lines when it does — measure the whole block, not the first table alone
- [ ] Output uses AskUserQuestion with Continue / Customized / Adjust options
- [ ] Output skips market research for customized projects where client confirmed requirements
- [ ] All 5 checkpoints (CP1, CP2, CP3, CP4, CP5) must contain an [Expectation Recap] block immediately before AskUserQuestion.
- [ ] Step 2.5 gate is evaluated explicitly: a project with no mechanism dependency (e.g. an expense tracker) must SKIP the domain research scan and record "无机制依赖" rather than producing citations. A mechanism-dependent project (e.g. handwriting recognition, habit formation, sleep scoring) must run it.
- [ ] Every URL appearing in the 领域研究 output (CP1 summary table and, later, the project-brief section) is the target of a preceding WebFetch tool call in the same run — check the transcript, not the prose. Any citation with no such call is marked ⚠️ and is absent from CP1's 领域研究判定.
- [ ] Every ✅, ❌, and ⚠️无定论 row carries a transferability verdict (直接适用 / 仅作背景) — not only ✅ rows. Rows whose status is 检索无命中 / 抓不到一手来源 / 一手来源抽验未通过 correctly OMIT it (there is no source to compare against); a verdict invented for one of those is a failure, not a pass.
- [ ] A ⚠️ produced by zero search hits is labeled 检索无命中 (with the queries tried) and NOT 文献无定论; the run shows a positive-control query on a known-hit mechanism before any zero result is reported.

## Redundancy Risk
Baseline comparison: Base model can discuss ideas but lacks structured AI-era feasibility validation and iterative clarification flow
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential

## Generated support reference
Not observable: interactive, host-env
- [ ] New Apple app intake invokes shared lifecycle skill; no recursive kickoff call.
- [ ] Existing CLAUDE.md/AGENTS.md contents preserved; installer and check execute after generation.
- [ ] Missing or edited managed reference cannot be reported as successful generation.
- [ ] No per-app manual indexing/global config/cache mutation; non-Apple init skips reference.
