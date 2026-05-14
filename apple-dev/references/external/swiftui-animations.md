# SwiftUI Animations

## References

| Topic | Reference |
|-------|-----------|
| Core concepts, implicit/explicit, timing, performance | `references/animation-basics.md` |
| Transitions for view insertion/removal, Animatable protocol | `references/animation-transitions.md` |
| Transactions, phase/keyframe animations, `@Animatable` macro | `references/animation-advanced.md` |

### Animation Basics

Core animation concepts, implicit vs explicit animations, timing curves, and performance patterns.

## Core Concepts

State changes trigger view updates. SwiftUI provides mechanisms to animate these changes.

**Animation Process:**
1. State change triggers view tree re-evaluation
2. SwiftUI compares new tree to current render tree
3. Animatable properties are identified and interpolated (~60 fps)

**Key Characteristics:**
- Animations are additive and cancelable
- Always start from current render tree state
- Blend smoothly when interrupted

## Implicit Animations

Use `.animation(_:value:)` to animate when a specific value changes.

```swift
// GOOD - uses value parameter
Rectangle()
    .frame(width: isExpanded ? 200 : 100, height: 50)
    .animation(.spring, value: isExpanded)
    .onTapGesture { isExpanded.toggle() }
```

## Explicit Animations

Use `withAnimation` for event-driven state changes.

```swift
// GOOD - explicit animation
Button("Toggle") {
    withAnimation(.spring) {
        isExpanded.toggle()
    }
}
```

**When to use which:**
- **Implicit**: Animations tied to specific value changes, precise view tree scope
- **Explicit**: Event-driven animations (button taps, gestures)

## Animation Placement

Place animation modifiers after the properties they should animate.

```swift
// GOOD - animation after properties
Rectangle()
    .frame(width: isExpanded ? 200 : 100, height: 50)
    .foregroundStyle(isExpanded ? .blue : .red)
    .animation(.default, value: isExpanded)  // Animates both

// BAD - animation before properties
Rectangle()
    .animation(.default, value: isExpanded)  // Too early!
    .frame(width: isExpanded ? 200 : 100, height: 50)
```

## Selective Animation

Animate only specific properties using multiple animation modifiers or scoped animations.

```swift
// Multiple animation modifiers
Rectangle()
    .frame(width: isExpanded ? 200 : 100, height: 50)
    .animation(.spring, value: isExpanded)  // Animate size
    .foregroundStyle(isExpanded ? .blue : .red)
    .animation(nil, value: isExpanded)  // Don't animate color

// Scoped animation
Rectangle()
    .foregroundStyle(isExpanded ? .blue : .red)  // Not animated
    .animation(.spring) {
        $0.frame(width: isExpanded ? 200 : 100, height: 50)  // Animated
    }
```

## Timing Curves

### Built-in Curves

| Curve | Use Case |
|-------|----------|
| `.spring` | Interactive elements, most UI |
| `.easeInOut` | Appearance changes |
| `.bouncy` | Playful feedback |
| `.linear` | Progress indicators only |

### Modifiers

```swift
.animation(.default.speed(2.0), value: flag)  // 2x faster
.animation(.default.delay(0.5), value: flag)  // Delayed start
.animation(.default.repeatCount(3, autoreverses: true), value: flag)
```

### Good vs Bad Timing

```swift
// GOOD - appropriate timing for interaction type
Button("Tap") {
    withAnimation(.spring(response: 0.3, dampingFraction: 0.7)) {
        isActive.toggle()
    }
}
.scaleEffect(isActive ? 0.95 : 1.0)

// BAD - too slow for button feedback
Button("Tap") {
    withAnimation(.easeInOut(duration: 1.0)) {  // Way too slow!
        isActive.toggle()
    }
}

// BAD - linear feels robotic
Rectangle()
    .animation(.linear(duration: 0.5), value: isActive)  // Mechanical
```

## Animation Performance

### Prefer Transforms Over Layout

```swift
// GOOD - GPU accelerated transforms
Rectangle()
    .frame(width: 100, height: 100)
    .scaleEffect(isActive ? 1.5 : 1.0)  // Fast
    .offset(x: isActive ? 50 : 0)        // Fast
    .rotationEffect(.degrees(isActive ? 45 : 0))  // Fast
    .animation(.spring, value: isActive)

// BAD - layout changes are expensive
Rectangle()
    .frame(width: isActive ? 150 : 100, height: isActive ? 150 : 100)  // Expensive
    .padding(isActive ? 50 : 0)  // Expensive
```

### Narrow Animation Scope

```swift
// GOOD - animation scoped to specific subview
VStack {
    HeaderView()  // Not affected
    ExpandableContent(isExpanded: isExpanded)
        .animation(.spring, value: isExpanded)  // Only this
    FooterView()  // Not affected
}

// BAD - animation at root
VStack {
    HeaderView()
    ExpandableContent(isExpanded: isExpanded)
    FooterView()
}
.animation(.spring, value: isExpanded)  // Animates everything
```

### Avoid Animation in Hot Paths

```swift
// GOOD - gate by threshold
.onPreferenceChange(ScrollOffsetKey.self) { offset in
    let shouldShow = offset.y < -50
    if shouldShow != showTitle {  // Only when crossing threshold
        withAnimation(.easeOut(duration: 0.2)) {
            showTitle = shouldShow
        }
    }
}

// BAD - animating every scroll change
.onPreferenceChange(ScrollOffsetKey.self) { offset in
    withAnimation {  // Fires constantly!
        self.offset = offset.y
    }
}
```

## Disabling Animations

```swift
// GOOD - disable with transaction
Text("Count: \(count)")
    .transaction { $0.animation = nil }

// GOOD - disable from parent context
DataView()
    .transaction { $0.disablesAnimations = true }

// BAD - hacky zero duration
Text("Count: \(count)")
    .animation(.linear(duration: 0), value: count)  // Hacky
```

## Debugging

```swift
// Slow down for inspection
#if DEBUG
.animation(.linear(duration: 3.0).speed(0.2), value: isExpanded)
#else
.animation(.spring, value: isExpanded)
#endif

// Debug modifier to log values
struct AnimationDebugModifier: ViewModifier, Animatable {
    var value: Double
    var animatableData: Double {
        get { value }
        set { value = newValue }
    }
    func body(content: Content) -> some View {
        content.opacity(value)
    }
}
```

### Quick Reference

#### Do
- Use `.animation(_:value:)` with value parameter
- Use `withAnimation` for event-driven animations
- Prefer transforms over layout changes
- Scope animations narrowly
- Choose appropriate timing curves

#### Don't
- Animate layout properties in hot paths
- Apply broad animations at root level
- Use linear timing for UI (feels robotic)
- Animate on every frame in scroll handlers

### Transitions

Transitions for view insertion/removal, custom transitions, and the Animatable protocol.

## Property Animations vs Transitions

**Property animations**: Interpolate values on views that exist before AND after state change.

**Transitions**: Animate views being inserted or removed from the render tree.

```swift
// Property animation - same view, different properties
Rectangle()
    .frame(width: isExpanded ? 200 : 100, height: 50)
    .animation(.spring, value: isExpanded)

// Transition - view inserted/removed
if showDetail {
    DetailView()
        .transition(.scale)
}
```

## Basic Transitions

### Critical: Transitions Require Animation Context

```swift
// GOOD - animation outside conditional
VStack {
    Button("Toggle") { showDetail.toggle() }
    if showDetail {
        DetailView()
            .transition(.slide)
    }
}
.animation(.spring, value: showDetail)

// GOOD - explicit animation
Button("Toggle") {
    withAnimation(.spring) {
        showDetail.toggle()
    }
}
if showDetail {
    DetailView()
        .transition(.scale.combined(with: .opacity))
}

// BAD - animation inside conditional (removed with view!)
if showDetail {
    DetailView()
        .transition(.slide)
        .animation(.spring, value: showDetail)  // Won't work on removal!
}

// BAD - no animation context
Button("Toggle") {
    showDetail.toggle()  // No animation
}
if showDetail {
    DetailView()
        .transition(.slide)  // Ignored - just appears/disappears
}
```

### Built-in Transitions

| Transition | Effect |
|------------|--------|
| `.opacity` | Fade in/out (default) |
| `.scale` | Scale up/down |
| `.slide` | Slide from leading edge |
| `.move(edge:)` | Move from specific edge |
| `.offset(x:y:)` | Move by offset amount |

### Combining Transitions

```swift
// Parallel - both simultaneously
.transition(.slide.combined(with: .opacity))

// Chained
.transition(.scale.combined(with: .opacity).combined(with: .offset(y: 20)))
```

## Asymmetric Transitions

Different animations for insertion vs removal.

```swift
// GOOD - different animations for insert/remove
if showCard {
    CardView()
        .transition(
            .asymmetric(
                insertion: .scale.combined(with: .opacity),
                removal: .move(edge: .bottom).combined(with: .opacity)
            )
        )
}
```

## Custom Transitions

Use the `Transition` protocol to define custom transitions.

```swift
struct BlurTransition: Transition {
    var radius: CGFloat

    func body(content: Content, phase: TransitionPhase) -> some View {
        content
            .blur(radius: phase.isIdentity ? 0 : radius)
            .opacity(phase.isIdentity ? 1 : 0)
    }
}

// Usage
.transition(BlurTransition(radius: 10))
```

### Good vs Bad Custom Transitions

```swift
// GOOD - reusable transition
if showContent {
    ContentView()
        .transition(BlurTransition(radius: 10))
}

// BAD - inline logic (won't animate on removal!)
if showContent {
    ContentView()
        .blur(radius: showContent ? 0 : 10)  // Not a transition
        .opacity(showContent ? 1 : 0)
}
```

## Identity and Transitions

View identity changes trigger transitions, not property animations.

```swift
// Triggers transition - different branches have different identities
if isExpanded {
    Rectangle().frame(width: 200, height: 50)
} else {
    Rectangle().frame(width: 100, height: 50)
}

// Triggers transition - .id() changes identity
Rectangle()
    .id(flag)  // Different identity when flag changes
    .transition(.scale)

// Property animation - same view, same identity
Rectangle()
    .frame(width: isExpanded ? 200 : 100, height: 50)
    .animation(.spring, value: isExpanded)
```

## The Animatable Protocol

Enables custom property interpolation during animations.

### Protocol Definition

```swift
protocol Animatable {
    associatedtype AnimatableData: VectorArithmetic
    var animatableData: AnimatableData { get set }
}
```

### Basic Implementation

```swift
// GOOD - explicit animatableData
struct ShakeModifier: ViewModifier, Animatable {
    var shakeCount: Double

    var animatableData: Double {
        get { shakeCount }
        set { shakeCount = newValue }
    }

    func body(content: Content) -> some View {
        content.offset(x: sin(shakeCount * .pi * 2) * 10)
    }
}

extension View {
    func shake(count: Int) -> some View {
        modifier(ShakeModifier(shakeCount: Double(count)))
    }
}

// Usage
Button("Shake") { shakeCount += 3 }
    .shake(count: shakeCount)
    .animation(.default, value: shakeCount)

// BAD - missing animatableData (silent failure!)
struct BadShakeModifier: ViewModifier {
    var shakeCount: Double
    // Missing animatableData! Uses EmptyAnimatableData

    func body(content: Content) -> some View {
        content.offset(x: sin(shakeCount * .pi * 2) * 10)
    }
}
// Animation jumps to final value instead of interpolating
```

### Multiple Properties with AnimatablePair

```swift
// AnimatablePair for two properties
struct ComplexModifier: ViewModifier, Animatable {
    var scale: CGFloat
    var rotation: Double

    var animatableData: AnimatablePair<CGFloat, Double> {
        get { AnimatablePair(scale, rotation) }
        set {
            scale = newValue.first
            rotation = newValue.second
        }
    }

    func body(content: Content) -> some View {
        content
            .scaleEffect(scale)
            .rotationEffect(.degrees(rotation))
    }
}

// Nested AnimatablePair for 3+ properties
struct ThreePropertyModifier: ViewModifier, Animatable {
    var x: CGFloat
    var y: CGFloat
    var rotation: Double

    var animatableData: AnimatablePair<AnimatablePair<CGFloat, CGFloat>, Double> {
        get { AnimatablePair(AnimatablePair(x, y), rotation) }
        set {
            x = newValue.first.first
            y = newValue.first.second
            rotation = newValue.second
        }
    }

    func body(content: Content) -> some View {
        content
            .offset(x: x, y: y)
            .rotationEffect(.degrees(rotation))
    }
}
```

Note: for new code, prefer the `@Animatable` macro over manual `AnimatablePair` boilerplate.

### Transitions Quick Reference

#### Do
- Place transitions outside conditional structures
- Use `withAnimation` or `.animation` outside the `if`
- Implement `animatableData` explicitly for custom Animatable
- Use `AnimatablePair` for multiple animated properties
- Use asymmetric transitions when insert/remove need different effects

#### Don't
- Put animation modifiers inside conditionals for transitions
- Forget `animatableData` implementation (silent failure)
- Use inline blur/opacity instead of proper transitions
- Expect property animation when view identity changes

### Advanced Animations

Transactions, phase animations, keyframe animations, completion handlers, and the `@Animatable` macro.

## Transactions

The underlying mechanism for all animations in SwiftUI.

### Basic Usage

```swift
// withAnimation is shorthand for withTransaction
withAnimation(.default) { flag.toggle() }

// Equivalent explicit transaction
var transaction = Transaction(animation: .default)
withTransaction(transaction) { flag.toggle() }
```

### The .transaction Modifier

```swift
Rectangle()
    .frame(width: flag ? 100 : 50, height: 50)
    .transaction { t in
        t.animation = .default
    }
```

### Animation Precedence

**Implicit animations override explicit animations** (later in view tree wins).

```swift
Button("Tap") {
    withAnimation(.linear) { flag.toggle() }
}
.animation(.bouncy, value: flag)  // .bouncy wins!
```

### Disabling Animations

```swift
// Prevent implicit animations from overriding
.transaction { t in
    t.disablesAnimations = true
}

// Remove animation entirely
.transaction { $0.animation = nil }
```

### Custom Transaction Keys

Pass metadata through transactions.

```swift
struct ChangeSourceKey: TransactionKey {
    static let defaultValue: String = "unknown"
}

extension Transaction {
    var changeSource: String {
        get { self[ChangeSourceKey.self] }
        set { self[ChangeSourceKey.self] = newValue }
    }
}

// Set source
var transaction = Transaction(animation: .default)
transaction.changeSource = "server"
withTransaction(transaction) { flag.toggle() }

// Read in view tree
.transaction { t in
    if t.changeSource == "server" {
        t.animation = .smooth
    } else {
        t.animation = .bouncy
    }
}
```

## Phase Animations

Cycle through discrete phases automatically. Each phase change is a separate animation.

### Basic Usage

```swift
// Triggered phase animation
Button("Shake") { trigger += 1 }
    .phaseAnimator(
        [0.0, -10.0, 10.0, -5.0, 5.0, 0.0],
        trigger: trigger
    ) { content, offset in
        content.offset(x: offset)
    }

// Infinite loop (no trigger)
Circle()
    .phaseAnimator([1.0, 1.2, 1.0]) { content, scale in
        content.scaleEffect(scale)
    }
```

### Enum Phases (Recommended for Clarity)

```swift
enum BouncePhase: CaseIterable {
    case initial, up, down, settle

    var scale: CGFloat {
        switch self {
        case .initial: 1.0
        case .up: 1.2
        case .down: 0.9
        case .settle: 1.0
        }
    }
}

Circle()
    .phaseAnimator(BouncePhase.allCases, trigger: trigger) { content, phase in
        content.scaleEffect(phase.scale)
    }
```

### Custom Timing Per Phase

```swift
.phaseAnimator([0, -20, 20], trigger: trigger) { content, offset in
    content.offset(x: offset)
} animation: { phase in
    switch phase {
    case -20: .bouncy
    case 20: .linear
    default: .smooth
    }
}
```

### Good vs Bad

```swift
// GOOD - use phaseAnimator for multi-step sequences
.phaseAnimator([0, -10, 10, 0], trigger: trigger) { content, offset in
    content.offset(x: offset)
}

// BAD - manual DispatchQueue sequencing
Button("Animate") {
    withAnimation(.easeOut(duration: 0.1)) { offset = -10 }
    DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
        withAnimation { offset = 10 }
    }
    DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
        withAnimation { offset = 0 }
    }
}
```

## Keyframe Animations

Precise timing control with exact values at specific times.

### Basic Usage

```swift
Button("Bounce") { trigger += 1 }
    .keyframeAnimator(
        initialValue: AnimationValues(),
        trigger: trigger
    ) { content, value in
        content
            .scaleEffect(value.scale)
            .offset(y: value.verticalOffset)
    } keyframes: { _ in
        KeyframeTrack(\.scale) {
            SpringKeyframe(1.2, duration: 0.15)
            SpringKeyframe(0.9, duration: 0.1)
            SpringKeyframe(1.0, duration: 0.15)
        }
        KeyframeTrack(\.verticalOffset) {
            LinearKeyframe(-20, duration: 0.15)
            LinearKeyframe(0, duration: 0.25)
        }
    }

struct AnimationValues {
    var scale: CGFloat = 1.0
    var verticalOffset: CGFloat = 0
}
```

### Keyframe Types

| Type | Behavior |
|------|----------|
| `CubicKeyframe` | Smooth interpolation |
| `LinearKeyframe` | Straight-line interpolation |
| `SpringKeyframe` | Spring physics |
| `MoveKeyframe` | Instant jump (no interpolation) |

### Multiple Synchronized Tracks

Tracks run **in parallel**, each animating one property.

```swift
// Bell shake with synchronized rotation and scale
struct BellAnimation {
    var rotation: Double = 0
    var scale: CGFloat = 1.0
}

Image(systemName: "bell.fill")
    .keyframeAnimator(
        initialValue: BellAnimation(),
        trigger: trigger
    ) { content, value in
        content
            .rotationEffect(.degrees(value.rotation))
            .scaleEffect(value.scale)
    } keyframes: { _ in
        KeyframeTrack(\.rotation) {
            CubicKeyframe(15, duration: 0.1)
            CubicKeyframe(-15, duration: 0.1)
            CubicKeyframe(10, duration: 0.1)
            CubicKeyframe(-10, duration: 0.1)
            CubicKeyframe(0, duration: 0.1)
        }
        KeyframeTrack(\.scale) {
            CubicKeyframe(1.1, duration: 0.25)
            CubicKeyframe(1.0, duration: 0.25)
        }
    }
```

### KeyframeTimeline

Query animation values directly for testing or non-SwiftUI use.

```swift
let timeline = KeyframeTimeline(initialValue: AnimationValues()) {
    KeyframeTrack(\.scale) {
        CubicKeyframe(1.2, duration: 0.25)
        CubicKeyframe(1.0, duration: 0.25)
    }
}

let midpoint = timeline.value(time: 0.25)
print(midpoint.scale)  // Value at 0.25 seconds
```

## Animation Completion Handlers

Execute code when animations finish.

### With withAnimation

```swift
Button("Animate") {
    withAnimation(.spring) {
        isExpanded.toggle()
    } completion: {
        showNextStep = true
    }
}
```

### With Transaction (For Reexecution)

```swift
// Completion fires on every trigger change
Circle()
    .scaleEffect(bounceCount % 2 == 0 ? 1.0 : 1.2)
    .transaction(value: bounceCount) { transaction in
        transaction.animation = .spring
        transaction.addAnimationCompletion {
            message = "Bounce \(bounceCount) complete"
        }
    }

// BAD - completion only fires ONCE (no value parameter)
Circle()
    .scaleEffect(bounceCount % 2 == 0 ? 1.0 : 1.2)
    .animation(.spring, value: bounceCount)
    .transaction { transaction in  // No value!
        transaction.addAnimationCompletion {
            completionCount += 1  // Only fires once, ever
        }
    }
```

## @Animatable Macro

The `@Animatable` macro auto-synthesizes `animatableData` from all animatable stored properties, eliminating verbose manual conformance. Use `@AnimatableIgnored` to exclude properties that should not animate.

### Before (Manual)

```swift
struct Wedge: Shape {
    var startAngle: Angle
    var endAngle: Angle
    var drawClockwise: Bool

    var animatableData: AnimatablePair<Double, Double> {
        get { AnimatablePair(startAngle.radians, endAngle.radians) }
        set {
            startAngle = .radians(newValue.first)
            endAngle = .radians(newValue.second)
        }
    }

    func path(in rect: CGRect) -> Path { /* ... */ }
}
```

### After (@Animatable)

```swift
@Animatable
struct Wedge: Shape {
    var startAngle: Angle
    var endAngle: Angle
    @AnimatableIgnored var drawClockwise: Bool

    func path(in rect: CGRect) -> Path { /* ... */ }
}
```

### When to Use
- **Prefer `@Animatable`** for any custom `Shape`, `AnimatableModifier`, or type conforming to `Animatable` with multiple properties
- **Use `@AnimatableIgnored`** for properties that control behavior but should not interpolate (e.g., directions, flags, identifiers)
- The macro works with any type conforming to `Animatable`, not just `Shape`

### Advanced Quick Reference

#### Transactions
- `withTransaction` is the explicit form of `withAnimation`
- Implicit animations override explicit (later in view tree wins)
- Use `disablesAnimations` to prevent override
- Use `.transaction { $0.animation = nil }` to remove animation
- Pass metadata through animation system via `TransactionKey`

#### Phase Animations
- Use for multi-step sequences returning to start
- Prefer enum phases for clarity
- Each phase change is a separate animation
- Use `trigger` parameter for one-shot animations

#### Keyframe Animations
- Use for precise timing control
- Tracks run in parallel
- Use `KeyframeTimeline` for testing/advanced use
- Prefer over manual DispatchQueue timing

#### Completion Handlers
- Use `withAnimation(.animation) { } completion: { }` for one-shot completion handlers
- Use `.transaction(value:)` for handlers that should refire on every value change
- Without `value:` parameter, completion only fires once

#### @Animatable Macro
- Use `@Animatable` to auto-synthesize `animatableData` from stored properties
- Use `@AnimatableIgnored` to exclude non-animatable properties
- Replaces verbose manual `animatableData` getters/setters

_Source: vabole/apple-skills v1.0.10 · `skills/guide-swiftui-animations/` · MIT (c) 2026 Ilia Abolhasani · Vendored 2026-05-14._
