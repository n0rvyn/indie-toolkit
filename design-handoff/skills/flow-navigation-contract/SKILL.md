---
name: flow-md-navigation-contract
description: Catch dead entries and placeholder subviews before they ship. Produces FLOW.md — a navigation/structure contract that enumerates every screen (node) and every tappable entry that leads to one (edge) for a multi-tab app, plus a grep-able stub sentinel and a deterministic coverage count so "is it complete?" is answered by a script, not by an agent's say-so. The structural-side sibling to a DESIGN.md / spec-contract (which owns looks): DESIGN answers "does this screen look right?", FLOW answers "does this screen exist, what reaches it, is it done?". Emit FLOW.md FROM the prototype (the router IS the graph) — never hand-author it, never reverse-engineer it from the target code. Use when handing a prototype to a coding agent, or auditing why a built app has clickable things that go nowhere or open TODO placeholders.
user-invocable: true
---

# FLOW.md — Navigation & Completeness Contract

A method for guaranteeing that every clickable entry in a built app reaches a **real, finished** screen — not a dead tap, not a `Text("TODO")` placeholder. It is the **structural-side sibling** to a visual design contract (`DESIGN.md` / the spec-contract skill). They run on orthogonal axes and compose; neither replaces the other.

| | DESIGN.md / spec-contract | FLOW.md (this skill) |
|---|---|---|
| Axis | appearance / style | structure / reachability / completeness |
| Answers | does this screen look right? | does this screen exist, what reaches it, is it done? |
| Primitive | token / recipe / paradigm | node / edge / stub |
| Catches | wrong color, faked material, drift | dead entry, placeholder subview, missing screen |

## The core insight

The bug — "looks clickable but isn't" / "click it and there's only a placeholder" — comes from asking an agent to do an **open-ended search**: "go walk every view and confirm it's complete." Models have no termination judge for that. They walk a few paths, hit some finished screens, and declare victory — the maze problem. Right answer most of the time, wrong answer exactly where coverage matters.

FLOW.md rewrites that open search into a **closed checklist**: a finite, enumerable list of nodes, each ticked off deterministically. The value is the conversion from *generative traversal* to *checklist verification* — **not "drawing a map."** The map is just the enumeration that makes the checklist finite.

Three things that break a naive version of this — design around them:

1. **It's a directed graph, not N parallel trees.** Real apps have one subview reused by many entries (Settings reachable from Profile *and* a toolbar), cross-tab deep links, and modals/sheets/alerts that never enter the push stack. "Four trees per tab" double-counts shared screens and drops the cross-links. Model it as **stable-ID nodes, one node referenced by many edges.**
2. **"Clickable" is the wrong primitive — too wide and too narrow.** Too wide: a toggle, stepper, or text field is clickable but owes no subview; treat those as navigation and you generate a pile of false "incomplete" flags. Too narrow: the placeholder often hides not in a missing route but in a **missing state branch** of a screen that does exist (empty / loading / error). So FLOW classifies nodes by type, and **defers per-screen state-completeness to the spec-contract skill** (its prop-signature enumeration + empty-state audit). FLOW owns *between* screens; the spec-contract owns *inside* one.
3. **Topology is necessary, not sufficient.** "Does tapping X go somewhere?" passes a stub — it does go somewhere, to a `Text("TODO")`. A map of edges alone just moves the maze down one level. The completeness predicate has to be **a grep-able stub sentinel**, so "done" means "zero stubs left," judged by a script, not by the model.

## The seam with the spec-contract skill (keep them from overlapping)

- **FLOW owns inter-screen:** every screen node *exists* and is non-stub; every tappable entry *reaches* a real node; no dead ends; no cross-link dropped.
- **The spec-contract owns intra-screen:** when a node exists, it renders all its states (prop-signature branches + empty / zero-data / device-missing audit) and matches the visual identity.

FLOW says *"node `today.ai_finding` must exist and be non-stub."* The spec-contract then says *"and it must render teaser / headline / comparison for all four readiness states."* Do not re-audit per-screen states inside FLOW — point at the spec-contract for that. One concern, one home.

---

## Step 1 — Emit FLOW.md from the prototype; never hand-author it

This is the load-bearing move. **The prototype's router already *is* the navigation graph** — enumerating it by hand re-introduces the omission risk you're trying to kill (you'll forget a node), and reverse-engineering it from the target (Swift) code is circular: you'd be validating the implementation against itself.

Extract it mechanically from the design source:

- **Nodes** = the screen components the router can land on (the route table / screen registry).
- **Edges** = every navigation call site — in a `useNav()` / `go(route)` prototype, each `go('x')` is one edge; `present` (push / sheet / modal / fullscreen) comes from how it's invoked.
- **Leaves** = interactive elements that do *not* call `go` (toggles, steppers, inputs, in-place actions). List them explicitly so they're recorded as "owes no subview," not mistaken for dead ends.

Because extraction walks the actual source, it is **exhaustive by construction** — it cannot skip a node the way a human or a free-searching model can.

**Don't do the archaeology by hand each project — run the bundled extractor.** `flow-export.js` (beside this SKILL.md) is the deterministic 90%: run it from the design tool's `run_script` and it walks the router switch (`route === 'x'` / `route.startsWith('x:')` = the authoritative node source) + every `nav.go()` call site, then writes a `FLOW.md` **skeleton** + a dead-edge / unreached-node report. You annotate only the 10% a script can't know: per-node descriptions, `present` kind, and which stubs are *intentional*. Two extraction rules it encodes, learned the hard way:
- **Nodes come ONLY from the router switch** — never scrape a picker's `value:` list. A tweaks/settings picker enumerates *state values* (`light`, `recovery`, `ready`), not screens; scraping them inflates the node set with garbage.
- **"Unreached via `go()`" is a prompt, not a failure** — a node entered by a data flag (a post-run interstitial) or app-launch (onboarding) has no inbound `go()` and *should* be flagged for a human to confirm, not auto-passed.

If a project doesn't use the `useNav`/`go` convention, fall back to the manual procedure below — the skeleton just comes out thin, but the dead-edge check still runs.

**Self-check at export.** While emitting, flag any `go('x')` whose target has no screen component — that's a dead edge *in the prototype itself*, caught at design time. The FLOW.md you hand off is then **verified-complete intent**, not an aspiration. (In practice: add an export hook beside the prototype's other exports — e.g. the same place a Gaps-Tracker "export markdown" button lives — that walks the route table + `go()` sites and writes FLOW.md.)

> The runtime crawl everyone dreads on the target platform is nearly free on the design side: the prototype is the thing that already runs. Verify reachability *there*, hand over the result.

## Step 2 — The schema

Keep it a flat node/edge list with stable IDs. No graph DSL — a 4-tab app does not need formal graph theory.

```yaml
targetTabs: [today, plan, insights, me]

nodes:
  - id: today.root
    type: screen
    tab: today
    a11y: today_root          # accessibility identifier — the join key (Step 4)
    present: tab
    statesRef: spec-contract  # per-screen states defer to the spec-contract skill
    status: implemented       # implemented | stub | not-started
  - id: today.ai_finding
    type: screen
    a11y: today_ai_finding
    present: sheet            # push | sheet | modal | fullscreen
    status: stub             # ← what the coverage script counts

edges:
  - from: today.root
    via: prescription_card    # a11y id of the tappable entry
    to: today.ai_finding
    trigger: tap
  - from: me.root
    via: settings_row
    to: settings.root         # same node reachable from a toolbar elsewhere — one node, many edges
    trigger: tap

leaves:                       # clickable but owes NO subview — recorded so it's not a false dead-end
  - on: today.root
    control: readiness_toggle
    kind: action              # action (in-place) | input (field/stepper)
```

Node `type`: `screen` (owes a subview, gets a status) vs nothing else needs a type — actions/inputs live in `leaves`. `status` is the only field the script reads.

## Step 3 — The stub sentinel + deterministic coverage

Every not-yet-built screen carries one **unique, self-explanatory, grep-able** sentinel tied to its node id. No cryptic codenames — the string should read as exactly what it is:

```swift
// SwiftUI target:
struct AIFindingView: View {
  var body: some View {
    #warning("FLOW-STUB: today.ai_finding — not implemented")
    Text("TODO")
  }
}
```

`#warning` is the strongest form on iOS — Xcode lists every one at compile time, so the count is free and impossible to ignore. A plain comment (`// FLOW-STUB: <node-id>`) works anywhere and is grep-counted. Either way the rule is the same:

> **"Complete" = zero `FLOW-STUB` left.** The termination judge is `grep -c`, not the model's claim.

Coverage script (deterministic — script counts, model only fills):

```
parse FLOW.md            → N = screen nodes
grep -r "FLOW-STUB"      → Y stubs, with their node-ids
missing view files       → list nodes with no implementing view  (dead edges in the target)
report: "(N-Y)/N implemented · Y stubs: [ids] · D dead edges: [ids]"  → exit 1 if Y+D > 0
```

This mirrors the design.md CLI's lint/diff/exit-code shape, applied to the structural axis instead of the visual one. Wire it into CI for a long-lived project; run it by hand for a one-shot handoff.

## Step 4 — accessibility id as the single join key

Use each node's **accessibility identifier** as its FLOW.md `a11y` value, and use each edge's tappable entry's accessibility identifier as the edge's `via` value. These two fields are **the single join key** for every static and runtime check against the structural graph — one key serves both axes:
- **static** — cheap, grep the sentinel; can be fooled by a stub that compiles.
- **runtime (optional v2)** — an XCUITest crawler walks each node by its `a11y` id and walks each edge by its `via` id and asserts the destination renders **non-placeholder** content. Strict, but only worth building after v1 proves the static pass catches real placeholders.

Same key for both means you write the names once.

---

## Implementation loop (for the agent consuming FLOW.md)

1. Read FLOW.md. The `nodes` list is your **complete, finite checklist** — you are done when every screen node is `implemented`, not when you "feel" you've walked the app.
2. For each `screen` node, build the view and **delete its `FLOW-STUB` sentinel only when it's real** — never to silence the count.
3. For each `edge`, wire the entry (`via`) to navigate to `to` with the right `present` (push → `NavigationStack`, sheet → `.sheet`, modal → overlay+scale — see the spec-contract's Platform Mapping).
4. For each `leaf`, build the in-place action/input — do **not** route it to a screen; it owes no subview.
5. For each node's internal states, hand off to the **spec-contract skill** (prop-signature branches + empty-state audit). FLOW guarantees the screen exists; the spec-contract guarantees it's fully built inside.
6. Run the coverage script. `(N-Y)/N` must read `N/N`, dead edges `0`. If not, the listed ids are your remaining work — there is nothing to "decide is finished."

## Do's and Don'ts

- **Do** emit FLOW.md from the prototype's router (exhaustive by construction); self-check dead edges at export so the handoff is verified-complete intent.
- **Do** model it as a directed graph with stable node IDs — one shared screen is one node referenced by many edges, including cross-tab and sheet/modal edges outside the push stack.
- **Do** make "complete" a grep/`#warning` count, not a model claim — the termination judge lives in the script.
- **Do** record in-place controls (toggles, steppers, inputs) as `leaves` so they aren't flagged as dead ends.
- **Do** keep per-screen state-completeness in the spec-contract skill (prop signatures + empty-state audit); FLOW only owns existence + reachability.
- **Do** use the accessibility id as the single join key for static and (later) runtime checks.
- **Don't** hand-author the map or reverse-engineer it from the target code — the first re-opens the omission risk, the second is circular (implementation validating itself).
- **Don't** treat "clickable" as the primitive — it's too wide (actions/inputs owe nothing) and too narrow (placeholders hide in missing *states*, which are the spec-contract's job).
- **Don't** stop at topology — an edge that "goes somewhere" passes a stub; only the sentinel count proves done.
- **Don't** over-formalize. v1 for a 4-tab app = node table + edges + stub sentinel + grep count. Prove it catches placeholders before adding a runtime XCUITest crawler or a state matrix.
