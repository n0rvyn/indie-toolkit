---
name: app-support-entries
description: "Apple app intake and closeout: use for a new iOS/macOS app, feature development in an Apple app, an Apple app issue fix, or release preparation. Read and reconcile the shared About/Feedback/support-entry checklist and the app's actual implementation evidence. Not for standalone Swift language/API questions, non-Apple projects, or merely listing GitHub issues."
effort: medium
---

# Apple App support-entry lifecycle

First run bundled `scripts/read_support_reference.py` through the loaded skill directory (for example `python3 <loaded-skill-dir>/scripts/read_support_reference.py`). It resolves its real package location even when discovery uses a symlink, and prints [the single canonical checklist](../../references/app-support-entries.md). Do not simplify the link into a project .agents/references path or guess a versioned installed cache. A missing bundle is unverified, not passed; do not copy its rules into a second checklist. This skill is a discoverable intake/closeout entrypoint, not an automatic UI rewrite or executable release gate.

## Intake

1. Identify the selected Apple app/root and current task from the request. For a new project not already inside kickoff, use `apple-dev:project-kickoff`; that generator adds the stable reference automatically after creating the normal project instructions. When invoked by active kickoff, report checklist requirements only and do not invoke kickoff again. Do not retrofit every app's AGENTS.md, modify global config, or ask the owner to maintain an index.
2. Read the app's existing implementation record (for example an existing support-entry audit or README section), then check current source and the latest relevant build/test evidence. Never treat yesterday's missing IDs/email or a checkbox as current proof. Resolve only relevant approved/public destinations; do not inspect credentials or authenticate to ASC by default.
3. Return a compact **Support-entry status**: app/root, record path, source/build evidence, implemented/missing/unverified/not-applicable entries, available metadata and authorization scope. If no record exists, maintain a short record through the task's normal authorized documentation workflow; it is an implementation/evidence record, not a per-app discovery index.
4. Register unrelated gaps without expanding the user's fix/feature scope. For release work include unresolved entries in the acceptance report. Existing authorization persists; do not require repeated approval for already-approved UI work.

## Closeout

Reconcile the record against what the final source and tested artifact actually contain. Check destinations and agreed placement using the canonical reference. Report unresolved entries explicitly even when the requested bug itself is fixed. A source implementation, a visible control and a verified external destination are separate facts. Do not call release support-entry acceptance complete while relevant entries are missing/unverified.

No outbound mail, rating requests, privacy/legal declarations, ASC updates or release actions are authorized by loading this skill. The body guides the agent; an invocation trace and evidence are needed to prove it ran. Model description matching is not guaranteed execution.
