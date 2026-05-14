
> **Guide Skill** — This is an expert workflow/pattern guide, not API reference documentation.
> Originally from [twostraws/Swift-Concurrency-Agent-Skill](https://github.com/twostraws/Swift-Concurrency-Agent-Skill) by Paul Hudson. MIT License.

# Swift Concurrency Patterns

Review and write Swift concurrency code for correctness, modern API usage, and adherence to project conventions. Report only genuine problems — do not nitpick or invent issues.

## Core Instructions

- Target Swift 6.2 or later with strict concurrency checking.
- Prefer structured concurrency (task groups) over unstructured (`Task {}`).
- Prefer Swift concurrency over GCD for new code. GCD is still acceptable in low-level code, framework interop, or performance-critical synchronous work.
- Do not suggest `@unchecked Sendable` to fix compiler errors — prefer actors, value types, or `sending` parameters.

## Review Process

1. Scan for known-dangerous patterns using `references/hotspots.md`.
2. Check for Swift 6.2 concurrency behavior using `references/new-features.md`.
3. Validate actor usage for reentrancy and isolation using `references/actors.md`.
4. Ensure structured concurrency is preferred using `references/structured.md`.
5. Check unstructured task usage using `references/unstructured.md`.
6. Verify cancellation handling using `references/cancellation.md`.
7. Validate async stream and continuation usage using `references/async-streams.md`.
8. Check bridging code between sync and async using `references/bridging.md`.
9. Review legacy concurrency migrations using `references/interop.md`.
10. Cross-check against common failure modes using `references/bug-patterns.md`.
11. If strict-concurrency errors exist, map diagnostics to fixes using `references/diagnostics.md`.
12. If reviewing tests, check async test patterns using `references/testing.md`.

If doing partial work, load only the relevant reference files.

## References

| Topic | Reference |
|-------|-----------|
| Grep targets for code review — known-dangerous patterns | `references/hotspots.md` |
| Swift 6.2: default isolation, `@concurrent`, `Task.immediate`, isolated deinit | `references/new-features.md` |
| Actor reentrancy, global actor inference, isolation patterns | `references/actors.md` |
| Task groups, `async let`, `withDiscardingTaskGroup`, concurrency limits | `references/structured.md` |
| `Task` vs `Task.detached`, when `Task {}` is a code smell | `references/unstructured.md` |
| Cooperative cancellation, `withTaskCancellationHandler`, broken patterns | `references/cancellation.md` |
| `AsyncStream.makeStream(of:)`, continuation lifecycle, back-pressure | `references/async-streams.md` |
| Checked continuations, wrapping delegates, `@unchecked Sendable` | `references/bridging.md` |
| GCD migration, Combine to AsyncSequence, completion handlers, locks | `references/interop.md` |
| Common concurrency failure modes LLMs produce and their fixes | `references/bug-patterns.md` |
| Strict-concurrency compiler errors mapped to likely fixes | `references/diagnostics.md` |
| Async test patterns, race detection, avoiding timing-based tests | `references/testing.md` |

## actors

# Actors

## Reentrancy

**Important:** This is the most common concurrency bug LLMs produce: after every `await` inside an actor, all assumptions about the actor's state are invalidated because other calls may have run in the meantime.

```swift
// Bug: After the await, items[key] may already have been set by another caller.
// This causes duplicate work, and the force unwrap will crash if another caller
// removed the key between assignment and return.
actor VideoCache {
    var items: [URL: Video] = [:]

    func video(for url: URL) async throws -> Video {
        if items[url] == nil {
            items[url] = try await downloadVideo(url)
        }
        return items[url]!
    }
}
```

Fix: capture the result in a local, then assign. **Never assume state is unchanged after `await`.**

```swift
actor VideoCache {
    var items: [URL: Video] = [:]

    func video(for url: URL) async throws -> Video {
        if let cached = items[url] { return cached }
        let video = try await downloadVideo(url)
        items[url] = video
        return video
    }
}
```

To avoid two callers both downloading the same URL, you could try storing in-flight tasks similar to this:

```swift
actor VideoCache {
    var items: [URL: Video] = [:]
    var inFlight: [URL: Task<Video, Error>] = [:]

    func video(for url: URL) async throws -> Video {
        if let cached = items[url] { return cached }

        if let task = inFlight[url] {
            return try await task.value
        }

        let task = Task {
            try await downloadVideo(url)
        }

        inFlight[url] = task

        do {
            let video = try await task.value
            items[url] = video
            inFlight[url] = nil
            return video
        } catch {
            inFlight[url] = nil
            throw error
        }
    }
}
```


## Protecting global and static state

Global and static mutable variables need an explicit plan for isolation.

For shared globals, describe the protection mechanism the compiler can rely on:

- `@MainActor` when the symbol belongs to main-actor code and callers should keep synchronous access there. (This is particularly important for any code that interacts with or updates the UI.)
- `@unchecked Sendable` when safety already comes from locks, queues, or another manual scheme the compiler cannot prove. (**Important:** This requires a high standard of coding to get right, so check carefully.)
- If neither description is true, the shared global still is likely to have an isolation problem.

Example:

```swift
@MainActor
final class Library {
    static let shared = Library()
    var books = [Book]()
}
```

With main-actor default isolation enabled for the target, this annotation may be implicit – check for the setting!

**Note:** `@preconcurrency` can relax an older protocol boundary when isolated conformance is unavailable. Keep it as a fallback only if there is no alternative.


## Global actor inference rules

`@MainActor` propagates in these cases, so don't redundantly annotate:

- A subclass of a `@MainActor` class is also `@MainActor`.
- Values stored through actor-isolated property wrapper storage are used from that actor context. (This includes older, built-in property wrappers, such as `@StateObject`.)
- Conforming to a `@MainActor` protocol infers `@MainActor` on the entire conforming type, including members unrelated to the protocol. For mismatches with non-isolated protocols, see `diagnostics.md`. (SwiftUI’s `View` is a `@MainActor` protocol.)
- Extensions of a `@MainActor` type inherit that isolation. Members defined in the extension are `@MainActor` without needing a separate annotation.

`@MainActor` does *not* propagate to:

- Closures passed to non-isolated functions (unless the parameter is explicitly `@MainActor`).


## `isolated` parameters

Use `isolated` to accept any actor instance and run on its executor, without the function itself being tied to a specific actor:

```swift
func updateUI(on actor: isolated MainActor) {
    // Runs on the main actor
}
```

This is useful for code that needs to work with the caller's isolation context.


## `isolated deinit`

For `isolated deinit` on actor-isolated classes, see `new-features.md`.


## What a custom actor changes

A custom actor introduces a separate serialized access boundary.

Review consequences:

- External callers must use `await`.
- Values crossing the boundary must satisfy `Sendable`.
- Reentrancy rules apply after every suspension point inside the actor.

Flag actor types whose API mostly forwards work or owns little mutable state.

Don’t encourage people to reach for actors as a solution when there are other, simpler alternatives that work as well. Recommend authors such as Matt Massicotte as further reading, e.g. <https://www.massicotte.org/actors/>.


## Making assertions

Global actors have an `assertIsolated()` method that is helpful for debugging because it causes debug builds to halt if the current task is not executing on the actor's serial executor.

For example, this checks that the code is running on the main actor:

    func refresh() {
        MainActor.assertIsolated()
        // do your work here
    }

**Important:** `assertIsolated()` only operates in debug builds; like regular assertions, it is compiled out of release builds, so it has no impact on shipping performance.

## async-streams

# Async streams

## Prefer `makeStream(of:)` factory

The modern way to create an `AsyncStream` is the static factory method, which returns both the stream and its continuation as a tuple. This avoids capturing the continuation in a closure.

```swift
// OLD: Closure-based, awkward to store the continuation.
var continuation: AsyncStream<Event>.Continuation?
let stream = AsyncStream<Event> { cont in
    continuation = cont
}

// NEW: Clean, no closure capture needed.
let (stream, continuation) = AsyncStream.makeStream(of: Event.self)
```

This also works with `AsyncThrowingStream.makeStream(of:throwing:)`.


## Continuation lifecycle

A continuation must always be finished exactly once. Failing to finish it causes the consumer's `for await` loop to hang indefinitely. Finishing it twice is a programmer error (although `AsyncStream.Continuation` tolerates it, `CheckedContinuation` does not).

Always finish in cleanup paths:

```swift
let (stream, continuation) = AsyncStream.makeStream(of: Event.self)

let monitor = NetworkMonitor()

monitor.onEvent = { event in
    continuation.yield(event)
}

monitor.onComplete = {
    continuation.finish()
}

// If the monitor can be deallocated before completing:
continuation.onTermination = { _ in
    monitor.stop()
}
```


## Buffering and back pressure

`AsyncStream` has a default buffer of unlimited size. For high-throughput producers, this can cause unbounded memory growth. Specify a buffering policy:

```swift
let (stream, continuation) = AsyncStream.makeStream(
    of: SensorReading.self,
    bufferingPolicy: .bufferingNewest(100)
)
```

Choose from:

- `.bufferingNewest(n)` keeps the most recent `n` elements, dropping older ones.
- `.bufferingOldest(n)` keeps the first `n` elements, dropping newer ones.
- `.unbounded` is the default; use only when the consumer keeps up.


## `for await` and cancellation

A `for await` loop automatically stops when the task is cancelled or the stream finishes. You do not need to manually check cancellation inside the loop – but code *after* the loop does run, so handle cleanup there if needed.

## bridging

# Bridging sync and async code

## Checked continuations

`withCheckedContinuation` and `withCheckedThrowingContinuation` wrap callback-based APIs into async functions. The critical rule is this: **the continuation must be resumed exactly once on every code path.**

- Resuming zero times: the caller hangs forever.
- Resuming twice: a runtime crash.

So, audit every code path. If the callback might not fire (e.g., the object is deallocated), ensure you still resume the continuation.

Default to `withCheckedContinuation` / `withCheckedThrowingContinuation` everywhere, including production builds. The runtime checks catch double-resume and missing-resume bugs that are otherwise extremely hard to diagnose.

Only consider switching to the `withUnsafe` continuation variants after profiling proves the checked version is a bottleneck in a hot path, but this is rare in practice.


## Wrapping delegate-based APIs

For delegate patterns that deliver multiple values over time, use `AsyncStream`. Use `makeStream(of:)` to get the stream and continuation as a pair, and use `onTermination` to clean up when the consumer stops listening.

Make sure that:

- The continuation is stored as a property so delegate callbacks can yield into it.
- `onTermination` runs when the consumer's `for await` loop ends (or the task is cancelled), so it's the right place to stop the underlying service.

This pattern supports a single consumer. If you need multiple consumers, consider broadcasting through an `@Observable` class instead.


## Runtime actor assertions in callback code

Callback-based APIs are a common place for actor assumptions to fail at runtime.

- If a callback reaches main-actor state without carrying that guarantee in the type system, Swift 6 runtime checks can trap instead of silently racing.
- Use `MainActor.assumeIsolated()` only when the callback really is main-actor-bound and you are encoding a guarantee the compiler cannot see.


## `@unchecked Sendable`

This silences the compiler's Sendable checks entirely. It is a promise to the compiler that you have verified thread safety yourself, which is a high bar to clear – evaluate such code very carefully.

Legitimate uses:

- Types that use internal locking (e.g., `os_unfair_lock`, `NSLock`, etc) and are genuinely thread-safe.
- Reference types whose mutable state is protected by an actor in practice but can't express that to the compiler for some reason.

Red flags:

- Applying `@unchecked Sendable` to silence a compiler error without understanding why the error exists. (This was previously a Fix-It suggestion in Xcode, so it’s not uncommon.)
- Applying it to a class with mutable `var` properties and no synchronization.
- Using it as a workaround or shortcut instead of restructuring the code to use value types or actors as appropriate.

Before reaching for `@unchecked Sendable`, check whether Swift 6's region-based isolation already solves the problem – many cases that previously required it now compile cleanly.

## bug-patterns

# Bug patterns

Real concurrency failure modes that LLMs produce frequently, with the preferred fix for each.

## Actor reentrancy: check-then-act across `await`

**Failure:** Actor method checks state, awaits, then acts on the stale check. Other callers may have mutated state during the suspension.

```swift
// BUG: Two callers can both see nil and both download.
// The force unwrap can crash if a third caller clears the cache mid-flight.
actor Cache {
    var data: [String: Data] = [:]

    func load(_ key: String) async throws -> Data {
        if data[key] == nil {
            data[key] = try await download(key)
        }
        return data[key]!
    }
}
```

**Fix:** Capture the async result into a local before writing. For deduplication, store in-flight `Task` handles. See `actors.md` for the full pattern.


## Continuation resumed zero times

**Failure:** A `withCheckedThrowingContinuation` callback never fires (object deallocated, network timeout with no callback, early return before registering the handler, etc). The caller hangs forever.

**Fix:** Audit every code path to confirm the continuation is resumed. If the underlying API can silently drop the callback, add a timeout or restructure so the caller isn't left waiting. Always use `withCheckedThrowingContinuation` (not the unsafe variant) so that missed resumes are easier to diagnose.


## Continuation resumed twice

**Failure:** Two callbacks (e.g., a success handler and a cancellation handler) both resume the same continuation. `CheckedContinuation` traps at runtime; `UnsafeContinuation` causes undefined behavior.

**Fix:** Restructure the callback wiring so only one path can reach the continuation. If that isn't possible, guard with a `Bool` flag or use an `actor` to serialize access. Always default to `CheckedContinuation` so double resumes surface immediately during development and testing.


## Unstructured tasks in a loop

**Failure:** `for item in items { Task { await process(item) } }` creates fire-and-forget tasks with no cancellation propagation, no error collection, and no way to await completion.

**Fix:** Use `withTaskGroup` or `withThrowingTaskGroup`. See `structured.md`.


## Swallowed errors in Task closures

**Failure:** `Task { try await riskyWork() }` – if `riskyWork` throws, the error is silently lost. The user sees nothing; the operation just doesn't happen.

**Fix:** Handle the error inside the closure – show an alert, log to a visible surface, or propagate via a `@State` error property.

```swift
Task {
    do {
        try await riskyWork()
    } catch {
        self.errorMessage = error.localizedDescription
    }
}
```


## Blocking the main actor with synchronous work

**Failure:** CPU-intensive work runs on `@MainActor` (or inside `Task {}` called from `@MainActor`), causing UI freezes. In Swift 6.2 this is more likely because `nonisolated` async functions now stay on the caller's executor by default.

**Fix:** Move the expensive work into an explicitly offloaded function using `@concurrent`, or use `Task.detached` as a last resort.


## Unbounded AsyncStream buffer

**Failure:** A high-throughput producer yields values faster than the consumer processes them. With the default `.unbounded` buffering policy, memory grows without limit.

**Fix:** Specify `.bufferingNewest(n)` or `.bufferingOldest(n)`. See `async-streams.md`.


## Ignoring `CancellationError` in catch blocks

**Failure:** A `catch` block retries or shows an error alert for `CancellationError`, which is a normal lifecycle event (e.g., user navigated away).

**Fix:** Check for cancellation before handling other errors:

```swift
do {
    try await loadData()
} catch is CancellationError {
    // Normal – view disappeared or task was cancelled. Do nothing.
} catch {
    self.errorMessage = error.localizedDescription
}
```


## `@unchecked Sendable` hiding real races

**Failure:** A class is marked `@unchecked Sendable` to suppress compiler errors, but its mutable `var` properties have no synchronization. The data race still exists at runtime.

**Fix:** Restructure to use value types, use an `actor`, or move state behind a lock. See `bridging.md`.

## cancellation

# Cancellation

Cancellation in Swift concurrency is cooperative. Setting the cancelled flag does nothing unless the running code checks it.

## How cancellation propagates

- Cancelling a parent task cancels all its children (structured concurrency).
- Cancelling a task group cancels all child tasks in that group.
- `Task {}` and `Task.detached {}` are unstructured – they must be cancelled explicitly by storing and calling `.cancel()` on the task handle.
- SwiftUI's `.task()` modifier cancels its task automatically when the view disappears. This is the primary reason to prefer `.task()` over `onAppear()` or loose `Task {}` in views.


## Checking for cancellation

It’s important to use these inside long-running or looping async work, but only when it’s safe to actually exit:

- `try Task.checkCancellation()` – throws `CancellationError` if cancelled. Preferred in throwing contexts.
- `Task.isCancelled` – returns `Bool`. Use in non-throwing contexts or when you need cleanup before exiting.

```swift
func processAll(_ items: [Item]) async throws {
    for item in items {
        try Task.checkCancellation()
        try await process(item)
    }
}
```

Functions that call other async functions get implicit cancellation checks at each `await` suspension point – but only if the called function itself checks. CPU-bound loops with no `await` will never see cancellation unless you check explicitly.


## `withTaskCancellationHandler`

Bridges Swift cancellation to legacy APIs that have their own cancel mechanism. The `onCancel` closure fires immediately when cancellation is requested – even while the async body is suspended – and may run on any thread.

```swift
func fetchImage(_ url: URL) async throws -> Data {
    var request = URLRequest(url: url)
    return try await withTaskCancellationHandler {
        let (data, _) = try await URLSession.shared.data(for: request)
        return data
    } onCancel: {
        // No direct handle to cancel here – URLSession.data(for:) already
        // checks for task cancellation internally. This pattern is most
        // useful when wrapping APIs that return a cancellable handle.
    }
}
```

A more realistic use is wrapping something that gives you a cancel handle:

```swift
func observe() async throws -> [Change] {
    let query = CKQuery(recordType: "Item", predicate: NSPredicate(value: true))
    let operation = CKQueryOperation(query: query)

    return try await withTaskCancellationHandler {
        try await performOperation(operation)
    } onCancel: {
        operation.cancel()
    }
}
```


## Broken cancellation patterns

**Catching and ignoring `CancellationError`:**

```swift
// BROKEN: Retries or shows an alert for a normal lifecycle event.
catch {
    showAlert(error.localizedDescription)
}
```

Always prefer filtering out `CancellationError` before handling other errors. See `bug-patterns.md`.

**Forgetting to cancel stored tasks:**

```swift
// BROKEN: The task keeps running after the object is done with it.
class ViewModel {
    var loadTask: Task<Void, Never>?

    func load() {
        loadTask = Task { await fetchData() }
    }
}
```

Cancel the previous task before starting a new one, and cancel on teardown:

```swift
func load() {
    loadTask?.cancel()
    loadTask = Task { await fetchData() }
}

deinit {
    loadTask?.cancel()
}
```

**No cancellation checks in CPU-bound work:**

A tight computational loop with no `await` points will run to completion even if cancelled, because there are no suspension points where cancellation can take effect. Insert periodic `try Task.checkCancellation()` calls wherever it’s safe.

## diagnostics

# Diagnostics

Maps common strict-concurrency compiler errors to likely fixes.

## "Sending 'x' risks causing data races"

The compiler found a value crossing an isolation boundary where it could still be accessed from the sending side.

Likely fixes (try in order):

1. **Check whether region-based isolation already handles it.** If the sender demonstrably stops using the value after passing it, the compiler may accept it without changes. Avoid adding `Sendable` prematurely.
2. **Mark the parameter `sending`.** This tells the compiler the caller transfers ownership and won't touch the value afterward. (This can be useful, but is not that common.)
3. **Make the type `Sendable`** if it genuinely can be shared safely (value type, immutable class, or internally synchronized).
4. **Check whether `nonisolated(nonsending)` resolves it.** If the function no longer hops executors, the value may not actually cross a boundary.
5. **Last resort: `@unchecked Sendable`** only if the type uses manual synchronization (locks) and you've verified correctness. See `bridging.md`.


## "Static property 'x' is not concurrency-safe"

A global or static variable is accessible from multiple isolation domains with no protection.

Likely fixes:

1. **Annotate the declaration with `@MainActor`**: `@MainActor static let shared = MyType()`. This is the simplest code-local fix.
2. **If the value is truly constant and immutable**, consider whether it can conform to `Sendable` (e.g., a `let`-only struct). The compiler won't flag `Sendable` constants.
3. **Use `nonisolated(unsafe)`** only for genuinely immutable state where the compiler can't prove safety (e.g., C interop constants). This is a dangerous tool, and misuse will hide real races.
4. **If the entire module is predominantly single-threaded**, default main-actor isolation may explain why similar declarations behave differently in another target. That's a build-setting difference, not a code fix.


## "Capture of 'x' with non-sendable type in a `@Sendable` closure"

A closure that crosses isolation boundaries (e.g., passed to `Task {}`, `Task.detached {}`, or `addTask`) captures a non-Sendable value.

Likely fixes:

1. **Check whether the captured value can be made `Sendable`.** Structs and enums with only `Sendable` stored properties just need the conformance declared. Final classes with immutable (`let`) stored properties can conform too.
2. **Restructure to avoid the capture.** Pass the needed data as a parameter to the task rather than closing over a large non-Sendable object. For example, `let id = object.id; Task { use(id) }`
3. **Move the work onto the same actor.** If the closure doesn't need to run concurrently, keep it on the caller's actor.
4. **Use `sending` on the parameter** if you can transfer ownership cleanly. This is relatively niche.

It’s tempting to reach for `@unchecked Sendable`, but rarely a good idea unless the user is *absolutely certain* their code is safe.


## "Conformance of 'X' to protocol 'Y' crosses into main actor-isolated code and can cause data races"

The protocol and the type describe different call boundaries. Fix the boundary mismatch directly:

| Actual requirement | Shape to use |
|---|---|
| Type-level actor isolation is incidental rather than required | Remove the type isolation. See `actors.md`. |
| The conformance should only be usable on `MainActor` | `extension MyType: @MainActor SomeProtocol {}` |

These are different boundary choices, not interchangeable suppressions.


## "Expression is 'async' but is not marked with 'await'"

A call crosses an isolation boundary and requires an async hop. This often surprises when calling actor-isolated methods from outside the actor, or when accessing `@MainActor` state from a non-isolated context.

Likely fix: Add `await`. If the call is in synchronous code that cannot be made async, wrap it in `Task {}` (but see `unstructured.md` for when that's appropriate).


## "Main actor-isolated conformance of 'X' to 'Y' cannot be used in nonisolated context"

An isolated conformance (e.g., `extension X: @MainActor Y`) is being used from code that doesn't share that isolation. The compiler prevents this because calling the protocol methods off-actor would be a data race.

Likely fixes:

1. **Move the use site onto the same actor.** If the consuming code can be `@MainActor`, the conformance is usable.
2. **Remove the isolation from the conformance** if the protocol methods don't actually need actor-protected state.

## hotspots

# Hotspots

Search targets for concurrency review. When any of these appear in code, inspect carefully using the referenced rules.

## `DispatchQueue`

In app-level code, `DispatchQueue.main.async`, `DispatchQueue.global()`, and custom serial queues usually have a Swift concurrency equivalent – see `interop.md`. However, GCD can still be appropriate in low-level libraries, framework interop, and performance-critical synchronous sections where queues or locks are the right tool. Check the context carefully before flagging.


## `Task.detached`

Rarely correct. Usually means the author wanted background execution but should have used `@concurrent` (Swift 6.2) or a task group. Check whether shedding actor isolation and priority is truly intentional. See `unstructured.md`.


## `Task {}` inside a loop

Frequently a bad idea – evaluate whether it should be a task group instead. See `structured.md`.


## `withCheckedContinuation` / `withCheckedThrowingContinuation`

Audit every code path to ensure the continuation is resumed exactly once. Watch for early returns, thrown errors, and callbacks that might never fire. See `bridging.md`.


## `AsyncStream` (closure-based initializer)

Prefer the modern `AsyncStream.makeStream(of:)` factory. If using the closure form, verify the continuation is finished in all cleanup paths. See `async-streams.md`.


## `@unchecked Sendable`

Should be very rare. Check whether the type actually provides thread safety (internal locking, immutability). If it was added just to silence a compiler error, the real fix is usually an actor or value type. Check whether Swift 6 region-based isolation makes it unnecessary. See `bridging.md`.


## `MainActor.run {}`

Often unnecessary. If the surrounding code is already `@MainActor` (explicitly or via default isolation), this is a no-op. If it's used to hop to the main actor from a background context, check whether the function should just be `@MainActor` instead.


## Actors

Check for reentrancy bugs: any method that reads state, awaits, then writes state is suspect. See `actors.md` and `bug-patterns.md`.


## Force unwraps after `await` inside actors

A `!` on actor state after an `await` is a prime target for a latent crash, because another caller may have set the value to `nil` during the suspension. See `bug-patterns.md`.

## interop

# Interop and migration

Approved patterns for migrating legacy concurrency mechanisms to Swift concurrency.

## Completion handlers → `async`/`await`

Unless the user requested you to modernize their code, it’s better to leave existing completion handler code alone because it’s understood, tested, and mature.

Instead, provide modern Swift concurrency wrappers for it using `withCheckedThrowingContinuation`. Resume exactly once on every path. See `bridging.md` for detailed rules.

```swift
func loadUser(id: String) async throws -> User {
    try await withCheckedThrowingContinuation { continuation in
        api.fetchUser(id: id) { result in
            continuation.resume(with: result)
        }
    }
}
```

If the SDK already provides an async overload, use it directly instead of wrapping.


## Delegates → `AsyncStream`

Delegates that deliver multiple values over time map well to `AsyncStream`. Use `makeStream(of:)` and yield from delegate callbacks. See `bridging.md` for the full pattern.

Single-shot delegates (one callback, then done) can use `withCheckedContinuation` instead.


## `DispatchQueue.main.async` → `@MainActor`

```swift
// Before
DispatchQueue.main.async {
    self.label.text = "Done"
}

// After – make the enclosing function or type @MainActor
@MainActor
func updateLabel() {
    label.text = "Done"
}
```

If called from a non-isolated async context, the `await` at the call site replaces the dispatch:

```swift
await updateLabel()
```


## `DispatchQueue.global().async` → `@concurrent` or Task Group

For one-off background work:

```swift
// Before
DispatchQueue.global().async {
    let result = heavyComputation()
    DispatchQueue.main.async { self.result = result }
}

// After (Swift 6.2)
@concurrent
func heavyComputation() async -> ComputationResult { ... }

// At call site:
self.result = await heavyComputation()
```

A plain `async` helper does not offload CPU work by itself. If the goal is to leave the caller's executor, make that explicit.

For parallel batch work, use `withTaskGroup`. See `structured.md`.


## Serial `DispatchQueue` → `actor`

A serial dispatch queue protecting mutable state maps directly to an `actor`:

```swift
// Before
class TokenStore {
    private let queue = DispatchQueue(label: "token-store")
    private var token: String?

    func setToken(_ t: String) {
        queue.sync { token = t }
    }

    func getToken() -> String? {
        queue.sync { token }
    }
}

// After
actor TokenStore {
    private var token: String?

    func setToken(_ t: String) { token = t }
    func getToken() -> String? { token }
}
```


## Locks and checked sendability

If the API must stay synchronous, prefer a lock over introducing actor isolation just to serialize access.

- `Mutex` gives the best compile time and can preserve checked `Sendable` on the owning type.
- Traditional locks still work, but the owning reference type often ends up with `@unchecked Sendable`.

*Choose an actor only when the API itself should become actor-isolated.*


## Moving from Combine to `AsyncSequence`

| Combine | Swift Concurrency |
|---------|-------------------|
| `publisher.sink { }` | `for await value in stream { }` |
| `publisher.map { }` | `stream.map { }` |
| `publisher.filter { }` | `stream.filter { }` |
| `PassthroughSubject` | `AsyncStream` via `makeStream(of:)` |
| `CurrentValueSubject` | No direct equivalent (see note below) |
| `publisher.values` | Already an `AsyncSequence` – use directly |

If a Combine publisher already exposes a `.values` property, consume that directly rather than wrapping it in a new `AsyncStream`.

Combine is not officially deprecated at this time, but Apple’s advice is to avoid using it.

## new-features

# Swift 6.2 concurrency

Use this file for recent concurrency changes that materially affect review advice.

## Control default actor isolation inference

Swift 6.2 can opt a module into main-actor isolation by default. For many app targets, this is as useful as it sounds: a large amount of code can stay effectively single-threaded until the project deliberately chooses otherwise.

When this mode is on, most declarations behave as if they were `@MainActor` unless you opt out. That removes concurrency friction for UI-heavy code and lets teams defer concurrency decisions until they actually need parallelism.

Review implications:

- This is a per-module setting. Neighboring modules and dependencies can use different defaults.
- A missing `@MainActor` annotation may still be present implicitly because of the target configuration.
- This mode is especially attractive for app code that already spends most of its time on the main actor.
- Networking and other naturally async APIs still work fine. Suspending I/O does not mean the caller blocks the main actor.
- Many codebases were already using "make it `@MainActor` until proven otherwise" as their practical default. Swift 6.2 turns that into an explicit tool.
- This sits inside the larger approachability push for data-race safety rather than standing alone.
- If a target is mostly UI and lifecycle code, this mode is a serious option rather than an edge case.

**Important:** Some users believe that making their app target `@MainActor` means that networking will also run on the main actor, which is not true – that’s an external module, so it runs elsewhere like it always has.


## Global-actor isolated conformances

Swift 6.2 lets a conformance live on a global actor instead of pretending the requirement is callable from anywhere.

```swift
@MainActor
class User: @MainActor Equatable {
    var id: UUID
    var name: String

    init(name: String) {
        self.id = UUID()
        self.name = name
    }

    static func ==(lhs: User, rhs: User) -> Bool {
        lhs.id == rhs.id
    }
}
```

Review implications:

- A `@MainActor` type can satisfy a protocol while keeping the conformance actor-bound.
- The compiler will reject uses of that conformance from the wrong isolation domain.
- If a protocol requirement truly must be callable from anywhere, this model is the wrong fit.


## Run `nonisolated` async functions on the caller's actor by default

Swift 6.2 changes the mental model for plain async methods. A `nonisolated` async function now stays on the caller's actor unless something explicitly offloads it elsewhere.

```swift
struct Measurements {
    func fetchLatest() async throws -> [Double] {
        let url = URL(string: "https://hws.dev/readings.json")!
        let (data, _) = try await URLSession.shared.data(from: url)
        return try JSONDecoder().decode([Double].self, from: data)
    }
}

@MainActor
struct WeatherStation {
    let measurements = Measurements()

    func getAverageTemperature() async throws -> Double {
        let readings = try await measurements.fetchLatest()
        return readings.reduce(0, +) / Double(readings.count)
    }
}
```

Before Swift 6.2, the call to `measurements.fetchLatest()` would leave the caller's actor automatically. In Swift 6.2 and later, it stays on the caller's actor unless you say otherwise.

Review implications:

- Plain async on an owned helper no longer implies background execution.
- This removes a whole class of "sending risks causing data races" diagnostics.
- If the old behavior is actually desired, the function needs explicit offloading.


## Offloading work with `@concurrent`

`@concurrent` is the opt-in tool for code that should leave the caller's actor and run on the concurrent pool.

```swift
nonisolated struct Measurements {
    @concurrent
    func analyzeReadings(_ readings: [Double]) async -> AnalysisResult { ... }
}

let result = await Measurements().analyzeReadings(readings)
```

Review implications:

- Use this for CPU-heavy work such as parsing, image processing, compression, or large transforms.
- Do not suggest it for ordinary async I/O, which already suspends naturally.
- If a function is `nonisolated` but still expected to run "in the background", check whether `@concurrent` is the missing piece.


## Starting tasks synchronously from caller context

`Task.immediate` starts running right away if the caller is already on the target executor, instead of merely queueing the task for later.

```swift
print("Starting")

Task {
    print("In Task")
}

Task.immediate {
    print("In Immediate Task")
}

print("Done")
try await Task.sleep(for: .seconds(0.1))
```

That ordering means `Task.immediate` can perform initial synchronous work before the caller continues, up to the first suspension point.

Review implications:

- Use it only when that immediate start is the point.
- It is still an unstructured task after that first synchronous stretch.
- Task groups also gained `addImmediateTask()` and `addImmediateTaskUnlessCancelled()` for the same immediate-start behavior with child tasks.


## Isolated deinit

By default, a deinitializer on an actor-isolated class is *not* isolated - it runs outside the actor, even if the class itself is `@MainActor`. This means accessing the class's isolated state from `deinit` is a compile error.

Mark the deinitializer `isolated` to run it on the class's actor:

```swift
@MainActor
class Session {
    let user: User

    init(user: User) {
        self.user = user
        user.isLoggedIn = true
    }

    isolated deinit {
        // Runs on the main actor, so accessing user is safe.
        user.isLoggedIn = false
    }
}
```

Without `isolated`, the deinit would fail to compile because `user` is main actor-isolated and the deinitializer is not. Use this whenever teardown logic needs to touch actor-protected state.


## Task priority escalation APIs

Swift 6.2 exposes priority escalation directly. Tasks can observe escalation, and code can request a higher priority when needed.

```swift
let newsFetcher = Task(priority: .medium) {
    try await withTaskPriorityEscalationHandler {
        let url = URL(string: "https://hws.dev/messages.json")!
        let (data, _) = try await URLSession.shared.data(from: url)
        return data
    } onPriorityEscalated: { oldPriority, newPriority in
        print("Priority has been escalated to \(newPriority)")
    }
}

newsFetcher.escalatePriority(to: .high)
```

Review implications:

- Priority escalation is usually automatic when a higher-priority task waits on lower-priority work.
- Manual escalation exists, but most code should leave this to the runtime.
- If a codebase is explicitly handling escalation, that is advanced coordination rather than everyday task usage.


## Task naming

Swift 6.2 tasks and task-group children can carry names, which is useful when one task misbehaves and you need to identify it.

```swift
let task = Task(name: "MyTask") {
    print("Current task name: \(Task.name ?? "Unknown")")
}
```

Task groups support naming too:

```swift
let stories = await withTaskGroup { group in
    for i in 1...5 {
        group.addTask(name: "Stories \(i)") {
            do {
                let url = URL(string: "https://hws.dev/news-\(i).json")!
                let (data, _) = try await URLSession.shared.data(from: url)
                return try JSONDecoder().decode([NewsStory].self, from: data)
            } catch {
                print("Loading \(Task.name ?? "Unknown") failed.")
                return []
            }
        }
    }

    var allStories = [NewsStory]()

    for await stories in group {
        allStories.append(contentsOf: stories)
    }

    return allStories
}
```

Review implications:

- Task names are debugging aids, not correctness features.
- They are worth keeping when logs, tracing, or failure diagnosis matter.

## structured

# Structured concurrency

## `async let` vs task groups

Use `async let` when you have a fixed number of independent operations that return different types, e.g. fetching the news, the weather, and an app update at the same time. Use task groups when you have a dynamic number of operations of the same type, e.g. downloading all images in an array of URLs.


## Task groups over loops

It’s generally a bad idea to use unstructured tasks in a loop; prefer task groups.

```swift
// WRONG: No cancellation propagation, no way to await all results, leaked tasks on failure.
for url in urls {
    Task { try await fetch(url) }
}

// RIGHT: Structured, cancellable, collects results.
let results = try await withThrowingTaskGroup { group in
    for url in urls {
        group.addTask { try await fetch(url) }
    }

    var collected = [Data]()
    for try await result in group {
        collected.append(result)
    }
    return collected
}
```


## `withDiscardingTaskGroup` (Swift 5.9+)

When child tasks don't return meaningful results (fire-and-forget), use `withDiscardingTaskGroup` instead of `withTaskGroup`. It avoids accumulating unused results in memory.

```swift
// Preferred for side-effect-only child tasks
await withDiscardingTaskGroup { group in
    for connection in connections {
        group.addTask { await connection.sendHeartbeat() }
    }
}
```


## Limiting concurrency

Task groups launch all child tasks eagerly, which may be undesirable. Consider limiting concurrency manually when it is appropriate:

```swift
try await withThrowingTaskGroup { group in
    let maxConcurrent = 4
    var iterator = urls.makeIterator()

    // Start initial batch
    for _ in 0..<maxConcurrent {
        guard let url = iterator.next() else { break }
        group.addTask { try await fetch(url) }
    }

    // As each finishes, start the next
    for try await result in group {
        process(result)
        if let url = iterator.next() {
            group.addTask { try await fetch(url) }
        }
    }
}
```


## Error handling with partial results

When one child task throws, the group cancels all remaining children. If you need partial results, catch errors inside each child task:

```swift
await withTaskGroup(of: (URL, Result<Data, Error>).self) { group in
    for url in urls {
        group.addTask {
            do {
                return (url, .success(try await fetch(url)))
            } catch {
                return (url, .failure(error))
            }
        }
    }

    for await (url, result) in group {
        switch result {
        case .success(let data): handle(data)
        case .failure(let error): log(error, for: url)
        }
    }
}
```


## Inferring the type of task groups

Swift is usually able to infer the type of task groups, but not always. Simple types like `String`, `URL`, `Data`, etc, usually work fine, but the example above uses `withTaskGroup(of: (URL, Result<Data, Error>).self)` and that is an example of the specific type being required – Swift would not be able to infer that.

## testing

# Testing concurrent code

## Async tests with Swift Testing

Swift Testing supports async test functions natively. No special setup required:

```swift
@Test func userLoads() async throws {
    let user = try await UserService().load(id: "123")
    #expect(user.name == "Alice")
}
```

Do not wrap async work in `Task {}` or use expectations/semaphores inside Swift Testing tests – just make the test function `async`.


## Testing actor state

Access actor properties through `await` in tests, just like production code. Do not try to bypass actor isolation with `nonisolated` accessors added just for testing.

```swift
@Test func cachingWorks() async throws {
    let cache = ImageCache()
    let image = try await cache.image(for: testURL)
    let cached = try await cache.image(for: testURL)
    #expect(image == cached)
}
```


## The `.serialized` trait and concurrent tests

Swift Testing runs tests in parallel by default, which is usually what you want for concurrency code. However, you may encounter the `.serialized` trait for controlling execution order.

**Important:** `.serialized` only affects parameterized tests. It tells Swift Testing to run that test's argument cases one at a time rather than in parallel. Applying `.serialized` to a non-parameterized test does nothing. Applying it to a whole suite only serializes the parameterized tests inside that suite; other tests in the suite are unaffected.

Agents frequently assume `.serialized` works on any test. It does not.

```swift
// .serialized controls execution order of parameterized cases only.
@Test(.serialized, arguments: ["alice", "bob", "charlie"])
func accountCreation(username: String) async throws {
    let account = try await AccountService().create(username: username)
    #expect(account.isActive)
}
```


## Confirmation for async events

When testing that an async event fires (e.g., a callback, notification, or stream value), use `confirmation()` from Swift Testing:

```swift
@Test func notificationFires() async {
    await confirmation { confirmed in
        // Start listening before posting, and yield to ensure
        // the for-await loop is actually iterating before the
        // notification is sent. Without the yield the post can
        // arrive before the listener is ready, making the test flaky.
        let task = Task {
            for await _ in NotificationCenter.default.notifications(named: .dataDidChange) {
                confirmed()
                break
            }
        }

        // Give the task a chance to reach its first suspension
        // inside the for-await loop.
        await Task.yield()

        NotificationCenter.default.post(name: .dataDidChange, object: nil)
        await task.value
    }
}
```

`confirmation()` fails the test if the closure is never called, replacing the old XCTest pattern of `XCTestExpectation` + `wait(for:timeout:)`.

**Important:** All async work being confirmed must complete before the `confirmation()` closure returns. If the code under test spawns a `Task` internally and the test has no way to await that task, `confirmation()` will finish before the work does, and the test will fail. Either make the production API `async` so the test can await it directly, or have it return its `Task` handle so the test can call `await task.value` before the closure ends.


## Actor isolation in tests

By default, Swift Testing runs tests on any executor it chooses. You can constrain this when testing code that requires specific actor isolation.

Mark individual tests or whole suites with `@MainActor` when the code under test requires main-actor isolation:

```swift
@MainActor
@Test func viewModelUpdatesOnMainActor() async {
    let vm = ViewModel()
    await vm.refresh()
    #expect(vm.items.isEmpty == false)
}
```

For finer control, `confirmation()` and `withKnownIssue()` both accept an `isolation` parameter. This runs just that closure on a specific actor while the rest of the test runs elsewhere:

```swift
@Test func loadingUpdatesUI() async {
    await confirmation(isolation: MainActor.shared) { confirmed in
        let vm = ViewModel(onUpdate: { confirmed() })
        await vm.load()
    }
}
```

Also be aware that test targets can have default actor isolation enabled at the module level (e.g., a default main-actor module). When reviewing test failures around isolation, check the target's build settings.


## Test scoping traits with `@TaskLocal`

**Requires Swift 6.1 or later.**

When multiple tests need a shared configuration (e.g., a mock environment or injected dependency), test scoping traits provide a concurrency-safe way to set it up using task-local values rather than shared mutable state.

Create a type conforming to `TestTrait` and `TestScoping`, then set the task-local value inside `provideScope()`:

```swift
struct MockEnvironmentTrait: TestTrait, TestScoping {
    func provideScope(
        for test: Test,
        testCase: Test.Case?,
        performing function: () async throws -> Void
    ) async throws {
        let env = Environment(apiBase: URL(string: "https://test.example.com")!)

        try await Environment.$current.withValue(env) {
            try await function()
        }
    }
}

extension Trait where Self == MockEnvironmentTrait {
    static var mockEnvironment: Self { Self() }
}
```

Then apply it to any test or suite:

```swift
@Test(.mockEnvironment) func fetchUsesTestAPI() async throws {
    // Environment.current is now the mock, scoped to this test's task.
    let users = try await UserService().fetchAll()
    #expect(users.isEmpty == false)
}
```

This avoids the concurrency hazards of a shared `setUp()` mutating global state. Each test's configuration lives in the task-local, so parallel tests get independent values automatically.


## Avoid timing-based tests

Never use `Task.sleep`, `Thread.sleep`, or fixed delays to "wait for something to happen." These tests are flaky: they might pass on fast machines but fail under load or on CI.

```swift
// BROKEN: Relies on timing.
@Test func dataLoads() async throws {
    viewModel.load()
    try await Task.sleep(for: .seconds(1))
    #expect(viewModel.items.isEmpty == false)
}
```

Instead, await the actual async operation:

```swift
// CORRECT: Awaits the real work.
@Test func dataLoads() async throws {
    await viewModel.load()
    #expect(viewModel.items.isEmpty == false)
}
```

If the API is callback-based, wrap it with `withCheckedContinuation` or use `confirmation()`.


## Testing cancellation

The goal is to verify that the *code under test* checks for cancellation, not just that `Task.checkCancellation()` works in a test harness. Design the test so the code under test is the thing that observes the cancellation flag.

A reliable approach: give the code under test a stream or signal it blocks on, cancel the task while it's suspended on that signal, then verify it exits with `CancellationError`:

```swift
@Test func processorRespectsCancel() async throws {
    // Processor.run() calls Task.checkCancellation() between items.
    // Feed it enough work that cancellation will be checked mid-flight.
    let processor = Processor(items: Array(repeating: .stub, count: 1_000))

    let task = Task {
        try await processor.run()
    }

    // Let the processor start, then cancel.
    try await Task.sleep(for: .zero)
    task.cancel()

    await #expect(throws: CancellationError.self) {
        try await task.value
    }
}
```

If the code under test is a `for await` loop, you can cancel the consuming task and verify the loop exits. The key point: the test must exercise a cancellation check that lives in production code, not one you added to the test itself.


## Race detection

It’s a good idea to enable Thread Sanitizer (TSan) in your test scheme to catch data races at runtime. TSan finds races that the compiler's static checks often miss, particularly in code using `@unchecked Sendable` or unsafe pointers.

In Xcode: Product → Scheme Edit Scheme → Diagnostics → Thread Sanitizer.

TSan adds overhead, so consider enabling it for a dedicated CI job rather than every local run.


## Swift Testing + Swift concurrency

For more help with Swift Testing, use the `guide-swift-testing` skill.

## unstructured

# Unstructured concurrency

## Task vs `Task.detached`

You should already know that `Task {}` inherits the caller's actor isolation, whereas `Task.detached {}` does not.

```swift
@MainActor
func example() {
    Task {
        // Still on MainActor; safe to update UI here.
        label.text = "Done"
    }

    Task.detached {
        // Not on MainActor; updating UI here is a bug.
        // Use this for genuinely independent background work.
    }
}
```

However, what you are less likely to know is this: `Task.detached` is rarely the right choice. 

Prefer `Task {}` with explicit isolation changes, or structured concurrency. Only use `Task.detached` when you specifically need to shed the caller's actor context and priority, and even then only if there are no better choices.


## Cancellation is cooperative

Always remember that cancelling a task does not stop its code – the task's body must check for cancellation explicitly.

```swift
func processItems(_ items: [Item]) async throws {
    for item in items {
        // Check before expensive work
        try Task.checkCancellation()
        await process(item)
    }
}
```

- `Task.checkCancellation()` throws `CancellationError` if cancelled.
- `Task.isCancelled` returns a Bool for non-throwing contexts.
- `task.cancel()` only sets the flag – it does not interrupt execution.

This means it’s important to ensure complex tasks regularly check for cancellation at safe intervals.

For legacy APIs that offer their own cancel mechanism, use `withTaskCancellationHandler` to bridge Swift's cooperative cancellation to the underlying API. See `cancellation.md` for details and examples.


## `Task.immediate` (Swift 6.2)

For `Task.immediate` details, see `new-features.md`. For most cases, regular `Task {}` is still the right choice.


## When `Task {}` is a code smell

Creating a `Task {}` to call an async function from a synchronous context is sometimes necessary (e.g., in a button action). But watch for these anti-patterns:

- **Task inside `onAppear()`**: Never create a `Task` inside a SwiftUI `onAppear()`. Use the `.task()` modifier instead, because it handles cancellation on disappear automatically.
- **Task to bridge sync → async in a function that could itself be async**: If the caller can be made async, do that instead of wrapping in `Task {}`.
- **Ignoring the return value of a throwing task**: The error is silently lost. At minimum, handle errors inside the task closure.

---
_Source: vabole/apple-skills v1.0.10 · `skills/guide-swift-concurrency/` · MIT (c) 2026 Ilia Abolhasani · Vendored 2026-05-14._
