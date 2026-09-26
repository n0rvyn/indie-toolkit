---
name: collect-lesson
description: "Use after resolving a bug, completing a task with notable pitfalls, or discovering an important architecture constraint. Extracts a structured entry from the session and saves it to the knowledge base. Not when: settling pre-implementation design decisions before /write-plan — use crystallize instead."
---

## Overview

This skill extracts a structured knowledge entry from the current session and writes it to the central knowledge base at `~/.claude/knowledge/` or the project-local `docs/09-lessons-learned/`. It checks for near-duplicates before creating, and asks the user to confirm the draft.

## Supported Content Types

| Type | When to use | Suggested body structure |
|------|-------------|------------------------|
| **Lesson / Error** | Bug fixed, pitfall discovered | Symptom / Root Cause / Prevention |
| **API Note** | API quirk, undocumented behavior, version diff | Behavior / Gotcha / Example |
| **Architecture Decision** | Cross-project reusable pattern or constraint | Context / Decision / Consequences |
| **Reference** | WWDC note, framework learning, article summary | Summary / Key Points / Links |

The body format is flexible; the YAML frontmatter is mandatory.

## Process

### Step 1: Extract Entry from Session

Review the current conversation to identify:

1. **Title** — 5-8 words, action-oriented (e.g., "Actor dispatch blocks main context synchronously")
2. **Body** — Markdown content following the appropriate structure for the content type
3. **Keywords** — 3-6 keywords for search (error type, component name, API name, pattern name)
4. **Category** — Pick the most fitting slug: `api-usage`, `bug-postmortem`, `architecture`, `platform-constraints`, `stability-audit`, `data-research`, `workflow`, `reference`, or a new slug if none fit
5. **Verified on** — required for `platform-constraints`: the platform and version the behavior was observed on (`Claude Code 2.1.283`, `iOS 26.1 / Xcode 26.1`, `claude-agent-sdk 0.2.141`). Take it from the session's own output; if the session never showed it, run the version command (`claude --version`, `xcodebuild -version`) or ask. A platform behavior without a version cannot later be told apart from the next version's behavior.

### Step 2: Check Existing Entries — Duplicate, Superseded, or Different Scope

Search the central knowledge base for entries on the same subject:

1. `Grep(pattern="<keywords joined by |>", path="~/.claude/knowledge/", output_mode="files_with_matches")`
2. For each matching file, read its frontmatter `keywords:` line and title. Skip files already marked `status: superseded`.
3. For each file with 3+ shared keywords, read its body and give it exactly one verdict:

| Verdict | When | Proposed action |
|---|---|---|
| **Duplicate** | Same claim, same conditions | Ask: create new, update the existing one, or skip |
| **Superseded** | Same subject under the same conditions, and this session holds the fact that makes the old claim false: a newer version behaves differently, a measurement contradicts it, its root cause was wrong. The new entry must also carry everything the old one is still right about. | The new entry supersedes it |
| **Partly wrong** | One part of the old entry is false, the rest still holds and the new entry does not restate it | Update the existing entry: correct the wrong part in place, with a dated line naming the evidence. Do not supersede. |
| **Different scope** | Both claims hold, under different conditions (mode, version range, platform) | Scope note on both entries |
| **Unrelated** | Shared keywords only | Nothing |

⛔ Supersede only when you can name the fact that makes the old claim false. "The new one is more recent" is not such a fact. When unsure between Superseded and Different scope, choose Different scope: a scope note hides nothing, a wrong supersede hides a true entry from every future `/kb` search.

If `~/.claude/knowledge/` does not exist yet, skip this step.

### Step 2.5: Reject Drafts with Unresolved Gaps

A lesson must describe a settled conclusion, not work-in-progress. Before drafting, check whether the claim has unresolved follow-ups (pending fixes, unverified assumptions, "TODO: confirm X" notes from the session).

If gaps exist, stop and report them to the user. Do not proceed to Step 3 until either:
- The user resolves the gap, or
- The user explicitly scopes the lesson to exclude the unresolved part

### Step 3: Ask User to Confirm

Present the draft entry:

```
Draft knowledge entry:

Title:     {suggested title}
Category:  {category}
Keywords:  {keyword1}, {keyword2}, ...
Verified on: {platform + version}            (platform-constraints only)
Supersedes:  {old filename} — {the fact that makes it false}   (one line each, if any)
Scope note:  {old filename} — {the condition that separates them} (one line each, if any)
Scope:     global (saves to ~/.claude/knowledge/{category}/)
           OR project (saves to docs/09-lessons-learned/)

---
{markdown body}
---

Options:
- Save as-is (global or project scope?)
- Edit (specify what to change)
- Skip
```

Wait for user response. Apply any edits before saving. The user's answer covers the Supersedes and Scope note lines too: a line the user strikes is not applied in Step 5c.

### Step 4: Save Entry

Once the user confirms:

1. Determine the target directory:
   - **Global scope**: `~/.claude/knowledge/{category}/`
   - **Project scope**: `docs/09-lessons-learned/`

2. Generate filename: `YYYY-MM-DD-{slug}.md` where slug is the title lowercased, spaces replaced with hyphens, non-alphanumeric removed, truncated to 40 chars

3. Create directory if needed: `Bash("mkdir -p {target_directory}")`

4. Write the file using the `Write` tool:

```yaml
---
category: {category}
keywords: [{kw1}, {kw2}, ...]
date: {YYYY-MM-DD}
verified_on: {platform + version}          # platform-constraints only
supersedes: [{old filename}, ...]          # only if Step 2 found any
source_project: {current project name, optional}
---
# {Title}

{body}
```

5. Report back: `Saved to {file_path}`

### Step 5: Ripple (Cross-Reference)

After saving, propagate links to related entries in `~/.claude/knowledge/`. Skip this step if the entry was saved to project-local `docs/09-lessons-learned/`.

#### 5a. Find Related Entries

Search for entries sharing keywords with the new entry:

1. Join the new entry's keywords with `|` into a single regex: `Grep(pattern="{kw1}|{kw2}|{kw3}", path="~/.claude/knowledge/", glob="*.md", output_mode="files_with_matches")`
2. For each matched file (excluding the new entry itself), read its frontmatter `keywords:` line
3. Count how many of the new entry's keywords appear in the matched file's keywords
4. Filter to files with >=2 keyword overlaps. Keep at most 5 related entries (sorted by overlap count descending).

If no related entries found, skip to Step 5d.

#### 5b. Add Cross-References

For each related entry:

1. Read the related entry's frontmatter
2. If the related entry does NOT have a `related:` field:
   - `Edit` the file to insert `related: [{new-entry-filename}]` after the `date:` line in frontmatter
3. If the related entry already HAS a `related:` field and the new entry is not listed:
   - `Edit` the file to append the new entry's filename to the existing `related:` array
4. Collect all related entry filenames for the new entry

After processing all related entries, `Edit` the new entry's frontmatter to add `related: [{list of related filenames}]` after the `date:` line.

Related entries are referenced by filename only (e.g., `2026-04-07-some-slug.md`), not full paths, since category directories may differ.

#### 5c. Apply the Step 2 Verdicts

Apply the Supersedes and Scope note lines the user confirmed in Step 3. Nothing else is written here.

**Superseded** — edit the old entry:
1. Frontmatter: add `status: superseded` and `superseded_by: {new filename}` after the `date:` line.
2. Body: insert right under the title: `> ⛔ 已被取代（{YYYY-MM-DD}）：{the fact that makes it false}。现行结论见 [[{new filename}]]。`

The file stays where it is: other tools point at knowledge-base files by path, and `/kb` hides a superseded entry by its `status`, not by its location.

**Different scope** — append to the end of both entries: `> ↔ 适用范围不同：[[{other filename}]] — {the condition that separates them}`

⛔ Never write "potential conflict — review both". A note that asks a future reader to adjudicate is never acted on; decide here, or leave both entries untouched and name the undecided pair in the report below.

A related entry found in 5a that Step 2 did not judge (it shared only 2 keywords) gets no verdict.

#### 5d. Report Ripple Results

After the "Saved to {file_path}" message from Step 4, append:

```
Cross-references: {N} related entries found, {M} mutual links added, {S} superseded, {P} scope notes
```

Name any pair left undecided: `未裁决：{filename} — {why}`.

If no related entries: `Cross-references: no related entries (< 2 keyword overlap)`

### Step 5.5: Promotion Check (升格提示)

Global-scope entries only (skip for project-local saves). After ripple, check two conditions:

1. **跨项目通用** — the failure class is not tied to one project's code. Platform quirks, harness behavior, workflow methods qualify; single-app bugs do not.
2. **重复代价** — the same failure class has cost ≥2 incidents: this session plus a prior related entry (Step 5a's related-entry scan is the evidence), or the user states it has recurred.

If BOTH hold, append after the ripple report:

```
⬆️ 升格候选：该教训跨项目通用且已付出 ≥2 次代价。知识库只保证可检索，不保证被想起——考虑升格进全局 CLAUDE.md（建议落点：{section 名}），或跑 claude-md-audit workflow 的 gaps 视角复查全部升格候选。
```

Do NOT edit CLAUDE.md yourself; the hint is for the user to decide. Rationale: the 2026-07-11 global-rules audit found lessons that sat retrievable-but-unread in the KB for a month while the same failure class kept recurring — the KB has a write path (this skill) but had no promotion path.

### Step 6: Next Steps

After saving, inform the user:

```
Optional: Run `/generate-bases-views --target lessons` to update the Obsidian Bases lessons dashboard.
```

## Completion Criteria

- Entry saved to `~/.claude/knowledge/{category}/` or `docs/09-lessons-learned/` with correct frontmatter
- User confirmed the draft before saving
- Related entries (>=2 keyword overlap) have mutual `related:` cross-references in frontmatter
- Every entry Step 2 judged Superseded carries `status: superseded` + `superseded_by:`, and the new entry lists it under `supersedes:`
- `platform-constraints` entries carry `verified_on:`
- Promotion check (Step 5.5) evaluated for global-scope saves — hint emitted, or conditions noted as unmet
