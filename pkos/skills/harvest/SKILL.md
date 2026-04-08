---
name: harvest
description: "Scans ~/Code/Projects/*/docs/ for crystals, lessons, and design docs, imports to PKOS vault with Obsidian Flavored Markdown. Use when the user says 'harvest', 'scan projects', 'import knowledge', or via Adam cron."
model: sonnet
user-invocable: false
---

## Overview

Scans all projects under `~/Code/Projects/` for high-value knowledge documents (crystals, lessons, design docs) and imports them into the PKOS vault at `~/Obsidian/PKOS/30-Projects/{project}/`. Uses incremental hash-based change detection to only process new or modified files. After import, dispatches ripple-compiler for each note to build cross-project MOC linkage.

**Harvest scope** (per crystal D-S01, D-S02):
- `docs/11-crystals/*-crystal.md` — decision records
- `docs/09-lessons-learned/*.md` OR `docs/09-lessons/*.md` — lessons learned
- `docs/06-plans/*-design.md` — design documents (NOT plans, NOT dev-guides)
- Excludes: plans (process artifacts), CLAUDE.md (AI behavior config), non-docs files

## Arguments

- `--dry-run`: Show what would be imported without writing files
- `--force`: Re-import all files even if hash unchanged
- `--project NAME`: Only harvest from a specific project (default: all)
- `--skip-ripple`: Skip ripple compilation after import (faster, for bulk initial import)

## Process

### Step 1: Discover Projects

```bash
find ~/Code/Projects -maxdepth 1 -type d ! -name ".*" ! -name "Z-Archived" | sort
```

For each project directory, check if `docs/` exists:
```bash
test -d ~/Code/Projects/{project}/docs && echo "has docs"
```

Skip projects without a `docs/` directory.

If `--project NAME` specified, filter to only that project.

### Step 2: Load State

Read `~/Obsidian/PKOS/.state/harvest-state.yaml`:
```yaml
harvested:
  - source: "Adam/docs/11-crystals/2026-03-18-goal-driven-architecture-crystal.md"
    hash: "a1b2c3d4..."
    vault_path: "30-Projects/Adam/goal-driven-architecture-crystal.md"
    type: crystal
    date: "2026-04-08"
  - source: "Runetic/docs/09-lessons-learned/first-attempt-failure.md"
    hash: "e5f6g7h8..."
    vault_path: "30-Projects/Runetic/first-attempt-failure.md"
    type: lesson
    date: "2026-04-08"
last_harvest: "2026-04-08T10:00:00"
```

If file does not exist, initialize with empty list.

### Step 3: Scan for Harvestable Documents

For each project with docs/:

**Crystals:**
```bash
find ~/Code/Projects/{project}/docs/11-crystals -name "*-crystal.md" 2>/dev/null
```

**Lessons:**
```bash
find ~/Code/Projects/{project}/docs/09-lessons* -name "*.md" 2>/dev/null
```

**Design docs:**
```bash
find ~/Code/Projects/{project}/docs/06-plans -name "*-design.md" 2>/dev/null
```

For each found file:
1. Compute file hash: `md5 -q "{file_path}"`
2. Look up in state: same source path + same hash → skip (unchanged)
3. Same source path + different hash → mark as update
4. New source path → mark as new

If `--force`: treat all files as new regardless of hash.

Collect candidates. Present summary:
```
Harvest scan: {N} projects, {M} documents found
  New: {new_count} (crystals: {c}, lessons: {l}, designs: {d})
  Updated: {updated_count}
  Unchanged: {unchanged_count}
```

If `--dry-run`: display the full list and stop.

### Step 4: Convert and Import

For each candidate (new or updated):

#### 4a. Read source document

Read the full file content. Extract frontmatter if present (YAML between `---` markers).

#### 4b. Classify document type

| Source pattern | Type | PKOS `type` value |
|---|---|---|
| `11-crystals/*-crystal.md` | crystal | `reference` |
| `09-lessons*/*.md` | lesson | `knowledge` |
| `06-plans/*-design.md` | design | `reference` |

#### 4c. Extract or infer metadata

**If frontmatter exists:**
- Extract `tags:` (or `tags:` / `keywords:` — normalize to `tags:`)
- Extract `date:` or infer from filename (`YYYY-MM-DD-` prefix)
- Extract `status:` if present

**If no frontmatter (older projects like ModelProxy):**
- Infer title from first `# ` heading
- Infer date from filename prefix or file mtime
- Infer tags from: heading keywords, bold terms in Discussion Points, decision text
- Set status to `active` (crystals) or `seed` (lessons/designs)

#### 4d. Convert to PKOS format with Obsidian Flavored Markdown

Generate the vault note following `references/obsidian-format.md`:

```yaml
---
type: {PKOS type from 4b}
source: project-harvest
created: {date}
tags: [{extracted or inferred tags}]
quality: 1
citations: 0
related: []
status: {extracted or "seed"}
harvest_source: "{project}/{relative_path}"
harvest_project: "{project}"
harvest_type: "{crystal|lesson|design}"
aliases: []
---

# {title}

> [!insight] Project: {project}
> Harvested from `{project}/docs/{relative_path}` on {today's date}.
> Type: {crystal|lesson|design doc}

{body content — preserve original markdown}

## Connections

{Scan PKOS vault for tag-overlapping notes in 30-Projects/ and 10-Knowledge/:}
{For each match: `- [[{note-title}]]`}
{If a MOC exists for any of this note's tags: `- See also: [[MOC-{tag}]]`}
```

**Format rules:**
- Preserve the original document body verbatim (OUT scope: do not modify source projects)
- Add wikilinks in the Connections section only, not inline in the body
- If the source document already has wikilinks (e.g., crystals with `[[references]]`), preserve them
- Strip source-project-specific paths in refs (e.g., `docs/06-plans/...` → just the filename)

#### 4e. Determine vault path

Target: `~/Obsidian/PKOS/30-Projects/{project}/{filename}`

```bash
mkdir -p ~/Obsidian/PKOS/30-Projects/{project}
```

Use the source filename as the vault filename. If a file with the same name already exists from a different source path (collision), append the source directory as suffix: `{filename-without-ext}-{dir-slug}.md`.

#### 4f. Write to vault

Write the converted note using the Write tool.

#### 4g. Update state entry

Add or update the entry in the harvested list with new hash and vault_path.

### Step 5: Ripple Compilation

Skip this step if `--skip-ripple`.

For each newly imported or updated note, dispatch `pkos:ripple-compiler` agent with:
```yaml
note_path: "30-Projects/{project}/{filename}"
title: "{title}"
tags: [{tags from frontmatter}]
related_notes: [{related notes from Connections section}]
```

Dispatch sequentially (not parallel) to avoid concurrent MOC edits.

If ripple fails for a note, log warning and continue — the source note is already saved.

### Step 6: Update State File

Write updated `~/Obsidian/PKOS/.state/harvest-state.yaml` with all entries (existing unchanged + new + updated).

### Step 7: Report

```
PKOS Harvest — {date}
  Projects scanned: {N}
  Documents found: {M}
  Imported: {K} (new: {new}, updated: {upd})
  Skipped: {S} (unchanged: {unch}, errors: {err})
  By type: crystals={c}, lessons={l}, designs={d}
  By project: {top 5 projects by import count}

  Ripple compilation:
    MOCs updated: {count}
    MOCs created: {count}
    Cross-references added: {count}

Run /generate-bases-views --target cross-project to update Bases views.
```

## Error Handling

- If a project's docs/ directory is unreadable → log, skip, continue
- If a single file import fails → log error with file path, skip, continue
- If ripple fails for a note → log warning, note is already saved
- If state file is corrupted → backup to `.state/harvest-state.yaml.bak`, reinitialize
- Never modify source project files (OUT scope)

## Deduplication

- Same file content across projects (e.g., Cashie and Lifuel sharing a lesson): import both but with different vault paths under their respective project directories. The ripple-compiler will link them via shared tags, and the user can manually merge if desired.
- Same crystal imported twice (hash unchanged): skip via state file check.
