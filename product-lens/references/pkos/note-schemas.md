# Product Lens PKOS Note Schemas

This document defines the local Markdown fact model used between `product-lens` and PKOS.

## Design Rule

- `product-lens` publishes structured exchange artifacts.
- PKOS ingests those artifacts and writes canonical vault notes.
- Stable user-confirmed decisions are promoted into `crystal` notes through `dev-workflow:crystallize`.

## Exchange Layer

Exchange artifacts live in a PKOS-owned ingress area and are not final vault notes.

Recommended directory pattern:

```text
~/Obsidian/PKOS/.exchange/product-lens/
  portfolio-scan/
  progress-pulse/
  reprioritize/
  recent-feature-review/
  verdict-refresh/
```

Each artifact should be self-contained and machine-readable enough for PKOS ingestion.

## Exchange Artifact Schema

```yaml
---
type: product-lens-exchange
producer: product-lens
intent: portfolio_scan
created: 2026-04-12
project_root: ~/Code
targets: []
decision: focus
confidence: medium
tags: [product-lens, portfolio]
notion_sync_requested: false
source_refs:
  - /absolute/path/to/repo
  - /absolute/path/to/older-verdict.md
---
```

Body shape:

```markdown
# Product Lens Exchange

## Summary
- Decision: focus
- Biggest risk: ...

## Reasons
1. ...
2. ...

## Next Actions
1. ...
2. ...

## Evidence
- file or note path
- repo observation
```

## Final PKOS Note Types

After PKOS ingestion, artifacts should be converted into one of these note types.

### `signal`

Purpose: high-frequency observations and scans.

Recommended frontmatter:

```yaml
---
type: signal
source: product-lens
created: 2026-04-12
tags: [product-lens, portfolio, project-name]
quality: 1
citations: 0
related: []
status: fresh
producer_intent: portfolio_scan
decision: watch
confidence: low
project: AppA
---
```

Typical body sections:
- `## Observable Signals`
- `## Risks`
- `## Suggested Follow-up`

### `verdict`

Purpose: current decision state for a project or portfolio question.

Recommended frontmatter:

```yaml
---
type: verdict
source: product-lens
created: 2026-04-12
tags: [product-lens, verdict, project-name]
quality: 2
citations: 0
related: []
status: active
producer_intent: repo_reprioritize
decision: focus
confidence: medium
project: AppA
replaces:
  - [[2026-04-01-AppA-verdict]]
---
```

Typical body sections:
- `## Recommendation`
- `## Why`
- `## Biggest Risk`
- `## Next Actions`

### `feature-review`

Purpose: review of recently built or recently changed features.

Recommended frontmatter:

```yaml
---
type: feature-review
source: product-lens
created: 2026-04-12
tags: [product-lens, feature-review, project-name]
quality: 2
citations: 0
related: []
status: active
producer_intent: recent_feature_review
decision: simplify
confidence: medium
project: AppA
feature: tagging-system
commit_window_days: 14
---
```

Typical body sections:
- `## Feature Slice`
- `## Core Loop Impact`
- `## Cost and Drift Signals`
- `## Recommendation`

## Promotion Rule to `crystal`

Do not promote every `signal` or `verdict` into a `crystal`.

Promote only when:
- the conclusion is stable across multiple runs, or
- the user explicitly confirms the direction, or
- a later `/write-plan` must treat the conclusion as a hard boundary.

The promoted crystal should capture:
- settled decision
- rejected alternatives
- constraints
- scope boundaries

## Naming Conventions

### Exchange Artifacts

```text
YYYY-MM-DD-{intent}-{slug}.md
```

Examples:
- `2026-04-12-portfolio-scan-apps.md`
- `2026-04-12-recent-feature-review-notes-app.md`

### Final Notes

```text
YYYY-MM-DD-{project}-{kind}.md
```

Examples:
- `2026-04-12-AppA-signal.md`
- `2026-04-12-AppA-verdict.md`
- `2026-04-12-AppA-tagging-feature-review.md`

## Ingestion Ownership

PKOS ingestion should handle:
- final folder placement
- canonical tags
- note title normalization
- cross-linking and ripple compilation
- stale note supersession rules

`product-lens` should handle:
- structured judgment
- decision vocabulary
- evidence summaries
- follow-up action generation
