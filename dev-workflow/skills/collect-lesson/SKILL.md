---
name: collect-lesson
description: "Use after resolving a bug, completing a task with notable pitfalls, or discovering an important architecture constraint. Extracts a structured entry from the session and saves it to the knowledge base."
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

### Step 2: Check for Near-Duplicates

Search the central knowledge base for similar entries:

1. `Grep(pattern="<keywords joined by |>", path="~/.claude/knowledge/", output_mode="files_with_matches")`
2. For each matching file, read its frontmatter `keywords:` line and title
3. If any file has significant keyword overlap (3+ shared keywords): present it to the user as "Similar entry already in knowledge base:" and ask whether to create a new entry, update the existing one, or skip

If `~/.claude/knowledge/` does not exist yet, skip this step.

### Step 3: Ask User to Confirm

Present the draft entry:

```
Draft knowledge entry:

Title:     {suggested title}
Category:  {category}
Keywords:  {keyword1}, {keyword2}, ...
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

Wait for user response. Apply any edits before saving.

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
source_project: {current project name, optional}
---
# {Title}

{body}
```

5. Report back: `Saved to {file_path}`

## Completion Criteria

- Entry saved to `~/.claude/knowledge/{category}/` or `docs/09-lessons-learned/` with correct frontmatter
- User confirmed the draft before saving
