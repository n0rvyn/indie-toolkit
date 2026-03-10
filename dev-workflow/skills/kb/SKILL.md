---
name: kb
description: "Use when you need to search the cross-project knowledge base manually. Accepts a query, searches ~/.claude/knowledge/ for past lessons, API gotchas, architecture decisions, and learning notes."
user-invocable: true
---

## Overview

Search the cross-project knowledge base at `~/.claude/knowledge/`. Returns matching entries with context for quick scanning, and offers to read full files.

## Process

### Step 1: Collect Query

If the user invoked `/kb <query>`, use the text after `/kb` as the query directly.

Otherwise, ask:
1. **Query** — search string (required)
2. **Category filter** — optional; one of the subdirectory names (e.g., `api-usage`, `bug-postmortem`, `architecture`, `platform-constraints`). Omit to search all.

### Step 2: Search

Run two parallel Grep searches over `~/.claude/knowledge/`:

1. **Content search**: `Grep(pattern=<query>, path="~/.claude/knowledge/", output_mode="content", context=3)`
2. **Keyword search**: `Grep(pattern=<query>, path="~/.claude/knowledge/", glob="*.md", output_mode="content", context=0)` targeting `keywords:` lines in frontmatter

If the user specified a category filter, narrow the path to `~/.claude/knowledge/{category}/`.

If the query has multiple words, also try each word individually as a secondary search if the full-phrase search returns zero results.

### Step 3: Present Results

Group results by file. For each file, show:

```
[{rank}] {file_path}
Category: {category from directory name}  |  Date: {from frontmatter}
Keywords: {from frontmatter keywords line}

{matching lines with context — up to 8 lines per file}
```

After presenting all results: "Read any of these in full? Specify the number(s)."

If the user names result(s): call `Read` with the file path and present the full content.

### Step 4: Zero Results

If no results from either search:

```
No entries found for "{query}" in ~/.claude/knowledge/.

Suggestions:
- Try broader or alternative keywords
- Use /collect-lesson to save new knowledge from this session
```

Also run a quick scan of the current project's `docs/09-lessons-learned/` as a local fallback:
`Grep(pattern=<query>, path="docs/09-lessons-learned/", output_mode="content", context=3)`

If local results found, present them with label: "[Project-local results — not in central knowledge base]"
