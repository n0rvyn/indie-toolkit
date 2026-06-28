# design-handoff

Claude Design → Claude Code handoff contract skills. Vendored into this repo for version control and raw-URL distribution.

## Contents

Three skills that run **inside Claude Design** (not Claude Code):

- `skills/design-spec-contract` — produces DESIGN.md (visual contract)
- `skills/flow-navigation-contract` — produces FLOW.md (interaction / navigation contract), includes `flow-export.js`
- `skills/handoff-manifest` — produces handoff manifest

## Why in repo but NOT in marketplace

These skills are intentionally **absent from `.claude-plugin/marketplace.json`**. Reasons:

1. **异宿主执行**: they run inside Claude Design, not Claude Code. Registering them as a Claude Code plugin would mislead installation flows.
2. **raw GitHub URL 取用**: downstream repos fetch the SKILL.md files via raw URL to feed Claude Design's contract pipeline.
3. **契约同源**: shared schemas live in `apple-dev/references/design-contract-schema.md` (Phase 1 Task 2). Keeping the source templates versioned in the same repo guarantees they stay in sync with the consumer-side schema.

## Contract changes

Any change to a SKILL.md template here is a **breaking change for the handoff contract**. Required process:

1. Update the skill file here.
2. Sync the corresponding schema in `apple-dev/references/design-contract-schema.md` if applicable.
3. Commit and push to `main`.
4. Downstream repos re-fetch the raw URL.

See DECISION C11 in `docs/06-discussions/2026-06-28-visual-verify-flow-DECISION.md`.