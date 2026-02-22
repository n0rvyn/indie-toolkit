# Dimension 2: Journey Completeness (逻辑闭环)

**Core question:** Is the core user journey simple enough that one person can maintain it, and complete enough that users don't hit dead ends?

## Universal Sub-Questions

1. **Entry -> Core action -> Result -> Retention:** Does each stage connect without friction?
2. **Data lifecycle:** Create -> Use -> Update -> Delete/Archive -- is the full cycle implemented?
3. **Complexity budget:** How many distinct screens/states exist? Can one developer hold the entire flow in their head?
4. **First-run experience:** Can a new user reach the "aha moment" without a tutorial?
5. **Completion feedback:** When the user completes the core action, what feedback do they receive? (Visual, haptic, sound) Is there a sense of accomplishment or just a state change?
6. **Empty/error state narrative:** Do empty states and error messages guide users toward action, or just display technical information?
7. **Progression path:** Is there a visible path from beginner to proficient user? Does the product reveal capabilities progressively as the user's skill grows?

## Platform-Specific Sub-Questions

### Default

8. **Exception paths:** Can users recover from errors? Do empty states provide guidance instead of blank screens?

### iOS

> iOS core question variant: Does the core journey use iOS platform capabilities naturally, or is it reinventing OS-level functionality?

8. **OS wheel reinvention:** Is any part of this app rebuilding what Shortcuts, Widgets, ShareSheet, or system apps already do? If yes, what's the justification?
9. **Platform integration depth:** Does the journey use iOS-native patterns (SwiftUI navigation, system share sheet, Spotlight indexing, Handoff) or fight against them?
10. **Widget/Shortcut extension:** Could the core action be a Widget or Shortcut Action instead of a full app? If yes, should it be?
11. **Notification-driven retention:** Does the retention loop use notifications appropriately, or does it rely on users remembering to open the app?
12. **Cross-device journey:** If user has iPhone + iPad + Mac, does the journey span devices naturally via iCloud/Handoff?

## Evidence Sources

- Local: View/screen navigation graph, state machine completeness, error handling coverage, empty state implementations
- External: Onboarding flow analysis, user reviews mentioning confusion or missing features

## Scoring Anchors

| Score | Anchor |
|-------|--------|
| ★ | Core journey has dead ends or broken states; users can't complete basic tasks |
| ★★ | Happy path works but exceptions crash or confuse; missing data lifecycle stages |
| ★★★ | Core journey complete; some edge cases unhandled; manageable complexity |
| ★★★★ | Tight journey with good error recovery and feedback at key moments; complexity well within one-person capacity |
| ★★★★★ | Elegant minimal journey; every state tells a clear story; zero dead ends; completion feedback creates satisfaction |
