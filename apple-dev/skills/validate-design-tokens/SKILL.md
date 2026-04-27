---
name: validate-design-tokens
description: "Use when scanning per-View SwiftUI files for Design Token compliance, or the user says 'validate tokens', 'check design tokens', 'check view files for hardcoded values'. Reports hardcoded spacing/colors/fonts/corner-radius in View files, plus an optional DesignSystem.swift ↔ DESIGN.md cross-check (read-only). Not for: applying fixes (use sync-design-md for token sync), doc-vs-code drift across architecture docs (use design-drift)."
compatibility: Requires macOS and Xcode
---

# Validate Design Tokens Skill

Check SwiftUI code for Design Token compliance.

## Input Parameters

- `filePaths`: List of View files to check

## Validation Rules

### Pre-check: DESIGN.md Source-of-Truth Detection

Before running compliance checks, locate the design source of truth:

1. Read `docs/02-architecture/design-source.md` if it exists. Use the recorded `Path` field as DESIGN.md location.
2. Otherwise Glob `**/DESIGN.md` (excluding `node_modules/`, `.build/`, `DerivedData/`). If exactly one result, use it. If multiple, skip Section 7 (DESIGN.md cross-check) and emit `ℹ️ Multiple DESIGN.md candidates found — DESIGN.md cross-check skipped. Run /sync-design-md to declare authoritative source.`
3. If no DESIGN.md found: skip Section 7 entirely, run only Sections 0-6.

**Pre-check: Read deployment target**

```
Grep("IPHONEOS_DEPLOYMENT_TARGET", "*.xcodeproj/project.pbxproj", output_mode="content")
```

- If target < 18.0: skip Section 0 entirely, output:
  `ℹ️ Deprecated API check skipped — deployment target {X} < iOS 18`
- If target ≥ 18.0 or not found: run Section 0.

### 0. Deprecated API Detection (iOS 18+ minimum deployment target)

**Search for `.cornerRadius(`:**
- Flag as ❌ deprecated (removed from SwiftUI public API, deprecated since iOS 17)
- Correct pattern: `.clipShape(.rect(cornerRadius: N))` or `RoundedRectangle(cornerRadius: N)`

**Search for `.foregroundColor(`:**
- Flag as ⚠️ deprecated (replaced by `.foregroundStyle(`)

**Search for `NavigationView {`:**
- Flag as ❌ deprecated (replaced by `NavigationStack` / `NavigationSplitView`)

### 1. Spacing Compliance

**Search for**:
- `.padding(N)` where N is not on the AppSpacing scale (2/4/8/12/16/24/32/48/64)
- `.spacing(N)` where N is not on the AppSpacing scale
- Hardcoded frame sizes

**Valid patterns**:
- `.padding(AppSpacing.md)`
- `.padding(16)`  // matches AppSpacing.sm
- `.spacing(AppSpacing.xs)`
- `.padding(.horizontal, AppLayout.marginCompact)`

**Invalid patterns**:
- `.padding(15)`  // Not on scale
- `.padding(10)`  // Not on scale

### 1a. Layout Margin Compliance

**Search for**:
- `.padding(.horizontal, 16)` and `.padding(.horizontal, 20)` in files whose View struct name ends with `View`, `Screen`, or `Page`

Flag ALL occurrences with: "If this is a page-level margin, use `AppLayout.marginCompact` / `AppLayout.marginRegular` instead."

**Valid patterns**:
- `.padding(.horizontal, AppLayout.marginCompact)`
- `.padding(.horizontal, AppLayout.marginRegular)`
- `.frame(maxWidth: AppLayout.maxContentWidth)`

**Invalid patterns** (🟡 advisory):
- `.padding(.horizontal, 16)` → If page margin, suggest `AppLayout.marginCompact`
- `.padding(.horizontal, 20)` → If page margin, suggest `AppLayout.marginRegular`

### 1b. Spacing Hierarchy Review (advisory 🟡)

**Heuristic**: Check if VStack/HStack spacing values match the hierarchy level of their children.

| Children type | Expected spacing range | Suggested tokens |
|---|---|---|
| Text, Image, Label (leaf elements) | 4–12pt | AppSpacing._3xs ~ .xs |
| Card, Section, Group (containers) | 24–48pt | AppSpacing.md ~ .xl |

- Flag as 🟡 (advisory, not mandatory) when spacing seems mismatched for the hierarchy level

### 2. Color Compliance

**Search for**:
- `Color(hex:)`
- `Color(red:green:blue:)`
- Hardcoded `Color.blue`, `Color.red` (should use semantic)

**Valid patterns**:
- `Color.appPrimary`
- `Color.appBackground`
- System semantic colors: `Color.primary`, `Color.secondary`

**Invalid patterns**:
- `Color(hex: "#FF0000")`

`Color.blue` → ⚠️ Context-dependent
  - If used for brand/primary action: replace with `Color.appPrimary`
  - If used for links, info icons, system tints: ✅ acceptable (this IS a semantic system color)
  - Rule: flag with "Verify: is this a brand color or a system semantic color?"

### 3. Typography Compliance

**Search for**:
- `.font(.system(size:))`

**Valid patterns**:
- `.font(.body)`
- `.font(.headline)`
- `.font(.largeTitle)`

**Invalid patterns**:
- `.font(.system(size: 17))`  // Should use `.font(.body)`

### 4. Corner Radius Compliance

**Search for**:
- `cornerRadius:` values in `.clipShape(.rect(cornerRadius:))` or `RoundedRectangle(cornerRadius:)` where N is hardcoded

**Valid patterns**:
- `.clipShape(.rect(cornerRadius: AppCornerRadius.medium))`
- `RoundedRectangle(cornerRadius: AppCornerRadius.medium)`
- `.clipShape(.rect(cornerRadius: 12))`  // If matches AppCornerRadius.medium

**Invalid patterns**:
- `.clipShape(.rect(cornerRadius: 15))`  // Not in standard set

### 5. Shadow Compliance

**Search for**:
- `.shadow(color:radius:x:y:)` with `opacity > 0.08`

**Valid patterns**:
- `.appShadow(.subtle)`
- `.shadow(color: .black.opacity(0.04), ...)`

**Invalid patterns**:
- `.shadow(color: .black.opacity(0.5), ...)`  // Too heavy

### 6. Layout Frame Consistency

**Purpose**: Detect same-type components with inconsistent sizing/frame behavior.

**Process**:
1. For each file in `filePaths`, extract the View struct name
2. Identify the component type suffix (Card, Row, Cell, Badge, Chip, Tile, Banner)
3. If a suffix is identified, search the project for other components with the same suffix:
   ```
   Grep("struct \\w+{suffix}", glob: "*.swift")
   ```
4. For each same-type component found, compare these layout attributes:

| Attribute | Search Pattern | Consistency Rule |
|-----------|---------------|-----------------|
| Width behavior | `.frame(maxWidth:` / `.frame(width:` / no frame | All same-type must use identical width strategy |
| Padding | `.padding(` | Same directions, same values or same token |
| Background | `.background(` | Same color/material type |
| Corner radius | `.clipShape(.rect(cornerRadius:` / `RoundedRectangle(cornerRadius:` | Same value or same token |
| Shadow | `.shadow(` | Same parameters |

**Valid patterns** (consistent):
```swift
// InsightCard — full width
struct InsightCard: View {
    var body: some View {
        VStack { ... }
            .padding(AppSpacing.sm)
            .frame(maxWidth: .infinity)
            .background(.background.secondary)
            .clipShape(.rect(cornerRadius: AppCornerRadius.medium))
}
// ExpenseCard — matches InsightCard
struct ExpenseCard: View {
    var body: some View {
        VStack { ... }
            .padding(AppSpacing.sm)
            .frame(maxWidth: .infinity)
            .background(.background.secondary)
            .clipShape(.rect(cornerRadius: AppCornerRadius.medium))
}
```

**Invalid patterns** (inconsistent):
```swift
// InsightCard — full width
struct InsightCard: View {
    var body: some View {
        VStack { ... }
            .padding(16)
            .frame(maxWidth: .infinity)  // expanding
}
// ExpenseCard — content hugging (MISMATCH)
struct ExpenseCard: View {
    var body: some View {
        VStack { ... }
            .padding(12)               // different padding
            // no .frame(maxWidth:)    // hugging vs expanding
}
```

### 7. DESIGN.md Cross-Check (when DESIGN.md is present)

**Purpose**: Detect drift between Swift token literal values (`AppColor`, `AppSpacing`, `AppShadow`, plus `AppFont` enum if present) and the project's DESIGN.md as source of truth.

**Scope**: This section validates the **token definitions in DesignSystem.swift**, not the View files. View-level Design Token compliance is covered by Sections 1-6.

**Process**:

1. Locate `DesignSystem.swift` (Glob `**/DesignSystem/DesignSystem.swift`). If not found: skip with `ℹ️ DesignSystem.swift not found — DESIGN.md cross-check skipped`.
2. Verify DESIGN.md is Stitch 9-section format (≥6 of: Visual Theme / Color Palette / Typography / Component Stylings / Layout / Depth / Do's and Don'ts / Responsive / Agent Prompt). If not: skip with `ℹ️ DESIGN.md is not Stitch 9-section format — cross-check skipped`.
3. Apply the mapping from `apple-dev:project-kickoff` references/doc-templates.md "DESIGN.md → Swift Token 映射".
4. For each token:

| Dimension | Swift source | DESIGN.md source | Drift threshold |
|-----------|--------------|------------------|----------------|
| Color | Asset Catalog hex (`Primary500.colorset/Contents.json`) or `Color(red:green:blue:)` literals | Section 2 hex values | per-channel max-delta > 4 of 256 (RGB 8-bit, computable via `python3 -c` one-liner — see sync-design-md "Color match rule") |
| Spacing | `AppSpacing._4xs..._2xl` numeric literals | Section 5 spacing scale | exact (no tolerance) |
| Shadow | `AppShadow.subtle/.../.large` (y, radius, opacity) | Section 6 elevation values | y/radius exact, opacity ±0.01 |
| Typography | `AppFont` enum (if exists) or `docs/02-architecture/typography-rules.md` (fallback) — skip if neither exists | Section 3 typography table | size exact, weight exact |

5. Emit drift findings as 🔴 Must Fix entries with both values cited.

**Example drift output**:

```
🔴 Must Fix:
- DesignSystem.swift:118 - AppColor.primary500 = #4080D0
  DESIGN.md § 2 Color Palette specifies: #4A90E2 (per-channel max-delta = 18, > threshold 4)
  Suggestion: Run /sync-design-md mode=to-swift to align, or revise DESIGN.md if Swift value is correct.

- DesignSystem.swift:191 - AppSpacing.sm = 16 ✅ matches DESIGN.md § 5
- DesignSystem.swift:243 - AppShadow.small radius = 4
  DESIGN.md § 6 Depth specifies radius = 6 (drift)
```

**Note**: Do not auto-fix. This skill reports only. Use `apple-dev:sync-design-md` to apply changes.

## Output Format

```
🔴 Must Fix:
- HomeView.swift:42 - Hardcoded spacing .padding(15)
  Suggestion: Use .padding(AppSpacing.sm)

- CardView.swift:18 - Hardcoded color Color(hex: "#FF0000")
  Suggestion: Define as semantic color Color.appError

🟡 Consider:
- ProfileView.swift:67 - System color Color.blue
  Suggestion: If brand color, use Color.appPrimary

✅ Compliant:
- SettingsView.swift - All spacing uses Design Token
- DashboardView.swift - All colors use semantic tokens
```

## Success Criteria

- All hardcoded spacing/colors/fonts are detected
- Suggestions include exact token names
- Output grouped by severity
