# Dimension 5: Moat (护城河)

**Core question:** What stops a well-funded competitor or AI from replicating this in a weekend?

## Universal Sub-Questions

1. **Taste moat:** Is the product's quality a result of opinionated design that's hard to copy without the same sensibility?
2. **Data accumulation:** Do users build up valuable data over time that increases switching costs?
3. **Domain expertise:** Does the product encode rare domain knowledge that competitors would need years to acquire?
4. **Network effects:** Does more users = better product? (Rare for indie apps, but powerful if present)

## Platform-Specific Sub-Questions

### Default

5. **General AI replacement risk:** If ChatGPT/Claude capabilities advance, does this product still provide value that a conversation with AI cannot?
6. **Platform AI absorption risk:** Could Apple Intelligence or Google AI build this into the OS as a system feature?

### iOS

> iOS core question variant: What's the Sherlock risk, and what platform-depth advantages does this app have that Apple and big competitors can't easily replicate?

7. **Sherlock risk assessment:** What is the probability Apple builds this into the next iOS? Historical pattern: f.lux -> Night Shift, Duet -> Sidecar, battery apps -> Battery Health, flashlight apps -> Control Center. Does this app's core feature fit the pattern of "obvious utility Apple hasn't gotten to yet"?

   **Sherlock risk scoring methodology:**

   | Factor | Low Risk (1) | Medium Risk (2) | High Risk (3) |
   |--------|-------------|-----------------|----------------|
   | Feature type | Creative/professional tool | Productivity tool | Quality-of-life utility |
   | Android equivalent | No built-in equivalent | Partial equivalent | Fully built-in |
   | Recent WWDC signals | No related sessions | Adjacent technology shown | Directly related API introduced |
   | Apple hiring | No signals | Related domain roles | Specific feature-area roles |
   | Complexity | Requires deep domain expertise | Moderate complexity | Simple, well-defined scope |

   Sum factors: 5-7 = Low Sherlock risk, 8-11 = Medium, 12-15 = High.

8. **Platform integration depth:** Which iOS-exclusive APIs does this use (HealthKit, ARKit, CoreML, CallKit, WidgetKit, App Intents)? Deeper integration = harder to replicate on other platforms and harder for cross-platform competitors.
9. **CloudKit data lock-in:** Is user data stored in CloudKit (private database)? CloudKit data = high migration cost = strong retention moat.
10. **Ecosystem integration:** Does the app benefit from Apple ecosystem (Watch complication, Mac Catalyst/iPad, ShareSheet, Siri Shortcuts)? More touch points = stickier.
11. **AI disruption on iOS:** Can Apple Intelligence or on-device ML features absorb this app's core function?

## Evidence Sources

- Local: Data model complexity, domain-specific logic, unique algorithms, user data storage patterns
- External: AI tool landscape in this category, competitor feature velocity, platform risk signals

## Scoring Anchors

| Score | Anchor |
|-------|--------|
| ★ | Pure feature play; AI or a weekend project could replicate; no switching costs |
| ★★ | Minor taste advantage; some user data but easily exported; AI could approximate |
| ★★★ | Meaningful taste or domain moat; moderate data accumulation; AI augments but doesn't replace |
| ★★★★ | Strong domain expertise encoded; significant user data lock-in; AI-resistant core value |
| ★★★★★ | Multiple moat layers; deep data + domain + taste; competitors would need to match years of iteration |
