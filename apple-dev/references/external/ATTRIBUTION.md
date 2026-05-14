# External Vendored Content Attribution

Files under `apple-dev/references/external/` are vendored from third-party MIT-licensed sources. Each file retains an attribution footer pointing back to its origin. This document is the manifest.

## Upstream

**vabole/apple-skills** v1.0.10 — https://github.com/vabole/apple-skills
License: MIT (Copyright (c) 2026 Ilia Abolhasani)
Vendored: 2026-05-14

## Footer convention

Every vendored markdown file ends with:

```
---
_Source: vabole/apple-skills v1.0.10 · `skills/<original-path>` · MIT (c) 2026 Ilia Abolhasani · Vendored 2026-05-14._
```

Some files (those merged into existing apple-dev references) carry an inline attribution at the start of the absorbed section instead of an end-of-file footer.

## Sync policy

Manual quarterly review. Diff upstream vs vendored copy; decide per file whether to pull updates. No automated sync (to avoid pulling unintended upstream noise).
