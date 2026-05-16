# Deep Modules and Module-Evaluation Vocabulary

**Purpose**

This reference captures Ousterhout's deep-vs-shallow module distinction and Pocock's evaluation vocabulary (deletion test, seam-vs-adapter, locality, gray-box delegation). These concepts are injected into `next-increment`, `design-decision`, `write-plan`, and `write-dev-guide` as evaluation vocabulary — not as a mandate to refactor. The `.out-of-scope/improve-codebase-architecture-skill.md` archive explicitly directs this vocabulary into `next-increment` and `design-decision`; this doc is the shared vocabulary source.

---

## Why This Matters in 2026

AI coding agents are good at creating shallow modules: many small classes, many pass-through methods, each doing a thin slice of work. The cost is high because every reasoning trace must walk many hops to understand the code, and context windows inflate. Deep modules with simple interfaces collapse this cost — a caller sees one clean interface and the implementation handles complexity internally.

When evaluating increment candidates or design decisions, the question is not "how many files/classes does this add?" but "does this create deep, independently comprehensible modules, or does it add another shallow layer?"

---

## Declarative-UI Caveat

The deep-vs-shallow heuristic is designed for **imperative module boundaries** — back-end services, data layers, utility libraries. For **declarative UI** (SwiftUI Views, React components, Jetpack Compose), composing into many small Views/components is correct and idiomatic. The framework's design is already shallow-module-optimized at the View level.

In declarative-UI domains, **only apply the deletion test and locality lenses**. Do not flag a View tree as "shallow modules" because that is not the right abstraction primitive. The evaluation concern in UI is whether Views are colocated by feature (locality) and whether the architecture creates seams vs adapters at the state/data boundary.

---

## Concept 1: Deep vs Shallow Modules (Ousterhout)

From *A Philosophy of Software Design* (2nd ed., 2021), John Ousterhout.

A **deep module** provides powerful functionality behind a simple interface. The interface is much smaller than the implementation. Complexity is encapsulated.

A **shallow module** has an interface that is large relative to the functionality it provides. Every method is thin, and understanding the module requires reading all of it.

### Definition Table

| Property | Deep Module | Shallow Module |
|---|---|---|
| Interface size | Small relative to functionality | Large relative to functionality |
| Public methods | Few, general-purpose | Many, specific-purpose |
| Internal abstraction | Deep (complex logic hidden) | Shallow (logic scattered) |
| Change impact | Localized (interface contract stable) | Scattered (touch many call sites) |
| Cognitive load for caller | Low (one clean interface) | High (many small pieces) |

### Identification Checklist

- Count interface lines vs implementation lines. Deep: implementation >> interface. Shallow: similar or reversed.
- Number of public methods: if a class has 30+ public methods with no clear grouping, it's shallow.
- Abstraction depth: a deep module hides its complexity behind a few general-purpose methods. A shallow module exposes every internal decision as a method.
- Pass-through methods: a method that does nothing but delegate to another class is a smell — it adds interface surface without functionality.

### Examples

**Swift/SwiftUI (deep):**
```swift
// Deep: DataManager provides complex persistence behind one clean interface
class DataManager {
    func save(_ item: Item) async throws  // all complexity inside
    func fetch(id: UUID) async throws -> Item  // abstraction hides SQL, cache, sync
}
```

**TypeScript (shallow):**
```typescript
// Shallow: each utility is exported separately, callers must compose
export function validateEmail(s: string): boolean { return /.../.test(s); }
export function validatePhone(s: string): boolean { return /.../.test(s); }
export function validateZip(s: string): boolean { return /.../.test(s); }
```

**Python (deep):**
```python
# Deep: one DataFrameTransformer class hides all transformation complexity
class DataFrameTransformer:
    def transform(self, df: pd.DataFrame) -> pd.DataFrame:
        # handles missing values, type inference, feature engineering
```

---

## Concept 2: Deletion Test (Pocock)

**The question:** Would the codebase observably behave differently if this code did not exist?

If the answer is no — if deleting the code produces no change in observable behavior — the code is either:
- Dead code (never referenced)
- Over-abstracted (exists only to satisfy an architectural idea, not a real need)
- A shallow module (adds interface without functionality)

**How to apply the deletion test in `next-increment`:**

Before listing an increment candidate, apply the deletion test to its `what` field:
1. Temporarily remove the proposed change from the codebase mentally
2. Does the system behave differently from the user's perspective?
3. If no → the candidate fails the deletion test. Replace it with a candidate whose `what` describes observable behavior change.

**Deletion test in plan writing:**
Do not propose increments whose deletion test would pass on existing code. An increment that only restructures code without changing behavior is not delivering value — it is tech-debt work, which is valid but must be framed as such.

---

## Concept 3: Seam vs Adapter (Pocock)

A **seam** is a natural boundary where modules can be swapped without affecting each other. The interface is clean; the implementation behind it can change without callers knowing.

An **adapter** is an awkward bridge created to make incompatible parts work together. It exists only because two layers don't agree on a common interface. Adapters are tech-debt smells — they are often necessary but should be minimized and clearly labeled.

### Seam Examples

**Swift/SwiftUI (seam):**
```swift
protocol PersistenceLayer {
    func save(_ item: Item) async throws
    func fetch(id: UUID) async throws -> Item
}
// Can swap UserDefaultsStorage, CoreDataStorage, NetworkStorage
// Callers only know PersistenceLayer — seam is the protocol boundary
```

**TypeScript (seam):**
```typescript
interface Logger { log(msg: string): void }
// Can swap ConsoleLogger, FileLogger, RemoteLogger
// Consumers only know the Logger interface
```

### Adapter Examples (smell)

```swift
// Adapter: DTO converter exists only because API and domain disagree
struct APIModel { var id: String; var name: String; var _sortable: Bool }
struct DomainModel { var id: UUID; var name: String; var isSortable: Bool }
// Converter bridges the gap — a sign that the two models should agree
```

**How to use in `design-decision`:**
When evaluating two options, ask: does Option A create a natural seam (swappable boundary) or does it add an adapter (bridge that exists only because of disagreement)? Seams are preferred. Adapters are acceptable as temporary tech-debt but should be on a path toward elimination.

---

## Concept 4: Locality (Pocock)

**The principle:** Code that changes together should live together.

If editing feature X requires touching 7 files scattered across 4 directories, locality is weak. The feature is not cohesively organized.

**In phase boundary decisions (`write-dev-guide`):**
When proposing a phase, ask: does this phase touch the same module as another phase? If yes, consider whether the two phases should merge (locality — related changes belong together) or whether the module itself needs to be split along a seam (in which case, that seam creation becomes its own phase).

**In task boundary decisions (`write-plan`):**
A task that scatters related changes across many files has weak locality. A better task groups changes by the deep module they affect — one task, one module, coherent change.

**In declarative-UI (SwiftUI/React):**
Locality applies to Views: related Views (header, content, footer of the same screen) should live in the same file or adjacent files. Scattering a feature's Views across 5 different directories is a locality violation.

---

## Concept 5: Gray-Box Delegation (Ousterhout)

For non-critical modules with a simple interface, you can let the AI handle the implementation and review only the interface contract. This is "gray-box" because you trust the module's interface without fully auditing its internals.

**When to use:**
- Utility modules, formatters, simple data transformations
- Modules with clean, narrow interfaces (few parameters, clear return types)
- Non-critical paths (not finance, auth, security, or data integrity)

**When NOT to use:**
- Security-critical modules (auth, permission checks, encryption)
- Finance or data-integrity modules (loss of precision, rounding errors)
- Modules with complex internal invariants that the AI could violate

**Connection to deep modules:** The deeper the module (simple interface, complex internals), the safer the gray-box treatment. The interface contract is the review surface. The implementer (AI) fills in the internals.

**In `write-plan` task review hints:**
Gray-box delegation is appropriate for deep modules where the Task Contract specifies the interface. Do NOT gray-box a shallow module — it needs close review because its interface IS its behavior.

---

## How to Use the Vocabulary

| Concept | When to Use | Skill / Step | Declarative-UI Applicable |
|---|---|---|---|
| Deep vs shallow | Designing module boundaries | write-plan Step 1, write-dev-guide Phase Splitting | No (composition units are intentionally shallow) |
| Deletion test | Filtering increment candidates | next-increment Step 2 | Yes (does this View cause user-observable change?) |
| Seam vs adapter | Picking between design approaches | design-decision Step 3 | Yes (state binding seam vs prop-drilling adapter) |
| Locality | Phase boundary, task boundary | write-dev-guide Phase Splitting, write-plan task split | Yes (related Views in one file vs scattered) |
| Gray-box | Delegating implementation review | write-plan task review hint | Yes for View body; No for ViewModel/state logic |

---

## Anti-Patterns This Reference Exists to Prevent

- Splitting one cohesive task into 6 thin tasks because each touches a different file (weak locality — group by module, not by file)
- Comparing two design options without checking which creates a seam vs an adapter (the seam-adapter distinction often discriminates between options)
- Designing phases by feature area instead of by deep-module boundary (phases aligned with deep modules are independently reviewable)
- Applying deep-vs-shallow to declarative UI and incorrectly flagging a View tree as "shallow modules" (the UI framework is already designed this way)
- Creating adapters instead of fixing the underlying interface disagreement (adapters are temporary; they should have a removal plan)
- Proposing increments that fail the deletion test (restructuring code without changing observable behavior is valid but must be framed as tech-debt reduction, not feature delivery)

---

## Sources

- John Ousterhout, *A Philosophy of Software Design* (2nd ed., 2021), Chapters 4 (Modules), 17 (Complexity)
- Matt Pocock, "Software Fundamentals Matter More Than Ever" (2025 talk, transcript captured in session)
- Matt Pocock's `mattpocock/skills` repo (evaluation vocabulary: deletion test, seam-vs-adapter, locality)
