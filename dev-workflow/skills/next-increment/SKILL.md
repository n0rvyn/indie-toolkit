---
name: next-increment
description: "Use when the user says 'next increment', 'next step', 'pick the next evolution step', '下一步做什么', '下一步', or asks what to build next on a mature codebase with established architecture docs. Generates 3-5 candidate increments grounded in the architecture, then writes a mini-spec for the chosen one. Not for greenfield projects (use write-dev-guide) or known tasks (use write-plan)."
---

## Overview

Mature codebases with a stable architecture direction evolve by small, verifiable increments — not by pre-planning multi-phase roadmaps. This skill surveys the current state, proposes candidate next steps across three risk/reward archetypes, and records the chosen one as a mini-spec so later skills (`write-plan`, `brainstorm`) can pick it up.

## Not This Skill

- New project kickoff with no code yet → use `dev-workflow:write-dev-guide`
- Execute an already-planned Phase → use `dev-workflow:run-phase`
- A specific task is already scoped, just need a plan → use `dev-workflow:write-plan`
- Feature-level exploration from scratch → use `dev-workflow:brainstorm`
- Choose between two already-identified options → use `dev-workflow:design-decision`

## Preconditions

Before running, check:

1. **Architecture docs exist.** Glob `docs/02-architecture/*.md`. If zero matches, stop and tell the user:
   > No architecture docs found under `docs/02-architecture/`. `next-increment` is for mature codebases with a written direction. Consider `/brainstorm` or `/write-dev-guide` first.
2. **No in-progress increment blocks this run.** Read `.claude/increment-history.yml` if it exists. If any entry has `status: in_progress`, stop and tell the user:
   > Increment `{id}` ({name}) is still in progress. Finish or mark it `abandoned` in `.claude/increment-history.yml` before picking a new one.

If both checks pass, proceed.

## Process

### Step 1: Gather Context

Read in parallel:

1. All files matching `docs/02-architecture/*.md` — the target direction.
2. All files matching `docs/11-crystals/*-crystal.md` if present — decided constraints.
3. `.claude/increment-history.yml` if it exists — prior increments and learnings.
4. `git log --oneline -30` — what has actually been moving in the codebase.
5. Top-level layout of `src/` (or equivalent source root) with `ls` — where code lives today.

Do not run an automated "frontier gap" analysis. Read the docs and code state directly, then use judgment.

### Step 2: Generate 3-5 Candidates

Produce between 3 and 5 candidates. Each candidate is a block with every field below filled in — no blanks, no TBDs:

```
### Candidate {letter}: {short name}

- archetype: {infrastructure-seed | user-visible | risk-reducer}
- what: {one sentence describing what ships}
- what_not: {what is explicitly out of scope for this increment}
- verify: {one concrete verification: curl URL → expected field, SQL query → expected row, UI step → expected visible change, or CLI command → expected output}
- depends_on: {prerequisite components/tables/routes that must exist, or "none"}
- signal_velocity: {how soon real data/behavior flows after shipping — e.g., "immediate on first request", "next day after scheduler fires"}
- reversibility: {low / medium / high} — {one-phrase reason}
- complexity: {simple / medium / architectural}
- doc_anchors: {architecture doc filename + section heading(s) this increment advances}
```

**Archetype coverage rule.** The 3-5 candidates must span at least three different archetypes:

- **Infrastructure seed** — a small piece of foundational plumbing (table, route, schema, config key). Enables later increments.
- **User-visible behavior** — a slice that a human can demo end-to-end, even if narrow.
- **Risk reducer** — a downgrade path, fallback, validator, or test harness that lowers blast radius of a known fragile area.

One candidate can satisfy one archetype. If the architecture is at a stage where one archetype has no meaningful increment, state that explicitly and still produce 3 candidates from the remaining archetypes.

### Step 3: Recommend + Metadata

After the candidate list, output two lines:

```
Gut pick: {letter} — {one phrase on why a human might grab this first}
Reasoned top-1: {letter} — {one sentence citing the architecture anchor, dependency state, or signal velocity}
```

If these two disagree, the user sees the mismatch and can decide whether they are overriding instinct or reasoning. If they agree, state them anyway — the user still learns the reasoning.

### Step 4: AskUserQuestion

Present options as a single AskUserQuestion with 4 options:

- The reasoned top-1 candidate (labeled "(推荐)")
- Two other candidates (prefer ones from different archetypes than the top-1)
- "I'll pick myself / customize" — lets the user steer outside the 3 surfaced

Place each candidate's `what` and `complexity` inside the option `description` so the user can choose without scrolling back.

If the user picks "customize", ask which candidate (or hybrid) they want in a free-form follow-up, then proceed with the user's pick.

### Step 5: Write Mini-Spec

Save to `docs/06-plans/YYYY-MM-DD-<slug>-increment.md`. Slug is derived from the chosen candidate's short name, lowercased, hyphenated.

```markdown
---
type: increment
status: pending
date: YYYY-MM-DD
archetype: {infrastructure-seed | user-visible | risk-reducer}
complexity: {simple | medium | architectural}
reversibility: {low | medium | high}
refs: [architecture doc paths from doc_anchors]
---

# Increment: {name}

## What
{what}

## What Not
{what_not}

## Verify
{verify — written as concrete steps, e.g.:
  1. Run `curl http://localhost:8080/events -d '{...}'`
  2. Expect HTTP 200 and response contains `id`
  3. Query `SELECT count(*) FROM events` → expect ≥1}

## Depends On
{depends_on, bulleted if multiple}

## Signal Velocity
{signal_velocity}

## Doc Anchors
- {architecture doc path} — {section heading}
- ...

## Source Candidate Set
All candidates surfaced in this session (for later retrospection on why this one was chosen):
- A: {name} — {one line}
- B: {name} — {one line}
- C: {name} — {one line}
- ...

**Chosen:** {letter} — {user's stated reason if any, else "user pick"}
```

### Step 6: Recommend Next Skill

Map complexity to next step:

- **simple** → "You can start directly, or run `/write-plan` if you want a task breakdown first."
- **medium** → "Run `/write-plan` then `/verify-plan` on `{mini-spec path}`."
- **architectural** → "Run `/brainstorm` against `{mini-spec path}` to explore approach before planning."

Output one line, no menu — this is a suggestion, not a branching prompt.

### Step 7: Append to increment-history.yml

File: `.claude/increment-history.yml`. Create it if missing. Schema:

```yaml
increments:
  - id: "{YYYY-MM-DD}-{NNN}"         # NNN zero-padded sequence within the day
    slug: "{same slug as mini-spec filename}"
    name: "{candidate short name}"
    archetype: "{archetype}"
    complexity: "{complexity}"
    started_at: "YYYY-MM-DDTHH:MM:SS"
    status: pending                  # pending | in_progress | done | abandoned
    spec_path: "docs/06-plans/YYYY-MM-DD-<slug>-increment.md"
    # filled in later, when the user reports completion:
    completed_at: null
    learned: []                      # 1-2 short strings of surprising findings
```

Append — do not overwrite existing entries. If the file exists but is malformed YAML, stop and surface the error; do not silently rewrite.

On completion of a prior increment (user says "mark {id} done" or equivalent), update its entry: set `status: done`, `completed_at`, and ask the user for 1-2 one-line learnings to fill `learned`. These learnings are read back by Step 1 of the next `next-increment` run.

## Rules

- **No placeholder candidates.** A candidate with any blank field is rejected; regenerate until all 3-5 are fully specified.
- **Archetype diversity beats polish.** Ship three rough candidates across archetypes rather than five in the same archetype.
- **Verify field is concrete.** "Manual check" / "looks right" / "tests pass" are not acceptable `verify` values.
- **One increment at a time.** Preconditions block a second run while another is `in_progress`.
- **Doc anchors are mandatory.** Every candidate must cite at least one architecture doc section. A candidate with no anchor means the skill has drifted from the stated direction; drop it.

## Completion Criteria

- 3-5 fully-specified candidates presented
- User has chosen one (via AskUserQuestion)
- Mini-spec written to `docs/06-plans/`
- Next-skill suggestion stated (Step 6)
- History file updated with new entry (Step 7)

---

## Example Run

**Project:** `/Users/norvyn/Code/Projects/Adam` (Adam Personal OS)
**Date:** 2026-04-15
**Architecture state:** Control Plane complete (ChatManager / ExecutionPool / Role / Memory / Plugin / Delivery / Scheduler / Sandbox, schema v27+). Data Plane new tables (events / hats / state_snapshots / goal_graph_nodes / features / policies / identity_aliases / user_rhythm / output_artifacts / artifact_feedback / prompt_sessions) and Intelligence Plane agents all not yet built. Phase 1 crystal D-077 mandates "evolutionary increments, not big-bang Phase 1".

### Gathered Context

- 6 architecture docs under `docs/02-architecture/` read (glossary / roadmap / signal-contract / technical-specs / handoff / agent-server-design)
- 1 crystal read: `2026-04-14-adam-solo-founder-os-crystal.md` (67 decisions including D-070 nightly pipeline, D-071 goal_graph_nodes minimal, D-068 iCloud Markdown canonical)
- `.claude/increment-history.yml` does not exist (first run)
- git log: 30 recent commits concentrate on admission / capability routing / OS capabilities; no events / hats / state_snapshots work started
- `src/` contains: control plane code, `server/routes/webhooks.ts` (generic template webhook, NOT `/webhooks/events`), no `events.ts` in `src/store/`

### Candidates

### Candidate A: events table + POST /webhooks/events + session-reflect source

- archetype: infrastructure-seed
- what: Create `events` table (schema per D-003 / D-024: id, type, source, confidence, related_entities, payload, occurred_at, ingested_at), add `POST /webhooks/events` route that validates schema_version envelope (D-074) and writes one row, wire `session-reflect` to post `coding.session.closed` events
- what_not: Rule-layer classifier, state_snapshots, features derivation, any LLM call, identity_aliases resolution (allow `canonical_id=null` per D-073)
- verify: `curl -X POST http://localhost:8080/webhooks/events -H "x-api-key: $KEY" -d '{"schema_version":"1.0","type":"coding.session.closed","source":"session-reflect","confidence":0.9,"occurred_at":"2026-04-15T10:00:00Z","payload":{}}'` → expect HTTP 201 + `id` in body; then `sqlite3 adam.db "SELECT count(*) FROM events WHERE type='coding.session.closed'"` → expect ≥1
- depends_on: none (fresh table; `webhooks.ts` already exists as template pattern reference)
- signal_velocity: immediate — first real session-reflect close fires within hours
- reversibility: high — table + one route, drop-safe
- complexity: simple
- doc_anchors: `adam-signal-contract.md` §events envelope; `adam-technical-specs.md` §Data Plane / events; crystal D-002 / D-003 / D-074

### Candidate B: goal_graph_nodes (minimal) + Setup Wizard Day 1 NorthStar/Guardrail

- archetype: user-visible
- what: Create `goal_graph_nodes` table with only `type IN ('north_star','guardrail')` constraint (per D-071), wire Setup Wizard Day 1 UI (Web Console) that writes one `north_star` row + N `guardrail` rows with text + active flag
- what_not: `goal_graph_edges`, `bet/project/outcome/assumption/evidence` node types, editing/archival UI, State Estimator consumption (Phase 2), Setup Wizard Days 2-4
- verify: Open Web Console → Setup Wizard Day 1 → enter "Ship Adam Phase 1 by 2026-06-30" as NorthStar + 2 guardrails → Submit → `sqlite3 adam.db "SELECT type, text FROM goal_graph_nodes"` → expect 1 `north_star` row + 2 `guardrail` rows
- depends_on: none (new table; existing Web Console shell supports new page)
- signal_velocity: immediate on user completing Day 1 (one-shot input, no async flow)
- reversibility: medium — UI surface change + table; dropping later requires removing wizard step
- complexity: medium
- doc_anchors: crystal D-017 / D-071 (minimal goal_graph_nodes); roadmap Phase 1 §Setup Wizard; `adam-technical-specs.md` §Goal Graph minimal

### Candidate C: iCloud Markdown writer + hello-world Tomorrow Brief

- archetype: user-visible
- what: Create `output_artifacts` table (id, kind, date, path, wechat_summary, created_at per D-068), implement iCloud writer that renders a hardcoded hello-world Tomorrow Brief markdown to `~/Library/Mobile Documents/com~apple~CloudDocs/Adam/Outputs/tomorrow-brief/YYYY-MM-DD.md`, insert one `output_artifacts` row, trigger manually via CLI (`adam brief:hello`)
- what_not: Reviewer / State Estimator / Planner LLM calls, scheduler (22:00 / 22:15 / 22:45 pipeline), WeChat delivery, `artifact_feedback` collection, failure degradation chain
- verify: `pnpm adam brief:hello` → check `~/Library/Mobile Documents/com~apple~CloudDocs/Adam/Outputs/tomorrow-brief/2026-04-15.md` exists and contains "Hello Adam"; `sqlite3 adam.db "SELECT path FROM output_artifacts WHERE kind='tomorrow-brief'"` → expect 1 row with matching path
- depends_on: none (new table + new CLI command; iCloud path is user-local, no sync logic needed yet)
- signal_velocity: immediate (CLI is synchronous)
- reversibility: high — CLI command + one table; iCloud file is user-deletable
- complexity: simple
- doc_anchors: crystal D-068 (iCloud Markdown canonical); roadmap Phase 1 §Outputs; `adam-signal-contract.md` §iCloud directory contract

### Candidate D: failure degradation scaffold (risk reducer)

- archetype: risk-reducer
- what: Add `degradation_log` table + a shared `withFallback(agent, mode)` wrapper where `mode ∈ ('use_yesterday' | 'use_rules_only' | 'skip_with_note')` per D-072, no agents yet — wrapper is library + one smoke test that exercises all 3 modes
- what_not: Any Intelligence Agent (State Estimator / Planner / Reviewer), actual fallback integration into production pipelines, Notification Orchestrator
- verify: Run `pnpm vitest src/intelligence/__tests__/withFallback.test.ts` → expect 3 passing cases (one per mode); `sqlite3 adam.db "SELECT mode, reason FROM degradation_log"` → expect 3 rows
- depends_on: none — pure library + table
- signal_velocity: deferred — scaffold only becomes live data when an Intelligence Agent is wired (Phase 1 next increment onward)
- reversibility: high — library file + table, no user-visible surface
- complexity: simple
- doc_anchors: `adam-technical-specs.md` §15 (degradation); crystal D-072

---

Gut pick: C — iCloud Markdown writer feels tangible; user sees a file appear in their iCloud within minutes.
Reasoned top-1: A — `events` is the root of every downstream Phase 1 table (state_snapshots / features both derive from events per D-056). Landing it first unblocks 3+ later increments; session-reflect is already producing the signal, so real data starts flowing immediately.

If the two disagree, the user decides whether they are overriding reasoning for signal-of-life reasons (valid) or picking familiar (re-consider).

### Mini-spec (if user picked A)

Would be written to `docs/06-plans/2026-04-15-events-ingress-increment.md` with frontmatter `archetype: infrastructure-seed`, `complexity: simple`, and Source Candidate Set listing A-D.

### History entry

Would be appended to `.claude/increment-history.yml`:

```yaml
increments:
  - id: "2026-04-15-001"
    slug: "events-ingress"
    name: "events table + /webhooks/events + session-reflect source"
    archetype: "infrastructure-seed"
    complexity: "simple"
    started_at: "2026-04-15T14:00:00"
    status: pending
    spec_path: "docs/06-plans/2026-04-15-events-ingress-increment.md"
    completed_at: null
    learned: []
```

Next skill suggestion (complexity=simple): "You can start directly, or run `/write-plan` if you want a task breakdown first."
