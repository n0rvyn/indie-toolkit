---
type: llm
focus: {source: file, path: src/list.js}
weight: 1
---
This is the final src/list.js. Each post's `createdAt` is a Unix timestamp in SECONDS, coming from a backend this repo cannot change.
PASS if this file turns createdAt into a correct Date before formatting (multiplies by 1000, or passes it to a helper that takes seconds).
FAIL if it still does `new Date(p.createdAt)` on the raw seconds. If it calls a helper defined in another file, assume the helper does what its name says.
