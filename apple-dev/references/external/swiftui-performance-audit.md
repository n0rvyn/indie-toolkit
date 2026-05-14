
> **Guide Skill** — This is an expert workflow/pattern guide, not API reference documentation.
> Originally from [Dimillian/Skills](https://github.com/Dimillian/Skills) by Thomas Ricouard. MIT License.


# SwiftUI Performance Audit

## Quick start

Use this skill to diagnose SwiftUI performance issues from code first, then request profiling evidence when code review alone cannot explain the symptoms.

## Workflow

1. Classify the symptom: slow rendering, janky scrolling, high CPU, memory growth, hangs, or excessive view updates.
2. If code is available, start with a code-first review using `references/code-smells.md`.
3. If code is not available, ask for the smallest useful slice: target view, data flow, reproduction steps, and deployment target.
4. If code review is inconclusive or runtime evidence is required, guide the user through profiling with `references/profiling-intake.md`.
5. Summarize likely causes, evidence, remediation, and validation steps using `references/report-template.md`.

## 1. Intake

Collect:
- Target view or feature code.
- Symptoms and exact reproduction steps.
- Data flow: `@State`, `@Binding`, environment dependencies, and observable models.
- Whether the issue shows up on device or simulator, and whether it was observed in Debug or Release.

Ask the user to classify the issue if possible:
- CPU spike or battery drain
- Janky scrolling or dropped frames
- High memory or image pressure
- Hangs or unresponsive interactions
- Excessive or unexpectedly broad view updates

For the full profiling intake checklist, read `references/profiling-intake.md`.

## 2. Code-First Review

Focus on:
- Invalidation storms from broad observation or environment reads.
- Unstable identity in lists and `ForEach`.
- Heavy derived work in `body` or view builders.
- Layout thrash from complex hierarchies, `GeometryReader`, or preference chains.
- Large image decode or resize work on the main thread.
- Animation or transition work applied too broadly.

Use `references/code-smells.md` for the detailed smell catalog and fix guidance.

Provide:
- Likely root causes with code references.
- Suggested fixes and refactors.
- If needed, a minimal repro or instrumentation suggestion.

## 3. Guide the User to Profile

If code review does not explain the issue, ask for runtime evidence:
- A trace export or screenshots of the SwiftUI timeline and Time Profiler call tree.
- Device/OS/build configuration.
- The exact interaction being profiled.
- Before/after metrics if the user is comparing a change.

Use `references/profiling-intake.md` for the exact checklist and collection steps.

## 4. Analyze and Diagnose

- Map the evidence to the most likely category: invalidation, identity churn, layout thrash, main-thread work, image cost, or animation cost.
- Prioritize problems by impact, not by how easy they are to explain.
- Distinguish code-level suspicion from trace-backed evidence.
- Call out when profiling is still insufficient and what additional evidence would reduce uncertainty.

## 5. Remediate

Apply targeted fixes:
- Narrow state scope and reduce broad observation fan-out.
- Stabilize identities for `ForEach` and lists.
- Move heavy work out of `body` into derived state updated from inputs, model-layer precomputation, memoized helpers, or background preprocessing. Use `@State` only for view-owned state, not as an ad hoc cache for arbitrary computation.
- Use `equatable()` only when equality is cheaper than recomputing the subtree and the inputs are truly value-semantic.
- Downsample images before rendering.
- Reduce layout complexity or use fixed sizing where possible.

Use `references/code-smells.md` for examples, Observation-specific fan-out guidance, and remediation patterns.

## 6. Verify

Ask the user to re-run the same capture and compare with baseline metrics.
Summarize the delta (CPU, frame drops, memory peak) if provided.

## Outputs

Provide:
- A short metrics table (before/after if available).
- Top issues (ordered by impact).
- Proposed fixes with estimated effort.

Use `references/report-template.md` when formatting the final audit.

## References

- Profiling intake and collection checklist: `references/profiling-intake.md`
- Common code smells and remediation patterns: `references/code-smells.md`
- Audit output template: `references/report-template.md`
- Add Apple documentation and WWDC resources under `references/` as they are supplied by the user.
- Optimizing SwiftUI performance with Instruments: `references/optimizing-swiftui-performance-instruments.md`
- Understanding and improving SwiftUI performance: `references/understanding-improving-swiftui-performance.md`
- Understanding hangs in your app: `references/understanding-hangs-in-your-app.md`
- Demystify SwiftUI performance (WWDC23): `references/demystify-swiftui-performance-wwdc23.md`

## Reference materials (from upstream references/)

### code-smells

# Common code smells and remediation patterns

## Intent

Use this reference during code-first review to map visible SwiftUI patterns to likely runtime costs and safer remediation guidance.

## High-priority smells

### Expensive formatters in `body`

```swift
var body: some View {
    let number = NumberFormatter()
    let measure = MeasurementFormatter()
    Text(measure.string(from: .init(value: meters, unit: .meters)))
}
```

Prefer cached formatters in a model or dedicated helper:

```swift
final class DistanceFormatter {
    static let shared = DistanceFormatter()
    let number = NumberFormatter()
    let measure = MeasurementFormatter()
}
```

### Heavy computed properties

```swift
var filtered: [Item] {
    items.filter { $0.isEnabled }
}
```

Prefer deriving this once per meaningful input change in a model/helper, or store derived view-owned state only when the view truly owns the transformation lifecycle.

### Sorting or filtering inside `body`

```swift
List {
    ForEach(items.sorted(by: sortRule)) { item in
        Row(item)
    }
}
```

Prefer sorting before render work begins:

```swift
let sortedItems = items.sorted(by: sortRule)
```

### Inline filtering inside `ForEach`

```swift
ForEach(items.filter { $0.isEnabled }) { item in
    Row(item)
}
```

Prefer a prefiltered collection with stable identity.

### Unstable identity

```swift
ForEach(items, id: \.self) { item in
    Row(item)
}
```

Avoid `id: \.self` for non-stable values or collections that reorder. Use a stable domain identifier.

### Top-level conditional view swapping

```swift
var content: some View {
    if isEditing {
        editingView
    } else {
        readOnlyView
    }
}
```

Prefer one stable base view and localize conditions to sections or modifiers. This reduces root identity churn and makes diffing cheaper.

### Image decoding on the main thread

```swift
Image(uiImage: UIImage(data: data)!)
```

Prefer decode and downsample work off the main thread, then store the processed image.

## Observation fan-out

### Broad `@Observable` reads on iOS 17+

```swift
@Observable final class Model {
    var items: [Item] = []
}

var body: some View {
    Row(isFavorite: model.items.contains(item))
}
```

If many views read the same broad collection or root model, small changes can fan out into wide invalidation. Prefer narrower derived inputs, smaller observable surfaces, or per-item state closer to the leaf views.

### Broad `ObservableObject` reads on iOS 16 and earlier

```swift
final class Model: ObservableObject {
    @Published var items: [Item] = []
}
```

The same warning applies to legacy observation. Avoid having many descendants observe a large shared object when they only need one derived field.

## Remediation notes

### `@State` is not a generic cache

Use `@State` for view-owned state and derived values that intentionally belong to the view lifecycle. Do not move arbitrary expensive computation into `@State` unless you also define when and why it updates.

Better alternatives:
- precompute in the model or store
- update derived state in response to a specific input change
- memoize in a dedicated helper
- preprocess on a background task before rendering

### `equatable()` is conditional guidance

Use `equatable()` only when:
- equality is cheaper than recomputing the subtree, and
- the view inputs are value-semantic and stable enough for meaningful equality checks

Do not apply `equatable()` as a blanket fix for all redraws.

## Triage order

When multiple smells appear together, prioritize in this order:
1. Broad invalidation and observation fan-out
2. Unstable identity and list churn
3. Main-thread work during render
4. Image decode or resize cost
5. Layout and animation complexity

### demystify-swiftui-performance-wwdc23

# Demystify SwiftUI Performance (WWDC23) (Summary)

Context: WWDC23 session on building a mental model for SwiftUI performance and triaging hangs/hitches.

## Performance loop

- Measure -> Identify -> Optimize -> Re-measure.
- Focus on concrete symptoms (slow navigation, broken animations, spinning cursor).

## Dependencies and updates

- Views form a dependency graph; dynamic properties are a frequent source of updates.
- Use `Self._printChanges()` in debug only to inspect extra dependencies.
- Eliminate unnecessary dependencies by extracting views or narrowing state.
- Consider `@Observable` for more granular property tracking.

## Common causes of slow updates

- Expensive view bodies (string interpolation, filtering, formatting).
- Dynamic property instantiation and state initialization in `body`.
- Slow identity resolution in lists/tables.
- Hidden work: bundle lookups, heap allocations, repeated string construction.

## Avoid slow initialization in view bodies

- Don’t create heavy models synchronously in view bodies.
- Use `.task` to fetch async data and keep `init` lightweight.

## Lists and tables identity rules

- Stable identity is critical for performance and animation.
- Ensure a constant number of views per element in `ForEach`.
- Avoid inline filtering in `ForEach`; pre-filter and cache collections.
- Avoid `AnyView` in list rows; it hides identity and increases cost.
- Flatten nested `ForEach` when possible to reduce overhead.

## Table specifics

- `TableRow` resolves to a single row; row count must be constant.
- Prefer the streamlined `Table` initializer to enforce constant rows.
- Use explicit IDs for back deployment when needed.

## Debugging aids

- Use Instruments for hangs and hitches.
- Use `_printChanges` to validate dependency assumptions during debug.

### optimizing-swiftui-performance-instruments

# Optimizing SwiftUI Performance with Instruments (Summary)

Context: WWDC session introducing the next-generation SwiftUI Instrument in Instruments 26 and how to diagnose SwiftUI-specific bottlenecks.

## Key takeaways

- Profile SwiftUI issues with the SwiftUI template (SwiftUI instrument + Time Profiler + Hangs/Hitches).
- Long view body updates are a common bottleneck; use "Long View Body Updates" to identify slow bodies.
- Set inspection range on a long update and correlate with Time Profiler to find expensive frames.
- Keep work out of `body`: move formatting, sorting, image decoding, and other expensive work into cached or precomputed paths.
- Use Cause & Effect Graph to diagnose *why* updates occur; SwiftUI is declarative, so backtraces are often unhelpful.
- Avoid broad dependencies that trigger many updates (e.g., `@Observable` arrays or global environment reads).
- Prefer granular view models and scoped state so only the affected view updates.
- Environment values update checks still cost time; avoid placing fast-changing values (timers, geometry) in environment.
- Profile early and often during feature development to catch regressions.

## Suggested workflow (condensed)

1. Record a trace in Release mode using the SwiftUI template.
2. Inspect "Long View Body Updates" and "Other Long Updates."
3. Zoom into a long update, then inspect Time Profiler for hot frames.
4. Fix slow body work by moving heavy logic into precomputed/cache paths.
5. Use Cause & Effect Graph to identify unintended update fan-out.
6. Re-record and compare the update counts and hitch frequency.

## Example patterns from the session

- Caching formatted distance strings in a location manager instead of computing in `body`.
- Replacing a dependency on a global favorites array with per-item view models to reduce update fan-out.

### profiling-intake

# Profiling intake and collection checklist

## Intent

Use this checklist when code review alone cannot explain the SwiftUI performance issue and you need runtime evidence from the user.

## Ask for first

- Exact symptom: CPU spike, dropped frames, memory growth, hangs, or excessive view updates.
- Exact interaction: scrolling, typing, initial load, navigation push/pop, animation, sheet presentation, or background refresh.
- Target device and OS version.
- Whether the issue was reproduced on a real device or only in Simulator.
- Build configuration: Debug or Release.
- Whether the user already has a baseline or before/after comparison.

## Default profiling request

Ask the user to:
- Run the app in a Release build when possible.
- Use the SwiftUI Instruments template.
- Reproduce the exact problematic interaction only long enough to capture the issue.
- Capture the SwiftUI timeline and Time Profiler together.
- Export the trace or provide screenshots of the key SwiftUI lanes and the Time Profiler call tree.

## Ask for these artifacts

- Trace export or screenshots of the relevant SwiftUI lanes
- Time Profiler call tree screenshot or export
- Device/OS/build configuration
- A short note describing what action was happening at the time of the capture
- If memory is involved, the memory graph or Allocations data if available

## When to ask for more

- Ask for a second capture if the first run mixes multiple interactions.
- Ask for a before/after pair if the user has already tried a fix.
- Ask for a device capture if the issue only appears in Simulator or if scrolling smoothness matters.

## Common traps

- Debug builds can distort SwiftUI timing and allocation behavior.
- Simulator traces can miss device-only rendering or memory issues.
- Mixed interactions in one capture make attribution harder.
- Screenshots without the reproduction note are much harder to interpret.

### report-template

# Audit output template

## Intent

Use this structure when reporting SwiftUI performance findings so the user can quickly see the symptom, evidence, likely cause, and next validation step.

## Template

```markdown
## Summary

[One short paragraph on the most likely bottleneck and whether the conclusion is code-backed or trace-backed.]

## Findings

1. [Issue title]
   - Symptom: [what the user sees]
   - Likely cause: [root cause]
   - Evidence: [code reference or profiling evidence]
   - Fix: [specific change]
   - Validation: [what to measure after the fix]

2. [Issue title]
   - Symptom: ...
   - Likely cause: ...
   - Evidence: ...
   - Fix: ...
   - Validation: ...

## Metrics

| Metric | Before | After | Notes |
| --- | --- | --- | --- |
| CPU | [value] | [value] | [note] |
| Frame drops / hitching | [value] | [value] | [note] |
| Memory peak | [value] | [value] | [note] |

## Next step

[One concrete next action: apply a fix, capture a better trace, or validate on device.]
```

## Notes

- Order findings by impact, not by file order.
- Say explicitly when a conclusion is still a hypothesis.
- If no metrics are available, omit the table and say what should be measured next.

### understanding-hangs-in-your-app

# Understanding Hangs in Your App (Summary)

Context: Apple guidance on identifying hangs caused by long-running main-thread work and understanding the main run loop.

## Key concepts

- A hang is a noticeable delay in a discrete interaction (typically >100 ms).
- Hangs almost always come from long-running work on the main thread.
- The main run loop processes UI events, timers, and main-queue work sequentially.

## Main-thread work stages

- Event delivery to the correct view/handler.
- Your code: state updates, data fetch, UI changes.
- Core Animation commit to the render server.

## Why the main run loop matters

- Only the main thread can update UI safely.
- The run loop is the foundation that executes main-queue work.
- If the run loop is busy, it can’t handle new events; this causes hangs.

## Diagnosing hangs

- Observe the main run loop’s busy periods: healthy loops sleep most of the time.
- Hang detection typically flags busy periods >250 ms.
- The Hangs instrument can be configured to lower thresholds.

## Practical takeaways

- Keep main-thread work short; offload heavy work from event handlers.
- Avoid long-running tasks on the main dispatch queue or main actor.
- Use run loop behavior as a proxy for user-perceived responsiveness.

### understanding-improving-swiftui-performance

# Understanding and Improving SwiftUI Performance (Summary)

Context: Apple guidance on diagnosing SwiftUI performance with Instruments and applying design patterns to reduce long or frequent updates.

## Core concepts

- SwiftUI is declarative; view updates are driven by state, environment, and observable data dependencies.
- View bodies must compute quickly to meet frame deadlines; slow or frequent updates lead to hitches.
- Instruments is the primary tool to find long-running updates and excessive update frequency.

## Instruments workflow

1. Profile via Product > Profile.
2. Choose the SwiftUI template and record.
3. Exercise the target interaction.
4. Stop recording and inspect the SwiftUI track + Time Profiler.

## SwiftUI timeline lanes

- Update Groups: overview of time SwiftUI spends calculating updates.
- Long View Body Updates: orange >500us, red >1000us.
- Long Platform View Updates: AppKit/UIKit hosting in SwiftUI.
- Other Long Updates: geometry/text/layout and other SwiftUI work.
- Hitches: frame misses where UI wasn’t ready in time.

## Diagnose long view body updates

- Expand the SwiftUI track; inspect module-specific subtracks.
- Set Inspection Range and correlate with Time Profiler.
- Use call tree or flame graph to identify expensive frames.
- Repeat the update to gather enough samples for analysis.
- Filter to a specific update (Show Calls Made by `MySwiftUIView.body`).

## Diagnose frequent updates

- Use Update Groups to find long active groups without long updates.
- Set inspection range on the group and analyze update counts.
- Use Cause graph ("Show Causes") to see what triggers updates.
- Compare causes with expected data flow; prioritize the highest-frequency causes.

## Remediation patterns

- Move expensive work out of `body` and cache results.
- Use `Observable()` macro to scope dependencies to properties actually read.
- Avoid broad dependencies that fan out updates to many views.
- Reduce layout churn; isolate state-dependent subtrees from layout readers.
- Avoid storing closures that capture parent state; precompute child views.
- Gate frequent updates (e.g., geometry changes) by thresholds.

## Verification

- Re-record after changes to confirm reduced update counts and fewer hitches.

---
_Source: vabole/apple-skills v1.0.10 · `skills/guide-swiftui-performance-audit/` · MIT (c) 2026 Ilia Abolhasani · Vendored 2026-05-14._
