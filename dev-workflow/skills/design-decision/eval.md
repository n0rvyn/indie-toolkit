# design-decision Eval

## Trigger Tests
- "Which approach is better: A or B?"
- "I'm stuck between these two designs"
- "How should I design this?"

## Negative Trigger Tests
- "Brainstorm some ideas"
- "Write the implementation"

## Output Assertions
- [ ] Output separates essential from accidental complexity
- [ ] Output presents trade-offs in structured format (Rule 13 comparison table)
- [ ] Output makes recommendation with reasoning
- [ ] User selected an approach before proceeding
- [ ] Step 0 Out-of-scope check must exist before Step 1 (Understand Complexity Source); must list .out-of-scope/*.md and surface matches to user.
- [ ] Step 0.5 Pre-decision Expectation Check must exist between Step 0 (out-of-scope check) and Step 1 (understand complexity).
- [ ] Pre-decision Expectation Check must require user confirmation before proceeding to Step 1.
- [ ] Step 3 contains 5th evaluation question on module shape (deep/shallow + seam/adapter), referencing dev-workflow/references/deep-modules-pattern.md; Output section includes "module-shape note" requirement per option

## Redundancy Risk
Baseline comparison: Base model can analyze trade-offs but lacks structured essential vs accidental complexity framework
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: monitor
