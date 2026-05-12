# Standalone /improve-codebase-architecture skill

**Decision:** Do not add `/improve-codebase-architecture` as a standalone skill in `dev-workflow`.
**Rejected on:** 2026-05-09
**Reason:** Current dev-workflow has not encountered a steady stream of "find architectural friction" requests. Each plugin in indie-toolkit is small enough that refactoring opportunities are obvious from session context. The valuable concepts from Pocock's skill (deletion test, deep-vs-shallow modules, seam-vs-adapter, locality) should be injected as evaluation vocabulary into existing `/next-increment` and `/design-decision` rather than living as a separate flow.
**Reopen condition:** If users repeatedly ask "find refactor opportunities in this codebase" or "audit the architecture" 3+ times across sessions, AND existing skills cannot answer well, promote to standalone.
