---
name: distill-discussion
description: "Use when you have raw discussion files (AI conversation exports, exploratory notes) and want to extract structured outputs. Routes each file to: crystal (decisions), lesson (failures/pitfalls), or skip (no conclusion)."
user-invocable: true
---

## Overview

Reads one or more discussion files and extracts structured knowledge from them. This is the file-based complement to `/crystallize` (which reads live conversation history). Use this skill after saving a conversation export to `docs/_discussions/`.

**Key differences from `/crystallize`:**
- Input is a file, not the current conversation context
- Can route to lesson output (not just crystals)
- Handles large files (>10KB) via agent dispatch for context isolation
- Processes external AI conversations (Claude.ai exports, ChatGPT exports) which have different structure than Claude Code chat logs

## Process

### Step 1: Identify Input Files

1. If the user specified file paths or a directory: use them
2. If no paths specified: ask the user which files or directory to process
3. If the user provides a directory path: Glob `{directory}/*.md` and present the list:
   ```
   Found {N} discussion files in {directory}:
   1. {path} ({size estimate: small <10KB / large >10KB})
   2. {path}
   ...

   Process all, or specify which ones?
   ```
   Wait for user response. If "all": process all files. If user specifies: process only those.

### Step 2: Classify Each File

For each input file:

Check file size with `Bash(wc -c < {path})`. Do NOT read the file to check size.

**If output > 10240 (10KB):** dispatch a `dev-workflow:distill-discussion-reader` agent (see Step 2a).
**If output <= 10240:** classify inline (see Step 2b).

#### Step 2a: Large File -- Agent Dispatch

Use the Task tool to dispatch the `dev-workflow:distill-discussion-reader` agent:

```
Read and classify this discussion file:

File: {path}
Project root: {project root}

Determine the conclusion type:
- crystal: the file contains clear decisions (approach chosen, alternatives rejected, constraints established)
- lesson: the file captures a failure, pitfall, or "don't do X" finding
- both: contains both decision records AND failure/pitfall records
- skip: discussion is exploratory, unresolved, or still pending

For "crystal" or "both": extract decisions in this format:
  Initial Idea: {user's original question/goal, denoised}
  Discussion Points: {key pivots, numbered}
  Rejected Alternatives: {what was tried and rejected, with reasons}
  Decisions: [D-001] {decision in imperative form}, [D-002] ...
  Constraints: {constraints that emerged}
  Scope Boundaries: IN: {item}, OUT: {item}

For "lesson" or "both": extract lesson entries in this format:
  Symptom: {what went wrong}
  Root Cause: {why}
  Prevention: {rule or check}
  Keywords: {3-6 keywords}
  Category: {category slug}
  Source Type: error | lesson

Return: classification, extracted content (in the formats above), and a 1-sentence summary.
```

Collect the agent's return value as `classification_result` for this file.

#### Step 2b: Small File -- Inline Classification

Read the file directly. Apply the same classification criteria:

- **crystal trigger:** file contains phrases like "decided", "going with", "rejected X because", "chosen approach", explicit decision lists, or a brainstorm session that reached a conclusion
- **lesson trigger:** file contains phrases like "mistake", "bug", "wrong approach", "should have", "lesson learned", "pitfall", "failed", or a debugging session where a root cause was found
- **both trigger:** file contains both sets of signals
- **skip trigger:** file ends with open questions, "TBD", "to explore", or discussion is still active

Produce `classification_result` with the same fields as the agent output above.

### Step 3: Present Classification to User

For all processed files, present a summary table:

```
Discussion Distillation Summary:

| File | Classification | Key Output | Action |
|------|---------------|-----------|--------|
| {filename} | crystal | {1-sentence decision summary} | Write crystal |
| {filename} | lesson | {1-sentence lesson summary} | Write lesson |
| {filename} | both | {summary} | Write crystal + lesson |
| {filename} | skip | {reason: pending/unresolved} | Skip |

Proceed with the above, or adjust any classification?
```

Wait for user confirmation. Apply any reclassifications the user requests.

### Step 4: Write Crystal Outputs

For each file classified as `crystal` or `both`:

1. Check if an existing crystal file covers the same topic: Glob `docs/11-crystals/*-crystal.md`, look for filename keywords matching the discussion topic
2. If an existing crystal is found: present both paths and ask "Append to existing crystal or create new?"
   - **Append:** read the existing crystal, add new `[D-xxx]` entries (continuing existing numbering), merge constraints and scope boundaries
   - **New:** create new file
3. Write to `docs/11-crystals/YYYY-MM-DD-{topic}-crystal.md` using the crystal format:

```markdown
---
type: crystal
status: active
tags: [{topic keywords}]
refs: [{source discussion file path}]
---

# Decision Crystal: {topic}

Date: YYYY-MM-DD

## Initial Idea
{from classification_result.Initial Idea}

## Discussion Points
{from classification_result.Discussion Points}

## Rejected Alternatives
{from classification_result.Rejected Alternatives, or "None."}

## Decisions (machine-readable)
{from classification_result.Decisions}

## Constraints
{from classification_result.Constraints, or "None."}

## Scope Boundaries
{from classification_result.Scope Boundaries, or omit section if none}

## Source Context
- Discussion file: {source file path}
- Design doc: none
- Design analysis: none
```

Note: Crystal outputs from `distill-discussion` follow the same format as `/crystallize` output so they are consumed identically by plan-writer and plan-verifier.

### Step 5: Write Lesson Outputs

For each file classified as `lesson` or `both`:

1. If the `add_entry` tool is available (provided by rag-server MCP; check tool availability before calling):
   - Call `add_entry` with the extracted lesson fields (title, category, scope: "project", content: the markdown body, keywords, source_type)
   - Report: `Saved as {id} at {path}`

2. If `add_entry` is unavailable:
   - Determine the next lesson number: Glob `docs/09-lessons-learned/E*.md`, count files, increment
   - Write to `docs/09-lessons-learned/E{NNN}-{slug}.md` with the lesson body
   - Report the path

### Step 6: Mark Source Files as Distilled

For each processed file (crystal, lesson, or both -- not skip):

1. Read the source discussion file
2. Prepend YAML frontmatter (or add to existing frontmatter if present):

```yaml
---
distilled: true
distilled-to:
  - {crystal file path, if produced}
  - {lesson file path, if produced}
---
```

3. Write the updated file back

For skipped files: add frontmatter `distilled: false` with a `skip-reason` field:

```yaml
---
distilled: false
skip-reason: "pending -- discussion unresolved as of YYYY-MM-DD"
---
```

### Step 7: Final Report

Present a completion summary:

```
Distillation complete:

Crystals written:  {N} file(s)
  - {path}
Lessons saved:     {N} entry/entries
  - {path or id}
Skipped:           {N} file(s) (reason: pending/unresolved)

Source files updated with distilled: true frontmatter.
```

## Completion Criteria

- All input files have been classified
- Crystal files written for `crystal` / `both` classifications
- Lesson entries saved for `lesson` / `both` classifications
- Source files updated with `distilled:` frontmatter
- Final report presented
