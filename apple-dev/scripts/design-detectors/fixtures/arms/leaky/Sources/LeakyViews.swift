// Fixture: the KNOWN-DEFECTIVE arm. Every detector must HIT here (exit 1).
// Each defect below renders pixel-identically to a correct build — that is the point.
import SwiftUI

// N1 positive: a lexicon-named chart component drawing with Path, no Charts import.
struct Spark: View {
    let values: [Double]
    var body: some View {
        Path { p in
            p.move(to: .zero)
            for (i, v) in values.enumerated() {
                p.addLine(to: CGPoint(x: Double(i) * 8, y: v))
            }
        }
        .stroke(.teal, lineWidth: 2)
    }
}

// N1 false-positive guard: a legitimate icon MAY draw a Path. If N1 flags this,
// the component-lexicon scoping regressed (the arm4 SparkleIcon lesson).
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

// N2 positive: a four-branch @State that is never written. Only .idle is reachable.
struct PhaseScreen: View {
    @State private var phase: LoadPhase = .idle
    var body: some View {
        switch phase {
        case .idle: Text("idle")
        case .loading: ProgressView()
        case .loaded: Text("done")
        case .failed: Text("failed")
        }
    }
}

// N3 positive: platform inset switched off AND the prototype bezel's clearance
// hardcoded in its place, in the same View.
struct HomeScreen: View {
    var body: some View {
        ScrollView {
            Text("content")
                .padding(.top, 64)
                .padding(.bottom, 100)
        }
        .ignoresSafeArea()
    }
}
