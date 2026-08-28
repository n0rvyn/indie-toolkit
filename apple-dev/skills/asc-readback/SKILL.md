---
name: asc-readback
description: "Read what App Store Connect ACTUALLY holds for an app, via the authenticated ASC API — live keywords / name / subtitle / description / promo text / What's New / screenshot checksums / review notes / support + marketing URLs, plus whether a version is really submitted. Use when the user says 'ASC 现在填的是什么', '关键词字段实际是什么', '我改的 ASC 字段存进去了吗', '提交出去了吗', 'read back ASC', 'check ASC state', 'is it actually submitted', 'scan my listing for a banned word', or after any ASC edit that must be confirmed. Also for post-rejection forensics: diff two versions to separate what changed from what stayed constant. Not for deciding WHAT the text should say (use /aso-research). Not for guidance on which box to fill (use /asc-listing). Not for code-level review compliance (use /asc-submit-preview)."
model: sonnet
allowed-tools: Bash, Read, Grep
---

# ASC read-back — what the backend actually holds

`asc-listing` tells you which box to fill. `aso-research` decides what the text should say.
**This skill answers a third question neither can: what is in there right now, and did my
change take effect?** It talks to the authenticated App Store Connect API.

Every request is a GET. The script cannot modify a listing.

## Why this exists

Two failure modes that no public endpoint and no amount of looking at the ASC web UI can catch:

1. **「填了但没保存」** — the ASC form looks identical whether or not a field committed.
   The only readback is an authenticated GET.
2. **「改了但没提交」** — after a rejection, editing the fields and saving does **not**
   queue the app. Apple's own docs: `Ready for Review` = *"added to a submission, but it
   hasn't been submitted to App Review yet."* Silent, no error. Real incident 2026-08-28:
   metadata fixed and saved, the developer believed it was resubmitted, it was not.

Also: **the keyword field is not publicly readable** — the public iTunes endpoints do not
return it, so `aso-research` has to infer it from rankings. The ASC API returns it verbatim.

## Setup (once)

Needs an App Store Connect API key (`AuthKey_XXXXXXXX.p8`) with at least App Manager or
Developer access, and `python3 -m pip install cryptography`.

Credential resolution, in order:

1. `ASC_KEY_PATH` + `ASC_KEY_ID` + `ASC_ISSUER_ID`
2. `ASC_KEY_PATH` alone, with a sibling `key.info` holding `Key ID:` and `Issuer ID:` lines
3. the first `AuthKey_*.p8` under `~/private_keys`, `~/.appstoreconnect/private_keys`, or
   any directory in `ASC_KEY_DIRS` (colon-separated), plus its sibling `key.info`

```bash
export ASC_KEY_DIRS=/path/to/asc_keys       # simplest: point at the dir holding .p8 + key.info
```

⛔ Never write the key, Key ID, or Issuer ID into a file that goes in a repo. The script reads
them from disk/env at run time and holds nothing.

## Commands

`SC=${CLAUDE_SKILL_DIR}/scripts/asc_readback.py`. `<app>` accepts a bundle id, a numeric app
id, or a case-insensitive name substring.

```bash
python3 $SC apps                             # every app on the account
python3 $SC show <app> [--limit N] [--screenshots] [--full]
python3 $SC state <app>                      # is it actually queued with Apple?
python3 $SC scan <app> --forbid openai,chatgpt
python3 $SC diff <app> 2.4 2.5               # what changed vs what stayed constant
python3 $SC assert <app> --locale en-US --field keywords --absent openai
```

### `state` — the one people get wrong

**The criterion is the submission's `state`, not the item's.**

| field | not submitted | after Resubmit | usable as criterion |
|---|---|---|---|
| `reviewSubmissions[].state` | `UNRESOLVED_ISSUES` | `WAITING_FOR_REVIEW` | ✅ **this one** |
| `reviewSubmissions[].submittedDate` | old timestamp | updates | ✅ corroborates |
| `reviewSubmissions/{id}/items[].state` | `READY_FOR_REVIEW` | **still `READY_FOR_REVIEW`** | ❌ never moves |

The item `state` is a **verdict** field: `READY_FOR_REVIEW` → `APPROVED` / `REJECTED`. It never
passes through `WAITING_FOR_REVIEW`, so reading it to answer "did I submit?" returns the same
value either way. Measured 2026-08-28 across a real resubmit.

⚠️ This contradicts the wording on Apple's help page, which describes the **web UI's** status
labels, not the API's item field. Trust the measurement.

Exit code: **0 only when a submission is actually `WAITING_FOR_REVIEW` or `IN_REVIEW`**. Every
other outcome exits **1** — rejected-and-not-resubmitted, staged-but-not-submitted, all
submissions finished, and never-submitted-at-all. So `… && python3 $SC state <app>` gates on
"really queued", not on "the call succeeded".

The verdict is decided by which states are *present*, not by list position: ASC documents no
ordering for this endpoint (see Limits).

### `scan` — compliance / banned-token check

Walks every localization of both `appInfo` (name, subtitle, privacyPolicyUrl) and the version
(keywords, description, promo, What's New, support + marketing URLs). Exits 1 on any hit.

It prints a **positive control** each run — how many fields and characters the walk actually
produced. If the walk produced nothing, the scan read no text and its "clean" result is
meaningless, so it fails loudly instead of reporting a false all-clear. The control counts what
was read; it does not look for a sentinel character, because a Chinese-only listing legitimately
contains no Latin letters.

⛔ **Screenshots are images; this cannot read them.** A brand name burned into screenshot
artwork will not be caught. Check those by eye — that is a real rejection path.

### `diff` — post-rejection forensics

Separates **variables from constants**. When a review outcome changes, the cause is among the
fields that differ; a field identical across both versions did not cause a new outcome, however
suspicious it looks. Screenshot `sourceFileChecksum`s are included, so "is this the same image
that passed last time?" is answerable.

The output windows on the **first differing character**, not the head of the string — long
descriptions usually differ only at the end.

### `assert` — post-edit gate

Exit 0/1, one field at a time. Use it right after editing anything in ASC:

```bash
# did the edit commit? assert on what SHOULD be there, then on what must not be
python3 $SC assert <app> --locale zh-Hans --field keywords --present 记账 \
  && python3 $SC assert <app> --locale zh-Hans --field keywords --absent openai \
  && python3 $SC state <app>
```

⚠️ **To confirm a save, use `--present` or `--equals`, not `--absent`.** An empty field contains
no forbidden token, so `--absent` passes vacuously on a field the save silently dropped — the
exact failure this skill exists to catch. `assert` prints the character count on every line and
warns loudly on a 0-char field, but the check that actually proves the write landed is
`--present`. Keep `--absent` for compliance scanning.

## Process

1. **Resolve the app.** Run `apps` if the identifier is uncertain; never guess an app id.
2. **Read before concluding.** Any claim about what a field contains must come from `show`
   or `assert` output pasted into the answer, not from memory or from a repo doc — repo copies
   of listing copy drift from the backend.
3. **After any ASC edit, run `assert --present` then `state`.** In that order: the edit can save
   and still not be submitted. `--absent` alone cannot prove a save landed (see above).
4. **After a rejection, run `diff` before theorizing.** Identify what actually changed.
5. **Report the numbers you saw.** Keyword fields are capped at 100 characters; `show` prints
   the measured length. Do not estimate it.

## Limits

- Read-only. Writing metadata is deliberately not implemented: a bad PATCH to a live listing is
  not cheap to undo. Hand the user the exact strings and let them paste, then `assert`.
- Screenshot **artwork** is opaque here; only filenames and checksums are visible.
- Territory availability is a separate resource. Note that store metadata is per **locale**,
  not per territory — there is no country-specific copy of a keyword field, so a
  country-scoped compliance demand forces either a global text change or a storefront removal.
- A single read can hit propagation lag. For a state change, read twice a couple of minutes
  apart before concluding.
- **Version ordering is not guaranteed by Apple.** Neither `GET /v1/apps/{id}/appStoreVersions`
  nor `…/reviewSubmissions` documents a `sort` parameter or a default order (checked against
  Apple's docs 2026-08-28), so `--limit 3` is not "the newest 3" on its own. The script sorts
  client-side on `createdDate` / `submittedDate` and prints those timestamps — read them rather
  than trusting the position. `diff` and `assert --version` pin the version explicitly and do
  not depend on order at all.
- `appStoreState` is deprecated in Apple's docs in favour of `appVersionState`; the script reads
  the successor first and falls back, printing `?` rather than `None` if both vanish.
