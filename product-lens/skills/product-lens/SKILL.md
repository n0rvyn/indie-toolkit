---
name: product-lens
description: "Unified entry point for product decisions. Use when the user or another AI asks whether to pursue an idea, evaluate a product, review recent features, reprioritize projects, or refresh a prior verdict."
---

## Overview

Unified router for `product-lens`. This skill is the recommended first entry for both humans and AI systems.

- **Humans** enter with natural-language product questions.
- **AI systems** should provide an intent-aligned, structured request and expect a machine-readable summary first.

This router does not replace the specialized skills. It routes to them.

## Inputs

The router accepts either:

### A. Human-style prompts

Examples:
- "Is this idea worth pursuing?"
- "Should I build this feature?"
- "Which project should I focus on?"
- "I got new evidence; should I change my decision?"

### B. AI-style structured requests

Expected fields are defined in `${CLAUDE_PLUGIN_ROOT}/references/pkos/ai-entry-contract.md`.

Minimum useful AI payload:

```json
{
  "intent": "portfolio_scan",
  "project_root": "~/Code",
  "mode": "summary",
  "save_report": true,
  "sync_notion": false
}
```

## Routes

### Route: Idea Screening

Trigger when the request is about whether a product idea is worth pursuing.

Action:
- route to `demand-check`

Output expectation:
- short decision summary first
- detailed demand report second

### Route: Full Product Evaluation

Trigger when the request asks for a full product evaluation of a single product.

Action:
- route to `evaluate`

Output expectation:
- summary first
- full six-dimension report second

### Route: Feature Decision

Trigger when the request asks whether to build a proposed feature for an existing app.

Action:
- route to `feature-assess`

Output expectation:
- GO / DEFER / KILL style summary first
- full feature report second

### Route: Portfolio Scan

Trigger when the request is about multiple projects, root-directory scanning, or periodic portfolio monitoring.

Action:
- route to `portfolio-scan`

Output expectation:
- machine-readable portfolio summary
- signal and verdict note paths

### Route: Project Progress Pulse

Trigger when the request asks how one or more projects are progressing.

Action:
- route to `project-progress-pulse`

Output expectation:
- observable progress facts only
- no fake completion percentages

### Route: Repo Reprioritize

Trigger when the request asks what to focus on next across multiple projects.

Action:
- route to `repo-reprioritize`

Output expectation:
- `focus / maintain / freeze / stop` style summary
- biggest blockers and next actions

### Route: Recent Feature Review

Trigger when the request asks how recent features or recent commits look.

Action:
- route to `recent-feature-review`

Output expectation:
- per-feature or per-slice recommendation
- source note paths for PKOS ingestion

### Route: Verdict Refresh

Trigger when the request asks whether an earlier conclusion still holds after new evidence.

Action:
- route to `verdict-refresh`

Output expectation:
- delta-oriented summary
- what changed and why

### Route: Dimension Teardown

Trigger when the request names a specific product dimension such as demand, moat, market, journey, business, or execution.

Action:
- route to `teardown`

Output expectation:
- single-dimension deep dive

## Routing Rules

1. Prefer the narrowest route that fully answers the request.
2. Do not trigger portfolio routes for ordinary coding or bug-fix tasks.
3. If the request is AI-structured and the `intent` is explicit, trust the intent unless it conflicts with obvious missing inputs.
4. If the request is human-style and ambiguous between:
   - full product evaluation
   - portfolio scan
   - feature decision
   then choose the route with the smallest scope that still fits the wording.
5. For AI periodic tasks, always return the machine-readable summary first.

## Summary Envelope

For AI-facing routes, the downstream skill should emit this shape before any long-form Markdown:

```json
{
  "decision": "focus",
  "confidence": "medium",
  "why": ["reason 1", "reason 2"],
  "biggest_risk": "one-line risk",
  "next_actions": ["action 1", "action 2"],
  "source_note_paths": ["~/Obsidian/PKOS/..."]
}
```

## PKOS Boundary

`product-lens` does not write directly to final PKOS vault note locations.

Instead:
1. `product-lens` produces structured exchange artifacts.
2. PKOS ingests them into canonical vault notes.
3. Notion receives summary fields only.

See:
- `${CLAUDE_PLUGIN_ROOT}/references/pkos/ai-entry-contract.md`
- `${CLAUDE_PLUGIN_ROOT}/references/pkos/note-schemas.md`
- `${CLAUDE_PLUGIN_ROOT}/references/pkos/notion-summary-schema.md`

## Completion Criteria

- The request is routed to the correct specialized skill family.
- AI-facing calls receive a machine-readable summary first.
- PKOS ownership boundaries are preserved.
