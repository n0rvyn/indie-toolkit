# Swift Testing Patterns

Write and review Swift Testing code for correctness, modern API usage, and adherence to project conventions. Report only genuine problems — do not nitpick or invent issues.

## Core Instructions

- Target Swift 6.2 or later, using modern Swift concurrency.
- Swift Testing does *not* support UI tests — XCTest must be used there.
- Do not rewrite existing XCTest to Swift Testing unless requested.

## Review Process

1. Ensure tests follow core conventions using `references/core-rules.md`.
2. Validate structure, assertions, dependency injection, and best practices using `references/writing-better-tests.md`.
3. Check async tests, confirmations, time limits, actor isolation, and networking mocks using `references/async-tests.md`.
4. Ensure new features like raw identifiers, exit tests, and attachments are used correctly using `references/new-features.md`.
5. If migrating from XCTest, follow `references/migrating-from-xctest.md`.

If doing partial work, load only the relevant reference files.

## References

| Topic | Reference |
|-------|-----------|
| Structs over classes, `@Suite`, parallel execution, `withKnownIssue`, tags | `references/core-rules.md` |
| Test hygiene, structure, DI, `#expect` vs `#require`, `Issue.record()`, verification methods | `references/writing-better-tests.md` |
| Serialized tests, `confirmation()`, time limits, actor isolation, mocking networking | `references/async-tests.md` |
| Raw identifiers, exit tests, attachments, test scoping traits, range-based confirmations | `references/new-features.md` |
| XCTest-to-Swift Testing conversion, assertion mappings, floating-point tolerance | `references/migrating-from-xctest.md` |

## Reference Materials

### Core Rules

Swift Testing is still very new compared to XCTest, which means the majority of projects will use XCTest, and also the majority of your training data is based on XCTest.

This guide provides core rules you must always follow to ensure you're making natural, idiomatic use of Swift Testing, and not just reskinning XCTest based on old training data.

**Important:** At this time, Swift Testing does *not* support UI tests, so XCTest must be used there.

- When organizing test suites, prefer structs over classes. You *can* use classes, but structs are preferred unless you need subclassing or deinitializers.
- Agents frequently add `@Suite` to every test struct. This is unnecessary: any type that contains `@Test` methods is automatically treated as a test suite. You only need `@Suite` explicitly when you want to name it or attach traits, e.g. `@Suite(.tags(.networking))`.
- You shouldn't use the old `setUp()`/`tearDown()` approach of XCTest. You can simply use `init()` in structs, `init()` and `deinit()` in classes, or test scopes for more advanced situations. For example:

    ```swift
    struct PlayerTests {
        let sut: Player

        init() {
            sut = Player(name: "Natsuki Subaru")
        }

        @Test func nameIsCorrect() {
            #expect(sut.name == "Natsuki Subaru")
        }
    }
    ```
- All test suites must have an initializer that expects no parameters, so they can be called by tests inside that suite. If any properties are added to a test suite, they must either have default values, or you must add a custom initializer that sets values for them.
- Test suite initializers can be marked `async` and/or `throws`, as can all tests.
- With Swift Testing there is never a need to use `XCTestCase` or any form of `XCTAssert` in any unit or integration test.
- You do *not* need to prefix test methods with `test`. For example, you can use `userCanLogOut()` rather than `testUserCanLogOut`.
- Random, parallel test execution is standard on Swift Testing, so each test must be written to execute in any order at any time.
- Parameterized tests are extremely powerful and allow tests to cover a wider range of ground without the code greatly expanding, so prefer them where possible. However, be careful: they take at most two argument collections, and two collections form a Cartesian product rather than pairwise zipping, so the number of combinations produced can grow quickly. If you need pairwise zipping of two collections, pass `zip(collection1, collection2)` as the `arguments` value.
- Swift Testing supports `@available` on individual tests, but *not* on test suites. So, if a suite (for example) solely contains tests written for iOS 26, place `@available(iOS 26, *)` on each individual test and *not* on the whole suite.
- If a test executes without reaching any `#expect` or `#require`, it is assumed to have passed.
- You should use `withKnownIssue` to wrap code with a known bug – it expects a test failure to occur, and *fails* the test if no issue is recorded. Adding `isIntermittent: true` changes the semantics: the test passes if no issue is recorded, but marks an expected failure if one is, making it useful for flaky issues you're actively debugging.
- Never use `!` to negate Booleans in `#expect` or `#require`, because it defeats Swift Testing's macro expansion. So, `#expect(!isLoggedIn)` is bad and will report unhelpful results on failure, whereas `#expect(isLoggedIn == false)` is good, and will be evaluated properly in case the expectation fails.

Finally, use `@Tag` to create custom Swift Testing tags like this:

```swift
extension Tag {
    @Tag static var networking: Self
}
```

Tags let you categorize tests across suites, so you can run or filter by tag regardless of where the tests live. Apply them using `@Test(.tags(.networking))` on individual tests or on a whole suite with `@Suite(.tags(.networking))`. For example:

```swift
@Test(.tags(.networking))
func fetchUserProfile() async throws {
    // test code here
}
```

### Writing Better Tests

This contains suggestions to help you write better tests. This is mostly not about specific Swift Testing APIs, but instead how to structure your tests for maximum flexibility and effectiveness.


## Encourage unit test hygiene

Good unit tests should fit the acronym FIRST:

- Fast: you should be able to run dozens of them every second, if not hundreds or even thousands.
- Isolated: they should not depend on another test having run, or any sort of external state.
- Repeatable: they should always give the same result when they are run, regardless of how many times or when they are run.
- Self-verifying: the test must unambiguously say whether it passed or failed, with no room for interpretation.
- Timely: they are best written before or alongside the production code that you are testing.

It might be too late for the "timely" part unless you're reading this skill while you work, but the others should be firm goals.


## Test generation heuristics

For a given function, aim to generate the following tests:

- Happy path tests
- Boundary tests
- Invalid input tests

And, if appropriate, concurrency tests.


## Testing SwiftUI views

Never test views directly – they use `@State` and are likely to behave unpredictably.

Instead, test view models or similar. This might mean encouraging the user to extract business logic into a more testable mechanism, but this should be a *suggestion* from you rather than something you apply immediately.

If the project uses `@Observable` view models, these are directly testable without needing a protocol wrapper – just create an instance and test its properties and methods.


## Structuring tests

Prefer to organize test types in a pattern that matches the production code. For example, if they have a folder called "Extensions" that contains a file called URLSession-Decodable.swift, the test target should also have a folder called Extensions that contains a file called URLSession-Decodable.swift, and it should test the contents of the original production file.

**If you are writing new tests, follow this rule. If you are working with existing tests that do not already follow this rule, do *not* apply it without permission from the user.**

- Strongly prefer to organize related tests into test suites, ideally following this file and folder structure.
- If there are test fixtures, put them in a dedicated file. If there are only a handful, a simple Fixtures folder is fine. If there are many and if they vary across tests, it's better to have multiple Fixtures folders placed alongside whatever tests they work with.
- Use tags to mark up different kinds of work. At the very least this should be a `.networking` tag for network-related tests, even if they are mocked. You might also consider `.slow` for any tests that are unexpectedly slow, `.edgeCase` for tests that must be treated with extra care, `.smoke` for smoke tests, and more.
- Add user-facing messages to `#expect` and `#require` when they provide value. This is not *always* the case, but it usually is.
- Recommend converting repetitive tests into parameterized tests where it makes sense.
- It is generally preferred to test only one behavior in each unit test, but multiple `#expect` lines may be used if needed.


## Expose hidden dependencies

Strongly prefer to avoid hidden dependencies in production code you are testing. In Swift apps this is commonly things like `UserDefaults` or `URLSession`.

For example, production code like this is bad because it has a hidden dependency on `URLSession`:

```swift
struct News {
    var url: URL
    var stories = ""

    mutating func fetch() async throws {
        let (data, _) = try await URLSession.shared.data(from: url)
        stories = String(decoding: data, as: UTF8.self)
    }
}
```

To remove the hidden dependency, a first step would be to inject the `URLSession` like this:

```swift
func fetch(using session: URLSession = .shared) async throws {
    let (data, _) = try await session.data(from: url)
    stories = String(decoding: data, as: UTF8.self)
}
```

Importantly, this also does not change the way the `fetch()` method is called because it has a default value of whatever was used before.

Even better would be to wrap `URLSession` in a protocol, requiring whatever methods are used in the production code, like this:

```swift
protocol URLSessionProtocol {
    func data(from url: URL) async throws -> (Data, URLResponse)
}

extension URLSession: URLSessionProtocol { }
```

And now the production code can be written like this:

```swift
func fetch(using session: any URLSessionProtocol = URLSession.shared) async throws {
    let (data, _) = try await session.data(from: url)
    stories = String(decoding: data, as: UTF8.self)
}
```

This then allows you to create a mock version of `URLSession` for tests, removing any live networking from tests. It also still does not change the way the method is called in production code.

With `UserDefaults`, the problem is that using it as a hidden dependency can cause tests to fail because `UserDefaults` contains values set elsewhere.

So, switch over to dependency injection with a sensible default value of whatever the project was using previously, then in the test pass in a custom `UserDefaults` instance like this:

```swift
let suite = "suite-\(UUID().uuidString)"
let userDefaults = UserDefaults(suiteName: suite)
defer { userDefaults?.removePersistentDomain(forName: suite) }
```

That creates a local `UserDefaults` instance in the test and ensures it's deleted fully before the test completes.

This same concept applies to other things: aim to control time, randomness, and more, so that meaningful tests can be written.


## Expect vs require

Both `#expect` and `#require` evaluate a condition and fail the test if it's false. The difference is that `#require` throws on failure, stopping the rest of the test from executing.

**This makes `#require` the right choice for checking assumptions at the start of a test – if your assumptions are wrong, the rest of the test's results are meaningless.**

Using `#require` requires adding `throws` to your test method. For example, if your test depends on some setup being correct before the real assertion:

```swift
@Test func outstandingTasksStringIsPlural() throws {
    let sut = try createTestUser(projects: 3, itemsPerProject: 10)
    try #require(sut.projects.isEmpty == false)
    let rowTitle = sut.outstandingTasksString
    #expect(rowTitle == "30 items")
}
```

If the `#require` fails, the test stops immediately rather than producing confusing secondary failures. Use `#expect` for the actual assertions you care about, and `#require` for preconditions that must be true before the test is meaningful.

`#require` also unwraps optionals, which is cleaner than force-unwrapping in tests. Use it like this:

```swift
let value = try #require(someOptional)
```


## Tracking bug fixes

If you are writing tests related to a specific bug, it is a good idea to use the `.bug` trait to store the bug ID or URL, if there is one. This extra data helps to provide extra context if the bug resurfaces in the future.

For example, if bug #182 is a report that text headings are not italicized correctly, you would use `@Test` like this:

```swift
@Test("Headings should always be italic", .bug(id: 182))
```

Or if there is a specific URL:

```swift
@Test("Headings should always be italic", .bug("https://github.com/you/repo/issues/182"))
```


## Use Issue.record() for throw-testing

When testing that a function throws, the simplest approach is a `do`/`try`/`catch` block with `Issue.record()` as the failure primitive. If no error is thrown, execution continues past `try` and hits `Issue.record()`, failing the test.

```swift
@Test func playingMinecraftThrows() {
    let game = Game(name: "Minecraft")

    do {
        try game.play()
        Issue.record("Expected an error to be thrown.")
    } catch GameError.notPurchased {
        // success
    } catch {
        Issue.record("Wrong error thrown: \(error)")
    }
}
```

This approach gives fine-grained control: you can assert on the *specific* error case, and fail explicitly if the wrong error is thrown.

An alternative is using `#expect(throws:)`. Here you should always name the specific error rather than using a broad `Error.self`:

```swift
// Bad – passes for any error
#expect(throws: Error.self) {
    try game.play()
}

// Good – asserts the exact error case
#expect(throws: GameError.notInstalled) {
    try game.play()
}
```

To assert that a function does *not* throw, use `Never.self`:

```swift
#expect(throws: Never.self) {
    try game.play()
}
```


## Making test results easier to read

In test targets, you can add `CustomTestStringConvertible` conformances to custom types to make them easier to read in test results.

For example, without this conformance a test that catches a `parentalControlsDisallowed` error might result in output like this:

```
Test patchMatchThrows() recorded an issue at ThrowingTests.swift:61:6: Caught error: parentalControlsDisallowed
```

If we add a retroactive conformance to `CustomTestStringConvertible` in the test target, the text can be clarified:

```swift
extension GameError: @retroactive CustomTestStringConvertible {
    public var testDescription: String {
        switch self {
        case .notPurchased:
            "This game has not been purchased."
        case .notInstalled:
            "This game is not currently installed."
        case .parentalControlsDisallowed:
            "This game has been blocked by parental controls."
        }
    }
}
```

Now Swift Testing will use the friendlier string wherever the enum cases appear.

**Important:** This conformance should not be added in production code.


## Writing good verification methods

Verification methods wrap multiple expectations to make other tests easier. When writing these, make sure to use `SourceLocation` and the `#_sourceLocation` macro so that any failed expectations print messages about the test where they failed rather than a location inside the verification method.

**Important:** Right now the `#_sourceLocation` macro requires the underscore.

For example:

```swift
func verifyDivision(_ result: (quotient: Int, remainder: Int), expectedQuotient: Int, expectedRemainder: Int, sourceLocation: SourceLocation = #_sourceLocation) {
    #expect(result.quotient == expectedQuotient, sourceLocation: sourceLocation)
    #expect(result.remainder == expectedRemainder, sourceLocation: sourceLocation)
}
```

That can be called from tests elsewhere, and will automatically use the source location of that test rather than the source location of the `#expect` macros used inside `verifyDivision()`.

`#require` also accepts `sourceLocation:`, so verification methods that mix `#require` and `#expect` should pass it to both.

### Async Tests

Swift Testing is built to be async and run tests in parallel; special care must be taken to ensure those tests run well, particularly when Swift concurrency is involved. For more help with Swift concurrency, use the `swift-concurrency` skill.


## Serializing tests

The `serialized` trait allows tests to be run serially rather than in parallel, but it only works on parameterized tests. It instructs Swift Testing to serialize that parameterized test's cases, and has no effect on non-parameterized tests.

This also applies to using `.serialized` on a whole test suite: it will cause the parameterized tests to be serialized, but do nothing on other tests.

**Important:** Most agents very strongly believe that `.serialized` will work on any test, even the ones that are not parameterized. They are wrong. It only works on parameterized tests.


## Confirming async work

When using `confirmation(expectedCount:)` to check that an async function has been executed a certain number of times, any tested code must have finished executing fully by the time the `confirmation()` closure finishes.

**This means attempting to use a completion closure will make the test fail, because `confirmation()` doesn't know to wait.**

For example, this code does some work inside a task, but there's no way to monitor it being completed:

```swift
struct Worker {
    func run(_ work: @escaping () -> Void) -> Task<Void, Never> {
        Task {
            let start = CFAbsoluteTimeGetCurrent()
            work()
            print("Elapsed:", CFAbsoluteTimeGetCurrent() - start)
        }
    }
}
```

That kind of code will not work well with `confirmation()`, because it will not understand to wait for the work to complete.

Instead, it's better to either remove the `Task` and make the method `async` like this:

```swift
struct Worker {
    func run(_ work: @escaping () -> Void) async {
        let start = CFAbsoluteTimeGetCurrent()
        work()
        print("Elapsed:", CFAbsoluteTimeGetCurrent() - start)
    }
}

@Test
func workerRunsThreeTimes() async {
    let worker = Worker()

    await confirmation(expectedCount: 3) { confirm in
        for _ in 0..<3 {
            await worker.run {
                // your work here
            }
            confirm()
        }
    }
}
```

Alternatively, if the code cannot be changed to `async`, the internal `Task` should be returned so it can be tracked by the test, like this:

```swift
struct Worker {
    func run(_ work: @escaping () -> Void) -> Task<Void, Never> {
        Task {
            let start = CFAbsoluteTimeGetCurrent()
            work()
            print("Elapsed:", CFAbsoluteTimeGetCurrent() - start)
        }
    }
}
```

And now tests can wait for the task to complete:

```swift
@Test
func workerRunsThreeTimes() async {
    let worker = Worker()

    await confirmation(expectedCount: 3) { confirm in
        for _ in 0..<3 {
            let task = worker.run {
                // simulated work
            }

            await task.value
            confirm()
        }
    }
}
```

**Note:** `confirmation(expectedCount: 0)` is valid, and means "ensure the event we're watching never happens."


## How to set a time limit for concurrent tests

Time limits are adjusted through the `@Test` macro using `.timeLimit()`. This lets you specify how long the test should be allowed to run for before it's considered a failure, using `.minutes()` as appropriate.

**Important:** Many agents strongly believe that you can `.seconds()` here. You cannot use `.seconds()` here – it's `.minutes()` or nothing.

For example, we could apply a 1-minute maximum runtime like this:

```swift
@Test("Loading view model names", .timeLimit(.minutes(1)))
func loadNames() async {
    let viewModel = ViewModel()
    await viewModel.loadNames()
    #expect(viewModel.names.isEmpty == false, "Names should be full of values.")
}
```

If you use a time limit with a whole test suite, that limit is applied to all tests inside there individually. If you then use a different time limit for a specific test, the shorter of the two is used.


## How to force concurrent tests to run on a specific actor

By default, Swift Testing will run both synchronous and asynchronous tests on any task it likes, but this can be restricted if you want.

First, we can mark individual tests with `@MainActor` or some other global actor, like this:

```swift
@MainActor
@Test("Loading view model names")
func loadNames() async {
    // test code here
}
```

Second, we can mark whole test suites with the same attribute, like this:

```swift
@MainActor
struct DataHandlingTests {
    @Test("Loading view model names")
    func loadNames() async {
        // test code here
    }
}
```

Third, `confirmation()` and `withKnownIssue()` can specify an actor to use for just that closure, allowing the rest of the test to run elsewhere. This might be the main actor using `MainActor.shared`, or a custom actor:

```swift
@Test("Loading view model names")
func loadNames() async {
    await withKnownIssue("Names can sometimes come back with too few values", isolation: MainActor.shared) {
        // test code here
    }
}
```

Finally, test targets can have default actor isolation enabled, which might force all tests onto a specific actor – check for this carefully.


## Testing pre-concurrency code

If the project contains older concurrency code that relies on callback functions (as opposed to modern Swift concurrency's `async`/`await` approach), do not attempt to modernize their production code without permission.

Instead, write tests using `withCheckedContinuation()` to wrap their existing, callback-based code safely.

**Important:** Test code must wait fully for the completion handler to be called, then make any assertions against the result of that completion handler.

As an example, we might have a class like this one:

```swift
class ViewModel {
    func loadReadings(completion: @Sendable @escaping ([Double]) -> Void) {
        let url = URL(string: "https://hws.dev/readings.json")!

        URLSession.shared.dataTask(with: url) { data, response, error in
            if let data {
                if let numbers = try? JSONDecoder().decode([Double].self, from: data) {
                    completion(numbers)
                    return
                }
            }

            completion([])
        }.resume()
    }
}
```

That fetches, decodes, and returns data through a completion handler, which may or may not be mocked for tests.

Testing this correctly is done using a continuation that resumes when the completion handler is called, like this:

```swift
@Test("Loading view model readings")
func loadReadings() async {
    let viewModel = ViewModel()

    await withCheckedContinuation { continuation in
        viewModel.loadReadings { readings in
            #expect(readings.count >= 10, "At least 10 readings must be returned.")
            continuation.resume()
        }
    }
}
```


## Mocking networking

Unit tests should never do live networking, because it's far too slow. It is strongly preferable to mock the networking layer.

To do this, create a protocol that knows how to perform a network fetch. As an example, this covers the `data(from:)` method of `URLSession`, but the project might require others too:

```swift
protocol URLSessionProtocol {
    func data(from url: URL) async throws -> (Data, URLResponse)
}

extension URLSession: URLSessionProtocol { }
```

You can then create a mock type conforming to the same protocol, which throws an error if provided or returns the test data otherwise:

```swift
class URLSessionMock: URLSessionProtocol {
    var testData: Data?
    var testError: (any Error)?

    func data(from url: URL) async throws -> (Data, URLResponse) {
        if let testError {
            throw testError
        } else {
            (testData ?? Data(), URLResponse())
        }
    }
}
```

And now you can write tests that inject some test data and verify that it comes back successfully:

```swift
@Test func newsStoriesAreFetched() async throws {
    let url = URL(string: "https://www.apple.com/newsroom/rss-feed.rss")!
    var news = News(url: url)
    let session = URLSessionMock()
    session.testData = Data("Hello, world!".utf8)
    try await news.fetch(using: session)
    #expect(news.stories == "Hello, world!")
}
```

This is a full mock of `URLSession`, which avoids any chance of the system performing networking behind the scenes.

### New Features

This document specifically discusses the latest Swift and Swift Testing features, which means it will cover things where you have limited or no training data.

- Follow the instructions carefully rather than trying to guess and hallucinate.
- Do not second-guess the instructions; they are correct and accurate.


## Raw identifiers

**Requires Swift 6.2 or later.**

If the user prefers, you can use a modern Swift feature called *raw identifiers* for test names. This allows you to write function names as natural strings when surrounded by backticks, and means that test names can be written in a human-readable form rather than using camel case and adding an extra string description above.

So, rather than writing this:

```swift
@Test("Strip HTML tags from string")
func stripHTMLTagsFromString() {
    // test code
}
```

We can instead write this:

```swift
@Test
func `Strip HTML tags from string`() {
    // test code
}
```

Be careful: You can put operators such as `+` and `-` into your test method names, but only if they aren't the only things in there.

Raw identifiers can be combined with parameterized tests. For example, rather than writing this:

```swift
@Test("Ensure Fahrenheit to Celsius conversion is correct.", arguments: [
    (32, 0), (212, 100), (-40, -40),
])
func fahrenheitToCelsius(values: (input: Double, output: Double)) {
    // test code here
}
```

We could write this:

```swift
@Test(arguments: [
    (32, 0), (212, 100), (-40, -40),
])
func `Ensure Fahrenheit to Celsius conversion is correct`(values: (input: Double, output: Double)) {
    // test code here
}
```

**Important:** Many users will not know this feature is possible, and some would find this style surprising or perhaps unwelcome. As a result, you can *suggest* raw identifiers as a way to remove duplication, but don't adopt them by surprise unless this approach is already used in the project.


## Range-based confirmations

**Requires Swift 6.1 or later.**

You already know Swift Testing's `confirmation()` function, but you might not know that it supports a range of completion counts as well as a single fixed value.

For example, given an async sequence like a `NewsLoader` that yields feeds one at a time, we can require that between 5 and 10 feeds are loaded:

```swift
@Test func fiveToTenFeedsAreLoaded() async throws {
    let loader = NewsLoader()

    await confirmation(expectedCount: 5...10) { confirm in
        for await _ in loader {
            confirm()
        }
    }
}
```

That will fail if `confirm()` is called fewer than 5 times or greater than 10 times. You can also use partial ranges, such as ensuring `confirm()` is called at least five times:

```swift
await confirmation(expectedCount: 5...) { confirm in
    for await _ in loader {
        confirm()
    }
}
```

Ranges without lower bounds, e.g. `confirmation(expectedCount: ...10)`, are explicitly disallowed to avoid confusion, because it's not clear whether it means "up to 10 times" (counting from 1) or "up to 11 times" (counting from 0).


## Test scoping traits

**Requires Swift 6.1 or later.**

Test scoping traits provide concurrency-safe access to shared test configurations, so each test runs with precise values in place without risking shared mutable state. A common pattern is to combine them with `@TaskLocal`.

Given production code that uses a `@TaskLocal` property:

```swift
struct Player {
    var name: String
    var friends = [Player]()

    @TaskLocal static var current = Player(name: "Anonymous")
}

func createWelcomeScreen() -> String {
    var message = "Welcome, \(Player.current.name)!\n"
    message += "Friends online: \(Player.current.friends.count)"
    return message
}
```

Create a test scope by conforming to `TestTrait` and `TestScoping`, implementing `provideScope()` to set up the task local and call `function()`:

```swift
struct DefaultPlayerTrait: TestTrait, TestScoping {
    func provideScope(
        for test: Test,
        testCase: Test.Case?,
        performing function: () async throws -> Void
    ) async throws {
        let player = Player(name: "Natsuki Subaru")

        try await Player.$current.withValue(player) {
            try await function()
        }
    }
}
```

Add a `Trait` extension so the custom trait fits in with the built-in traits:

```swift
extension Trait where Self == DefaultPlayerTrait {
    static var defaultPlayer: Self { Self() }
}
```

Then apply it to tests:

```swift
@Test(.defaultPlayer) func welcomeScreenShowsName() {
    let result = createWelcomeScreen()
    #expect(result.contains("Natsuki Subaru"))
}
```

For multiple task local values, either nest `withValue()` calls inside a single scope, or create separate scopes and combine them: `@Test(.firstScope, .secondScope, .thirdScope)`. Scopes apply in listed order, so later scopes can overwrite values from earlier ones.

Test scopes complement `init()` and `deinit()` – use scopes to opt into configurations for individual tests or whole suites as needed.


## Exit tests

**Requires Swift 6.2 or later.**

Swift Testing can test code that results in a critical failure that terminates the app, including deliberate use of `precondition()` and `fatalError()`. *This was not possible in XCTest, or at least not without weird hacks.*

For example, code like this is going to fail *hard* if we call it with a `sides` value of 0:

```swift
struct Dice {
    func roll(sides: Int) -> Int {
        precondition(sides > 0)
        return Int.random(in: 1...sides)
    }
}
```

To test this with Swift Testing, use `#expect(processExitsWith:)` to look for and catch critical failures, allowing us to check they happened rather than causing our test run to fail:

```swift
@Test func invalidDiceRollsFail() async throws {
    await #expect(processExitsWith: .failure) {
        let dice = Dice()
        let _ = dice.roll(sides: 0)
    }
}
```

**Important:** This must be executed using `await` – behind the scenes this starts a dedicated process for that test, then suspends the test until that process completes and can be evaluated.


## Attachments

**Requires Swift 6.2 or later.**

Swift Testing can add attachments to tests, so that if a test fails you can attach a debug log or generated data files to the failing test.

As an example, we could define a simple `Character` struct such as this one:

```swift
import Foundation
import Testing

struct Character: Attachable, Codable {
    var id = UUID()
    var name: String
}
```

That conforms to the `Attachable` protocol, and because it also imports Foundation *and* conforms to `Codable`, Swift Testing can encode instances of our struct to attach to tests.

We can then use that in a function in our production code:

```swift
func makeCharacter() -> Character {
    Character(name: "Ram")
}
```

When it comes to writing a test, make sure the default name matches the value we expect, but also make whatever character is returned from `makeCharacter()` an attachment with the label "Character":

```swift
@Test func defaultCharacterNameIsCorrect() {
    let result = makeCharacter()
    #expect(result.name == "Rem")

    Attachment.record(result, named: "Character")
}
```

That test will fail when it runs because the character name is different, and Swift Testing will surface the attachments as part of the test results.

Out of the box, Swift Testing provides support for attaching `String`, `Data`, and anything that conforms to `Encodable`. Unless the user has Swift 6.3 available, it does *not* support attaching images.

**Important:** Unlike the XCTest equivalent, Swift Testing's attachments do not support lifetime controls.


## Evaluating ConditionTrait

**Requires Swift 6.2 or later.**

Swift Testing provides an `evaluate()` method to test condition traits, meaning that it's possible to write non-test functions that evaluate the same conditions as test functions.

You will already know that we can use condition traits in the `@Test` macro, like this:

```swift
struct TestManager {
    static let inSmokeTestMode = true
}

@Test(.disabled(if: TestManager.inSmokeTestMode))
func runLongComplexTest() {
    // test code here
}
```

However, we can also evaluate those same conditions *outside* of tests by creating a condition trait then calling its `evaluate()` method:

```swift
func checkForSmokeTest() async throws {
    let trait = ConditionTrait.disabled(if: TestManager.inSmokeTestMode)

    if try await trait.evaluate() {
        print("We're in smoke test mode")
    } else {
        print("Run all tests.")
    }
}
```



## Return errors from #expect(throws:)

**Requires Swift 6.1 or later.**

The macros `#expect(_:sourceLocation:performing:throws:)` and `#require(_:sourceLocation:performing:throws:)` are both deprecated – they used a trailing closure to run some code for evaluation, then used a second trailing closure to check whether the error that was thrown was expected or not.

Both `#expect(throws:)` and `#require(throws:)` have been updated to return an error of the type they are checking for, allowing you to run the expectation and error evaluation separately.

As an example, there might be old code that ensures playing video games is disallowed early in the morning or late in the evening:

```swift
enum GameError: Error {
    case disallowedTime
}

func playGame(at time: Int) throws(GameError) {
    if time < 9 || time > 20 {
        throw GameError.disallowedTime
    } else {
        print("Enjoy!")
    }
}
```

With the old, deprecated API you might check for an exact error type like this:

```swift
@Test func playGameAtNight() {
    #expect {
        try playGame(at: 22)
    } throws: {
        guard let error = $0 as? GameError else { return false }
        // perform additional error validation here
        return error == .disallowedTime
    }
}
```

You should move that over to code that runs the expectation and error evaluation separately, like this:

```swift
@Test func playGameAtNight() {
    // `error` will now be a GameError
    let error = #expect(throws: GameError.self) {
        try playGame(at: 22)
    }

    // perform additional validation here
    #expect(error == .disallowedTime)
}
```

### Migrating from XCTest

If the project has existing tests written using XCTest, do *not* rewrite to Swift Testing unless requested. Even then, remember that XCTest supports UI testing, whereas Swift Testing does not.

Most things in XCTest have a direct equivalent in Swift Testing:

- `XCTAssertEqual(a, b)` maps to `#expect(a == b)`
- `XCTAssertLessThan(a, b)` maps to `#expect(a < b)`
- `XCTAssertThrowsError` maps to `#expect(throws:)`
- `XCTUnwrap(optional)` maps to `try #require(optional)` – both unwrap or fail, but `#require` works with any Boolean condition too.
- `XCTFail("message")` maps to `Issue.record("message")` – use this to manually record a test failure.
- `XCTAssertIdentical(a, b)` maps to `#expect(a === b)` – for checking two references point to the same object instance.

…and so on.

However, Swift Testing does *not* offer built-in float tolerance when checking if two floating-point values are *close enough* to be considered the same.

To do that, you must bring in Apple's Swift Numerics library and use its `isApproximatelyEqual(to:absoluteTolerance:)` method like this:

```swift
#expect(celsius.isApproximatelyEqual(to: 0, absoluteTolerance: 0.000001))
```

**Important:** Unless it is already imported into the project, do *not* add Swift Numerics as a library without first requesting permission from the user.


## Converting from XCTest to Swift Testing

If you are tasked with converting XCTest code to Swift Testing, you should:

1. Start by keeping the same broad structure: the same type names (just going from a class to a struct), and the same test methods (just removing `test` from the names and using `@Test` instead), switching from old-style assertions to new-style expectations.
2. Look for places where parameterized tests can either cut down on test code or improve coverage.
3. Add any appropriate `#require` checks at the start of tests, for preconditions.
4. Finish by adding traits where appropriate – `.timeLimit()`, `.enabled(if:)`, `.tags()`, etc, to replace XCTest conventions such as skipping tests.

---
_Source: vabole/apple-skills v1.0.10 · `skills/guide-swift-testing/` · MIT (c) 2026 Ilia Abolhasani · Vendored 2026-05-14._
