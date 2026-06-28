---
name: ios-design-spec-contract
description: Pin a web/JS design prototype down hard enough that a coding agent reproduces it in SwiftUI at near-100% fidelity instead of approximating it. Produces a FOUR-layer contract — Tokens (single source of truth) + DESIGN.md (token contract + rationale + material/motion extensions) + reference components (the canonical material implementation) + a JS→SwiftUI platform mapping (the cross-paradigm translation table) — plus an implementation + verification loop. Use when handing a web/React/HTML prototype to a coding agent that will build the native iOS app, when starting an iOS design system, or when auditing why generated SwiftUI drifts from the prototype. Optimized for material-heavy, iOS-native identities (Liquid Glass, dynamic gradients, sheets, springs).
user-invocable: true
---

# Design → SwiftUI Spec Contract

A method for capturing a web/JS design prototype tightly enough that a coding agent rebuilds it in **native SwiftUI** — not a lookalike. It extends the standard three-layer design contract with a fourth layer that the web→iOS path specifically needs: a **paradigm-translation map**.

> **Sibling skill — FLOW.md (flow-navigation-contract).** This skill owns the **appearance** axis: does each screen *look* right (tokens, material, motion, states). It does NOT verify that every screen *exists* and every tappable entry *reaches a finished one* — that reachability/completeness axis is FLOW.md's job. Run both; they compose. The seam: FLOW says "node `today.ai_finding` must exist and be non-stub"; this skill then says "and it must render its prop-signature states (4c) + empty-state branches (4e)." Keep per-screen state-completeness HERE — FLOW points back at 4c/4e rather than re-auditing states. Both ship through the **handoff-manifest** skill, which appends a Build Contract to the target repo's CLAUDE.md.

## The core insight (and the one this adds)

Flat design tokens (color, type, spacing, radius) lock the **easy 20%** of an identity. They cannot express the **80% that drifts**: material (blur stacks, refraction, layered translucency), motion (springs, easings, durations), composition (sheets, depth-through-overlap), and theming logic.

A token file or a prose style guide alone always leaves the identity-defining parts to interpretation — and interpretation is where deviation lives.

**For web→iOS there is a second, compounding deviation source:** the source of truth is JS/CSS/JSX, but the target is SwiftUI. An agent handed only tokens + prose will **transliterate the JSX literally** — re-deriving a glass surface from `backdrop-filter`, hand-rolling flex with `GeometryReader`, drawing charts with `Path` — producing valid-but-non-idiomatic SwiftUI that looks wrong and is unmaintainable. Worse, prototypes are full of **browser-only hacks** written purely to fake native behavior; transliterated faithfully, they fight the platform.

The fix is four layers, each owning what it is good at, with exactly one source of truth per value, and an explicit "this JS concept becomes this SwiftUI concept — and these hacks become nothing."

## The four layers

```
1. TOKENS            ← single source of truth for every atomic value
   (tokens.css  +  mirrored Tokens.swift / asset catalog)
        │  mirrored + explained by
        ▼
2. DESIGN.md         ← token contract + rationale + material/motion extensions
        │  read by the agent to implement
        ▼
3. REFERENCE CODE    ← the canonical material implementation (real components)
        │  translated via
        ▼
4. PLATFORM MAPPING  ← JS/CSS/React → SwiftUI concept table + "DO NOT PORT" list
   (a section inside DESIGN.md)
```

| Layer | Owns | Format |
|---|---|---|
| **Tokens** | Every atomic value, stored once | `tokens.css` (`--*` vars) + a mirrored `Tokens.swift` / asset catalog |
| **DESIGN.md** | Structured mirror of tokens + the why/how/don't + material & motion the standard schema can't hold | One `DESIGN.md` file |
| **Reference components** | Exact material recipes as working code an agent copies, each annotated with its SwiftUI equivalent | `.jsx` / `.html` / SwiftUI views — cosmetic-only, no business logic |
| **Platform mapping** | The JS→SwiftUI paradigm table + the explicit DO-NOT-PORT list of prototype-only scaffolding | A `## Platform Mapping` section in DESIGN.md |

**Rule of thumb:** if a value can be a number or color, it lives in Tokens and DESIGN.md mirrors it. If it's a *recipe* (a multi-property material, an animation, a layout), it lives in reference code and DESIGN.md points at it. If it's a *paradigm* (state, navigation, layout primitive, a faked-native behavior), it lives in the Platform Mapping.

---

## Step 1 — Tokens: one value, one home

- Pick a single canonical store and never duplicate a value out of it. On web that's CSS custom properties; mirror them into Swift constants / an asset catalog for the native build.
- The most common deviation source is a component that **re-types token values inline** (a local theme object copying hex codes, a readiness gradient written out in three files). Audit for this first and collapse it. Implementations must consume `var(--token)` / `Color.token`, never a hand-copied literal.
- Keep tokens atomic: a color is a color, a radius is a radius. Do not encode composites (a full glass surface) as a token — those are recipes (Step 3).
- Tokens that drive **state-dependent theming** (e.g. a readiness/mood state that swaps accent + background) are still atomic — store the per-state values, and let the mapping/recipe describe how state selects among them.

## Step 2 — DESIGN.md: the contract layer

Author it in a `@google/design.md`-style format — YAML front matter for machine-readable tokens, markdown body for rationale. It **mirrors** the token store (never invents values) and adds the "why".

Standard `components` schema only holds `backgroundColor / textColor / typography / rounded / padding / size / height / width`. That is not enough for a material-heavy iOS identity. The format preserves unknown top-level keys, so add custom blocks — they travel as structured agent context even though they aren't validated:

```yaml
materials:
  glass-regular:
    web: "backdrop-filter: blur(30px) saturate(180%)"   # what the prototype fakes
    swift: ".glassEffect(.regular, in: .rect(cornerRadius: {rounded.lg}))"  # iOS 26+ native
    tint: "rgba(255,255,255,0.62)"
    edge: "inset 0 1px 0 rgba(255,255,255,0.45)"          # refraction highlight — NATIVE provides this; do not hand-draw
    note: "Wrap adjacent glass cards in GlassEffectContainer to merge refraction."
motion:
  ease-sheet:  { web: "cubic-bezier(0.32,0.72,0,1)", swift: ".spring(response:0.42, dampingFraction:0.82)" }
  ease-tap:    { web: "cubic-bezier(0.4,0,0.2,1)",   swift: ".easeInOut(duration:0.25)" }
  press:       "scale(0.96) opacity(0.7) in 100ms"
```

Document the body sections in this order so `lint`/`diff` (if used) don't flag drift:
`## Overview · ## Colors · ## Typography · ## Layout · ## Elevation & Depth · ## Shapes · ## Materials & Motion · ## Components · ## Platform Mapping · ## Do's and Don'ts`.

**Motion tokens are the source of axis-1 curve checks.** The `motion:` block declares the canonical easing curves (web cubic-bezier → SwiftUI `.spring` / `.easeInOut`) and the timing shape of each interaction. Downstream parity checks — including the cross-project `design-parity-build` skill — read these tokens as the single source of truth for what "matches" means on motion: an implementation that uses a different curve (e.g. a plain `.linear` or a different spring `response/dampingFraction`) is an axis-1 regression even if the visual end-state looks right. Always emit motion tokens, even for prototypes with no animation; silence there means reviewers have nothing to compare against and accept whatever the coder produces.

**Native exceptions** — components the system provides and the prototype only fakes. List them in a `## Native Exceptions` block in DESIGN.md, with the canonical list anchored to `apple-dev/references/design-contract-schema.md` §6 (Tab Bar / SF Symbols / system keyboard / system sheet / safe-area / standard platform controls). These components are **screen-captured but excluded from axis-1 design diff** — they render via the OS, so comparing pixel-by-pixel against the prototype is meaningless. Augment or trim the list per project (e.g. a project that builds a custom keyboard adds it back into the diff set); the baseline list is a default, not a fixed contract. The downstream checker (e.g. `design-parity-build`) reads this list to know what to skip.

**Optional tooling (skip for solo / one-shot handoffs):** the design.md CLI's `lint` (broken refs, WCAG AA, section order), `diff` (token regressions), and `export` (emit tokens into the build) are worth wiring into **CI for a multi-person, long-lived system**. For a single designer handing a prototype to one coding agent once, they are overhead — and contrast lint misfires on dynamic gradient backgrounds. Keep the machine-readable front matter (agents parse it well); drop the CI gate unless the project's lifespan justifies it.

## Step 3 — Reference components: code is the least-ambiguous spec

For anything that's a recipe rather than a value, ship a **working, cosmetic-only component** and make the contract say "copy this." A correct implementation an agent can clone beats any prose description.

- Keep them business-logic-free so they port cleanly.
- One component per recurring material/composition: the glass surface, the segmented control, the sheet, the center modal, the window/device chrome.
- DESIGN.md names them and points to them; it does not re-describe their CSS.
- **Annotate each canonical component's header** with its native equivalent and a port instruction. This is the bridge to Layer 4:

```jsx
// CANONICAL. SwiftUI: .glassEffect(.regular, in: .rect(cornerRadius: 22)).
// DO NOT port the manual blur/saturate/edge-highlight hack below — it only exists to
// fake Liquid Glass in a browser. Native glassEffect provides blur, tint, and refraction.
```

A component without this header is ambiguous: the agent can't tell a real recipe from a browser workaround.

## Step 4 — Platform mapping: translate paradigms, not syntax

This is the layer the web→iOS path needs and the standard three-layer contract lacks. It lives as a `## Platform Mapping` section in DESIGN.md and has five parts.

**Anchor the target OS first.** Declare a single minimum OS for the project (e.g. `targetOS: iOS 26` in DESIGN.md front matter). The mapping then commits to the **newest native primitive at that floor** with NO fallback hedging — `glassEffect` instead of a faked blur, `MeshGradient` instead of layered radial gradients. Fallbacks are dead weight and an invitation to drift; only add one if the floor is genuinely below a primitive you need. When the floor is a hard constraint, say so in the mapping cell ("`.glassEffect` — required, iOS 26 floor") so the agent never reaches for a legacy approximation.

### 4a. Material / visual mapping
Every CSS visual idiom → its idiomatic SwiftUI form. Examples (tailor per project):

| Web / CSS | SwiftUI (idiomatic) |
|---|---|
| `backdrop-filter: blur() saturate()` glass | `.glassEffect(...)` (iOS 26+) — native, don't re-derive |
| `linear-gradient` / blob backgrounds | `MeshGradient` (iOS 18+) or `LinearGradient`, switched by state |
| `font-variant-numeric: tabular-nums` | `.monospacedDigit()` |
| `letter-spacing: -0.03em` | `.tracking(pt)` — **convert em→points, don't paste the em value** |
| `line-height: 0.95` on display type | No direct API — needs `lineHeightMultiple` via `AttributedString`/`UIFont`. **Flag as a known gap.** |
| `font-weight: 800` | `.fontWeight(.heavy)` (800≈heavy, 900=black) |
| color-based text hierarchy `rgba(0,0,0,0.65)` | `.foregroundStyle(Color(white:0, opacity:0.65))` — preserve "color, not view-opacity, makes hierarchy" |
| charts (Spark / bars / lines) | **Swift Charts** — never `Path` by hand |

### 4b. Structure / state mapping
The React→SwiftUI paradigm shifts the agent gets most wrong:

| React paradigm | SwiftUI |
|---|---|
| `useState` | `@State` |
| Context provider (theme/state/nav) | `@Environment` + an `@Observable` model — not prop drilling |
| client router `go(route)` | `NavigationStack(path:)` |
| flex / grid + `gap` | `HStack`/`VStack`/`Grid` with `spacing:` — **not `GeometryReader` math** |
| `position: fixed` overlay | `ZStack` / `.overlay` / `.safeAreaInset` |
| bottom sheet | `.sheet` + `.presentationDetents` |
| center modal (scale-in) | `ZStack` overlay + `.transition(.scale.combined(with:.opacity))` |
| interstitial / processing screen | full-screen `View` — editorial line + step list (not a bare spinner) |
| handoff / "sent" confirmation | a dedicated transition `View`, not an alert |
| **reverse flow (recall / undo / un-send)** | an **acknowledged transient state** ("recalling → recalled", ~1200ms) before clearing — never snap straight back. **Respect platform red lines:** recall a *planned / already-sent* item; never delete the user's completed record (e.g. a HealthKit workout) |

### 4c. Tweaks & variation controls — classify, don't just delete
A prototype's tweaks/variations panel looks like dev chrome, but each control encodes one of three very different things. **Deleting the panel is right; deleting what it enumerates can drop half the spec.** Classify every tweak:

| Tweak kind | What it is | What to do |
|---|---|---|
| **Design-exploration** | option A vs B not yet decided (font, layout variant, accent) | resolve to the chosen value → it becomes a token/default; **delete the control** |
| **State demonstrator** | a way to preview runtime conditions the app computes — readiness levels, empty vs populated data, loading/lifecycle states | the control is scaffolding, but its **value set is a hard spec: build EVERY branch.** The trigger in production is real data/state, not a toggle |
| **Real product setting** | a value the user genuinely controls — theme, language, a tone/frequency preference | maps to a **real Settings control** + a documented behavior mapping (value → what changes) |

For every tweak, write a row: *control → kind → for state-demonstrators, the full value set and the real trigger; for settings, the native control and the behavior it drives.* This converts a throwaway dev panel into the **conditional-UI checklist** and **settings spec** the engineer would otherwise reconstruct by guessing.

**The authoritative state set is each component's prop signature — not only the panel.** A tweaks panel demonstrates *some* states; the props enumerate *all* of them, including ones no control exposes. Read every component's signature and treat it as the branch list: each boolean/enum prop (`hasFinding`, `building`, `rest`, `phase`, `planState`, `loadData`) is a runtime branch to build; each `onX` callback (`onRecall`, `onSetGoal`, `onOpenTomorrow`) usually implies an **action-triggered UI, transition, or reverse-flow** the default render never shows — open its implementation to see what it triggers. The spec is the **union** of: prop signatures + the tweaks panel (4c) + the empty-state audit (4e). A screenshot shows one state; the signature names them all.

### 4d. The DO-NOT-PORT list
Name the prototype-only scaffolding explicitly so the agent deletes rather than translates it:
- the design canvas / pan-zoom host
- the tweaks/variations **panel UI** and its persistence (but first run 4c on what it enumerates)
- the device-bezel frame and faked status bar
- any `backdrop-filter` / box-shadow stack that exists only to fake a native material
- mock-data fixtures and dev route pickers (keep their SHAPES as the model contract)

> A prototype is a **specification of appearance and behavior**, not a codebase to transpile. The mapping tells the agent which lines are spec and which are scaffolding — and 4c keeps the scaffolding from hiding real spec.

### 4e. Empty & zero-data states — the absence the prototype won't show you

4c captures the states the prototype *demonstrates*. The most-missed states are the ones it **doesn't**: prototypes habitually render every card with mock data and never build the new-user / zero-data / device-missing variants. Those states are an **absence**, not a control — a tweaks-panel scan (4c) misses them entirely, and a screenshot has nothing to show. Yet "what this surface does with no data" is core spec, and it's where generated apps look most broken (charts of nothing, `—` skeletons, placeholders that lie).

So enumerate them explicitly, per surface, even when the prototype renders none of them. For every data-bearing surface specify its behavior under:
- **new user / zero data** — no goal, no history, 0 records
- **device / permission missing** — no Apple Watch, HealthKit not authorized
- **insufficient sample** — data still accumulating (N/M; not enough for a trend or baseline)
- **lifecycle empty** — rest day, nothing scheduled, not-yet-generated

Three treatments — pick per surface, don't default to "an empty card":
1. **zero data → one Tab-level full-page empty state** (a CTA-driven editorial screen: "set a goal", "run a few times and this grows"). NOT N individually-empty cards.
2. **accumulating → in-card micro-state** ("N/14 days · building") that keeps the card skeleton.
3. **device / permission missing → in-card prompt** ("Connect Apple Watch / needs a compatible device").

**Prefer hiding over faking.** A surface with nothing to say should collapse to zero height (like an idle sync badge), not show a placeholder — data is an input, not a page. Hide the coach-finding pill when there's no finding; drop the "yesterday" card on a rest day.

Ship this as a **first-class artifact**, the same way you ship reference components: an **Empty-State Audit** table — *surface · with-data render · empty scenario (what's missing) · treatment · do / simplify / skip*. It is the conditional-UI checklist for the absence the prototype hides; without it, the engineer ships only the happy path.

---

## Implementation loop (for the agent consuming the contract)

0. Note the project's **target OS floor** (front matter) — it decides which native primitives are fair game.

1. Read DESIGN.md front-to-back, including `materials`/`motion` extensions, the **Platform Mapping**, and Do's/Don'ts.
2. Pull atomic values via `Color.token` / `Tokens.swift` — never paste literals from the prototype.
3. For any material/motion/composition, open the named reference component, read its `// CANONICAL` header, and use the **SwiftUI equivalent it points to** — do not transliterate the browser hack.
4. Apply Platform Mapping for every state/navigation/layout construct — idiomatic SwiftUI, not a JSX clone. For tweaks, follow 4c: build every branch of a state-demonstrator; wire real settings to native controls. Enumerate each component's states from its **prop signature** (bool/enum props = branches; `onX` = transitions / reverse-flows), and build the **empty / zero-data / device-missing** branches from the empty-state audit (4e) — including states the prototype never rendered. After translating a component, count: its signature has N state-bearing params — did you build N branches?
5. Skip everything on the DO-NOT-PORT list.
6. Verify visually against the **running reference components**, not against memory or the JSX source — **and verify each surface in its empty / zero-data / device-missing state too.** The prototype likely never rendered these, so construct them from the empty-state audit (4e) rather than screenshot-matching a frame that doesn't exist.

## Do's and Don'ts

- **Do** keep one source of truth per value — collapse duplicated literals first; for web→iOS, mirror (don't re-author) tokens into Swift.
- **Do** put recipes (glass, animation, layout) in code and *point* at them; annotate each with its native equivalent.
- **Do** write the Platform Mapping as concepts (state→`@State`, flex→`HStack`), and keep an explicit DO-NOT-PORT list of prototype scaffolding.
- **Do** map to the newest native primitive available for the target OS (e.g. `glassEffect`, `MeshGradient`) instead of legacy fakes. **Anchor a single minimum OS up front** and, when it's a hard floor, drop fallbacks entirely — they only invite drift.
- **Do** classify every prototype tweak (design-exploration / state-demonstrator / real setting) before deleting the panel — a state-demonstrator's value set is a hard "build every branch" spec, not chrome.
- **Do** enumerate a component's states from its **prop signature** (bool/enum props = branches, `onX` callbacks = action-triggered transitions / reverse-flows), not only from the tweaks panel — the signature names states no control exposes.
- **Do** audit every data-bearing surface for its **empty / zero-data / device-missing** state even though the prototype renders mock data everywhere and never builds them — ship an **Empty-State Audit** table (4e), prefer hiding over faking, and use one Tab-level full-page empty state rather than N individually-empty cards.
- **Do** flag any idiom with no native equivalent as an explicit **known gap** in the mapping (e.g. CSS `line-height < 1` has no direct SwiftUI API) rather than letting the agent silently approximate it.
- **Don't** treat DESIGN.md as a complete spec alone — without reference components AND the platform mapping, material-heavy web→iOS designs still drift.
- **Don't** let DESIGN.md invent values the token store lacks; it mirrors, it doesn't author.
- **Don't** over-tokenize — a composite surface is a recipe, not a token.
- **Don't** transliterate the prototype. Browser hacks and scaffolding are not the design.
- **Don't** wire CLI lint/diff/CI for a solo, one-shot handoff — keep the structured front matter, drop the gate.
