#!/bin/bash
# Seeds a fixture knowledge base in the run's $HOME, a per-run temp dir, so a real
# ~/.claude/knowledge is never touched. The run can read it; it cannot write it
# (eval runs confine writes to the workspace).
set -e
KB="$HOME/.claude/knowledge"
entry() { mkdir -p "$KB/$(dirname "$1")"; cat > "$KB/$1"; }

# 36 distractor entries sharing the generic words a keyword-bag query carries
# (SwiftUI, XCUITest, prompt, image, test, token, screenshot), none about the task.
i=0
for topic in "SwiftUI List row separator insets" "SwiftUI NavigationStack path reset" "XCUITest element query timeout" \
  "prompt caching breakpoints" "image asset catalog compression" "test plan configuration order" \
  "token refresh race on launch" "screenshot naming in fastlane" "SwiftData predicate on optional" \
  "XCUITest keyboard dismissal" "prompt length budget for tools" "image picker memory spike" \
  "SwiftUI Chart axis labels" "test fixture JSON decoding dates" "LLM prompt few-shot ordering" \
  "SwiftUI sheet detents on iPad" "XCUITest accessibility identifier reuse" "image cache eviction policy" \
  "SwiftData store migration lightweight" "prompt injection in tool results" "token counting for Chinese text" \
  "screenshot diff tolerance" "SwiftUI animation transaction override" "test parallelization flakiness" \
  "XCUITest launch environment variables" "vision framework barcode detection" "SwiftUI focus state on macOS" \
  "prompt template versioning" "image orientation EXIF on import" "SwiftData CloudKit sync delay" \
  "XCUITest swipe gesture velocity" "LLM response JSON schema drift" "SwiftUI GeometryReader in ScrollView" \
  "test coverage report exclusions" "xcresulttool legacy flag" "SwiftUI preview crash on launch"; do
  i=$((i+1)); slug=$(printf '%s' "$topic" | tr 'A-Z ' 'a-z-' | tr -cd 'a-z0-9-')
  entry "api-usage/2026-07-$(printf '%02d' $(( (i % 28) + 1 )))-$slug.md" <<MD
---
category: api-usage
keywords: [$(printf '%s' "$topic" | sed 's/ /, /g')]
date: 2026-07-$(printf '%02d' $(( (i % 28) + 1 )))
---
# $topic

Notes on $topic. Mentions SwiftUI, XCUITest, prompt, image, test, token, screenshot, fixture and launch
in passing because the project uses all of them; the lesson itself is only about $topic.
MD
done

entry api-misuse/2026-08-25-uigraphicsimagerenderer-size-is-points-not-pixels.md <<'MD'
---
category: api-misuse
keywords: [UIGraphicsImageRenderer, displayScale, points vs pixels, downsampling, UIImage.size]
date: 2026-08-25
---
# `UIGraphicsImageRenderer(size:)` renders at displayScale — your "downsample" is a 9x upscale on a 3x screen

`UIImage.size` is in points and the default renderer format uses the device scale (3.0 on iPhone), so
rendering at 480x1044 produces a 1440x3131-pixel image. Set `format.scale = 1` when you mean pixels.
Anything sized "for upload" was three times larger per side than intended.
MD
entry platform-constraints/2026-08-25-vlm-image-token-is-a-fixed-budget.md <<'MD'
---
category: platform-constraints
keywords: [VLM, image tokens, prompt_tokens, image_count, fixed budget]
date: 2026-08-25
---
# A VLM's image tokens are a fixed budget per image
prompt_tokens grows by a fixed amount per image regardless of resolution; image_count drives the bill.
MD
