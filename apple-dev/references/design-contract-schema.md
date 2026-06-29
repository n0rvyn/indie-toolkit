# Design Contract Schema

> **Shared contract** between `design-handoff/` skills (DESIGN.md / FLOW.md templates) and
> `apple-dev/` review / audit / validate consumers. This is the single source of truth for
> what "matches" / "drifts" / "is a native exception" mean across the design-to-view chain.
>
> **Consumers** (Phase 4 wiring, recorded here so future readers know what must not break):
>
> - `apple-dev/agents/ui-reviewer.md` — Part A1 (spacing scale membership), Part A5 (same-suffix layout consistency)
> - `apple-dev/agents/design-reviewer.md` — Part A12 (spacing scale membership), Part A5 (same-suffix layout consistency)
> - `apple-dev/skills/sync-design-md/SKILL.md` — Step 4 (per-token color / spacing / shadow drift thresholds)
> - `apple-dev/skills/validate-design-tokens/SKILL.md` — Section 1 (spacing), Section 6 (same-suffix layout), Section 7 (DESIGN.md cross-check thresholds)
> - `apple-dev/skills/design-parity-build/SKILL.md` — Gap List classification (Native exception field), 11-field gap taxonomy
> - `design-handoff/skills/design-spec-contract/SKILL.md` — consumes Block 6 (Native exceptions) for its DESIGN.md `Native exceptions` section (its own `materials`/`motion` blocks are design-spec-contract-owned, not governed here)
>
> `a11y` (node) / `via` (edge) join keys are owned by `flow-navigation-contract`, NOT this schema; their enforcement is C1 (deferred) — there is no a11y/via block here.
>
> Anything this file declares as the contract is binding on the consumers above. If a
> consumer disagrees, the disagreement is a bug in the consumer — not in the contract.

---

## 1. Canonical spacing scale

The single canonical spacing scale, in points, is the **set**:

```
{2, 4, 8, 12, 16, 24, 32, 48, 64}
```

### Rule: set-membership, not multiplier

A spacing value is **"on scale"** if and only if it is a member of the set above. There is
no other rule. There are no "valid" values outside the set.

### Prohibited phrasings

The following phrasings are **explicitly forbidden** in design docs, review reports,
audit outputs, code comments, and reviewer prose. They contradict the set above and
cause silent flag drift between agents:

- "4pt multiples" — false. `12` and `20` are 4pt multiples but **not** on the canonical
  scale. `12` IS on the scale, `20` is NOT. The phrase is non-discriminating.
- "8pt multiples" — false. `8`, `16`, `24`, `32`, `48`, `64` happen to be 8pt multiples
  and also on the scale. But `4` and `12` are on the scale and are NOT 8pt multiples.
  The phrase excludes valid values.
- "Multiples of N" generally — any N other than 1 produces a subset or superset of the
  canonical scale. Use the set directly.

**The only correct phrase** is the set itself, or a paraphrase like "the canonical scale
`{2, 4, 8, 12, 16, 24, 32, 48, 64}`".

### Why this matters (DECISION 7.1)

`ui-reviewer` Part A1 said "8pt 倍数" while `design-reviewer` Part A12 said "4pt 倍数" —
a value like `12` passes one and fails the other. This block makes the set the single
rule. **Wired in Phase 4 (2026-06-28):** `ui-reviewer` Part A1 and `design-reviewer`
Part A12 now apply a set-membership check against this scale; the old "Npt 倍数"
phrasing has been removed from both (grep `倍数` = 0 in each).

### Consumers

- `ui-reviewer` Part A1 — must replace any "Npt 倍数" prose with a set-membership check
  against this scale
- `design-reviewer` Part A12 — same
- `validate-design-tokens` Section 1 — same

---

## 2. Token per-channel max-delta

When comparing a token's literal value in two artifacts (DESIGN.md vs DesignSystem.swift,
or a screenshot-rendered value vs a token), the tolerance is per-channel max-delta:

| Token kind | Per-channel max-delta | Notes |
|------------|-----------------------|-------|
| Color (RGB) | **≤ 4 of 256** | Applied to R, G, B independently. The match passes iff `max(|R₁-R₂|, |G₁-G₂|, |B₁-B₂|) ≤ 4`. See `sync-design-md` Step 4 for the exact one-liner. |
| Spacing (dimension) | **exact** | No tolerance. A 16pt token does not "match" a 15.9pt value. |
| Shadow opacity | **± 0.01** | `0.04` matches `0.05`; `0.04` does not match `0.08`. |
| Shadow y-offset | exact | — |
| Shadow blur radius | exact | — |
| Typography size | exact | — |
| Typography weight | exact | Named weights only (regular / medium / semibold / bold). No "500 vs semibold" tolerance. |
| Corner radius | exact | — |

### Color match rule (from `sync-design-md` Step 4, restated)

Normalize both hex strings to 6-digit lowercase (`#FFF` → `#ffffff`). Parse to
`(R, G, B)` 8-bit triples. Pass iff `max(|R₁-R₂|, |G₁-G₂|, |B₁-B₂|) ≤ 4`.

```bash
python3 -c "import sys; a,b=sys.argv[1:]; f=lambda h:tuple(int(h.lstrip('#')[i:i+2],16) for i in (0,2,4)); d=max(abs(x-y) for x,y in zip(f(a),f(b))); print('match' if d<=4 else f'drift d={d}')" "#4a90e2" "#4080d0"
```

This is a deterministic RGB-channel delta, not a perceptual ΔE. Threshold 4 ≈
ΔE76 ≈ 4–6 for mid-saturation hues — close enough to "barely-noticeable" without
LAB conversion. The trade is computability over perceptual accuracy.

### Consumers

- `sync-design-md` Step 4 — color match rule, opacity tolerance
- `validate-design-tokens` Section 7 — DESIGN.md cross-check drift table
- `design-parity-build` Step 4 — token comparison (reuse, do not re-implement)

---

## 3. Same-suffix layout consistency algorithm

A "same-suffix component group" is the set of SwiftUI `View` structs that share a
trailing name token from this **closed set**: `Card`, `Row`, `Cell`, `Badge`, `Chip`,
`Tile`, `Banner`, `Pill`, `Tag`. "Consistency" means all members of a group apply the
same layout primitives in the same shape. A struct whose trailing token is NOT in this
set (e.g. `ProfileView`, `ContentView` → token `View`) is **not a component-family
member** — skip the consistency check for it entirely (otherwise `View` groups nearly
every struct in the project into one meaningless set).

### Algorithm (deterministic, 4 steps)

1. **Extract suffix** from the inspected struct's name (split on PascalCase, take the
   last token). If that token is NOT in the closed suffix set above, skip this struct.
2. **Find same-suffix peers** in the project, then **filter to names that END in the
   suffix** — the grep alone over-matches (`struct \w+Card` matches `ScoreCardView` and
   `ReportCardCell`, which are NOT Card-family):

   ```bash
   Grep("struct \\w+{suffix}", glob: "*.swift")
   # then keep ONLY structs whose name ends in {suffix} before its `:` / `{` / `<`:
   #   PriceCard: View   ✅ (ends in Card)
   #   ScoreCardView     ❌ (Card is mid-name → different family)
   ```

   Replace `{suffix}` with the actual suffix (e.g., `Card`).
3. **For each peer, extract** the following five modifier call sites in the view body:

   | Attribute | What to grep |
   |-----------|--------------|
   | Width behavior | `.frame(maxWidth:` / `.frame(width:` / absence |
   | Padding | `.padding(` (direction + value) |
   | Background | `.background(` (color or material) |
   | Corner radius | `.cornerRadius(` / `.clipShape(.rect(cornerRadius:` / `.clipShape(RoundedRectangle(` / `RoundedRectangle(cornerRadius:` |
   | Shadow | `.shadow(` (color, radius, opacity) |
4. **Compare** the extracted tuples across all peers. Any peer that differs in ≥ 1
   attribute from the group baseline is marked inconsistent.

### What "consistent" means

For each of the five attributes, all peers in the group must use **the same value or
the same token** — literal `12` and token `AppCornerRadius.medium` are equivalent only
if `AppCornerRadius.medium == 12` in this project. If the literal-vs-token mapping is
unclear, flag as 🟡 (advisory) not 🔴 (must-fix).

### Consumers

- `ui-reviewer` Part A5
- `design-reviewer` Part A5
- `validate-design-tokens` Section 6

---

## 4. 11-field gap taxonomy

Every gap entry in a design-parity audit (and every gap referenced from a phased
implementation plan) MUST carry all 11 fields. The taxonomy is the contract — a gap
missing any field is malformed and the audit that produced it is incomplete.

| # | Field | Allowed values | Notes |
|---|-------|----------------|-------|
| 1 | `Gap ID` | `GAP-NNN` (3-digit, zero-padded, monotonic per audit) | Required for cross-referencing in phase plans. |
| 2 | `Gap scope` | `Design System/Tokens` / `Page` | Aggregation rule: a page-level gap caused by a wrong/missing shared token is reclassified to `Design System/Tokens`. |
| 3 | `Page name` | string or `—` (for DS-scope gaps) | Empty for `Design System/Tokens` scope. |
| 4 | `Design expectation` | freeform | What the design source specifies. Cite the design section or asset. |
| 5 | `Current behavior` | freeform | What the code does today. Cite file:line. |
| 6 | `Evidence (design)` | string | Section title or line in DESIGN.md / handoff. |
| 7 | `Evidence (code)` | file:line | Absolute path + line number. |
| 8 | `Severity` | `Blocker` / `High` / `Medium` / `Low` | — |
| 9 | `Fix type` | `Color` / `Typography` / `Spacing` / `Component` / `Page-level` / `Asset` / `Navigation` / `State` / `Interaction` / `Data` / `Accessibility` / `Native exception` | — |
| 10 | `Native exception` | `Yes` / `No` | See Block 6 for the baseline list. `Yes` = the gap is expected, not actionable. |
| 11 | `Fix status` | `Confirmed` / `Decision Point` / `Blocked` | Decision Points are deferred; Blocked have external dependencies; Confirmed are actionable in the next phase. |

### Field 12 (recommended, not required)

`Recommended fix` — freeform. The plan verifier does not require it, but every
`Confirmed` gap should have one, otherwise the implementer has to re-derive the fix.

### Consumers

- `design-parity-build` Step 5 (Gap List)
- `design-parity-templates.md` Section 5 (Gap List Entry template)

---

## 5. ui-e2e verdict schema

The visual end-to-end verdict for a single tested flow surface. Defined here; not yet
wired to any consumer (Phase 4+ territory). Future wiring: `ui-e2e` cross-project
sessions.

```yaml
verdict:
  a11y:           pass | fail         # accessibility checks (labels, traits, contrast)
  state:          pass | fail         # all designed states render (empty, loading, error, success, ...)
  axis1_token_diff: pass | fail       # design-vs-code token comparison (Block 2 thresholds)
  axis2_signal:   pass | fail | n/a   # signal-axis check (e.g., haptics, scroll, animation); n/a if not applicable
  subjective:     ok | uncertain      # designer's or reviewer's qualitative read
  evidence:       <freeform — file:line, screenshot path, log excerpt, or quoted user message>
```

### Field semantics

- `a11y` — independent of axis-1 token diff. A screen can match tokens perfectly and
  still fail a11y (e.g., missing `.accessibilityLabel`). Or match a11y and fail axis-1.
- `state` — covers all states the design source enumerates. A "Cannot verify" state
  (design source silent) maps to `pass` only with explicit designer confirmation.
- `axis1_token_diff` — uses Block 2 thresholds exactly. No project-specific relaxation.
- `axis2_signal` — `n/a` is valid. A static screen has no signal axis; do not coerce
  to `pass` artificially.
- `subjective` — `uncertain` is a real state. It blocks the verdict from being
  classified as `pass` overall.

### Verdict rollup rule (when this schema is wired)

A surface's overall verdict is `pass` iff all of `a11y`, `state`, `axis1_token_diff`
are `pass`, AND `axis2_signal` is `pass` or `n/a`, AND `subjective` is `ok`.
**Precedence when multiple non-pass states co-occur:** any hard-axis `fail` (`a11y` /
`state` / `axis1_token_diff` / `axis2_signal`) → overall `fail`, regardless of
`subjective`. Only when all hard axes pass and `subjective` is `uncertain` → overall
`needs-review`.

### Consumers

- Cross-project e2e sessions (future). Not wired in Phase 1.

---

## 6. Native-exception baseline list

A **native exception** is a component or behavior the design-vs-code audit excludes
from axis-1 token diff. These use system-provided rendering; the design source is
expected to show them with platform-native chrome, and any pixel diff is **not** a
gap.

### Baseline list (starting point — projects extend or trim per their design)

| Category | Components / behaviors | Why it's a native exception |
|----------|------------------------|-----------------------------|
| Tab Bar | `TabView` with `Tab(...)` items, bottom accessory (iOS 18+) | System chrome, height = 49pt + safe area; design specs that match this are accepted as-is. |
| SF Symbols | Any `Image(systemName:)` | Symbols render per Apple's weight / scale grid; per-pixel diff is not actionable. |
| System keyboard | `TextField` / `TextEditor` focus → keyboard | Hardware / system overlay, not app-rendered. |
| System sheet | `.sheet(...)` / `.fullScreenCover(...)` / `.confirmationDialog(...)` / `.alert(...)` | Container chrome is system-provided. App content inside is auditable; container is not. |
| Safe-area insets | `safeAreaInset` / device notch / Dynamic Island | Hardware-dependent, not a design choice. |
| Standard platform controls | `Toggle`, `Slider`, `Stepper`, `Picker` (wheel / menu), `DatePicker`, `ProgressView`, `NavigationStack` chrome | Each has a system rendering that varies across OS versions; design-vs-code diff at the system-control level is not actionable. |

### Per-project extension

A project's DESIGN.md (or equivalent handoff) may **add** to this list (e.g., a
"camera capture surface" that's a `UIViewControllerRepresentable` wrapper) or
**narrow** it (e.g., "we custom-render all toggles"). Per-project deviations are
listed in DESIGN.md under the **Native exceptions** section; the audit reads from
DESIGN.md, not from this baseline.

### Audit treatment

A gap whose `Fix type` is `Native exception` is recorded with `Native exception:
Yes`. It is excluded from the "must-fix" list and from `Blocker` severity
classification, but it IS recorded in the Gap List for completeness (so the audit
trail is honest about what was examined and skipped).

### Consumers

- `design-parity-build` Step 5 (Gap List — `Native exception` field, `Fix type` = `Native exception`)
- `design-handoff/skills/design-spec-contract/SKILL.md` — DESIGN.md `Native exceptions` section
- `ui-e2e` axis-1 future wiring — native-exception components are not diffed on axis 1
