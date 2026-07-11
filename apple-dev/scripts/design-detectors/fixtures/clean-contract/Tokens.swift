//  Tokens.swift
//  Runetic — design tokens, NATIVE MIRROR of design_handoff_runetic/tokens.css
//  ---------------------------------------------------------------------------
//  This file MIRRORS the web token store; it does NOT author new values.
//  When tokens.css changes, change this in lockstep. Views consume `Readiness` /
//  `RGlass` / `RType` / `RMotion` / `RLayout` — never paste a hex literal into a View.
//
//  Base system values (system colors, iOS Dynamic Type, spacing, radius) come
//  from the platform; only the Runetic-specific semantics are mirrored here.

import SwiftUI

// MARK: - Readiness

/// The single value that drives accent + wallpaper (constitution #3).
/// Do not add/rename/recolor cases without sign-off.
enum Readiness: String, CaseIterable {
    case recovery, normal, fatigue, warning

    var label: String {
        switch self {
        case .recovery: "已恢复"
        case .normal:   "可训练"
        case .fatigue:  "需谨慎"
        case .warning:  "建议休息"
        }
    }

    /// Primary accent — start of every gradient (ring, spark, wallpaper blob 1).
    var accent: Color {
        switch self {
        case .recovery: Color(hex: 0x34C759)   // system green
        case .normal:   Color(hex: 0x007AFF)   // system blue
        case .fatigue:  Color(hex: 0xFF9500)   // system orange
        case .warning:  Color(hex: 0xFF3B30)   // system red
        }
    }

    /// Secondary accent — end of every gradient.
    var accent2: Color {
        switch self {
        case .recovery: Color(hex: 0x00C7BE)   // mint
        case .normal:   Color(hex: 0x5856D6)   // indigo
        case .fatigue:  Color(hex: 0xFF6B9D)   // pink
        case .warning:  Color(hex: 0xFF2D55)   // pink
        }
    }

    /// Text color for copy sitting DIRECTLY on the wallpaper.
    var onWallpaper: Color {
        switch self {
        case .recovery: Color(hex: 0x0A3520)
        case .normal:   Color(hex: 0x0A1A3A)
        case .fatigue:  Color(hex: 0x3A1A05)
        case .warning:  .white          // the only ink-text-on-dark state
        }
    }

    /// Chip / pill fill sitting on the wallpaper. Mirrors --r-*-chip-bg.
    var chipBg: Color {
        switch self {
        case .recovery: Color(white: 1, opacity: 0.55)
        case .normal:   Color(white: 1, opacity: 0.55)
        case .fatigue:  Color(white: 1, opacity: 0.55)
        case .warning:  Color(white: 1, opacity: 0.18)
        }
    }

    var accentGradient: LinearGradient {
        LinearGradient(colors: [accent, accent2],
                       startPoint: .topLeading, endPoint: .bottomTrailing)
    }
}

// MARK: - Wallpaper
//  RECIPE, not a flat token. The web builder is shared.jsx::wpFromState (3 radial
//  blobs over a linear base). On iOS 26 rebuild as a MeshGradient — see
//  DESIGN.md "Platform Mapping". These are the per-state blob + base colors,
//  both schemes: base (light) + baseDark.

extension Readiness {
    /// 3 blob colors, ordered, for a MeshGradient (light scheme).
    var wallpaperBlobs: [Color] {
        switch self {
        case .recovery: [Color(hex: 0xA4F4C0), Color(hex: 0x7CE6E0), Color(hex: 0xFFE38A)]
        case .normal:   [Color(hex: 0x7CB3FF), Color(hex: 0xB5A2FF), Color(hex: 0xE5C8FF)]
        case .fatigue:  [Color(hex: 0xFFC078), Color(hex: 0xFF9C80), Color(hex: 0xFFD8A0)]
        case .warning:  [Color(hex: 0xFF3B30), Color(hex: 0xFF6B9D), Color(hex: 0x9B4DFF)]
        }
    }

    /// Linear base stops under the blobs — LIGHT scheme. Mirrors --wp-*-base.
    var wallpaperBase: [Color] {
        switch self {
        case .recovery: [Color(hex: 0xD5F7DE), Color(hex: 0xE5F5C8), Color(hex: 0xC7F0EA)]
        case .normal:   [Color(hex: 0xD6E5FF), Color(hex: 0xE0D8FF), Color(hex: 0xF5E8FF)]
        case .fatigue:  [Color(hex: 0xFFE3C4), Color(hex: 0xFFD3CC), Color(hex: 0xFFE9B5)]
        case .warning:  [Color(hex: 0x3A0B14), Color(hex: 0x5A1530), Color(hex: 0x2A0A28)]
        }
    }

    /// Linear base stops under the blobs — DARK scheme. Mirrors --wp-*-base-dark.
    var wallpaperBaseDark: [Color] {
        switch self {
        case .recovery: [Color(hex: 0x05130D), Color(hex: 0x081C15), Color(hex: 0x03100B)]
        case .normal:   [Color(hex: 0x070C1C), Color(hex: 0x0C1230), Color(hex: 0x05091A)]
        case .fatigue:  [Color(hex: 0x1A0E04), Color(hex: 0x251406), Color(hex: 0x160A03)]
        case .warning:  [Color(hex: 0x2A0810), Color(hex: 0x3E0F22), Color(hex: 0x1C0718)]
        }
    }
}

// MARK: - Material (Liquid Glass)
//  iOS 26+ — use the NATIVE .glassEffect. Do NOT reconstruct blur/saturate/edge
//  from the web recipe; the prototype's backdrop-filter stack is a browser fake.
//  See DESIGN.md and lib/glass-primitives.jsx (annotated CANONICAL header).

enum RGlass {
    /// Default card surface. Wrap groups of cards in a GlassEffectContainer.
    static func surface<S: Shape>(in shape: S) -> some View {
        Color.clear.glassEffect(.regular, in: shape)
    }
    static let cardRadius: CGFloat = 22   // --radius-xl
    static let sheetRadius: CGFloat = 28  // --radius-2xl
}

// MARK: - Typography

enum RType {
    /// Editorial display headline: heavy weight, tight tracking, tight leading.
    /// NOTE: leading 0.95–1.05 has NO direct SwiftUI API — apply via
    /// lineHeightMultiple on an AttributedString / UIFont. See mapping doc.
    static let displayWeight: Font.Weight = .heavy        // 800
    static let displayTrackingMin: CGFloat = -0.040       // em, convert per size
    static let displayTrackingMax: CGFloat = -0.025       // em, convert per size
    static let displayTrackingTight: CGFloat = -1.2       // that range at ~30pt, in points
    static let displayLeadingMin: CGFloat = 0.95
    static let displayLeadingMax: CGFloat = 1.05

    /// Eyebrow / section label. Color is explicit (RUI: never opacity).
    static let eyebrowSize: CGFloat = 11
    static let eyebrowWeight: Font.Weight = .heavy        // 800
    static let eyebrowTracking: CGFloat = 1.4
    static let eyebrowColor = Color(white: 0, opacity: 0.55)

    /// Ink hierarchy by COLOR, not opacity (over solid card surfaces).
    /// LIGHT rungs.
    static let inkPrimary   = Color(hex: 0x0A0A0A)
    static let inkSecondary = Color(white: 0, opacity: 0.65)
    static let inkTertiary  = Color(white: 0, opacity: 0.50)

    /// DARK rungs — the same ladder resolved for the dark scheme. Required:
    /// 深色 is a real setting, and reusing a light ink under dark inverts the
    /// light/dark relation between a glass card and the wallpaper beneath it.
    static let inkPrimaryDark   = Color(hex: 0xF5F5F7)
    static let inkSecondaryDark = Color(white: 1, opacity: 0.68)
    static let inkTertiaryDark  = Color(white: 1, opacity: 0.48)

    /// On-wallpaper tint mixes (RUI: tint to hue, don't dim with opacity).
    static let fgTintPrimaryMix: Double = 0.93
    static let fgTintBaseMix: Double = 0.80
}

// MARK: - Motion

enum RMotion {
    static let sheet   = Animation.spring(response: 0.42, dampingFraction: 0.82) // ease-sheet / 420ms
    static let control = Animation.easeInOut(duration: 0.25)                      // dur-base
    static let quick   = Animation.easeInOut(duration: 0.15)                      // dur-quick
    static let hero    = Animation.easeInOut(duration: 0.50)                      // dur-hero
    /// Press feedback: scale + opacity. Mirrors --press-scale / --press-opacity.
    static let pressScale: CGFloat = 0.96
    static let pressOpacity: CGFloat = 0.70
}

// MARK: - Layout

enum RLayout {
    static let pageGutter: CGFloat = 20
    static let cardGapMin: CGFloat = 14
    static let cardGapMax: CGFloat = 32
}

// MARK: - Helpers

extension Color {
    /// Hex literal initializer so the mirror reads like the CSS source.
    init(hex: UInt32) {
        self.init(.sRGB,
                  red:   Double((hex >> 16) & 0xFF) / 255,
                  green: Double((hex >> 8) & 0xFF) / 255,
                  blue:  Double(hex & 0xFF) / 255,
                  opacity: 1)
    }
}

extension View {
    /// Tabular figures — every aligned digit. Mirrors the <Num> primitive.
    func runeticNumerals() -> some View { self.monospacedDigit() }

    /// Standard press feedback. Mirrors PressState in glass-primitives.jsx.
    func runeticPress(_ pressed: Bool) -> some View {
        self.scaleEffect(pressed ? RMotion.pressScale : 1)
            .opacity(pressed ? RMotion.pressOpacity : 1)
            .animation(RMotion.quick, value: pressed)
    }
}
