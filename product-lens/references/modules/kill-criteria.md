# Kill Criteria

**Purpose:** Indie developers' biggest enemy is sunk cost fallacy. Every evaluation auto-generates concrete "stop if" conditions.

## Generation Rules

1. Each criterion must be **verifiable** -- not "if it doesn't work out" but "if [specific measurable condition]"
2. Include a **timeframe** where applicable -- "if after 3 months of launch, [condition]"
3. Derive criteria from the weakest dimensions (scored <=2 stars)
4. Always include at least one **external trigger** (market event, competitor action, platform change)
5. Generate 3-5 criteria total

## Output Format

```markdown
## Kill Criteria

Stop conditions (if any one is met, reconsider continuing):
1. **[Label]:** [Verifiable condition with timeframe]
2. **[Label]:** [External trigger condition]
3. **[Label]:** [Metric-based condition]
```

## Platform Additions

### iOS

Add these triggers when evaluating an iOS app:

1. **Apple announces competing feature at WWDC** -- If Apple builds the core feature into iOS, the app loses its reason to exist within 3-6 months
2. **App Review rejects core functionality** -- If the core feature depends on an API or mechanism that App Review blocks, and no workaround exists without gutting the product
3. **Category winner with network effects** -- If a single app dominates the category through network effects (social/marketplace dynamics) and your app lacks network effects
4. **Apple Intelligence absorption** -- If on-device ML features in a future iOS version can replicate the core value proposition without a third-party app
