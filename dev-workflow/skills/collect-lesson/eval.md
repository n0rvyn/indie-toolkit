# collect-lesson Eval

Cases: `evals/collect-lesson/` — run with `claude plugin eval ./dev-workflow --tag collect-lesson --scaffold --no-publish`. The behavior cases seed a fixture knowledge base with `scaffold_script`; without `--scaffold` they run against an empty one and fail.

## Output Assertions
Not observable: host-env
The run can read a knowledge base seeded into its temp `$HOME`, but writes outside the workspace are denied (verified 2026-09-26: project `.claude/settings.json` allow rules and `--allow-tools "Write(//…)"` path grants both still denied). So what Step 4 and Step 5c write into `~/.claude/knowledge/` is not observable; the verdict that drives it is, in the draft (`draft-proposes-supersede`, `draft-proposes-scope-note`).
- [ ] A confirmed Superseded verdict adds `status: superseded` and `superseded_by: {new filename}` to the old entry's frontmatter, and the `⛔ 已被取代` line under its title
- [ ] The new entry lists the old one under `supersedes:`
- [ ] A confirmed Different-scope verdict appends the `↔ 适用范围不同` line to both entries
- [ ] No entry gets a "potential conflict — review both" note
- [ ] Global saves add mutual `related:` fields for entries with ≥2 shared keywords, and the report line counts related, links, superseded, scope notes
