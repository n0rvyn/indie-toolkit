# Dimension 2: Journey Completeness (逻辑闭环)

**Core question:** Is the core user journey simple enough that one person can maintain it, and complete enough that users don't hit dead ends?

## Universal Sub-Questions

1. **Entry -> Core action -> Result -> Retention:** Does each stage connect without friction?
2. **Data lifecycle:** Create -> Use -> Update -> Delete/Archive -- is the full cycle implemented?
3. **Complexity budget:** How many distinct screens/states exist? Can one developer hold the entire flow in their head?
4. **First-run experience:** Can a new user reach the "aha moment" without a tutorial?

## Platform-Specific Sub-Questions

### Default

5. **Exception paths:** Can users recover from errors? Do empty states provide guidance instead of blank screens?

### iOS

> iOS core question variant: Does the core journey use iOS platform capabilities naturally, or is it reinventing OS-level functionality?

5. **OS wheel reinvention:** Is any part of this app rebuilding what Shortcuts, Widgets, ShareSheet, or system apps already do? If yes, what's the justification?
6. **Platform integration depth:** Does the journey use iOS-native patterns (SwiftUI navigation, system share sheet, Spotlight indexing, Handoff) or fight against them?
7. **Widget/Shortcut extension:** Could the core action be a Widget or Shortcut Action instead of a full app? If yes, should it be?
8. **Notification-driven retention:** Does the retention loop use notifications appropriately, or does it rely on users remembering to open the app?
9. **Cross-device journey:** If user has iPhone + iPad + Mac, does the journey span devices naturally via iCloud/Handoff?

## Evidence Sources

- Local: View/screen navigation graph, state machine completeness, error handling coverage, empty state implementations
- External: Onboarding flow analysis, user reviews mentioning confusion or missing features

## Scoring Anchors

| Score | Anchor |
|-------|--------|
| ★ | Core journey has dead ends or broken states; users can't complete basic tasks |
| ★★ | Happy path works but exceptions crash or confuse; missing data lifecycle stages |
| ★★★ | Core journey complete; some edge cases unhandled; manageable complexity |
| ★★★★ | Tight journey with good error recovery; complexity well within one-person capacity |
| ★★★★★ | Elegant minimal journey; every state accounted for; zero dead ends |
