# review-before-commit Eval

Cases: `evals/review-before-commit/` — run with `claude plugin eval <plugin-dir> --tag review-before-commit --no-publish`. This file holds no assertions that the cases cover.

## Output Assertions
Not observable: host-env, interactive
- [ ] With uncommitted changes, the skill dispatches the Agent tool with `subagent_type: "dev-workflow:change-classifier"` and passes Repo root, Path scope, Change source, Plan file, Lens C source and Timestamp; it does not classify the diff or grep for callers itself
- [ ] When a plan file is referenced in the session or `phase.py status` reports `state.plan_file`, its absolute path is passed as `Plan file`
- [ ] If the dispatch fails or returns `Status: failed` / no `## Change Classifier Result` block, the reply says the review did NOT run and does not report "no risks" or ask "Proceed with `/commit`?"
- [ ] `Breaking-change check: NOT RUN (...)` from the agent is repeated verbatim in the summary
- [ ] High/medium risks from the agent's `### Risks` table (top 4) are asked in one AskUserQuestion call, and the answers are written into the report's `Resolution` column
- [ ] The report exists at `.claude/reviews/review-before-commit-{timestamp}.md` and the reply ends by asking "Proceed with `/commit`?" without committing
