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

## Step 1 — Lint the contract. Do not hand off a contract that does not pass.

This skill stands at the **only** gate the contract passes through on its way out. Everything downstream — the reviewers, the drift auditors, the build agent — treats the contract as **ground truth**. Nothing downstream ever checks it. If it ships broken, it is never checked again.

### 1a. Confirm the artifacts exist (paths vary per project)

- `tokens.css` (+ mirrored `Tokens.swift` / asset catalog) — atomic values *(spec-contract L1)*
- `DESIGN.md` — token contract + materials/motion + **Platform Mapping** + DO-NOT-PORT *(spec-contract L2/L4)*
- `components/` reference components, each with a `// CANONICAL` header *(spec-contract L3)*
- **Empty-State Audit** table *(spec-contract, `## Empty-State Audit` section)*
- **`## Screen Composition`** — per-screen block order *(spec-contract; without it the builder invents the layout)*
- `FLOW.md` — node/edge list + stub sentinels *(flow-navigation-contract)*
- coverage script (parses FLOW.md, greps `FLOW-STUB`, lists dead edges) *(flow-navigation-contract Step 3)*

### 1b. Run the contract lint. **RED > 0 → stop. Do not write the manifest.**

```sh
python3 apple-dev/scripts/design-detectors/n4_contract_lint.py <contract-dir>
# exit 0 = ship it   ·   exit 1 = the contract is broken, fix it before handing off
```

Four predicates, all pure grep / set-difference — no judgment, no model:

| # | Predicate | What it catches |
|---|---|---|
| **a** | **Dangling anchor** — every cross-file reference (`statesRef: "DESIGN.md 4c"`) resolves to a heading that actually exists in the target file | A contract that tells the builder to go read a section that was never written |
| **b** | **Ghost symbol** — every type named in a header comment or in prose (`` Views consume `RColor` ``) exists in that file's symbol table | A native mirror that advertises an API it does not have |
| **c** | **Mirror set-difference** — two stores that claim to be lockstep mirrors have a **bidirectional** empty difference | A `Tokens.swift` whose header says "does NOT author new values" while 12 CSS tokens have no Swift counterpart |
| **d** | **Ladder completeness** — every semantic colour step (`ink`, `surface`, glass tint, wallpaper base) resolves in **both** light and dark | The one that hurts most — see below |

> **Predicate (d) is the expensive one, and it is invisible without a script.**
> In a controlled test, the contract's ink ladder existed **only in light**. The builder had no dark surface colour to apply, so it left the native glass untinted. On a dark wallpaper, untinted `.glassEffect` renders **lighter** than its backdrop: the card came out at `L* 53.6` where the design called for `25.7` — a card that should be darker than the wall rendered **brighter** than it. The elevation relationship inverted.
> **Nothing upstream caught it, because the missing value is an absence, and no reviewer greps for absences.** A ~40-line set-difference at this gate would have.

### 1c. This skill has been a source of predicate (a) failures. Do not reintroduce them.

The Build Contract block below is appended to the target repo's `CLAUDE.md`. **Reference DESIGN.md sections by their literal heading text, never by an outline number** (`4c` / `4e`) — those numbers live in `design-spec-contract`'s own internal outline and **are not part of the section order it emits**. A `statesRef: "DESIGN.md 4c"` in a shipped FLOW.md points at a heading that does not exist, and predicate (a) will fail the very handoff this skill is writing.

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
- **State branches no screenshot shows** — enumerate each component's states from its prop signature (see DESIGN.md § *State & tweak mapping*); `onX` callbacks imply transitions / reverse-flows.
  **A branch that is built is not a branch that is reachable.** Every state-bearing property must have at least one write. A `@State` that is declared, read by four branches, and never assigned is a constant wearing a state annotation — and it looks *complete* to a screenshot, to a render-diff, and to a "did you handle all the states?" checklist.
- **DO-NOT-PORT scaffolding** — pan/zoom canvas, tweaks panel, device bezel, faked `backdrop-filter`. Delete, don't translate.
  **And delete the values the scaffolding forced.** The prototype's fake bezel gave the content container a clearance (`padding: '64px 20px 100px'`). Deleting `ios-frame.jsx` does not delete that padding — it stays behind in the screen container and gets ported as `.padding(.top, 64)` + `.ignoresSafeArea()`. **A file-level DO-NOT-PORT list does not stop a value-level leak**; in a controlled test this leaked into two of seven builds, including one whose contract explicitly named the fake bezel. List the geometry constants the scaffolding imposed, and name the native replacement (`safeAreaInset`, `.toolbar`) for each.

### Done = every gate green (a script decides, not you)
- **CONTRACT lint:** `python3 apple-dev/scripts/design-detectors/n4_contract_lint.py <contract-dir>` → **exit 0**. Dangling anchors = 0 · ghost symbols = 0 · mirror difference = ∅ · every colour ladder resolves in **both** light and dark.
- **FLOW coverage:** `{./flow-coverage.sh}` → nodes implemented = N/N · `grep -rc "FLOW-STUB"` = 0 · dead edges = 0
- **PARADIGM:** every `never X` / `always X` line in the Do's and Don'ts below has been grepped against the target sources → 0 violations.
  `python3 apple-dev/scripts/design-detectors/n1_paradigm.py --contract <contract-dir> --arm <target>` — the assertions are compiled from the contract's `## Platform Mapping` table, not hardcoded, so it needs the contract path.
- **STATE LIVENESS:** every `@State` / `@Published` has ≥ 1 write → 0 `DEAD-STATE`. (`n2_dead_state.py`)
- **SCAFFOLD:** no View has `.ignoresSafeArea()` on a content container together with a literal edge padding ≥ 48. (`n3_scaffold_leak.py`)

> **Why these are gates and not suggestions.** Each one catches a defect class that renders **pixel-identically to a correct build**: a chart hand-rolled with `Path` looks exactly like a `Swift Charts` chart; a dead `@State` renders its default branch perfectly; a ported bezel clearance lines up on the one device it was ported from. **No screenshot, render-diff, or visual review can see any of them.** A grep can see all three.
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
