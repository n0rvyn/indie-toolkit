// Fixture: the KNOWN-CLEAN arm. Every detector must stay silent here (exit 0).
import SwiftUI
import Charts

// N1 negative: the lexicon-named chart uses Swift Charts.
struct Spark: View {
    let values: [Double]
    var body: some View {
        Chart(Array(values.enumerated()), id: \.offset) { item in
            LineMark(x: .value("i", item.offset), y: .value("v", item.element))
        }
    }
}

// N1 false-positive guard (the arm4 SparkleIcon lesson): an icon drawing a Path
// in the CLEAN arm. If N1 reports a violation here, the gate must go red.
struct ChevronIcon: View {
    var body: some View {
        Path { p in
            p.move(to: CGPoint(x: 0, y: 0))
            p.addLine(to: CGPoint(x: 6, y: 6))
            p.addLine(to: CGPoint(x: 0, y: 12))
        }
        .stroke(.secondary, lineWidth: 1.5)
    }
}

enum LoadPhase { case idle, loading, loaded, failed }

// N2 negative: the @State has a write point — the branches are reachable.
struct PhaseScreen: View {
    @State private var phase: LoadPhase = .idle
    var body: some View {
        content.task { phase = .loaded }
    }
    @ViewBuilder private var content: some View {
        switch phase {
        case .idle: Text("idle")
        case .loading: ProgressView()
        case .loaded: Text("done")
        case .failed: Text("failed")
        }
    }
}

// N3 negative: normal insets, no safe-area override.
struct HomeScreen: View {
    var body: some View {
        ScrollView {
            Text("content")
                .padding(.top, 12)
        }
    }
}
