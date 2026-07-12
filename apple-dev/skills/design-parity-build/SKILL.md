---
name: design-parity-build
description: "Use when auditing a Claude Design (or similar handoff) against an iOS codebase, or the user says 'design parity', 'design 1:1', 'verify Claude Design', 'Claude Design audit', 'audit design implementation', '设计落地审计', 'Claude Design 对齐', '1:1 还原 Claude Design', or '/design-parity-build'. Writes audit doc to docs/06-plans/ for /write-dev-guide. Not for: token sync (sync-design-md), per-View scan (validate-design-tokens), subjective review without an external design source (run /review-execution which dispatches apple-dev:design-reviewer agent), multi-doc drift (design-drift), DS codegen (generate-design-system)."
compatibility: Requires macOS and Xcode
---

<!-- cost-posture: inherit (judgment + synthesis + orchestration — gap severity classification, decision point grouping, audit doc synthesis, and bridge to /write-dev-guide are judgment calls; do NOT downgrade to sonnet/haiku per dev-workflow Skill Cost Posture rule) -->

# Design Parity Build

Audit a Claude Design (or equivalent design handoff) against an iOS codebase, classify every gap, and hand off a phased implementation plan to `/write-dev-guide`.

The skill is **audit + bridge only**. It does not modify Swift code, sync tokens, or execute phases. After it produces the audit document, the user runs `/write-dev-guide` (which auto-discovers the file via `docs/06-plans/*-design.md`), then `/run-phase` per phase.

## Not This Skill

- Apply DESIGN.md ↔ DesignSystem.swift token writes → `apple-dev:sync-design-md`
- Per-View SwiftUI hardcoded value scan → `apple-dev:validate-design-tokens`
- Subjective visual hierarchy / color / spacing review → `/review-execution` (dispatches `apple-dev:design-reviewer` agent)
- Cross-document drift across project-brief / architecture / ADRs → `dev-workflow:design-drift`
- Initial DesignSystem.swift code generation → `apple-dev:generate-design-system`
- Phase plan execution → `dev-workflow:run-phase`
- Cross-phase finalization → `dev-workflow:finalize`

## Inputs

1. **Mode** (required): `full-build` / `single-page` / `polish` / `ds-only`. If invocation does not specify, ask via `AskUserQuestion`.
2. **Design source handoff** (required): user provides at invocation the Claude Design output — URLs, exported markdown, prompts, screenshots, link bundles. The skill does NOT scan the project for design files automatically. If handoff is absent, ask the user to paste before continuing.
3. **iOS project root** (auto-detected from cwd; ask if ambiguous).
4. **Optional scope** (single-page mode only): the page name(s) to audit.

## Process

### Step 1: Mode Selection

Parse invocation arguments for `mode=` or a bare mode keyword (`full-build` / `single-page` / `polish` / `ds-only`).

If absent, ask the user via `AskUserQuestion`:

| Mode | When to choose |
|------|----------------|
| `full-build` | Greenfield app — implementing the whole designed product against an iOS scaffold with no data legacy |
| `single-page` | Existing app — adding one designed page/view; only audit that page's surface |
| `polish` | Existing live app — visual / interaction upgrade; account for migration risk on data-bound surfaces |
| `ds-only` | Design System update only — audit DS / Tokens deltas + impact map across consuming views |

### Step 2: Lock Design Source

Use the handoff content the user supplied with invocation. If absent:

> 请粘贴 Claude Design 的 handoff 内容（URL / 导出 markdown / 提示词 / 截图链接均可）。本 skill 不主动扫盘，只用你提供的内容作为唯一设计真相来源。

If the user cannot or will not provide a source, stop with:

> ❌ 没有设计源即无审计基准。请先准备 Claude Design handoff 后重新触发。

Record handoff content in conversation context for the rest of the session.

### Step 3: Locate iOS Design System

**Precheck — confirm project is iOS UI**:

Run `grep -rln "struct .*View: View" --include="*.swift" .` (limit to first 5 matches). If 0 hits:

> ⚠️ 没有找到 SwiftUI View — 这个项目看起来不是 iOS UI 项目。design-parity-build 仅适用于 iOS UI 项目。是否继续？(yes / no)

If user says no, stop with `❌ design-parity-build targets iOS UI projects only.`. If yes, proceed but record a Note in the audit doc that page-search results may be incomplete.

Then read in order, recording paths found:

1. `docs/02-architecture/design-source.md` — if exists, extract the recorded `Path` field as DESIGN.md location.
2. Glob `**/DesignSystem/DesignSystem.swift` (excluding `node_modules/`, `.build/`, `DerivedData/`).
3. Glob `**/AppFont.swift` (typography enum, optional).

Outcomes:

- **Both DesignSystem.swift and design-source.md found**: full DS audit possible.
- **Only DesignSystem.swift found**: DS audit possible; treat the design handoff as authoritative source.
- **Neither found**: in `full-build` / `ds-only` mode, mark every DS item as `Missing` and continue. In `single-page` / `polish` mode, ask the user whether to proceed (DS audit will be limited).

Do NOT fail; record the situation in the audit doc's notes.

### Step 4: Mode-Specific Audit

Execute the audit subset per mode (see **Mode Behavior** section below). For each task in scope, follow the templates in `references/design-parity-templates.md` strictly — do not invent fields, do not omit required fields.

**Reuse rules** (do not re-implement):

- Token value comparison (color, spacing, typography): follow the rules in `apple-dev:sync-design-md` Step 4 (per-channel max-delta ≤ 4 for color; exact for spacing; ±0.01 opacity for shadows).
- Token field naming and `DESIGN.md → Swift` mapping: follow `apple-dev:project-kickoff` `references/doc-templates.md` section "DESIGN.md → Swift Token 映射" rules where applicable.

For each implemented page, search the iOS codebase by:

1. Page name → SwiftUI View name (`grep -rn "struct .*View: View" --include="*.swift"`)
2. Navigation entry → `NavigationStack` / `NavigationLink` / `sheet(` / `fullScreenCover(` callsites
3. Confirm a single primary file:line; if ambiguous, list candidates and mark `Cannot verify` until disambiguated.

### Step 5: Generate Outputs

Produce the matrix subset for the chosen mode, using templates from `references/design-parity-templates.md`:

- **DS / Tokens Parity Matrix** — every DS item with status enum
- **Designed Page Inventory** — every page from the design source
- **Implementation Coverage Matrix** — every designed page + iOS implementation status
- **Page-by-Page Match Report** — observable comparison per implemented page
- **Gap List** — every gap with all 11 required fields

Each gap MUST classify:

| Field | Allowed values |
|-------|----------------|
| Gap scope | `Design System/Tokens` / `Page` |
| Severity | `Blocker` / `High` / `Medium` / `Low` |
| Fix type | Color / Typography / Spacing / Component / Page-level / Asset / Navigation / State / Interaction / Data / Accessibility / Native exception |
| Native exception | `Yes` / `No` |
| Fix status | `Confirmed` / `Decision Point` / `Blocked` |

**Aggregation rule**: if a Page gap is caused by a missing or wrong shared token/component, classify as `Design System/Tokens`, not `Page`. Per-page styling fixes are only valid when the underlying DS item is correct.

### Step 6: Decision Points (Grouped)

Before writing the audit doc, resolve Decision Points (gaps where the design handoff is ambiguous, conflicting, or unverifiable from code).

**Grouping policy**:

1. Group DPs by `Fix type` (Color / Typography / Spacing / Component / Page-level / Asset / Navigation / State / Interaction / Data / Accessibility / Native exception).
2. Within each group, sort by severity: `Blocker` → `High` → `Medium` → `Low`.
3. Skip groups with 0 DPs.
4. Per `AskUserQuestion` call: present **one group, ≤ 4 DPs**. If a group has > 4 DPs, split by severity tier (Blocker+High first, Medium second, Low third).

**Per-DP question structure** (2-pass per group):

- **Pass 1 (always)**: `AskUserQuestion` with `multiSelect=true`. Each option = one DP labeled `[severity] {short title}`, description summarizes the conflict. Selected = `Confirmed`. Unselected = `Defer (Decision Point)` by default.
- **Pass 2 (only if any DP was unselected in Pass 1)**: in chat, prompt: `未选中的 DP 中，是否有因外部依赖（设计源不可达 / 第三方组件 / 资产缺失）无法推进的？请用 DP-xxx 形式逐条列出（例：DP-003, DP-007）。否则回复"无"`. Parse the reply, then echo back: `已记录 Blocked: DP-xxx, DP-yyy — 确认？(yes / 修改)`. Only after user confirms, mark those as `Blocked`. The rest of the unselected items stay `Defer`.

This 2-pass split is required because `AskUserQuestion`'s multiSelect surface only carries 2 states per option (selected / not).

**Stop condition**: continue until every group is processed. Do not skip groups to save attention. If user wants to halt mid-stream, write the partial audit doc with the unresolved DPs explicitly listed under `Open Questions / Needs Verification`.

### Step 7: Write Audit Doc

Path: `docs/06-plans/YYYY-MM-DD-design-parity-{mode}-design.md`.

The filename **must end in `-design.md`** so `dev-workflow:write-dev-guide` Step 1 auto-discovers it via `docs/06-plans/*-design.md`.

Structure (full skeleton in `references/design-parity-templates.md` Section 6):

```markdown
---
type: design-parity-audit
mode: {full-build|single-page|polish|ds-only}
status: active
current: true
refs: [design-handoff-link-1, design-handoff-link-2]
---

# Design Parity Audit — {mode}

**Generated:** {ISO timestamp}
**Design source:** {summary of handoff}
**iOS DesignSystem.swift:** {path or "missing"}

## 1. Design System / Tokens Parity Matrix
{table per template 1; omit if mode == single-page and no scoped DS impact}

## 2. Designed Page Inventory
{table per template 2; omit if mode == ds-only}

## 3. Implementation Coverage Matrix
{table per template 3; in ds-only mode this becomes "Impact Analysis: which views consume affected tokens"}

## 4. Page-by-Page Design Match Report
{section per page per template 4; omit if mode == ds-only}

## 5. Gap List
{entries per template 5}

## 6. Suggested Phase Outline
{ordered list per template 7 — foundation-first hard rule}

## 7. Open Questions / Needs Verification
{list of Defer (Decision Point) and Blocked items, plus anything the audit could not verify}

## 8. Hard Constraints (for /write-dev-guide)
- Design wins when design and code disagree.
- DS / Tokens phase MUST precede page-level phases (if any DS gap exists).
- Each designed page = one phase. Do not merge multiple pages into one phase.
- Do not implement Decision Point items.
- Do not introduce features, flows, or copy not present in the design source.
```

### Step 8: Hand Off

Print to chat (do NOT invoke any other skill programmatically):

```
✅ Design Parity Audit complete.

Output: docs/06-plans/YYYY-MM-DD-design-parity-{mode}-design.md
- Confirmed gaps: {N}
- Decision Points pending: {M} (listed in Open Questions)
- Blocked: {K}

Next step:
  /write-dev-guide

The audit doc above will be auto-discovered via docs/06-plans/*-design.md glob.
The "Suggested Phase Outline" section gives write-dev-guide the foundation-first ordering.
The "Hard Constraints" section enforces design-wins / no-implement-DP rules.

After dev-guide is approved, run /run-phase for Phase 1.
```

## Mode Behavior

| Mode | DS Parity | Page Inventory | Coverage | Match | Gap List | Foundation Phase Hint |
|------|-----------|----------------|----------|-------|----------|------------------------|
| `full-build` | All items | All pages | All pages | All pages | All | Required if any DS gap |
| `single-page` | Only tokens / components used by the page | Single page only | Single page only | Single page only | Scoped to page + dependencies | Required if scoped DS gap exists |
| `polish` | All items | All pages (mark legacy implementation) | All pages (mark legacy) | All pages | All (annotate migration risk) | Required if any DS gap |
| `ds-only` | All items | ❌ skip | Impact analysis: list views consuming each affected token | ❌ skip | DS items only | Required (sole phase) |

**Special handling per mode**:

- **`full-build` with no DesignSystem.swift**: every DS item is `Missing`; foundation phase will create the entire DS first.
- **`single-page` with shared DS impact**: if the audited page reveals a token gap that affects other pages, expand scope to a "DS micro-foundation" phase (only the affected tokens/components) before the page phase.
- **`polish` migration risk**: any token / component change that affects views displaying user data (lists, detail screens, forms) gets `migration risk: high` annotation in the gap entry. The audit doc's Suggested Phase Outline must group these into a "Migration-aware Tokens" sub-phase.
- **`ds-only` impact analysis**: for each affected DS item, run `grep -rn "{TokenName}" --include="*.swift"` to enumerate consuming files. List counts in the impact column. This replaces the page-level audit.

## Hard Constraints

These are enforced both during audit and propagated to the audit doc for `/write-dev-guide`:

1. **Design wins** when design and code disagree.
2. **DS / Tokens gaps must precede page-level fixes**. If any DS gap exists in the Gap List, the first phase must be the DS / Tokens Foundation phase.
3. **Aggregation**: a Page gap caused by missing/wrong shared token/component is classified as `Design System/Tokens`, not `Page`. Per-page hardcoded local fixes are forbidden when a DS-level fix exists.
4. **Do not** optimize, improve UX, simplify, or reinterpret beyond the design.
5. **Do not** implement Decision Point items — only `Confirmed` gaps are eligible.
6. **Do not** infer unverifiable gaps — list them under Open Questions instead.
7. **Do not** omit low-severity visual gaps if they affect 1:1 fidelity.
8. **Do not** replace custom design with default SwiftUI styling unless explicitly listed under `Native exception` (acceptable: native Tab Bar behavior, SF Symbols rendering, system keyboard, system sheets, safe-area, standard platform controls).
9. **Do not** introduce new product behavior, copy, data, tokens, or components not present in the design source.
10. **Compare ONLY observable design and behavior**. Do not infer designer intent or motivation. Anything not directly visible in the design source goes to Open Questions, not the Gap List.

## Outputs

After Step 8, the user has:

1. `docs/06-plans/YYYY-MM-DD-design-parity-{mode}-design.md` (audit doc)
2. Console summary: confirmed / pending / blocked counts
3. Explicit next-step instruction (`/write-dev-guide`)

The five matrices live inside the audit doc as sections 1–5; they are not separate files.

## Step 0 — Run the deterministic detectors first. They see what you cannot.

Before reading a single line of the design doc, run these. They take seconds, they need no judgment, and each one catches a defect class that **renders pixel-identically to a correct build** — meaning no amount of careful looking, by you or by a human, will ever find it.

```sh
# Resolve the detectors from THIS plugin's root — never from a repo-relative path.
# (Your CWD is the user's project; `apple-dev/…` does not exist there. A handed-off
# project also carries a vendored copy at scripts/design-gates/ — either works.)
DET="${CLAUDE_PLUGIN_ROOT}/scripts/design-detectors"
[ -d "$DET" ] || DET=scripts/design-gates
[ -d "$DET" ] || { echo "⚠️ detectors not found — report Step 0 as NOT RUN, do not call it clean"; }

# 0a. The contract itself. If this fails, STOP — you are about to audit code
#     against a broken ruler.
python3 "$DET"/n4_contract_lint.py <contract-dir>   || exit 1

# 0b. The code, against what the contract actually said.
#     n1 compiles its assertions FROM the contract's ## Platform Mapping table — it has
#     no hardcoded rule list, so it needs to be told where the contract is.
python3 "$DET"/n1_paradigm.py     --contract <contract-dir> --arm <target>
python3 "$DET"/n2_dead_state.py   --arm <target>    # a @State with zero writes: every branch built, one reachable
python3 "$DET"/n3_scaffold_leak.py --arm <target>   # the prototype's fake-bezel clearance, ported as a literal

# 0c. If you have a render and a reference (device screenshot + prototype render,
#     same resolution), also:
python3 "$DET"/n5_block_layout.py  --render R --ref F   # is this even the right composition?
python3 "$DET"/n6_surface_color.py --render R           # does the glass hit its declared surface colour?
```

**Every finding goes into the Gap List, or is explicitly waived with a reason.** A detector finding you neither fixed nor waived is a finding you suppressed.

> **Why these are Step 0 and not an appendix.**
> This skill's own description promises "1:1". In practice it read documents and compared them to other documents. It never built, never rendered, never diffed — and it could satisfy every one of its Success Criteria **without finding a single real defect**, because those criteria only asked whether the audit *document* was well-formed.
>
> Meanwhile, in a controlled test, the build that had **everything** — full contract, full source, reference screenshots — shipped with: a chart hand-rolled in `Path` (contract said Swift Charts), the prototype's fake-bezel padding ported literally along with an `.ignoresSafeArea()` that switched off the platform mechanism, a four-state enum whose `@State` was never written, and a dark card rendering *brighter* than the wall behind it. **All four are invisible to any review that looks at pictures or reads prose.** All four are a grep.

## Success Criteria

- **The detectors in Step 0 ran, and their output is in the audit doc.** A run with zero findings must show the zero-finding output — "I didn't see any problems" is not the same as "the check ran and found none."
- **Every detector finding is either in the Gap List or waived with a stated reason.**
- Audit doc exists at the predicted path with all required sections for the chosen mode.
- Every gap in the Gap List has all 11 required fields populated.
- Every Decision Point is either `Confirmed` (folded into Gap List) or recorded under Open Questions (`Defer` or `Blocked`).
- The audit doc filename ends in `-design.md` so `/write-dev-guide` auto-discovers it.
- The user receives the prose hand-off message with explicit next-step.

## Edge Cases

- **Handoff content is a screenshot link the skill cannot read**: ask the user to summarize the visible design tokens and pages in markdown form, or run the audit only against the parts described textually.
- **Design source contradicts itself** (two different colors for the same token in different docs): record as a `Decision Point` with severity `Blocker` and present both options to the user.
- **Existing iOS implementation has features the design does not show**: do NOT mark these as gaps. List in `Open Questions / Needs Verification` as "design source silent on existing feature X — confirm whether to retain or remove."
- **Mode says `polish` but no existing iOS app exists**: ask the user to switch to `full-build` mode.
- **Mode says `single-page` but no existing iOS app exists**: ask the user to either (a) switch to `full-build` with scope narrowed to that single page, or (b) confirm they want a `single-page` audit where DesignSystem.swift will also be marked `Missing` and the foundation phase will be the entire DS micro-foundation for that page's tokens/components.
- **Design source token name collides with a Swift reserved/standard symbol** (e.g., `Color`, `View`, `Map`, `Image`, `List`): record as a `Decision Point` with severity `Blocker`. Present alias options to the user (e.g., `AppColor.brandPrimary`, `BrandView`, `MapTile`) and require user choice before proceeding. Do NOT silently rename — that violates Hard Constraint #9.
- **User halts mid Decision Point grouping**: write the partial audit doc with unresolved DPs explicitly under Open Questions; do not silently confirm them.
