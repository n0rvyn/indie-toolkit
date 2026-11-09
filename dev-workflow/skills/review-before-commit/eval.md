# review-before-commit Eval

Cases: `evals/review-before-commit/` — run with `claude plugin eval <plugin-dir> --tag review-before-commit --scaffold --allow-tools Bash Write Edit --no-publish`. Trigger cases cover routing; `03-evidence-calibration` covers the classifier dispatch, a read-only evidence check and report grading against synthetic platform/policy, static/runtime, fallback and broken-consumer evidence. This file holds no assertions that the cases cover.

## Output Assertions
Not observable: host-env, interactive
- [ ] When a user supplies a plan or evidence/corrections in a prior turn, the dispatch passes the absolute Plan file and relevant Verification context rather than relying on the agent seeing conversation history
- [ ] If the dispatch fails or returns `Status: failed` / no `## Change Classifier Result` block, the reply says the review did NOT run and does not report "no risks" or ask "Proceed with `/commit`?"
- [ ] `Breaking-change check: NOT RUN (...)` from the agent is repeated verbatim in the summary
- [ ] Only confirmed high/medium risks after evidence verification (top 4) are asked in one AskUserQuestion call, and the answers are written into the report's `Resolution` column
- [ ] If a material premise remains unverified after safe checks, the report retains the proposed severity and missing evidence, no clean verdict is reported, and the factual claim is excluded from acceptance choices
- [ ] After interactive disposition, the summary uses the verified report's counts and verdict, and asks "Proceed with `/commit`?" without committing
