# Dimension 6: Execution Quality (执行质量)

**Core question:** Is the technical debt within one person's control, and is the codebase appropriately engineered (not over or under)?

## Universal Sub-Questions

1. **Architecture health:** Are there tech debt signals (massive files, circular dependencies, TODO/FIXME density)?
2. **Dependency burden:** How many third-party dependencies? Are any unmaintained or risky?
3. **Over-engineering detection:** Is there premature abstraction, unused infrastructure, or enterprise patterns in an indie codebase?
4. **Completeness:** Feature completeness vs. polish level -- is the core solid or half-finished?

## Platform-Specific Sub-Questions

### Default

5. **Maintenance burden:** Can one person realistically keep this running (platform updates, dependency updates, bug fixes)?

### iOS

> iOS core question variant: Can one person keep pace with Apple's annual platform cadence without burning out?

5. **WWDC maintenance burden:** Each June, Apple announces new iOS. How much annual forced maintenance does this app require (new APIs, deprecations, new device sizes, new capabilities)?
6. **SwiftUI vs UIKit choice:** Does the app's UI require capabilities that SwiftUI still doesn't fully support (e.g., precise text editing control, custom layout engines, advanced collection view behaviors)? If not, SwiftUI is appropriate regardless of app complexity. Evaluate based on specific UI requirements, not a simple/complex dichotomy.
7. **Apple framework reliance:** Is the app built on stable Apple frameworks, or does it depend on frameworks Apple frequently changes (e.g., StoreKit 1 -> 2, UIKit -> SwiftUI transitions)?
8. **App Review compliance:** Are there any features that sit in App Review grey zones (web views, payment links, API usage that could be restricted)?
9. **One-person cadence:** Given the codebase size and technology choices, can one developer realistically ship the September iOS update + features + bug fixes?
10. **Privacy label maintenance:** How complex are the app's privacy nutrition labels? More features and third-party SDKs = more labels to maintain and audit. Incorrect labels = App Review rejection risk.

## Evidence Sources

- Local: Code structure analysis, dependency count, TODO/FIXME grep, test coverage, file size distribution
- External: Technology choices vs. category norms, update frequency, changelog quality

## Scoring Anchors

| Score | Anchor |
|-------|--------|
| ★ | Severe tech debt; fragile architecture; unmaintainable by one person |
| ★★ | Significant issues but functional; over-engineered or under-tested; risky dependencies |
| ★★★ | Adequate quality; some debt but manageable; appropriate engineering level |
| ★★★★ | Clean architecture; minimal debt; good dependency choices; one person can maintain confidently |
| ★★★★★ | Exemplary for indie scale; tight codebase; zero unnecessary complexity; sustainable indefinitely |
