# Out-of-Scope Archive

This directory records ideas that were considered for `dev-workflow` and explicitly rejected. It exists to prevent the same suggestion from resurfacing across sessions, agents, and contributors.

## When to add an entry

- A decision-point (`DP-xxx`) was raised, the user chose "no / out of scope / not do / range outside", and the reason is durable (will still be valid in 3+ months).
- A skill, agent, or pattern from another marketplace was evaluated and explicitly not adopted.
- A scope item was removed from a plan with a documented rationale.

## When NOT to add an entry

- Ephemeral preferences ("not now, maybe later") — those go in plan headers as deferred items.
- Implementation-detail rejections (function naming, internal split) — too small to be worth tracking.
- Decisions a code reader can derive from the codebase itself.

## Entry format

Each `.md` file MUST contain these 4 fields:

```markdown
# {Short title of the rejected idea}

**Decision:** Do not {action}.
**Rejected on:** YYYY-MM-DD
**Reason:** {1–3 sentences. Cite the rule, file, or constraint that makes this rejection durable.}
**Reopen condition:** {What would have to change for this to be revisited? Be specific. "If users start asking N times" is fine.}

{Optional: 1–2 paragraphs of background context, links to source discussion.}
```

## Who reads this archive

- `plan-verifier` agent — greps this directory before raising any new `DP-xxx`. If a `DP-xxx` would re-raise a rejected idea, it must skip generation and include a one-line note in the verification report: `Skipped DP candidate: {idea} — rejected per .out-of-scope/{file}`.
- `design-decision` skill — reads this directory at Step 1 to ensure none of the options it is comparing was already rejected.
- Future contributors — when proposing a new feature, scan this directory first.

## Reopening a rejected decision

If you believe a rejected decision should be revisited:
1. Move the file from `.out-of-scope/` to a new plan or design doc as the explicit topic.
2. Document what changed (the "Reopen condition" that fired).
3. Run normal `/brainstorm` -> `/write-plan` flow.
4. If the new flow concludes "still rejected", update the original `.out-of-scope/*.md` with a new `Re-rejected on:` line; do not delete.
