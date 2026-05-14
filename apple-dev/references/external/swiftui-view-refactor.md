
> **Guide Skill** — This is an expert workflow/pattern guide, not API reference documentation.
> Originally from [Dimillian/Skills](https://github.com/Dimillian/Skills) by Thomas Ricouard. MIT License.


# SwiftUI View Refactor

## Overview
Refactor SwiftUI views toward small, explicit, stable view types. Default to vanilla SwiftUI: local state in the view, shared dependencies in the environment, business logic in services/models, and view models only when the request or existing code clearly requires one.

## Core Guidelines

### 1) View ordering (top → bottom)
- Enforce this ordering unless the existing file has a stronger local convention you must preserve.
- Environment
- `private`/`public` `let`
- `@State` / other stored properties
- computed `var` (non-view)
- `init`
- `body`
- computed view builders / other view helpers
- helper / async functions

### 2) Default to MV, not MVVM
- Views should be lightweight state expressions and orchestration points, not containers for business logic.
- Favor `@State`, `@Environment`, `@Query`, `.task`, `.task(id:)`, and `onChange` before reaching for a view model.
- Inject services and shared models via `@Environment`; keep domain logic in services/models, not in the view body.
- Do not introduce a view model just to mirror local view state or wrap environment dependencies.
- If a screen is getting large, split the UI into subviews before inventing a new view model layer.

### 3) Strongly prefer dedicated subview types over computed `some View` helpers
- Flag `body` properties that are longer than roughly one screen or contain multiple logical sections.
- Prefer extracting dedicated `View` types for non-trivial sections, especially when they have state, async work, branching, or deserve their own preview.
- Keep computed `some View` helpers rare and small. Do not build an entire screen out of `private var header: some View`-style fragments.
- Pass small, explicit inputs (data, bindings, callbacks) into extracted subviews instead of handing down the entire parent state.
- If an extracted subview becomes reusable or independently meaningful, move it to its own file.

Prefer:

```swift
var body: some View {
    List {
        HeaderSection(title: title, subtitle: subtitle)
        FilterSection(
            filterOptions: filterOptions,
            selectedFilter: $selectedFilter
        )
        ResultsSection(items: filteredItems)
        FooterSection()
    }
}

private struct HeaderSection: View {
    let title: String
    let subtitle: String

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title).font(.title2)
            Text(subtitle).font(.subheadline)
        }
    }
}

private struct FilterSection: View {
    let filterOptions: [FilterOption]
    @Binding var selectedFilter: FilterOption

    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack {
                ForEach(filterOptions, id: \.self) { option in
                    FilterChip(option: option, isSelected: option == selectedFilter)
                        .onTapGesture { selectedFilter = option }
                }
            }
        }
    }
}
```

Avoid:

```swift
var body: some View {
    List {
        header
        filters
        results
        footer
    }
}

private var header: some View {
    VStack(alignment: .leading, spacing: 6) {
        Text(title).font(.title2)
        Text(subtitle).font(.subheadline)
    }
}
```

### 3b) Extract actions and side effects out of `body`
- Do not keep non-trivial button actions inline in the view body.
- Do not bury business logic inside `.task`, `.onAppear`, `.onChange`, or `.refreshable`.
- Prefer calling small private methods from the view, and move real business logic into services/models.
- The body should read like UI, not like a view controller.

```swift
Button("Save", action: save)
    .disabled(isSaving)

.task(id: searchText) {
    await reload(for: searchText)
}

private func save() {
    Task { await saveAsync() }
}

private func reload(for searchText: String) async {
    guard !searchText.isEmpty else {
        results = []
        return
    }
    await searchService.search(searchText)
}
```

### 4) Keep a stable view tree (avoid top-level conditional view swapping)
- Avoid `body` or computed views that return completely different root branches via `if/else`.
- Prefer a single stable base view with conditions inside sections/modifiers (`overlay`, `opacity`, `disabled`, `toolbar`, etc.).
- Root-level branch swapping causes identity churn, broader invalidation, and extra recomputation.

Prefer:

```swift
var body: some View {
    List {
        documentsListContent
    }
    .toolbar {
        if canEdit {
            editToolbar
        }
    }
}
```

Avoid:

```swift
var documentsListView: some View {
    if canEdit {
        editableDocumentsList
    } else {
        readOnlyDocumentsList
    }
}
```

### 5) View model handling (only if already present or explicitly requested)
- Treat view models as a legacy or explicit-need pattern, not the default.
- Do not introduce a view model unless the request or existing code clearly calls for one.
- If a view model exists, make it non-optional when possible.
- Pass dependencies to the view via `init`, then create the view model in the view's `init`.
- Avoid `bootstrapIfNeeded` patterns and other delayed setup workarounds.

Example (Observation-based):

```swift
@State private var viewModel: SomeViewModel

init(dependency: Dependency) {
    _viewModel = State(initialValue: SomeViewModel(dependency: dependency))
}
```

### 6) Observation usage
- For `@Observable` reference types on iOS 17+, store them as `@State` in the owning view.
- Pass observables down explicitly; avoid optional state unless the UI genuinely needs it.
- If the deployment target includes iOS 16 or earlier, use `@StateObject` at the owner and `@ObservedObject` when injecting legacy observable models.

## Workflow

1. Reorder the view to match the ordering rules.
2. Remove inline actions and side effects from `body`; move business logic into services/models and keep only thin orchestration in the view.
3. Shorten long bodies by extracting dedicated subview types; avoid rebuilding the screen out of many computed `some View` helpers.
4. Ensure stable view structure: avoid top-level `if`-based branch swapping; move conditions to localized sections/modifiers.
5. If a view model exists or is explicitly required, replace optional view models with a non-optional `@State` view model initialized in `init`.
6. Confirm Observation usage: `@State` for root `@Observable` models on iOS 17+, legacy wrappers only when the deployment target requires them.
7. Keep behavior intact: do not change layout or business logic unless requested.

## Notes

- Prefer small, explicit view types over large conditional blocks and large computed `some View` properties.
- Keep computed view builders below `body` and non-view computed vars above `init`.
- A good SwiftUI refactor should make the view read top-to-bottom as data flow plus layout, not as mixed layout and imperative logic.
- For MV-first guidance and rationale, see `references/mv-patterns.md`.

## Large-view handling

When a SwiftUI view file exceeds ~300 lines, split it aggressively. Extract meaningful sections into dedicated `View` types instead of hiding complexity in many computed properties. Use `private` extensions with `// MARK: -` comments for actions and helpers, but do not treat extensions as a substitute for breaking a giant screen into smaller view types. If an extracted subview is reused or independently meaningful, move it into its own file.

## Reference materials (from upstream references/)

# MV Patterns Reference

Distilled guidance for deciding whether a SwiftUI feature should stay as plain MV or introduce a view model.

Inspired by the user's provided source, "SwiftUI in 2025: Forget MVVM" (Thomas Ricouard), but rewritten here as a practical refactoring reference.

## Default stance

- Default to MV: views are lightweight state expressions and orchestration points.
- Prefer `@State`, `@Environment`, `@Query`, `.task`, `.task(id:)`, and `onChange` before reaching for a view model.
- Keep business logic in services, models, or domain types, not in the view body.
- Split large screens into smaller view types before inventing a view model layer.
- Avoid manual fetching or state plumbing that duplicates SwiftUI or SwiftData mechanisms.
- Test services, models, and transformations first; views should stay simple and declarative.

## When to avoid a view model

Do not introduce a view model when it would mostly:
- mirror local view state,
- wrap values already available through `@Environment`,
- duplicate `@Query`, `@State`, or `Binding`-based data flow,
- exist only because the view body is too long,
- hold one-off async loading logic that can live in `.task` plus local view state.

In these cases, simplify the view and data flow instead of adding indirection.

## When a view model may be justified

A view model can be reasonable when at least one of these is true:
- the user explicitly asks for one,
- the codebase already standardizes on a view model pattern for that feature,
- the screen needs a long-lived reference model with behavior that does not fit naturally in services alone,
- the feature is adapting a non-SwiftUI API that needs a dedicated bridge object,
- multiple views share the same presentation-specific state and that state is not better modeled as app-level environment data.

Even then, keep the view model small, explicit, and non-optional when possible.

## Preferred pattern: local state plus environment

```swift
struct FeedView: View {
    @Environment(BlueSkyClient.self) private var client

    enum ViewState {
        case loading
        case error(String)
        case loaded([Post])
    }

    @State private var viewState: ViewState = .loading

    var body: some View {
        List {
            switch viewState {
            case .loading:
                ProgressView("Loading feed...")
            case .error(let message):
                ErrorStateView(message: message, retryAction: { await loadFeed() })
            case .loaded(let posts):
                ForEach(posts) { post in
                    PostRowView(post: post)
                }
            }
        }
        .task { await loadFeed() }
    }

    private func loadFeed() async {
        do {
            let posts = try await client.getFeed()
            viewState = .loaded(posts)
        } catch {
            viewState = .error(error.localizedDescription)
        }
    }
}
```

Why this is preferred:
- state stays close to the UI that renders it,
- dependencies come from the environment instead of a wrapper object,
- the view coordinates UI flow while the service owns the real work.

## Preferred pattern: use modifiers as lightweight orchestration

```swift
.task(id: searchText) {
    guard !searchText.isEmpty else {
        results = []
        return
    }
    await searchFeed(query: searchText)
}

.onChange(of: isInSearch, initial: false) {
    guard !isInSearch else { return }
    Task { await fetchSuggestedFeed() }
}
```

Use view lifecycle modifiers for simple, local orchestration. Do not convert these into a view model by default unless the behavior clearly outgrows the view.

## SwiftData note

SwiftData is a strong argument for keeping data flow inside the view when possible.

Prefer:

```swift
struct BookListView: View {
    @Query private var books: [Book]
    @Environment(\.modelContext) private var modelContext

    var body: some View {
        List {
            ForEach(books) { book in
                BookRowView(book: book)
                    .swipeActions {
                        Button("Delete", role: .destructive) {
                            modelContext.delete(book)
                        }
                    }
            }
        }
    }
}
```

Avoid adding a view model that manually fetches and mirrors the same state unless the feature has an explicit reason to do so.

## Testing guidance

Prefer to test:
- services and business rules,
- models and state transformations,
- async workflows at the service layer,
- UI behavior with previews or higher-level UI tests.

Do not introduce a view model primarily to make a simple SwiftUI view "testable." That usually adds ceremony without improving the architecture.

## Refactor checklist

When refactoring toward MV:
- Remove view models that only wrap environment dependencies or local view state.
- Replace optional or delayed-initialized view models when plain view state is enough.
- Pull business logic out of the view body and into services/models.
- Keep the view as a thin coordinator of UI state, navigation, and user actions.
- Split large bodies into smaller view types before adding new layers of indirection.

## Bottom line

Treat view models as the exception, not the default.

In modern SwiftUI, the default stack is:
- `@State` for local state,
- `@Environment` for shared dependencies,
- `@Query` for SwiftData-backed collections,
- lifecycle modifiers for lightweight orchestration,
- services and models for business logic.

Reach for a view model only when the feature clearly needs one.

---
_Source: vabole/apple-skills v1.0.10 · `skills/guide-swiftui-view-refactor/` · MIT (c) 2026 Ilia Abolhasani · Vendored 2026-05-14._
