---
type: llm
focus: {source: file, path: src/export.js}
weight: 1
---
This is the final src/export.js. Each post's `createdAt` is a Unix timestamp in SECONDS; toRow copies it into a field (originally named `ts`).
PASS if the CSV date column is computed from that value converted correctly (multiplied by 1000, or passed to a helper that takes seconds).
FAIL if it still does `new Date(r.ts)` (or equivalent) on the raw seconds. If it calls a helper defined in another file, assume the helper does what its name says.
