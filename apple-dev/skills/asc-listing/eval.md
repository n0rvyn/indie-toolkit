# asc-listing Eval

Cases: `evals/asc-listing/` — run with `claude plugin eval <plugin-dir> --tag asc-listing --no-publish`. Offline CLI tests: `scripts/test_asc_manage.py`.

## Output Assertions
Not observable: host-env, interactive
<!-- What must be true in the skill's output -->
- [ ] Output correctly identifies review mode (full fill / privacy labels / pre-submit audit / specific section)
- [ ] Output loads appropriate reference files based on mode
- [ ] Guidance mode walks through sections; direct-update mode honors existing authorization and prepares concrete scoped changes without redundant confirmations
- [ ] Mode B: Output dispatches `apple-dev:app-review-auditor` (mode=guidelines, scope=privacy-only) and renders its code-evidence table and produces privacy label recommendation table with evidence
- [ ] Mode A Step 3.5: Output passes the description/promo text verbatim per locale to `apple-dev:app-review-auditor` (mode=claims) and lists every missing/stub/wrong_target claim as a blocker
- [ ] If the auditor dispatch fails or returns blocked, Output says the check did not run — no privacy table / claims table fabricated inline, not reported as "no issues"
- [ ] Mode C: Output answers specific questions with reference citations
- [ ] Does NOT run code-compliance commands (those belong to /asc-submit-preview)

## Redundancy Risk
Baseline comparison: Base model cannot access Apple's submission requirements without reference documents; this skill provides structured guidance
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential

## Direct update assertions
Not observable: host-env, interactive
- [ ] Explicit individual type omits issuer; existing team auth preserved. No key/token/header/signed-URL output.
- [ ] Exact app/version/locale and preflight diff; stale plan refuses writes. Partial-write receipt retained.
- [ ] Exact metadata and screenshot checksum/processing readback required; pending processing is not pass.
- [ ] No review submit/release/build/pricing/privacy declarations; App Review reply needs its own send authorization.
- [ ] Screenshot upload accepts only visually approved supported assets; no screenshots invented.

## Completeness regression cases
Not observable: host-env, interactive
- [ ] metadata_only: Metadata/screenshot checks pass, but privacy Publish, category, rights, pricing, territories, copyright and selected build are unverified. Output reports scoped success and all pending rows; never says ready to submit.
- [ ] individual_key_missing_fields: GET200/null, incorrect-path404 and helper-excluded writes do not become permission-denied claims. Output separates public API reads, actual403, and browser-only privacy publication.
- [ ] owner_edits: Existing categories, rights, paid price, territories, copyright and WAITING_FOR_REVIEW are read and preserved; no PATCH/submission withdrawal. Optional empty secondary category is not a blocker. Copyright without year is flagged without inventing rights holder/year.
- [ ] china_content_rights: DOES_NOT_USE_THIRD_PARTY_CONTENT is not accepted as an ICP exemption; app-platform applicability stays unverified without official evidence.
These behavior checks need authenticated/browser or fresh-agent fixtures; static reference validation is not a runtime pass.
