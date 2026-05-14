# Searchable

## Intent

Use `searchable` to add native search UI with optional scopes and async results.

## Core patterns

- Bind `searchable(text:)` to local state.
- Use `.searchScopes` for multiple search modes.
- Use `.task(id: searchQuery)` or debounced tasks to avoid overfetching.
- Show placeholders or progress states while results load.

## Example: searchable with scopes

```swift
@MainActor
struct ExploreView: View {
  @State private var searchQuery = ""
  @State private var searchScope: SearchScope = .all
  @State private var isSearching = false
  @State private var results: [SearchResult] = []

  var body: some View {
    List {
      if isSearching {
        ProgressView()
      } else {
        ForEach(results) { result in
          SearchRow(result: result)
        }
      }
    }
    .searchable(
      text: $searchQuery,
      placement: .navigationBarDrawer(displayMode: .always),
      prompt: Text("Search")
    )
    .searchScopes($searchScope) {
      ForEach(SearchScope.allCases, id: \.self) { scope in
        Text(scope.title)
      }
    }
    .task(id: searchQuery) {
      await runSearch()
    }
  }

  private func runSearch() async {
    guard !searchQuery.isEmpty else {
      results = []
      return
    }
    isSearching = true
    defer { isSearching = false }
    try? await Task.sleep(for: .milliseconds(250))
    results = await fetchResults(query: searchQuery, scope: searchScope)
  }
}
```

## Design choices to keep

- Show a placeholder when search is empty or has no results.
- Debounce input to avoid spamming the network.
- Keep search state local to the view.

## Pitfalls

- Avoid running searches for empty strings.
- Don’t block the main thread during fetch.
---
_Source: vabole/apple-skills v1.0.10 · `skills/guide-swiftui-ui-patterns/references/searchable.md` · MIT (c) 2026 Ilia Abolhasani · Vendored 2026-05-14._
