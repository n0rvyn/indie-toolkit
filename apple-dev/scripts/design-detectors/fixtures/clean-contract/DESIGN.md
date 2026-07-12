---
name: Runetic
description: Personal AI running coach for an amateur-but-elite-leaning runner. iPhone-first; Apple Watch is execution-only (no Watch UI). Data is an input to coaching, never a destination.
targetOS: "iOS 26"   # HARD FLOOR. Map to the newest primitive at this floor; NO fallbacks.
sourceOfTruth:
  appTokens: design_handoff_runetic/tokens.css        # Runetic-specific semantics (readiness, wallpaper, editorial type)
  baseTokens: lib/liquid-glass.css                    # base glass / iOS type scale / spacing / radius / motion / system colors
  swiftMirror: design_handoff_runetic/Tokens.swift
  referencePrototype: "Runetic Prototype.html"        # the running visual spec — verify against this, not memory

# Mirror of the canonical token store. Do not author values here that the
# token store lacks. Hex values restate tokens.css / liquid-glass.css.
colors:
  accent-recovery:  "#34C759"
  accent2-recovery: "#00C7BE"
  accent-normal:    "#007AFF"
  accent2-normal:   "#5856D6"
  accent-fatigue:   "#FF9500"
  accent2-fatigue:  "#FF6B9D"
  accent-warning:   "#FF3B30"
  accent2-warning:  "#FF2D55"
  ink-primary:      "#0a0a0a"
  ink-secondary:    "rgba(0,0,0,0.65)"
  ink-tertiary:     "rgba(0,0,0,0.50)"
  ink-primary-dark:   "#f5f5f7"
  ink-secondary-dark: "rgba(255,255,255,0.68)"
  ink-tertiary-dark:  "rgba(255,255,255,0.48)"
  eyebrow:          "rgba(0,0,0,0.55)"

typography:
  display:  { fontFamily: "SF Pro Display / Inter", weight: 800, tracking: "-0.025 to -0.04em", lineHeight: "0.95–1.05", sizeRange: "28–84pt" }
  eyebrow:  { fontFamily: "SF Pro Text / Inter", size: 11px, weight: 800, letterSpacing: 1.4px, textTransform: uppercase, color: "{colors.eyebrow}" }
  body:     { fontFamily: "SF Pro Text / Inter", size: 17px, weight: 400, letterSpacing: "-0.011em" }
  numerals: { fontVariantNumeric: tabular-nums }

rounded: { md: 14px, lg: 18px, xl: 22px, "2xl": 28px, pill: 9999px }
spacing: { gutter: 20px, gapMin: 14px, gapMax: 32px }

# --- Schema extensions: material + motion the standard schema can't hold. ---
materials:
  liquid-glass:
    web:    "background: rgba(255,255,255,0.60); backdrop-filter: blur(30px) saturate(180%)"
    swift:  ".glassEffect(.regular, in: .rect(cornerRadius: 22))"     # iOS 26+ NATIVE
    edge:   "inset 0 1px 0 rgba(255,255,255,0.45) — refraction highlight"
    note:   "Native glassEffect provides blur+tint+refraction. DO NOT port the web blur/saturate/edge stack — it only fakes glass in a browser. Wrap adjacent cards in GlassEffectContainer to merge refraction."
    tints:  "ultrathin .20 / thin .38 / regular .60 / thick .78 (+sat 200% blur 50)"
    canonicalComponent: "lib/glass-primitives.jsx::GlassBlur"
  wallpaper:
    web:    "3 radial-gradient blobs over a linear base, per readiness state"
    swift:  "MeshGradient from Readiness.wallpaperBlobs over base; cross-fade on state change"  # iOS 26 floor — no LinearGradient fallback needed
    canonicalComponent: "src/shared.jsx::DynamicWallpaper + wpFromState"
    note:   "Texture only — no grain/patterns/illustrations. 4 states drive it (constitution #3)."

motion:
  ease-sheet:   { web: "cubic-bezier(0.32,0.72,0,1) 350–420ms", swift: ".spring(response:0.42, dampingFraction:0.82)" }
  ease-control: { web: "cubic-bezier(0.4,0,0.2,1) 250ms",       swift: ".easeInOut(duration:0.25)" }
  press:        { web: "scale(0.96) opacity(0.7) 150ms",        swift: "scaleEffect(0.96)+opacity(0.7), RMotion.quick" }
  wallpaper-morph: { web: "wp-fade-in 950ms", swift: "withAnimation(.easeInOut(0.95)) on Readiness change" }

components:
  card:    { material: "{materials.liquid-glass}", rounded: "{rounded.xl}", padding: "{spacing.gutter}" }
  eyebrow: { typography: "{typography.eyebrow}" }
  ring:    { note: "ReadyRing/CompactRing — score arc filled by accent→accent2 gradient" }
---

## Overview

Runetic is a **personal AI running coach**, not a data dashboard. The loop:
**训练前** give a prescription ("今日该怎么跑") → **训练中** send to Apple Watch → **训练后** the analysis folds into tomorrow's prescription text. There is no Watch UI, no community, no separate report pages, no Knowledge tab. Long-term analysis exists only as an input to coaching.

This document is the **contract layer**. It mirrors the token store and adds the why/how/don't. For any material, motion, or layout *recipe*, it points at a working reference component — copy that, do not re-derive it from this prose. The running visual spec is `Runetic Prototype.html`; verify against it, not memory.

## Colors

Accents are **state-driven, not fixed.** The four readiness states each own an `accent`/`accent2` pair (mirrored in front matter, canonical in `tokens.css`). Components read the active `--accent` / `Readiness.accent` — never a per-state literal. System colors (blue/green/orange/red + grays, light & dark) live in `lib/liquid-glass.css`.

Text hierarchy is built from **explicit colors, not opacity** (RUI). `opacity: 0.5` over a wallpaper makes text vanish — use `ink-primary` / `ink-secondary` / `ink-tertiary` over solid surfaces, and the per-state hue-tinted scale (`fg-tint-*`) over wallpapers.

The ink ladder has **both sides**: light rungs `--ink-primary` / `--ink-secondary` / `--ink-tertiary` and dark rungs `--ink-primary-dark` / `--ink-secondary-dark` / `--ink-tertiary-dark` (Swift: `RType.inkPrimary` … `RType.inkPrimaryDark` …). 深色 is a real setting (see 4c), so every semantic ink step resolves in both schemes — never dim a light ink with opacity to fake dark.

## Typography

中文教练对话 + 英文数据 label/eyebrow — the bilingual duality is intentional. SF Pro on Apple hardware; Inter is the open web fallback.

- **Editorial display** (28–84pt, weight 800, tracking −0.025 to −0.04em, leading 0.95–1.05) — the Apple-Music headline feel. Type-led, not icon-led.
- **Eyebrow / section label** (11pt, weight 800, letterSpacing 1.4, uppercase, color `rgba(0,0,0,0.55)`).
- **Counter-intuitive rule:** small text gets BIGGER weight — 10pt→800, 13pt→700.
- **All aligned digits are tabular** (`<Num>` on web, `.monospacedDigit()` native).

## Layout

20px page gutter; 14–32px card gaps. Generous padding. Use flex/grid + `gap` on web; `HStack`/`VStack`/`Grid(spacing:)` native — never `GeometryReader` math for simple rows.

## Elevation & Depth

Depth comes from **Liquid Glass over a vivid wallpaper**, not drop shadows. The wallpaper is the only texture (no grain, no illustration). Glass refracts it; ambient halos (`--shadow-glass-*`) sit under cards. The glass recipe is a RECIPE — see Materials & Motion and copy `GlassBlur` / use native `.glassEffect`.

## Shapes

Squircle radius scale (`tokens` in liquid-glass.css): cards 22 (`xl`), sheets 28 (`2xl`), pills 9999. Continuous-curvature where supported.

## Materials & Motion

- **liquid-glass** — implemented in `lib/glass-primitives.jsx::GlassBlur`. On iOS 26+ use the **native `.glassEffect`** (front matter `materials.liquid-glass.swift`). The web blur/saturate/edge stack is a browser fake — see DO-NOT-PORT.
- **wallpaper** — `src/shared.jsx::DynamicWallpaper` + `wpFromState`; native `MeshGradient` from `Readiness.wallpaperBlobs`. Cross-fades 950ms on state change (the "打开 App → 知道身体" morph).
- **sheets / modals** — bottom sheet (`SheetShell` in `screens-week.jsx`) for info/forms/actions; center scale-in modal (`SkipPreviewModal`) for decisions. Spring `response 0.42, damping 0.82`.
- **press** — every tappable surface: scale 0.96 + opacity 0.7 over ~150ms (`PressState`).

## Components

| Component | Canonical reference | Notes |
|---|---|---|
| Glass surface | `lib/glass-primitives.jsx::GlassBlur` | → native `.glassEffect`. 6 tints. |
| Card | `GlassBlur tint="thick" radius=22` | default content container |
| Bottom sheet | `screens-week.jsx::SheetShell` | drag handle taps to close, backdrop click closes, blur 8px |
| Center modal | `screens-week.jsx::SkipPreviewModal` | decision / destructive moments only |
| Readiness ring | `shared.jsx::ReadyRing / CompactRing` | score arc, accent→accent2 gradient |
| Tab bar | `shared.jsx::RuneticTabBar` | 4 tabs 今日/训练/洞察/我; active = accent |
| Numerals | `shared.jsx::Num` | tabular-nums everywhere digits align |

## 4. Platform Mapping (JS → SwiftUI)

> The prototype is a **specification of appearance and behavior**, not a codebase to transpile. Translate paradigms, not syntax. Skip everything in the DO-NOT-PORT list.

### 4a Material / visual

| Web / CSS (prototype) | SwiftUI (idiomatic) |
|---|---|
| `backdrop-filter: blur(30px) saturate(180%)` glass | `.glassEffect(.regular, in: .rect(cornerRadius:22))` — required (iOS 26 floor); don't re-derive the edge stack |
| adjacent glass cards | wrap in `GlassEffectContainer { }` to merge refraction |
| 3-blob `radial-gradient` wallpaper | `MeshGradient` from `Readiness.wallpaperBlobs` over base |
| `font-variant-numeric: tabular-nums` / `<Num>` | `.monospacedDigit()` |
| `letter-spacing: -0.03em` | `.tracking(pt)` — **convert em→points per size, don't paste the em** |
| `line-height: 0.95` on display type | **No direct API.** Apply `lineHeightMultiple` via `AttributedString`/`UIFont`. Known gap — flag if unachievable. |
| `font-weight: 800` | `.fontWeight(.heavy)` (800≈heavy; 900=black) |
| color-based hierarchy `rgba(0,0,0,0.65)` | `.foregroundStyle(Color(white:0, opacity:0.65))` — keep color-not-view-opacity |
| Spark / MiniBars / charts | **Swift Charts** — never hand-rolled `Path` |
| accent→accent2 fills | `Readiness.accentGradient` |

### 4b Structure / state

| React paradigm (prototype) | SwiftUI |
|---|---|
| `useState` | `@State` |
| `ReadinessCtx` / `ThemeCtx` / `NavCtx` (Context) | `@Environment` + an `@Observable` model — not prop drilling |
| `useNav().go(route)` client router | `NavigationStack(path:)` |
| flex / grid + `gap` | `HStack`/`VStack`/`Grid(spacing:)` — not `GeometryReader` |
| `position: fixed` overlay | `ZStack` / `.overlay` / `.safeAreaInset` |
| `SheetShell` bottom sheet | `.sheet` + `.presentationDetents` |
| `SkipPreviewModal` center modal | `ZStack` overlay + `.transition(.scale.combined(with:.opacity))` |
| per-state content (T1/T3/T9 etc. switch on readiness) | `switch readiness { … }` returning the state's copy/data |

### 4c State & tweak mapping (the conditional-UI checklist)

The prototype's Tweaks panel is **not design options** — it's a **state matrix**. The panel UI is DO-NOT-PORT, but every value it enumerates is a runtime branch the native app must implement. Build them all; the production trigger is real data/state, never a control.

| Tweak (prototype) | Kind | Native obligation |
|---|---|---|
| `globalState` 已恢复/可训练/需谨慎/建议休息 | state demonstrator | the 4 `Readiness` values — **computed from sensor data (HRV/load), not chosen.** Build all 4; they drive accent + wallpaper |
| `theme` 浅色/深色/跟随系统 | real setting | native color scheme + a Settings control |
| `coachFinding` 有/无发现 (T1) | state demonstrator | Today must handle "AI finding present" AND "none" |
| `loadData` 充足/积累中 (T2) | state demonstrator | load card: full data vs still-accumulating |
| `yesterday` 有跑步/休息日 (T3) | state demonstrator | yesterday card: ran vs rest day |
| `postRun` 未跑/已判读 (T4) | state demonstrator | post-run analysis interstitial appears because data arrived, then resolves |
| `insightsData` 充足/零数据 (I*) | state demonstrator | every Insights screen needs a true empty state |
| `meData` 充足/新用户 (M1-3) | state demonstrator | Me tab: established vs brand-new user |
| `planState` 空/生成中/就绪 (P1) | state demonstrator | Plan tab lifecycle — all three, incl. the generating interstitial |
| `startRoute` / 当前屏 | dev nav | DO NOT PORT — pure prototype routing |

**Coach engagement is product config, not a tweak** (it wasn't wired as one): tiers `active/balanced/passive` (frequency) + tone `calm-pro/warm/data-driven` are real settings — build the Settings controls and document value→behavior when that screen is specced.

### 4d DO NOT PORT (prototype scaffolding — delete, don't translate)

- `lib/design-canvas.jsx` and `Runetic.html` — the pan/zoom demo canvas.
- `lib/tweaks-panel.jsx`, `useTweaks`, the route / readiness / plan-state pickers in `prototype-app.jsx` — dev affordances.
- `lib/ios-frame.jsx` / `RuneticFrame` bezel, dynamic island, faked status bar — the OS provides these.
- the `GlassBlur` `backdrop-filter` / `box-shadow` edge stack — fakes Liquid Glass in a browser; use native `.glassEffect`.
- `BlurTopBar`'s manual blur — use a native navigation bar / `.toolbar`.
- mock fixtures (`RECENT_RUNS`, `WEEK_PLANS`, `LOAD_BY_STATE`, `AI_FINDINGS`, …) — wire to real data; keep only their SHAPES as the model contract.

### 4e Per-screen state completeness (empty / zero-data / device-missing)

Every screen that FLOW.md marks with a `statesRef` owes these branches. FLOW guarantees the screen *exists*; this section owns what it must *show*.

| Screen | Branches owed |
|---|---|
| today.root | readiness×4 · phase pre/done · planState 空/生成中/就绪 · loadData 充足/积累中 · yesterday 有跑步/休息日 · watchSync 已连/未连 |
| plan.root | planState 空 / 生成中 / 就绪 |
| insights.root | dataState full / partial / empty (a true zero-data screen, not a spinner) |
| me.root | meData full / new user |
| day / week | today · past · future · rest |

Each branch is real-data driven (never a control). Both color schemes resolve for all of them: light rungs + dark rungs (Colors).

## Do's and Don'ts

- **Do** read `RType.inkPrimary` / `Readiness.*` from `Tokens.swift`; never paste a hex from the prototype.
- **Do** use native `.glassEffect` and `MeshGradient` — map to the newest platform primitive, not the web fake.
- **Do** drive accent + wallpaper from the single `Readiness` value (constitution #3).
- **Do** keep hierarchy in color + weight; small text gets bigger weight.
- **Don't** transliterate JSX — translate paradigms (Platform Mapping) and skip DO-NOT-PORT scaffolding.
- **Don't** add a Watch UI, a report page, a Knowledge tab, or a 5th tab.
- **Don't** turn data (HRV/CTL/TSB) into its own page — it's an input to the prescription (constitution #1).
- **Don't** re-author values here that the token store lacks; this mirrors, it doesn't invent.
