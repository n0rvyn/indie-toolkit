---
name: sync-design-md
description: "Use when applying writes between a Stitch DESIGN.md and SwiftUI DesignSystem.swift, or the user says 'sync design', 'update design tokens to match', 'design.md 同步', 'apply DESIGN.md changes to swift', 'reflect swift tokens back to DESIGN.md'. Runs bidirectional to-swift / from-swift modes that modify files; check mode reports drift only. Not for: per-View token compliance scan (use validate-design-tokens), doc-vs-code drift across multiple doc types (use design-drift), or projects without a Stitch 9-section DESIGN.md."
compatibility: Requires macOS and Xcode
---

# Sync DESIGN.md ↔ DesignSystem.swift

Bidirectional sync between Google Stitch's DESIGN.md (9-section) and the project's `DesignSystem.swift` Swift token file.

DESIGN.md is the source of truth for visual identity. Swift is the consumer. This skill keeps them aligned without losing Swift-side extensions (computed properties, helper modifiers, conditional tokens).

## Input

Mode (required, ask user via AskUserQuestion if not specified):

- **check** — diff only, report drift, do not modify any file
- **to-swift** — DESIGN.md → DesignSystem.swift (DESIGN.md wins; default for designer-led workflows)
- **from-swift** — DesignSystem.swift → DESIGN.md (Swift wins; for engineer-led adjustments that should be reflected back to designer)

Optional:

- DESIGN.md path (auto-detected if `docs/02-architecture/design-source.md` exists; else search `**/DESIGN.md`)
- DesignSystem.swift path (auto-detected from `**/DesignSystem/DesignSystem.swift`)

## Process

### Step 1: Locate Source of Truth

1. Read `docs/02-architecture/design-source.md` if it exists. Use the recorded `Path` field as DESIGN.md location.
2. If no source-of-truth file: Glob `**/DESIGN.md` (excluding `node_modules/`, `.build/`, `DerivedData/`). If multiple matches, ask user which one is authoritative.
3. Glob `**/DesignSystem/DesignSystem.swift`. If multiple, ask user.
4. If either file is missing, stop and instruct the user:
   - Missing DESIGN.md → run `/project-kickoff` step 7 to generate via Stitch
   - Missing DesignSystem.swift → run `/project-kickoff` step 9.6

### Step 2: Verify DESIGN.md is Stitch 9-section Format

Apply the recognition rule from `apple-dev:project-kickoff` `references/doc-templates.md` section "DESIGN.md (Stitch 9-section) 识别": ≥ 6 of the canonical sections must be present.

If not Stitch format: stop with `❌ DESIGN.md is not Stitch 9-section format. This skill only syncs the Stitch standard. For other formats, edit DesignSystem.swift directly.`

### Step 3: Extract Tokens from Both Sides

**From DESIGN.md** — parse using `references/doc-templates.md` "DESIGN.md → Swift Token 映射" rules. Produce a normalized token dict:

```yaml
colors:
  primary500: "#4A90E2"
  primary600: "#3A7AC2"
  appPrimary: "primary500"   # semantic alias
  appBackground: "gray50"
typography:
  largeTitle: { size: 34, weight: bold, family: "SF Pro" }
  body: { size: 17, weight: regular, family: "SF Pro" }
spacing:
  _2xs: 8
  sm: 16
  md: 24
shadows:
  subtle: { y: 1, radius: 2, opacity: 0.04 }
  medium: { y: 4, radius: 8, opacity: 0.08 }
```

**From DesignSystem.swift** — Grep + Read the relevant enums (`AppColor`, `AppSpacing`, `AppShadow`, `AppCornerRadius`, `Color` extensions). Produce the same normalized dict by parsing literal values.

**Typography handling** — typography has no central enum by default convention. Sync rule:

1. Glob `**/AppFont.swift` or `grep -r "enum AppFont" {project}/*.swift`. If found: parse the enum literal values and treat as the Swift typography source.
2. Otherwise: scan `docs/02-architecture/typography-rules.md` (written during project-kickoff 9.6 fallback). If found: treat as the Swift-side typography record.
3. Otherwise: emit `ℹ️ Typography sync skipped — project uses inline .font() modifiers without a central enum or rules doc. Run /project-kickoff 9.6 to generate typography-rules.md, or define an AppFont enum.` Do not attempt to compare against scattered View-level `.font()` calls.

### Step 4: Diff

Per-token comparison. Classify each token as:

- ✅ **match** — values equal within tolerance (color: see below; spacing: exact; shadow: y/radius exact, opacity ±0.01)

  **Color match rule** (no perceptual ΔE; deterministic computation):
  - Normalize both hex strings to 6-digit lowercase (e.g., `#FFF` → `#ffffff`, `#4A90E2` → `#4a90e2`)
  - Parse to (R, G, B) 8-bit triples
  - Match iff `max(|R1-R2|, |G1-G2|, |B1-B2|) ≤ 4` (per-channel max-delta ≤ 4 of 256)
  - Bash one-liner: `python3 -c "import sys; a,b=sys.argv[1:];f=lambda h:tuple(int(h.lstrip('#')[i:i+2],16) for i in (0,2,4));d=max(abs(x-y) for x,y in zip(f(a),f(b)));print('match' if d<=4 else f'drift d={d}')" "#4a90e2" "#4080d0"`
  - Rationale: pure RGB-channel delta is computable in one shell call; threshold 4 ≈ ΔE76 ≈ 4-6 for mid-saturation hues, which matches the "barely-noticeable" intent of ΔE<2 without requiring LAB conversion. Drop perceptual accuracy for determinism.
- 🔴 **drift** — value present on both sides but differs
- 🟡 **only-in-design** — DESIGN.md has it, Swift does not
- 🟡 **only-in-swift** — Swift has it, DESIGN.md does not

Output a drift report to `.claude/reviews/design-sync-{YYYY-MM-DD-HHmmss}.md`:

```markdown
# DESIGN.md ↔ DesignSystem.swift Sync Report

Mode: {check|to-swift|from-swift}
DESIGN.md: {path}
DesignSystem.swift: {path}
Generated: {timestamp}

## Summary

- ✅ Matches: {N}
- 🔴 Drift: {N}
- 🟡 Only in DESIGN.md: {N}
- 🟡 Only in Swift: {N}

## Drift Details

### 🔴 colors.primary500
- DESIGN.md: `#4A90E2`
- Swift (`AppColor.primary500`, file:line): `#4080D0`
- per-channel max-delta: 18 (> threshold 4)

### 🟡 spacing.xxxl (only in DESIGN.md)
- DESIGN.md: `96pt`
- Swift: missing
- Suggestion: add `static let _3xl: CGFloat = 96` to `AppSpacing`

### 🟡 typography.captionMono (only in Swift)
- Swift: `AppFont.captionMono = .system(size: 12, design: .monospaced)`
- DESIGN.md: missing
- Note: Swift-side extension. May be intentional engineering need; confirm with designer.
```

### Step 5: Apply Changes (skip if mode == check)

**Mode `to-swift`**:

1. For each 🔴 drift entry: Edit DesignSystem.swift to replace the Swift value with DESIGN.md value
2. For each 🟡 only-in-design: Edit DesignSystem.swift to add the missing token (in the appropriate enum)
3. Do NOT touch 🟡 only-in-swift entries (preserve Swift-side extensions)
4. After edits: detect build target and verify compilation. Use this Bash decision tree:

   ```bash
   if [ -f Package.swift ]; then
     swift build 2>&1 | tail -50
   elif ls *.xcworkspace 2>/dev/null | head -1 > /dev/null; then
     ws=$(ls *.xcworkspace | head -1)
     scheme=$(xcodebuild -list -workspace "$ws" -json 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print([s for s in d['workspace']['schemes'] if 'Test' not in s and 'UI' not in s][0])")
     xcodebuild -workspace "$ws" -scheme "$scheme" build 2>&1 | tail -50
   elif ls *.xcodeproj 2>/dev/null | head -1 > /dev/null; then
     proj=$(ls *.xcodeproj | head -1)
     scheme=$(xcodebuild -list -project "$proj" -json 2>/dev/null | python3 -c "import sys,json;d=json.load(sys.stdin);print([s for s in d['project']['schemes'] if 'Test' not in s and 'UI' not in s][0])")
     xcodebuild -project "$proj" -scheme "$scheme" build 2>&1 | tail -50
   else
     echo "BUILD_SKIPPED: no buildable target detected"
   fi
   ```

   - If `BUILD_SKIPPED`: record "build verification skipped — no buildable target" in the drift report; do NOT revert edits
   - If build returns non-zero AND output contains compile error markers (`error:`, `cannot find`, `expected`): revert via `git checkout -- {DesignSystem.swift path}` and report the failure
   - If build returns non-zero with infrastructure errors (provisioning, code signing, simulator): record warning, do NOT revert (edits are likely correct; build failure is unrelated)
5. Update `docs/02-architecture/design-source.md` `Last sync` field

**Mode `from-swift`**:

1. For each 🔴 drift entry: Edit DESIGN.md to replace the DESIGN.md value with Swift value, in the corresponding section's table row
2. For each 🟡 only-in-swift: append a row to the appropriate DESIGN.md section's table
3. Do NOT touch 🟡 only-in-design entries (Swift may not have implemented them yet — ask user separately)
4. Update `docs/02-architecture/design-source.md` `Last sync` field

**Both modes — confirmation gate**:

Before applying, present the drift count and ask via AskUserQuestion:

> 即将同步：
> - 🔴 修复 {N} 处 drift
> - 🟡 添加 {N} 个新 token
>
> - **确认应用** — 执行修改
> - **仅查看报告** — 切换到 check 模式
> - **取消** — 不修改

### Step 6: Report

Print path to the drift report and the summary line:

```
✅ Sync complete
Report: .claude/reviews/design-sync-2026-04-27-143055.md
Mode: to-swift
Applied: 4 fixes, 1 addition
Build: passed
```

## Edge Cases

- **DESIGN.md target section is prose, not a table** (common for sections 1 Visual Theme, 4 Component Stylings, 7 Do's and Don'ts, 8 Responsive, 9 Agent Prompt — all of which may be freeform): for `from-swift` mode, do NOT attempt to append a structured row. Instead emit `⚠️ Section "{N. Name}" is prose-formatted; cannot append structured row. Manual edit required at {DESIGN.md path}:{first line of section}.` Skip the entry but record it in the drift report so the user can address manually.
- **DESIGN.md uses Display P3 hex but Asset Catalog uses sRGB**: convert via Bash with `sips` or document the deliberate offset in `design-source.md`
- **DESIGN.md typography uses non-system font without registration**: skip the Font sync, emit `⚠️ Custom font {Name} requires .ttf in Resources + Info.plist registration. Sync skipped.`
- **AppShadow has 5 levels but DESIGN.md only specifies 3**: keep Swift's extras as 🟡 only-in-swift (do not delete)
- **Conflict during from-swift when DESIGN.md is in git and has uncommitted changes**: stop, ask user to commit or stash first

## Success Criteria

- Drift report written to `.claude/reviews/design-sync-*.md`
- In to-swift / from-swift mode: changes applied and build/format check passed
- `docs/02-architecture/design-source.md` `Last sync` updated
- No data lost on either side (Swift-side extensions preserved when DESIGN.md is authoritative)

## Not This Skill

- Initial DesignSystem.swift creation → use `apple-dev:project-kickoff` step 9.6 or `apple-dev:generate-design-system`
- Design Token compliance check in View files (e.g., hardcoded `.padding(15)`) → use `apple-dev:validate-design-tokens`
- Cross-file design vs code drift (View uses wrong color) → use `dev-workflow:design-drift`
