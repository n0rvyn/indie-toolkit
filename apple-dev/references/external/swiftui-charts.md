# Swift Charts

## References

| Topic | Reference |
|-------|-----------|
| Marks, axes, selection, styling, composition, Chart3D | `references/charts.md` |
| Accessibility, VoiceOver, Audio Graph, custom descriptors | `references/charts-accessibility.md` |

### Charts Reference

SwiftUI Charts API reference covering marks, axes, selection, styling, composition, and Chart3D.

## Core APIs

### Import the Framework

Always check that the file imports `Charts` before using `Chart`, `Chart3D`, `BarMark`, `SectorMark`, or `ChartProxy`.

```swift
import SwiftUI
import Charts
```

### Chart Container

`Chart` is the root view. Add one or more marks inside it.

```swift
Chart(sales) { item in
    BarMark(
        x: .value("Month", item.month),
        y: .value("Revenue", item.revenue)
    )
}
```

### Data Models Should Be Identifiable

Prefer `Identifiable` models for chart data so identity stays stable as data changes.

```swift
struct SalesPoint: Identifiable {
    let id: UUID
    let month: String
    let revenue: Double
}
```

If your model cannot conform to `Identifiable`, provide an explicit id key path:

```swift
Chart(sales, id: \.month) { item in
    BarMark(
        x: .value("Month", item.month),
        y: .value("Revenue", item.revenue)
    )
}
```

### Plottable Values

Use `.value(_, _)` to describe what each axis value means. Those labels are reused by axes, legends, and accessibility.

```swift
LineMark(
    x: .value("Day", entry.date),
    y: .value("Steps", entry.count)
)
```

## Chart Types

### BarMark

```swift
BarMark(
    x: .value("Product", product.name),
    y: .value("Units", product.units)
)
```

Stacking via `MarkStackingMethod`: `.standard`, `.normalized`, `.center`, `.unstacked`.

### LineMark

```swift
LineMark(
    x: .value("Day", day.date),
    y: .value("Steps", day.count)
)
.interpolationMethod(.monotone)
```

Interpolation methods: `.linear`, `.monotone`, `.cardinal`, `.catmullRom`, `.stepStart`, `.stepCenter`, `.stepEnd`. Cardinal and Catmull-Rom accept optional tension/alpha parameters.

### AreaMark

```swift
AreaMark(
    x: .value("Hour", sample.hour),
    y: .value("Temperature", sample.value),
    stacking: .unstacked
)
```

Ranged areas use `yStart`/`yEnd` for bands like min/max or confidence intervals.

### PointMark

```swift
PointMark(
    x: .value("Time", measurement.time),
    y: .value("Value", measurement.value)
)
```

### RectangleMark

```swift
RectangleMark(
    xStart: .value("Start Day", cell.startDay),
    xEnd: .value("End Day", cell.endDay),
    yStart: .value("Low", cell.low),
    yEnd: .value("High", cell.high)
)
```

### RuleMark

```swift
RuleMark(y: .value("Goal", 10_000))
    .foregroundStyle(.red)
```

### SectorMark

Use `SectorMark` for pie and donut-style charts.

```swift
Chart(expenses) { expense in
    SectorMark(
        angle: .value("Amount", expense.amount),
        innerRadius: .ratio(0.6),
        angularInset: 2
    )
    .foregroundStyle(by: .value("Category", expense.category))
}
```

Use `innerRadius` to turn a pie chart into a donut chart, and `angularInset` to separate slices visually.

### Plot Types

Data-driven plot wrappers: `AreaPlot`, `BarPlot`, `LinePlot`, `PointPlot`, `RectanglePlot`, `RulePlot`, and `SectorPlot`.

`LinePlot` and `AreaPlot` also accept function closures for plotting mathematical functions without discrete data:

```swift
Chart {
    LinePlot(x: "x", y: "sin(x)") { x in
        sin(x)
    }
}
.chartXScale(domain: -Double.pi ... Double.pi)
.chartYScale(domain: -1.5 ... 1.5)
```

### Chart3D

`Chart3D` is a separate API for 3D chart content. It supports 3D `PointMark`, `RectangleMark`, `RuleMark`, and `SurfacePlot`.

```swift
Chart3D(points) { point in
    PointMark(
        x: .value("X", point.x),
        y: .value("Y", point.y),
        z: .value("Z", point.z)
    )
}
.chart3DPose(.front)
.chart3DCameraProjection(.perspective)
```

`SurfacePlot` visualizes mathematical surfaces by evaluating a two-variable function:

```swift
Chart3D {
    SurfacePlot(x: "x", y: "height", z: "z") { x, z in
        sin(x) * cos(z)
    }
}
.chartXScale(domain: -Double.pi ... Double.pi)
.chartZScale(domain: -Double.pi ... Double.pi)
```

Camera and pose configuration:

- **Projection**: `.chart3DCameraProjection(.orthographic)` (default, precise measurements) or `.perspective` (depth effect)
- **Pose presets**: `.chart3DPose(.default)`, `.front`, `.back`, `.left`, `.right`
- **Custom pose**: `.chart3DPose(azimuth: .degrees(45), inclination: .degrees(30))`
- On visionOS, Chart3D supports natural 3D interaction gestures for rotation and exploration

## Axis Tweaks

### Axis Visibility and Labels

```swift
Chart(data) { item in
    BarMark(
        x: .value("Month", item.month),
        y: .value("Revenue", item.revenue)
    )
}
.chartXAxis(.visible)
.chartYAxis(.hidden)
.chartXAxisLabel("Month")
.chartYAxisLabel("Revenue")
```

### Custom Axis Marks

```swift
Chart(steps) { day in
    LineMark(
        x: .value("Day", day.date),
        y: .value("Steps", day.count)
    )
}
.chartXAxis {
    AxisMarks(
        preset: .aligned,
        position: .bottom,
        values: .stride(by: .day)
    ) {
        AxisGridLine()
        AxisTick(length: .label)
        AxisValueLabel(format: .dateTime.weekday(.abbreviated))
    }
}
```

Useful `AxisMarks` inputs:

- `preset`: `.automatic`, `.extended`, `.aligned`, `.inset`
- `position`: `.automatic`, `.leading`, `.trailing`, `.top`, `.bottom`
- `values`: `.automatic`, `.automatic(desiredCount:)`, `.stride(by:)`, `.stride(by:count:)`, or an explicit array

### Axis Components

Within `AxisMarks`, combine the built-in axis components as needed:

```swift
AxisGridLine()
AxisTick()
AxisValueLabel()
```

`AxisValueLabel` can be tuned for dense axes:

```swift
AxisValueLabel(
    collisionResolution: .greedy(minimumSpacing: 8),
    orientation: .vertical
)
```

Label orientations: `.automatic`, `.horizontal`, `.vertical`, `.verticalReversed`.

Collision strategies: `.automatic`, `.greedy`, `.greedy(priority:minimumSpacing:)`, `.truncate`, `.disabled`.

### Axis Domains and Plot Area Tweaks

```swift
Chart(data) { item in
    LineMark(
        x: .value("Index", item.index),
        y: .value("Score", item.score)
    )
}
.chartXScale(domain: 0...30)
.chartYScale(domain: 0...100)
.chartPlotStyle { plotArea in
    plotArea
        .background(.gray.opacity(0.08))
}
```

### Scrollable Axes

```swift
@State private var scrollX = 7

Chart(data) { item in
    BarMark(
        x: .value("Day", item.day),
        y: .value("Value", item.value)
    )
}
.chartScrollableAxes(.horizontal)
.chartXVisibleDomain(length: 7)
.chartScrollPosition(x: $scrollX)
```

## Selection APIs

### Single-Value Selection

Use `chartXSelection(value:)` or `chartYSelection(value:)` for one selected value.

```swift
@State private var selectedDate: Date?

Chart(steps) { day in
    LineMark(x: .value("Day", day.date), y: .value("Steps", day.count))

    if let selectedDate {
        RuleMark(x: .value("Selected Day", selectedDate))
            .foregroundStyle(.secondary)
    }
}
.chartXSelection(value: $selectedDate)
```

### Range Selection

Use `chartXSelection(range:)` or `chartYSelection(range:)` for a dragged range. Bind to a `ClosedRange`.

```swift
@State private var selectedWeeks: ClosedRange<Int>?

Chart(weeks) { week in
    BarMark(x: .value("Week", week.index), y: .value("Revenue", week.revenue))
}
.chartXSelection(range: $selectedWeeks)
```

### Angle Selection

Use `chartAngleSelection(value:)` with `SectorMark` charts.

```swift
@State private var selectedAmount: Double?

Chart(expenses) { expense in
    SectorMark(angle: .value("Amount", expense.amount))
        .foregroundStyle(by: .value("Category", expense.category))
}
.chartAngleSelection(value: $selectedAmount)
```

**Important**: Selection bindings return the plottable axis value, not the full data element. Map back to your model if you need the selected record.

## Annotations

```swift
BarMark(
    x: .value("Month", item.month),
    y: .value("Revenue", item.revenue)
)
.annotation(position: .top) {
    Text(item.revenue.formatted())
}
```

Common positions include `.overlay`, `.top`, `.bottom`, `.leading`, and `.trailing`.

## ChartProxy and Custom Touch Handling

Use `chartOverlay`/`chartBackground` or `chartGesture` with `ChartProxy` when built-in selection modifiers are not enough.

```swift
.chartOverlay { proxy in
    GeometryReader { geometry in
        Rectangle().fill(.clear).contentShape(Rectangle())
            .gesture(
                DragGesture(minimumDistance: 0)
                    .onChanged { value in
                        guard let plotFrame = proxy.plotFrame else { return }
                        let frame = geometry[plotFrame]
                        let x = value.location.x - frame.origin.x
                        guard x >= 0, x <= frame.size.width else { return }
                        selectedDate = proxy.value(atX: x, as: Date.self)
                    }
                    .onEnded { _ in selectedDate = nil }
            )
    }
}
```

`ChartProxy` gives you lower-level access to:

- `value(atX:as:)`, `value(atY:as:)` for converting gesture coordinates into chart values
- `position(forX:)`, `position(forY:)` for placing custom overlays
- `selectXValue(at:)`, `selectYValue(at:)`, `selectXRange(from:to:)` for driving built-in selection
- `plotFrame` with `plotSize` for coordinate conversion

## Modifier Scope

Apply chart-wide modifiers to the `Chart` container and mark-specific modifiers to the individual mark.

```swift
Chart(data) { item in
    LineMark(
        x: .value("Day", item.date),
        y: .value("Value", item.value)
    )
    .interpolationMethod(.monotone)   // Mark-level modifier
}
.chartXAxis { AxisMarks() }            // Chart-level modifier
.chartYScale(domain: 0...100)          // Chart-level modifier
.chartPlotStyle { $0.background(.thinMaterial) }
```

## Styling and Visual Channels

### Categorical Coloring

Use `foregroundStyle(by: .value(...))` to color marks by a data property. Swift Charts generates a legend automatically.

**Avoid** applying `.foregroundStyle(.red)` per mark for categorical data — this suppresses the automatic legend and breaks accessibility.

### Custom Color Scales

```swift
.chartForegroundStyleScale([
    "North": .blue,
    "South": .orange,
    "East": .green
])
```

### Legend Control

```swift
.chartLegend(.visible)
.chartLegend(.hidden)
.chartLegend(position: .bottom, alignment: .center)
```

## Composing Multiple Marks

```swift
// Line with points
LineMark(x: .value("Day", day.date), y: .value("Steps", day.count))
    .interpolationMethod(.monotone)
PointMark(x: .value("Day", day.date), y: .value("Steps", day.count))

// Bars with threshold line
BarMark(x: .value("Month", item.month), y: .value("Revenue", item.revenue))
RuleMark(y: .value("Target", 10_000))
    .foregroundStyle(.red)
    .lineStyle(StrokeStyle(dash: [5, 3]))
```

## Animating Chart Data

Chart marks animate automatically when data identity is stable and changes are wrapped in an animation.

**Always** use `Identifiable` models (or explicit `id:`) so Swift Charts can match old and new data points and animate transitions between them.

## Best Practices

### Do
- Use semantic `.value(_, _)` labels so axes and accessibility read clearly
- Prefer `Identifiable` models for stable chart data identity
- Use `foregroundStyle(by:)` for categorical series to get automatic legends and accessibility
- Use `RuleMark` for goals, thresholds, and selected-value indicators
- Use explicit `AxisMarks(values:)` when automatic tick generation gets crowded
- Use `chartXScale` and `chartYScale` when you need stable visual comparisons
- Use `chartXSelection(range:)` for brushed selection

### Don't
- Put chart-wide modifiers such as `chartXAxis` or `chartXSelection` on individual marks
- Apply manual `.foregroundStyle(.color)` per mark for categorical data — use `foregroundStyle(by:)` instead
- Rely on unstable identities when chart data can be inserted, removed, or reordered
- Assume selection returns a model object; it only returns the plottable axis value

### Charts Accessibility

Swift Charts provides built-in accessibility support. VoiceOver users get three rotor actions automatically:

- **Describe Chart** — overview of axes and data series
- **Audio Graph** — sonification where pitch represents data values
- **Chart Detail** — interactive mode for exploring individual data points

#### Meaningful Labels

**Always** use clear, descriptive strings in `.value(_, _)` calls. These labels are read by VoiceOver and used in the Audio Graph.

```swift
// Good — descriptive labels
LineMark(
    x: .value("Date", entry.date),
    y: .value("Daily Steps", entry.count)
)

// Bad — generic labels
LineMark(
    x: .value("X", entry.date),
    y: .value("Y", entry.count)
)
```

#### Custom Audio Graphs

For advanced accessibility, conform your chart view to `AXChartDescriptorRepresentable` and implement `makeChartDescriptor()`.

```swift
struct StepsChart: View, AXChartDescriptorRepresentable {
    let steps: [DailySteps]

    var body: some View {
        Chart(steps) { day in
            LineMark(x: .value("Date", day.date), y: .value("Steps", day.count))
        }
        .accessibilityChartDescriptor(self)
    }

    func makeChartDescriptor() -> AXChartDescriptor {
        // Return AXChartDescriptor with axes and series descriptions
    }
}
```

#### Summary Checklist

- [ ] `import Charts` is present in files using chart types
- [ ] Chart data models use `Identifiable` (or `Chart(data, id:)` is provided)
- [ ] All chart families are represented with the correct mark type
- [ ] Axes use `AxisMarks` when default ticks are too dense or unclear
- [ ] `chartXScale` or `chartYScale` is set when fixed domains matter
- [ ] Chart-wide modifiers are applied to `Chart`, not individual marks
- [ ] `foregroundStyle(by:)` used for categorical series (not manual per-mark colors)
- [ ] `.value()` labels are descriptive for VoiceOver and Audio Graph accessibility

#### WWDC Sessions

- [Hello Swift Charts](https://developer.apple.com/videos/play/wwdc2022/10136/) (WWDC 2022) — introduction to the framework
- [Swift Charts: Raise the bar](https://developer.apple.com/videos/play/wwdc2022/10137/) (WWDC 2022) — marks, composition, customization
- [Explore pie charts and interactivity in Swift Charts](https://developer.apple.com/videos/play/wwdc2023/10037/) (WWDC 2023) — SectorMark, selection, scrolling
- [Swift Charts: Vectorized and function plots](https://developer.apple.com/videos/play/wwdc2024/10155/) (WWDC 2024) — LinePlot, AreaPlot, function plotting
- [Bring Swift Charts to the third dimension](https://developer.apple.com/videos/play/wwdc2025/313/) (WWDC 2025) — Chart3D, SurfacePlot, 3D marks

_Source: vabole/apple-skills v1.0.10 · `skills/guide-swiftui-charts/` · MIT (c) 2026 Ilia Abolhasani · Vendored 2026-05-14._
