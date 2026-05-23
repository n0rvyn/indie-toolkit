---
name: verify-plan
description: "Use when a plan has been written and needs validation before execution, or the user says 'verify plan', 'check the plan', 'review the plan', 'validate plan', '检查计划', '验证计划'. VERIFY-ONLY — does not execute the plan; invoke execute-plan separately. Applies Verification-First method with falsifiable error candidates, failure reverse reasoning, optional Design Token consistency checks, Design Faithfulness anchoring, and Architecture Review. Not when: code already executed — use implementation-reviewer instead. Not when: plan does not yet exist — use write-plan first."
user-invocable: true
---

## Overview

This skill dispatches the `dev-workflow:plan-verifier` agent to validate an implementation plan in a separate context so it starts with a fresh, unbiased perspective.

**Mode:** VERIFY-ONLY. This skill dispatches plan-verifier (read-only) and writes only to `.claude/reviews/`. No source files are modified. As a clarity aid (not enforced), the dispatching context may echo `[Mode: VERIFY — read-only]` as the first line of its response before invoking this skill, so the user has explicit confirmation that no execution is about to happen.

**Optional flag: `--fast`**
When passed: use Sonnet instead of Opus for verification.
Appropriate for plans with < 5 tasks or simple single-concern changes.
Default (no flag): Opus for thorough verification.

## Process

### Step 1: Gather Context

Collect the following before dispatching:

1. **Plan file path** — identify from:
   - Most recent `write-plan` output in conversation
   - User-specified path
   - Search `docs/06-plans/*-plan.md` for recent plan files
2. **Design doc path** — check the plan header for a `Design doc:` reference; if none, set to "none"
3. **Design analysis path** — check the plan header for a `Design analysis:` reference; if none, search `docs/06-plans/*-design-analysis.md`; if none found, set to "none"
4. **Crystal file path** — resolve in this order:
   - If the plan header has a `Crystal file:` reference → use that path
   - Else search `docs/11-crystals/*-crystal.md`: if exactly 1 file → use it automatically
   - If multiple files → ask the user which one applies
   - If no files → set to "none"
5. **Bug diagnosis value** — read the plan header's `**Bug diagnosis:**` field verbatim. Three possible shapes: (a) `not applicable` → pass through as `not applicable`; (b) inline structured bundle → pass through verbatim; (c) `see .claude/bug-diagnosis-{slug}.md` path reference → pass through the path string (plan-verifier opens the file itself per its Inputs item 7). Do not interpret or summarize the field — let plan-verifier's BD strategy parse it.
6. **Project root** — current working directory

If the plan file path is unclear, ask the user.

### Step 1.5: Retrieve Error Patterns (via `dev-workflow:kb`)

After collecting plan and design doc paths, extract technical keywords from the plan (framework names, API names, component names found in the plan file) and search for known error patterns:

1. Invoke `dev-workflow:kb` skill via the Skill tool with the technical keywords as the query. The kb skill searches `~/.claude/knowledge/` (categories: api-misuse / api-usage / architecture / bug-postmortem / data-research / platform-constraints / workflow) for error patterns and lessons related to the plan's technologies.
2. If results are returned: collect them as `retrieved_context` — a compact list of (source_path, section, content preview) for each hit
3. If the kb skill returns no matches, or the knowledge directory is empty: set `retrieved_context` to empty and continue

### Step 2: Dispatch Agent

Use the Task tool to launch the `dev-workflow:plan-verifier` agent:
- Default (no --fast): add `model: "opus"` to the Task tool call
- With --fast flag: add `model: "sonnet"` to the Task tool call

Note: must explicitly set model to ensure the agent uses the intended model regardless of parent session configuration.

Before dispatching, extract any **previously resolved decisions** from the plan file:
- Search the plan's `## Decisions` section for entries with `**Chosen:**` (not just `**Recommendation:**`)
- Build a summary list: `DP-xxx: Title → User chose Option {A|B|C}`
- If no resolved decisions exist, set to "none"

Structure the task prompt as:

```
Verify this implementation plan:

Plan file: {path}
Design doc: {path or "none"}
Design analysis: {path or "none"}
Crystal file: {path or "none"}
Bug diagnosis: {verbatim value from plan header **Bug diagnosis:** field, or "not applicable"}
Project root: {path}

Plugin agents dir: ${CLAUDE_PLUGIN_ROOT}/agents
Previously resolved decisions (do not re-ask these):
{List of "DP-xxx: Title → Chosen Option X" or "none"}

Retrieved error patterns and lessons (from knowledge base):
{retrieved_context — one entry per line, or "none" if empty}

Out-of-scope archive (read before generating any DP):
{project_root}/dev-workflow/.out-of-scope/  (contains rejected ideas — see README.md inside for format)
```

### Step 3: Present Results

When the agent completes:

1. Check the agent's return for a `Report:` path. If present, read the report file.
   - If the agent was truncated (no `Report:` in return): search `.claude/reviews/plan-verifier-*.md` for the most recent file. If found with `**Status:** in-progress`, the agent was truncated — use the partial results and note: "⚠️ Verifier was truncated. Partial results below — some strategies may not have run."
2. Present the summary to the user
3. Report the verdict:
   - **Approved** — proceed to Step 4
   - **Must revise** — the summary includes revision items; apply revisions to the plan, then re-dispatch the verifier (max 2 revision cycles)
4. For detailed analysis: read the full report at the path returned by the agent
5. **Decision Points:** Check the agent's return for `Decisions:` count.
   - If Decisions > 0:
     - First time this session: Read `${CLAUDE_PLUGIN_ROOT}/references/decision-points.md`
     - Apply the rules with parameters:
       - Source file: the verification report
       - Mode: `mixed`
       - Recording: `default`
   - Then proceed to Step 4

### Step 4: Mark Verified

When the plan is approved:

1. Append a verification marker to the end of the plan file:

```markdown

---
## Verification
- **Verdict:** Approved
- **Date:** {YYYY-MM-DD}
```

2. Suggest next step: `dev-workflow:execute-plan`

## Completion Criteria

- Plan file has `## Verification` section with `Verdict: Approved` appended
- Or: user explicitly chose to proceed after 2 revision cycles (verdict noted as "partial")
