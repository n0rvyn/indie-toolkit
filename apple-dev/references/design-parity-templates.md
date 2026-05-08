# Design Parity Templates

Templates consumed by `apple-dev:design-parity-build`. Do not edit during a single audit run — copy and fill.

## 1. Design System / Tokens Parity Matrix

```markdown
| DS Item | Type | Design Expectation | iOS Status | File Path | Swift Symbol | Notes |
|---------|------|--------------------|-----------|-----------|--------------|-------|
| `primary500` | Color | `#4A90E2` | Implemented | `Sources/DesignSystem/DesignSystem.swift:42` | `AppColor.primary500` | Match within 4-channel delta |
| `largeTitle` | Typography | SF Pro Bold 34pt | Partially implemented | `Sources/DesignSystem/AppFont.swift:18` | `AppFont.largeTitle` | Weight differs (semibold vs bold) |
| `_xl` | Spacing | 32pt | Missing | — | — | Not present in `AppSpacing` |
| `subtle` | Shadow | y:1 r:2 op:0.04 | Implemented | `Sources/DesignSystem/DesignSystem.swift:118` | `AppShadow.subtle` | — |
| `cornerRadius.card` | Radius | 12pt | Cannot verify | — | — | DesignSystem.swift not found in project |
```

**Status enum**: `Implemented` / `Partially implemented` / `Missing` / `Cannot verify` / `Native exception`

**Item types** (cover all): Color / Typography / Spacing / Radius / Border-Divider / Shadow-Elevation / Surface-Background / Icon-SF-Symbol / Asset / Component / Button-Style / Input-Style / Card-List-Style / Navigation-Style / Other

## 2. Designed Page Inventory

```markdown
| Page | Purpose | Main Sections | DS Components Used | States | Nav Entry |
|------|---------|---------------|---------------------|--------|-----------|
| Home | App landing dashboard | Header, FeedList, FAB | `PrimaryButton`, `Card`, `Avatar` | empty, loading, error | Tab 1 |
| ItemDetail | View single item | HeroImage, MetaRow, Actions | `Card`, `IconButton` | loading, error, deleted | Push from Home |
| Settings | App configuration | SectionList | `Toggle`, `Disclosure` | — | Tab 4 |
```

States enumerate the explicit alternative renders the design specifies (empty, loading, error, selected, disabled, expanded, collapsed, etc.). If the design source is silent on states, record `—` and list under Open Questions.

## 3. Implementation Coverage Matrix

```markdown
| Designed Page | Status | File Path | Primary View | Nav Entry | Notes |
|---------------|--------|-----------|--------------|-----------|-------|
| Home | Implemented | `App/Views/HomeView.swift:12` | `HomeView` | `MainTabView.swift:24` | — |
| ItemDetail | Partially implemented | `App/Views/ItemDetailView.swift:8` | `ItemDetailView` | `HomeView.swift:78` (`.navigationDestination`) | Missing error state |
| Settings | Missing | — | — | — | No matching view found |
| Onboarding | Cannot verify | — | — | — | Multiple candidates: `OnboardingView`, `WelcomeView` — disambiguate |
```

**Status enum**: `Implemented` / `Partially implemented` / `Missing` / `Cannot verify`

For `ds-only` mode, replace this matrix with **Impact Analysis**:

```markdown
| Affected DS Item | Consuming Files (count) | Sample File:Line | Migration Risk |
|------------------|--------------------------|-------------------|----------------|
| `AppColor.primary500` | 23 | `App/Views/HomeView.swift:34` | Low (UI-only) |
| `AppSpacing.md` | 81 | `App/Views/Home/Card.swift:12` | Medium (layout shifts) |
| `AppFont.body` | 47 | `App/Views/ItemRow.swift:18` | High (line-height shifts in lists with user data) |
```

## 4. Page-by-Page Match Report

Per implemented or partially-implemented page, one section:

```markdown
### Home (`App/Views/HomeView.swift:12`)

**Match classification**: `Minor mismatch`

**Observable comparisons**:

| Aspect | Design | iOS | Match |
|--------|--------|-----|-------|
| Header layout | Avatar (left) + Title (center) + Bell (right) | Avatar (left) + Title (left) + Bell (right) | 🔴 Title alignment |
| Header padding | 24 / 16 | 20 / 12 | 🔴 Both |
| FeedList card radius | 16pt | 12pt | 🔴 |
| FAB position | Bottom-right, 24pt margin | Bottom-right, 20pt margin | 🔴 Margin |
| Empty state copy | "No items yet — tap + to add" | "Empty" | 🔴 Copy |
| Loading state | Skeleton rows | ProgressView | 🟡 Acceptable native? — verify |

**Acceptable native differences**:
- Tab Bar uses default `TabView` chrome — design shows custom but native is acceptable.
- Pull-to-refresh uses system gesture; design shows arrow but system convention wins.

**Mismatches drive Gap List entries**: GAP-014, GAP-015, GAP-019, GAP-022.
```

**Match classification**: `Exact or acceptable native difference` / `Minor mismatch` / `Major mismatch` / `Missing implementation` / `Cannot verify`

Compare ONLY observable design and behavior: layout, spacing, typography, colors, icons, assets, hierarchy, radius, shadow, border, buttons, inputs, cards, nav title, tab bar, scroll, safe-area, all states, copy, data formatting, accessibility labels.

## 5. Gap List Entry

Per gap, all 11 fields required:

```markdown
### GAP-001 — Home FAB margin

| Field | Value |
|-------|-------|
| Gap scope | Page |
| Page name | Home |
| Design expectation | FAB bottom-right with 24pt margin from safe-area bottom and 24pt from trailing edge |
| Current behavior | FAB at 20pt / 20pt margin (`HomeView.swift:84`) |
| Evidence (design) | Section "Home / FAB placement" of handoff: "24pt safe-area inset" |
| Evidence (code) | `App/Views/HomeView.swift:84`, `.padding(.trailing, 20).padding(.bottom, 20)` |
| Severity | Low |
| Fix type | Spacing |
| Native exception | No |
| Fix status | Confirmed |
| Recommended fix | Replace literal `20` with `AppSpacing.lg` (24pt) once that token is verified in DS. If `AppSpacing.lg` is missing, this becomes a DS-level gap (re-classify). |
```

**Hard rule**: if the recommended fix is `add token X to DS`, the gap's `Gap scope` must be re-classified to `Design System/Tokens`. Per-page hardcoded values are forbidden when a DS-level fix exists.

## 6. Audit Doc Skeleton

The full file written to `docs/06-plans/YYYY-MM-DD-design-parity-{mode}-design.md`:

```markdown
---
type: design-parity-audit
mode: {full-build|single-page|polish|ds-only}
status: active
current: true
tags: [design-parity, audit]
refs:
  - {design-handoff-url-or-summary-1}
  - {design-handoff-url-or-summary-2}
---

# Design Parity Audit — {mode}

**Generated:** {YYYY-MM-DDTHH:MM:SS}
**Design source:** {summary of handoff content provided by user}
**iOS DesignSystem.swift:** {path or "missing"}
**Project root:** {cwd}

---

## 1. Design System / Tokens Parity Matrix

{table from Template 1; omit if mode == single-page AND no scoped DS impact}

**Summary**: Implemented {N} / Partial {N} / Missing {N} / Cannot verify {N} / Native exception {N}

---

## 2. Designed Page Inventory

{table from Template 2; omit if mode == ds-only}

**Total designed pages**: {N}

---

## 3. Implementation Coverage Matrix

{table from Template 3; in ds-only mode this becomes Impact Analysis}

**Coverage**: Implemented {N} / Partial {N} / Missing {N} / Cannot verify {N}

---

## 4. Page-by-Page Match Report

{one section per page per Template 4; omit if mode == ds-only}

---

## 5. Gap List

{entries from Template 5, ordered: DS gaps first by severity, then page gaps grouped by page}

**Totals**: {N} total — Blocker {N} / High {N} / Medium {N} / Low {N}
**By status**: Confirmed {N} / Decision Point {N} / Blocked {N}

---

## 6. Suggested Phase Outline

(See Template 7 below for the foundation-first rule. This section is the input to /write-dev-guide's Phase splitting.)

{ordered list}

---

## 7. Open Questions / Needs Verification

- [DP-xxx] {short title} — {context}; deferred per user
- {Blocked item} — {reason cannot proceed}
- {Cannot verify item} — {what would unblock}
- {Design-source-silent items} — features in iOS not shown in design; user to confirm retain/remove

---

## 8. Hard Constraints (for /write-dev-guide)

- Design wins when design and code disagree.
- DS / Tokens phase MUST precede page-level phases (if any DS gap exists).
- Each designed page = one phase. Do not merge multiple pages into one phase.
- Do not implement Decision Point items.
- Do not introduce features, flows, copy, data, tokens, or components not present in the design source.
- Acceptable native exceptions: Tab Bar default chrome, SF Symbols rendering, system keyboard, system sheets, safe-area behavior, standard platform-native controls.
```

## 7. Suggested Phase Outline

Apply this ordering when generating the `## 6. Suggested Phase Outline` section of the audit doc:

**Foundation-first hard rule**: if any `Design System/Tokens` gap exists in the Gap List, Phase 1 MUST be `Design System / Tokens Foundation`. No page phase may start until this phase completes.

Then per mode:

### `full-build` mode

```markdown
1. **Phase 1 — Design System / Tokens Foundation** (only if DS gaps exist)
   - Implement / fix all DS gaps from Section 5
   - Acceptance: DS Parity Matrix shows 0 `Missing` / 0 `Drift` for non-`Native exception` items
2. **Phase 2 — {Page A}**
   - Implement / fix all gaps for Page A from Section 5
3. **Phase 3 — {Page B}**
4. ...
N. **Phase N — Submission Prep** (per dev-guide convention)
```

One designed page = one phase. Do not merge.

### `single-page` mode

```markdown
1. **Phase 1 — DS Micro-Foundation** (only if scoped DS gaps exist for this page)
   - Add only the tokens/components used by the audited page
2. **Phase 2 — {Page Name}**
   - Implement / fix all gaps for the page
```

If no DS impact, Phase 1 = the page; output is a single-phase guide.

### `polish` mode

```markdown
1. **Phase 1 — Migration-aware DS Updates** (only if DS gaps with migration-risk: high exist)
   - Token / component changes that affect views displaying user data
   - Acceptance includes regression check on data-bound surfaces
2. **Phase 2 — DS / Tokens Foundation** (remaining DS gaps with low/medium migration risk)
3. **Phase 3..N-1 — One per page** (ordered by user-impact)
N. **Phase N — Verification** (regression test suite)
```

### `ds-only` mode

```markdown
1. **Phase 1 — Design System / Tokens Update** (the only phase)
   - Apply all DS gaps from Section 5
   - Acceptance includes Impact Analysis sweep: all consuming files compile; no visual regression on listed sample pages
```

This single-phase output still goes through `/write-dev-guide` for proper acceptance criteria framing, then `/run-phase` for execution.

---

**Phase mapping rule**: every phase must back-reference the specific Gap IDs from Section 5 (Gap List) it addresses. The Suggested Phase Outline section in the audit doc should pre-fill these references so `/write-dev-guide` carries them forward.
