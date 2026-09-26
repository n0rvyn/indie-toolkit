---
name: kb
description: "Use when the user says '/kb', 'search kb', 'find lesson about X', '搜知识库', '以前怎么处理 X', or needs to search the cross-project knowledge base manually. Accepts a query, searches ~/.claude/knowledge/ for past lessons, API gotchas, architecture decisions, and learning notes. Not when: user wants to ADD a new lesson from current session (use /collect-lesson); user wants to extract decisions from a settled session (use /crystallize); user means their Obsidian PKOS vault (use /pkos — different store: PKOS vault vs ~/.claude/knowledge cross-project lessons)."
user-invocable: true
model: sonnet
context: fork
agent: Explore
# background: false — brainstorm Step 1.3 / fix-bug (known-error lookup) consume this skill's
# result in the SAME turn (they phrase the next question from the retrieved lessons).
# `background` defaults to true, which returns only the agent name.
background: false
---

## Overview

Search the cross-project knowledge base at `~/.claude/knowledge/`. Returns matching entries with context for quick scanning, and offers to read full files.

## Process

### Step 1: Collect Query

If the user invoked `/kb <query>`, use the text after `/kb` as the query directly.

Otherwise, ask:
1. **Query** — search string (required)
2. **Category filter** — optional; one of the subdirectory names (e.g., `api-usage`, `bug-postmortem`, `architecture`, `platform-constraints`). Omit to search all.

### Step 1b: Detect Query Mode

Classify the query as **question** or **browse**:

- **Question mode**: Query contains `?`, starts with how/why/what/when/where/does/can/is/should/will, or is a natural language sentence (>5 words with verb structure)
- **Browse mode**: Query is a single word, a short phrase (1-3 words), or a kebab-case/snake_case identifier

This classification determines how results are presented in Step 3.

### Step 2: Search

First, resolve the knowledge base path: run `echo $HOME/.claude/knowledge/` via Bash to get the absolute path. Use this expanded path for all subsequent Grep and Read calls.

Queries usually arrive as a bag of 5–15 keywords from another skill (brainstorm, write-plan, verify-plan), mixing Chinese and English. Literal search alone handles that badly: the full phrase matches nothing, and single words match dozens of files sharing a generic word (`SwiftUI`, `prompt`, `test`). Measured on 27 real calls (2026-08-07 → 09-24): 12 entries that applied to the task were never returned, 10 of them literally findable. So find candidates two ways, then confirm by reading.

1. **Catalog pass (semantic).** Read the whole catalog in one call: `Grep(pattern="^(# |keywords:)", path=<KB path>, glob="*.md", output_mode="content")` — every entry's title and keywords, about 27k tokens for 300 entries (each line carries its path; measured 2026-09-26). Pick the entries whose title or keywords address **the query's technology and its problem**, in either language. Sharing a generic word is not enough.
2. **Literal pass.** Pick the query's 2–4 most distinctive terms (API names, error codes, specific nouns — not `SwiftUI`, `app`, `test`, `prompt`). `Grep(pattern="<term1>|<term2>|…", path=<KB path>, glob="*.md", output_mode="files_with_matches")`. This catches entries where the term appears only in the body.
3. **Confirm.** Union both passes, drop anything outside the category filter, and `Read(file, limit=40)` each candidate (at most 10). Keep an entry only if it would change what someone doing this task does. Candidates picked from titles alone are often wrong: in the 2026-09-26 measurement, 13 of 25 title-picked candidates did not hold up on reading.

If the user specified a category filter, narrow every path above to `<KB path>/{category}/`.

The kept entries are the results. The matching lines shown under each result in Step 3 below come from this Confirm read.

### Step 2.5: Resolve Validity

An entry's age says nothing about whether it still holds; its frontmatter does. For every matched file, read the validity fields in one call: `Grep(pattern="^(status|superseded_by|supersedes|verified_on):", path=<file>, output_mode="content")`.

1. **Superseded entries leave the result list.** For a file with `status: superseded`, find its `superseded_by:` filename with `Glob(pattern="**/{filename}", path=<resolved KB path>)`. If that successor is itself superseded, follow the chain (at most 3 hops). Put the final successor in the old entry's place in the results (once, if it is already there) and remember the pointer `{successor} ← {old filename}`.
   - The old entry is not shown as a result of its own. It appears only as the pointer line under its successor. A query that matched only the old entry still returns the successor: the knowledge moved, it did not disappear.
   - `superseded_by` missing or the file not found → keep the old entry as a result and mark it `⚠️ 标为已取代，但接替条目 {name} 找不到`. Never drop an entry whose successor cannot be shown.
2. **Version check.** For a file with `verified_on:`, keep the value for display. If it names Claude Code (`Claude Code 2.1.x`), run `claude --version` once and compare: a different version marks the entry `⚠️ 版本已变`. Other platforms are displayed, not compared.

### Step 3: Present Results

**Validity marker** (used by both modes), from Step 2.5:
- `⚠️ 版本已变：验证于 {verified_on}，当前 {current}` — a Claude Code version mismatch
- `ℹ️ 验证于 {verified_on}` — `verified_on` present, not comparable
- `⚠️ 标为已取代，但接替条目 {name} 找不到` — broken chain
- no marker — anything else

Under each successor, list what it replaced: `↳ 取代了 {old filename}`.

Show each entry's date (frontmatter `date:`, else the filename's `YYYY-MM-DD-` prefix). Age is shown, never used as a warning.

---

#### Step 3A: Browse Mode

Group results by file. For each file, show:

```
[{rank}] {file_path}  {validity marker, if any}
Category: {category from directory name}  |  Date: {date}
Keywords: {from frontmatter keywords line}
↳ 取代了 {old filename}        (one line per replaced entry, if any)

{matching lines with context — up to 8 lines per file}
```

If any result carries `⚠️ 版本已变`, append after the results list:
> ⚠️ {N} 条结果验证于旧版本，使用前先在当前版本上复核。

After presenting all results: "Read any of these in full? Specify the number(s)."

If the user names result(s): call `Read` with the file path and present the full content.

---

#### Step 3B: Question Mode (Synthesis)

1. **Rank results**: From the results after Step 2.5 (superseded entries already replaced by their successors), rank files by how directly they answer the question (judged from the Step 2 confirm read), then most recent date first. Take the top 5 files. Never read or cite a superseded entry as a source.

2. **Read full content**: For each of the top 5 files, call `Read(file_path, limit=100)` to get the complete entry (capped at 100 lines to bound context usage).

3. **Synthesize answer**: Using the read entries, compose a direct answer to the user's question. Format:

```
## Answer

{2-5 sentence direct answer to the question. Reference specific entries as [entry-filename] when citing a fact or recommendation.}

## Sources

[1] {file_path}  {validity marker, if any}
    Category: {cat} | Date: {date} | Keywords: {kw}
    ↳ 取代了 {old filename}   (if any)

[2] {file_path}  {validity marker, if any}
    Category: {cat} | Date: {date} | Keywords: {kw}

...

Need more detail on a source? Specify the number.
```

4. **Confidence fallback**: If the read entries do not contain enough information to answer the question directly, fall back to browse mode output and prefix with: "Found related entries but can't confidently answer this question. Here are the relevant entries:"

5. **Version warning**: If any cited source carries `⚠️ 版本已变`, say so in the Answer itself (the claim was observed on an older version) and append the version warning after the Sources section.

### Step 4: Zero Results

If Step 2 keeps no entry:

```
No entries found for "{query}" in ~/.claude/knowledge/.

Suggestions:
- Try broader or alternative keywords
- Use /collect-lesson to save new knowledge from this session
```

Also run a quick scan of the current project's `docs/09-lessons-learned/` as a local fallback:
`Grep(pattern=<query>, path="docs/09-lessons-learned/", output_mode="content", context=3)`

If local results found, present them with label: "[Project-local results — not in central knowledge base]"

#### PKOS Vault Fallback

If still no results after the project-local fallback, and `~/Obsidian/PKOS/` exists:

1. `Grep(pattern=<query>, path="~/Obsidian/PKOS/10-Knowledge", output_mode="content", context=3, head_limit=10)`
2. `Grep(pattern=<query>, path="~/Obsidian/PKOS/50-References", output_mode="content", context=3, head_limit=10)`

If PKOS results found, present them with label: "[PKOS vault results — not in central knowledge base. Use /pkos kb-bridge to export relevant entries.]"

**Structured query hint:** If the query targets specific properties (date range, topic, quality score), suggest:
> For structured queries, open `~/Obsidian/PKOS/99-System/bases/` in Obsidian — Bases views support filtering by date, topic, quality, and status.

This is a read-only search fallback. It does not modify the PKOS vault.

**Note**: This PKOS fallback also applies to Step 3B (Question/Synthesis mode) — if the initial search in `~/.claude/knowledge/` returns zero results, try the PKOS vault before giving up on synthesis.
