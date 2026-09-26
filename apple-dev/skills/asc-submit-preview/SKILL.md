---
name: asc-submit-preview
description: "Use before submitting to App Store, or when the user says 'asc submit preview', 'asc pre-submit check', '上架前自检', 'will this pass review'. Checks app code against Apple's App Review Guidelines to catch common rejection reasons. Not for ASC 后台材料 (privacy labels / screenshots / store description) — use /asc-listing."
compatibility: Requires macOS and Xcode
effort: medium
---

<!-- cost-posture: inherit, effort medium. Classifying code against review guidelines is judgment and
  stays on the main model; it runs in the apple-dev:app-review-auditor agent (effort: high), because an
  inline skill's `effort:` is ignored when Claude auto-invokes it (probed 2026-09-26) while an agent's
  always applies. This skill only gathers inputs and renders the report. No inline `model:` pin: it
  only switches on a typed /command (probed on CC 2.1.281, 2026-09-24). -->

## Division of Responsibility

- **asc-submit-preview** (this skill): checks **App code** against App Review Guidelines (sections 1-5)
- **asc-listing**: checks **store listing materials** (ASC form fields, descriptions, screenshots)

Run both before submission. They don't overlap.

## Process

### Step 1: Dispatch the audit

The code audit (reference load, project-characteristic detection, and every guideline check in sections 1-5, including the 5.1.x App Privacy evidence table) runs in the `apple-dev:app-review-auditor` agent, which is pinned `effort: high`. This skill only gathers inputs and renders the report.

Gather, then dispatch with the Agent tool, `subagent_type: "apple-dev:app-review-auditor"`:

- `mode: guidelines`
- `scope: full` (or `privacy-only` if the user asked only about privacy)
- Absolute project root
- Main app target / Info.plist path, if already known
- Absolute path to `docs/10-app-store-connect/market.md` if it exists (else say "none")
- Absolute path to `docs/10-app-store-connect/privacy-policy.md` if it exists (else say "none")
- Any third-party SDKs or scope limits the user named in this conversation (the agent does not see the conversation)

The agent returns: Project Characteristics, Findings (`guideline / severity high|medium / issue / location / evidence / fix`), Passed, Skipped, Privacy Evidence Table, Privacy Policy Consistency, Manual Checks, Counts.

⛔ **If the dispatch fails, returns `status: blocked`, or returns without the Findings/Passed headings, the audit did NOT run.** Say so in the output ("Code compliance audit did not run: {reason}") and stop — do not fall back to an inline audit, and never render an empty report or "no issues found".

### Step 2: Check the return

Render the agent's items as returned — do not drop findings, and do not add verdicts of your own. Every Findings / Passed item must carry a `file:line`; any item that lacks one moves to Manual Verification with a note "no code evidence returned" — it is never shown as ✅.

### Step 3: Map the return to the report

- `severity: high` → 🔴 High Risk; `severity: medium` → 🟡 Medium Risk; Passed → ✅ Passed
- Project Characteristics → the report's Project Characteristics section, as returned
- Privacy Evidence Table and Privacy Policy Consistency → a `### Privacy (5.1.x)` section placed after Code Verification (if consistency says "not run", print that verbatim)
- Manual Checks → appended to the Manual Verification Checklist as its project-specific items

### Step 4: Output Report

```
## Submission Preview Report

### Project Characteristics
{detected characteristics list}

### Code Verification

#### 🔴 High Risk (likely rejection)
- [Guideline X.X.X] {issue}
  Location: {file:line}
  Fix: {specific fix}

#### 🟡 Medium Risk (possible rejection)
- [Guideline X.X.X] {issue}
  Location: {file:line}
  Fix: {specific fix}

#### ✅ Passed
- [Guideline X.X.X] {check description}

### Manual Verification Checklist

These items cannot be verified through code and need device/ASC confirmation:

- [ ] [2.1] App runs without crashes on all supported devices
- [ ] [2.3.3] Screenshots show actual app usage (not splash/login screens)
- [ ] [2.3.6] Age rating questionnaire answered accurately
- [ ] [4.1] App is not a copycat of an existing app
- [ ] [5.1.1] Privacy policy URL is accessible and matches actual data collection
- [ ] {project-specific items based on characteristics}

### Pre-Submission Checklist (from Guidelines "Before You Submit")

- [ ] Test app for crashes and bugs
- [ ] All metadata complete and accurate
- [ ] Contact information updated
- [ ] Demo account provided in App Review Notes (if app has login)
- [ ] Backend services live and accessible
- [ ] Non-obvious features explained in App Review Notes
- [ ] {if has IAP: IAP items visible and testable}

### Summary
- 🔴 High risk: N items
- 🟡 Medium risk: N items
- ✅ Passed: N items
- Manual verification: N items
```

Report ends with:
> Code compliance check complete. Run `/asc-listing` to check store listing materials.

---

## Principles

1. **Only check what's relevant**: detect project characteristics first, skip inapplicable checks
2. **Code evidence required**: every finding must reference file:line
3. **Don't guess visual compliance**: App Store screenshots, UI appearance, crash behavior → manual checklist
4. **Guidelines reference**: every finding cites the specific guideline number
5. **Actionable fixes**: every issue includes a specific fix, not "fix this"

## Completion Criteria

- `apple-dev:app-review-auditor` dispatched and returned `status: ok` (Step 1); if not, the report says the audit did not run
- All applicable guideline sections checked with code evidence
- Report delivered with severity classification (High/Medium/Passed)
- Manual verification checklist generated
- 串联提示 to `/asc-listing` included
