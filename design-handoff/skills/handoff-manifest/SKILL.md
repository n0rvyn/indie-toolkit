---
name: handoff-manifest
description: The last mile between Claude Design and Claude Code. After the design-spec-contract (DESIGN.md) and flow-navigation-contract (FLOW.md) skills have produced their artifacts, this skill packages them for the build agent — it APPENDS a "Build Contract" section to the target repo's existing CLAUDE.md (the file Claude Code auto-reads every session) and emits a thin paste-ready pointer for the Share → Send to box. Use at handoff time, once the contracts exist, to guarantee the coding agent knows which artifacts to read, in what order, what to watch for, and what "done" means (script gates, not its own judgment).
user-invocable: true
---

# Handoff Manifest — wiring the contracts into Claude Code

The two contract skills (`design-spec-contract` → DESIGN.md, `flow-navigation-contract` → FLOW.md) produce artifacts. **Producing them is not handing them off.** A coding agent does not open arbitrary `.md` files — it reads the **repo-root `CLAUDE.md`** automatically every session, and nothing else unless that file points at it. This skill is the pointer.

## The one fact this skill exists for

> `CLAUDE.md` is a fixture of every repo — it is **not produced by this handoff; we only append to it.** Claude Code reads it at session start with zero configuration. So the durable contract belongs there, appended as one self-contained section, committed alongside the artifacts. (`AGENTS.md` is a cross-vendor convention, not what Claude Code natively auto-reads — prefer `CLAUDE.md` for a Claude Code target. If the repo has both, append to `CLAUDE.md`.)

## Two delivery channels, different lifespans — use both, weighted

| Channel | Lifespan | Carries |
|---|---|---|
| **repo `CLAUDE.md` (append a section)** | persistent — every session, every collaborator | the **substance**: artifact index, read order, watch-fors, the two gates |
| **Share → Send to → "more detail" paste box** | one-shot — seeds session #1 only, forgotten after | a **thin pointer** that says "read CLAUDE.md's Build Contract first; done = the two gates" |

A native build spans many sessions; a paste-box prompt evaporates after the first. So the contract lives in `CLAUDE.md`; the paste box only kicks the first session toward it. Don't put the substance in the paste box — it won't survive.

---

## Step 1 — Inventory the artifacts the two skills produced

Before writing the manifest, confirm what exists (paths vary per project):

- `tokens.css` (+ mirrored `Tokens.swift` / asset catalog) — atomic values *(spec-contract L1)*
- `DESIGN.md` — token contract + materials/motion + **Platform Mapping** + DO-NOT-PORT *(spec-contract L2/L4)*
- `components/` reference components, each with a `// CANONICAL` header *(spec-contract L3)*
- **Empty-State Audit** table *(spec-contract 4e)*
- `FLOW.md` — node/edge list + stub sentinels *(flow-navigation-contract)*
- coverage script (parses FLOW.md, greps `FLOW-STUB`, lists dead edges) *(flow-navigation-contract Step 3)*

If FLOW.md was emitted from the prototype's router with the dead-edge self-check (it should be), it is already verified-complete intent.

## Step 2 — Append the Build Contract to the repo's CLAUDE.md

Append (never overwrite) this section. Fill the `{…}` from Step 1. It compresses the two skills' "Implementation loop" sections — it is not new instruction, just the pointer + the gates.

````markdown
<!-- ───────── BEGIN Build Contract (appended by design-handoff) ───────── -->
## Build Contract — read before writing any view

This app's design is fully specified by the artifacts below. Read them; do not
infer from screenshots or memory. Target OS floor: {iOS 26}.

### Artifacts — what each answers
| File | Answers | Rule |
|---|---|---|
| `{tokens.css / Tokens.swift}` | every atomic value | consume the token; NEVER paste a literal |
| `{DESIGN.md}` | does a screen *look* right (color, type, material, motion) | obey its `## Platform Mapping` + `DO-NOT-PORT` list |
| `{components/}` | material/layout recipes | use the SwiftUI form each `// CANONICAL` header names; don't transliterate the browser hack |
| `{Empty-State Audit}` | what each surface does with no/partial data | build these branches — the prototype never rendered them |
| `{FLOW.md}` | does each screen *exist* + what reaches it + is it done | the `nodes` list IS your checklist |

### Read order
DESIGN.md (front matter → target OS) → FLOW.md (the screen checklist) →
per node: build the view · wire its edges (`present`: push→NavigationStack, sheet→.sheet, modal→overlay+scale) ·
then satisfy DESIGN's states + material for it.

### Watch for — where generated apps break
- **Placeholder subviews** — every unbuilt screen carries `#warning("FLOW-STUB: <node-id>")`. Delete only when the screen is real, never to silence the count.
- **Missing empty / zero-data / device-missing states** — see the Empty-State Audit. The prototype renders mock data everywhere; build the absences. Prefer hiding over faking.
- **State branches no screenshot shows** — enumerate each component's states from its prop signature (DESIGN 4c); `onX` callbacks imply transitions / reverse-flows.
- **DO-NOT-PORT scaffolding** — pan/zoom canvas, tweaks panel, device bezel, faked `backdrop-filter`. Delete, don't translate.

### Done = both gates green (a script decides, not you)
- **FLOW coverage:** `{./flow-coverage.sh}` → nodes implemented = N/N · `grep -rc "FLOW-STUB"` = 0 · dead edges = 0
- **DESIGN (optional, if wired):** `design.md lint` passes (token refs, section order)
<!-- ───────── END Build Contract ───────── -->
````

Keep it self-contained between the BEGIN/END markers so a re-handoff can replace the block in place without disturbing the rest of CLAUDE.md.

## Step 3 — Emit the paste-ready pointer

For the **Share → Send to → "Give the agent more detail to implement"** box. Thin by design — it only aims session #1 at the durable contract:

```text
This repo's design intent lives in CLAUDE.md → "Build Contract", which indexes
DESIGN.md (looks), FLOW.md (structure/reachability), tokens, and the reference
components. Read that section before writing any view, and build screens off
FLOW.md's node checklist. You are NOT done by judgment — done means the two gates
pass: FLOW coverage N/N with zero FLOW-STUB, and DESIGN lint (if wired) green.
Delete everything on the DO-NOT-PORT list rather than translating it.
```

## Step 4 — Land the artifacts in the repo, not the Design project

The contract files must sit **in the iOS repo** (so `CLAUDE.md`'s relative pointers resolve and they version with the code) — not left in the Design project. Use the "Handoff to Claude Code" export to move tokens / DESIGN.md / FLOW.md / components / Empty-State Audit + coverage script into the repo, then append the Step 2 block to that repo's CLAUDE.md.

## Do's and Don'ts

- **Do** append to the existing repo `CLAUDE.md` — it's a fixture we add to, not a file we generate. Use BEGIN/END markers so re-handoff replaces cleanly.
- **Do** keep the paste box thin — a pointer to CLAUDE.md, never the substance (it's one-shot and evaporates).
- **Do** make "done" the two script gates (FLOW coverage + optional DESIGN lint), so the build agent can't self-declare completion — same termination-by-script principle as FLOW.md.
- **Do** move the artifacts into the iOS repo so relative paths resolve and they version with the code.
- **Don't** target `AGENTS.md` for a Claude Code handoff — `CLAUDE.md` is what it auto-reads. (Add an `AGENTS.md` too only if a different tool in the chain needs it.)
- **Don't** restate the whole contract in the paste box, and don't paste DESIGN/FLOW bodies into CLAUDE.md — index them, keep one source of truth per artifact.
- **Don't** hand off before FLOW.md's export-time dead-edge self-check is clean — otherwise you're shipping known-broken intent.
