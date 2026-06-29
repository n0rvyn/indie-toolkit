# Refactoring UI — Quantified Metrics & Audit Rubric (Generic)

> Source: *Refactoring UI* by Adam Wathan & Steve Schoger (full book, 252 pp). Page numbers cited as `p.NN`.
> Purpose: a reusable, self-contained standard for (a) **auditing** existing UI and (b) **building** new UI.
> Audience: this file is written so a fresh agent who has **never read the book** can apply it. For a per-View audit, dispatch an agent with **Part B + one View file** — it does not need Parts A or C to score a View.
>
> **Project-neutrality note:** This is the canonical, generic version of the rubric. Token names in this file are placeholders (e.g. `<spacing token scale>`, `<primary/secondary/tertiary button style>`, `<elevation/shadow token>`, `<surface token>`). Each project substitutes its own DESIGN.md / token namespace for these placeholders when applying the rubric. The structural rules — not the sample token names — are what an audit scores against.
>
> **Apple/SwiftUI companion (prose 互引):** the Apple-specific expression of these metrics lives in `apple-dev/references/ui-design-principles.md` §17-20 (same source book, *Refactoring UI*). This file is the platform-neutral canonical rubric; that one applies it to SwiftUI/macOS. They cross-reference, not duplicate.

---

## How to read this file

The book is web/CSS (px, `hsl()`, `box-shadow`, `em`). Every auditable metric below carries its **SwiftUI/macOS** translation and a **how-to-check**. Three parts:

- **Part A — Canonical systems.** The book's reference scales/values. These are **examples, not law** (the book says so repeatedly: *"here's an example scale… it's not a science, trust your eyes."*).
- **Part B — Auditable metrics.** The measurable, per-View checkable subset. **This is what an audit consumes.**
- **Part C — Build-time principles.** Process/judgment advice that is **not per-View checkable**. Use when designing new UI; do **not** try to "audit" it.

### The #1 rule for auditing: score against STRUCTURAL rules, not the sample numbers

A design does **not** fail because its spacing scale isn't literally `4/8/12/16…`. It fails when:

- no constrained, predefined scale **exists** (values are hand-picked ad hoc), or
- the scale is **linear** (equal steps) instead of progressive, or
- **adjacent steps are <25% apart** (the book's one hard numeric rule, p.72), or
- **two competing systems** coexist (legacy + new) instead of one, or
- a value is used that is **not from the scale** (off-scale literal).

Exact values are "trust your eyes." Existence, consistency, non-linearity, and the 25% gap are the falsifiable pass/fail criteria.

---

## Part A — Canonical systems (reference values; examples, not law)

| System | Rule | Book's example values | Page |
|---|---|---|---|
| **Spacing/sizing** | One scale, base 16, **progressive** (packed at small end, wider at top), **no two adjacent values closer than ~25%** | `4 8 12 16 24 32 48 64 96 128 192 256 384 512 640 768` (all = 16×) | p.71–73 |
| **Type scale** | Hand-crafted, constrained; **px/rem not em**; avoid fractional px | `12 14 16 18 20 24 30 36 48 60 72` | p.103–107 |
| **Font weight** | Two weights usually enough; **never <400 for UI body** (small text) | `400/500` normal · `600/700` emphasis | p.41 |
| **Text-color hierarchy** | **2–3 levels**, by reducing contrast | dark primary · grey secondary · lighter-grey tertiary | p.40 |
| **Color palette size** | Greys **8–10**; each primary/accent **5–10**; complex UI up to **~10 hues × 5–10 shades**; avoid true black | 9-step is ideal: `100`(lightest)/`500`(base)/`900`(darkest) | p.144–151 |
| **Color model** | Use **HSL**, not hex/RGB | hue 0°=red, 120°=green, 240°=blue | p.138–141 |
| **Lightness vs saturation** | Raise **saturation** as lightness moves away from 50% (or shades wash out) | — | p.152 |
| **Brightness via hue** | Lighten → rotate toward nearest **60/180/300°**; darken → toward **0/120/240°**; **≤20–30°** total | — | p.155–157 |
| **Greys aren't grey** | Saturate greys for temperature: cool=+blue, warm=+yellow/orange; raise S on light/dark shades | cool `H~208–210 S 12–21%`; warm `H~39–41 S 12–21%` | p.158–160 |
| **Contrast (WCAG)** | normal text (<~18px) **≥4.5:1** · large text **≥3:1** (AA). AAA = 7:1 / 4.5:1 | flip contrast (dark text on light-color) when colored bg too heavy; rotate hue toward cyan/magenta/yellow for colored text | p.162–165 |
| **Elevation / shadow** | **~5 levels**, smallest→largest, increasing ~linearly; higher elevation → ambient (tight) shadow more subtle | single: `0 1px 3px /.2`, `0 4px 6px`, `0 5px 15px`, `0 10px 24px`, `0 15px 35px`. two-part: `0 1px 3px/.12, 0 1px 2px/.24` … `0 20px 40px/.2` | p.180–189 |
| **Raised vs inset** | raised = lighter top edge (hand-picked, not white-opacity) + dark drop shadow below; inset = lighter bottom edge + dark inset shadow at top; **sharp** shadows (few-px blur) | `box-shadow: 0 1px 3px hsla(0,0%,0%,.2)` | p.172–178 |
| **Flat depth** | lighter than bg = closer/raised; darker = inset; solid shadow (offset, no blur) | `box-shadow: 0 3px 0 hsl(220,7%,83%)` | p.190–193 |
| **Border radius** | Consistent; **never mix square + rounded** in one UI | — | p.25 |
| **Line length** | **45–75 characters** per line | `20–35em` (`max-width`) | p.114–116 |
| **Line-height** | **Inverse to font size**: small text taller (1.5–1.75), large headlines →1. Proportional to width: narrow 1.5, wide up to 2 | — | p.122–125 |
| **Letter-spacing** | Tighten headlines (`-0.05em`); widen all-caps (`+0.05em`); else leave alone | — | p.132–134 |
| **Border width** | Thin border too subtle? **increase width (1→2px)** instead of darkening color | — | p.56–59 |
| **Gradient** | Two hues **≤30° apart** | — | p.230 |
| **Icon size** | Drawn for **16–24px**; don't scale up 3–4× (chunky); enclose small icon in a shape to fill space | — | p.208–213 |

---

## Part B — Auditable metrics (per-View checklist)

**Score each View + sub-View against every applicable row.** Columns: structural rule (pass/fail) · SwiftUI expression + how to check · applicability to a native macOS app.

### Hierarchy (p.36–62)

| ID | Rule (pass/fail) | SwiftUI check | Applies |
|---|---|---|---|
| **H1** | Hierarchy carried by **weight/color too**, not size alone (no oversized primary / tiny secondary) | `.font()` size+weight + `.foregroundStyle()`; flag huge size gaps used as the only signal | ✅ |
| **H2** | **≤2–3 text colors** per view (primary/secondary/tertiary) | count distinct `.foregroundStyle` label tokens; >3 = fail | ✅ |
| **H3** | **≤2 font weights** for body; **no weight <regular** on small text | `Font.Weight`; flag `.light/.thin/.ultraLight` on small text | ✅ |
| **H4** | Actions ranked: primary (solid/high-contrast), secondary (outline/low-contrast), tertiary (link-like); **≤1 primary per view** | `.buttonStyle(<primary/secondary/tertiary button style>)`; flag multiple primaries or all-same | ✅ |
| **H5** | Low-contrast text on colored bg = **hand-picked same-hue color**, not white+opacity | flag `.opacity()` on text over colored background | ✅ |
| **H6** | Icon beside text **de-emphasized** (softer color) so it doesn't outweigh text | compare icon vs text `.foregroundStyle` | ✅ |
| **H7** | Section titles sized like **labels**, not oversized headings | flag section-title font ≥ title1 when it's just a label | ✅ |

### Layout & spacing (p.66–99)

| ID | Rule | SwiftUI check | Applies |
|---|---|---|---|
| **S1** | All spacing from the **token scale**, no ad-hoc literals | flag literal `.padding(13)` / `spacing: 7` not from `<spacing token scale>` | ✅ |
| **S2** | **Space around a group > space within it** (no ambiguous spacing) | inspect nested `VStack`/`padding`: label↔field gap < group↔group gap | ✅ |
| **S3** | Block-level view (has `.background` + border/stroke) uses `frame(maxWidth:.infinity)` | project rule; flag block views hugging content | ✅ |
| **S4** | Width = content need (max-width), not "fill because sibling fills" | check `.frame(maxWidth:)` / fixed widths | ✅ |
| **S5** | Generous whitespace; not cramped | flag content padding below the project's mid-tier spacing token on primary containers | ✅ |

### Typography (p.102–134)

| ID | Rule | SwiftUI check | Applies |
|---|---|---|---|
| **T1** | All sizes from the **type scale**, no literal `Font.system(size:)` | grep literal sizes not in `<type token scale>` | ✅ |
| **T2** | Mixed-size text on one row **baseline-aligned**, not centered | `HStack(alignment: .firstTextBaseline)`; flag `.center` with mixed sizes | ✅ |
| **T3** | Body line length **45–75 chars** | editor/body text frame width vs font size | ✅ (editor body) |
| **T4** | Line-height inverse to size (large headlines not over-spaced) | `.lineSpacing()`; flag large title with big lineSpacing | ✅ |
| **T5** | Body left-aligned; center only ≤2–3 lines | `.multilineTextAlignment`; flag centered long copy | ✅ |
| **T6** | All-caps text gets widened tracking | `.tracking()/.kerning()` on `.textCase(.uppercase)` | ✅ |

### Color (p.138–168)

| ID | Rule | SwiftUI check | Applies |
|---|---|---|---|
| **C1** | Colors from **tokens**, no `Color(hex:)`/literal RGB in views | grep literal colors outside DesignSystem | ✅ |
| **C2** | Text contrast **≥4.5:1** (normal) / **≥3:1** (large) | compute ratio from resolved token values | ✅ |
| **C3** | State **not by color alone** (add icon/shape/text) | check status badges/indicators carry a non-color signal | ✅ |

### Depth & surface separation (p.172–196, 238–241)

| ID | Rule | SwiftUI check | Applies |
|---|---|---|---|
| **D1** | Adjacent surfaces **visibly separated** — by shadow, a real bg-color delta, or spacing; **cards must not be invisible** | flag `.background(panel)` where panel ≈ parent bg AND no `.shadow`/`<elevation/shadow token>` | ✅ (high-impact) |
| **D2** | Elevation via the **shadow token scale**, mapped to z-position; not ad-hoc `.shadow` | flag raw `.shadow()` literals; check `<elevation/shadow token>` usage on cards/popovers/modals | ✅ |
| **D3** | lighter=raised / darker=inset applied consistently | check surface-color direction vs intent | ✅ |
| **D4** | Prefer shadow / two bg-colors / spacing **over borders**; drop redundant borders | count `.border`/`strokeBorder`; flag border + distinct bg together | ✅ |
| **D5** | Border width balanced (not too-thin-too-light) | flag 1px hairline at very low contrast | ✅ |

### Finishing (p.220–246)

| ID | Rule | SwiftUI check | Applies |
|---|---|---|---|
| **F1** | Empty states **designed** (illustration/icon + emphasized CTA), not bare "No items" | inspect empty branches of lists/collections | ✅ |
| **F2** | Corner radius from **radius token**, consistent (no square+round mix) | grep literal `cornerRadius:`; check consistency | ✅ |
| **F3** | Bland areas get an accent (accent border / supercharged default) | opportunity-level, low priority | ✅ (optional) |

### Marked **N/A** for a native macOS writing app (do **not** manufacture gaps — *参考文档未提及 ≠ 删除*)

`em` units (SwiftUI has none) · favicon redraw · user-upload cropping/`object-fit: cover`/background-bleed · justified-text hyphenation · decorative background patterns / world-map · 12-column grid percentages · "use good photos" (no stock photography) · right-align numbers (only if a numeric table exists).

---

## Part C — Build-time principles (NOT per-View auditable)

Use when **designing** new UI; these are judgment/process, not checkable on an existing View.

- **Start from scratch** (p.7–33): start with a *feature* not the layout/shell · detail & color come later (design in grayscale first; let spacing/contrast/size carry it) · don't design too much, work in short cycles · be a pessimist (ship the smallest useful version) · choose a personality (font / color / radius / language) · **limit your choices / systematize everything** (define scales up front for size, weight, line-height, color, margin, padding, width, height, shadow, radius, border-width, opacity).
- **Hierarchy** (p.36): hierarchy is the biggest "designed" lever · emphasize by **de-emphasizing** competitors · labels are a last resort (combine label+value) · separate visual from document hierarchy (style ≠ semantic tag) · destructive ≠ automatically big-red-bold.
- **Layout** (p.76–95): you don't have to fill the whole screen (use only the width you need; give elements a max-width, shrink only when forced) · grids are overrated (fixed width for sidebars, fluid for content) · relative sizing doesn't scale (fine-tune sizes/padding independently per breakpoint).
- **Type/fonts** (p.108): neutral sans / system stack; prefer typefaces with ≥5 weights; avoid condensed short-x-height for body.
- **Think outside the box** (p.242): selectable **cards** instead of radio rows; richer tables/dropdowns (sections, columns, icons, color).
- **Leveling up** (p.249): study designs for decisions you wouldn't have made; rebuild interfaces from scratch to learn the details.

---

## Appendix — SwiftUI translation cheatsheet

| Book (CSS) | SwiftUI / macOS |
|---|---|
| `box-shadow` | `.shadow(color:radius:x:y:)` or an `<elevation/shadow token>` modifier |
| two-part shadow | two stacked `.shadow` modifiers |
| `hsl()` | `Color(hue:saturation:brightness:)` (HSB) or `NSColor` per-appearance |
| `font-weight` | `Font.Weight` (`.regular/.medium/.semibold/.bold`) |
| `letter-spacing` | `.tracking()` / `.kerning()` |
| `line-height` | `.lineSpacing()` (additive, not multiplicative — convert) |
| line length (ch/em) | text container `.frame(maxWidth:)` tuned to ~45–75 chars at the body size |
| `text-align` | `.multilineTextAlignment()` |
| `border` / `border-radius` | `.overlay(RoundedRectangle…strokeBorder)` / `.clipShape`/`cornerRadius` |
| `background-color` delta for separation | distinct `<surface token>` layer or `.background` token |
| `em` type units | N/A — SwiftUI uses points; keep a fixed type scale |