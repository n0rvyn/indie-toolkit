---
name: migrate
description: "Migrates an external Obsidian vault into PKOS. Scans any source vault (configured via migrate-sources.yaml), generates migration reports, imports Markdown/PDF/images with PKOS frontmatter. Use when the user says 'migrate', '/migrate --scan-only', or wants to import notes from an external vault."
model: sonnet
user-invocable: true
---

## Overview

Migrates an external Obsidian vault into PKOS. The skill is **source-vault-agnostic** — all source definitions live in `~/Obsidian/PKOS/.state/migrate-sources.yaml`, not hardcoded in this skill. This makes the skill reusable for any source vault without code changes.

**Core capabilities:**
- `--scan-only`: Discover all files in the source vault, classify by type, deduplicate against PKOS, and present a migration report. Writes nothing.
- Full migration: Import Markdown, archive PDFs with OCR, copy images, track state, dispatch ripple compilation.

## Source Vault Configuration

The skill reads source vault definitions from `~/Obsidian/PKOS/.state/migrate-sources.yaml`. If this file does not exist, initialize it with:

```yaml
sources: {}
```

**Adding a source** (example for 99-Obsidian):

```yaml
sources:
  99-Obsidian:
    path: "/Users/norvyn/Code/Scripts/99-Obsidian/"
    type: obsidian
    classification_rules:
      - pattern: "WeChat/Channel/**"
        type: reference
        source: wechat-ai
        quality: 1
      - pattern: "WeChat/Official Account/**"
        type: knowledge
        source: wechat
        quality: 3
      - pattern: "**"
        type: knowledge
        source: external-vault
        quality: 1
    pdf_archive_prefix: "~/Obsidian/PDFs/"
    wechat_ai_judgment: true
```

**Classification rule format:**
- `pattern`: Glob-style path pattern relative to source vault root. First matching rule wins.
- `type`: PKOS type (`knowledge`, `idea`, `reference`, `person`, `project`)
- `source`: PKOS source field value
- `quality`: Initial quality value (0-5)

**`wechat_ai_judgment: true`** enables AI dynamic classification for WeChat content (素材 vs 作品), via the inbox-processor agent. When false, falls back to rule-based classification.

## Arguments

- `--scan-only`: Generate migration report without writing any files. Equivalent to `--dry-run`.
- `--dry-run`: Alias for `--scan-only`.
- `--source-vault PATH`: Absolute path to the source vault directory. Overrides config.
- `--source-name NAME`: Use a named source from `migrate-sources.yaml` (e.g., `--source-name 99-Obsidian`). If only one source is defined, it is used automatically.
- `--force`: Re-migrate all files (skip deduplication check against state file), but still check PKOS vault deduplication.
- `--skip-ripple`: Skip ripple compilation after import.
- `--resume`: Resume from interruption point (default behavior if state file exists and `--force` is not set).

## Process

### Step 1: Resolve Source Vault

1. If `--source-vault PATH` provided: use that path, derive source name from directory name.
2. If `--source-name NAME` provided: look up in `migrate-sources.yaml`. Error if not found.
3. If neither provided: check if exactly one source exists in `migrate-sources.yaml` → use it. If multiple, error with message "Specify --source-name or --source-vault".
4. If `migrate-sources.yaml` does not exist: error with instructions to create it.

Resolve `pdf_archive_prefix` (default: `~/Obsidian/PDFs/` if not set in config).

### Step 2: Discover Files

For the resolved source vault path:

```bash
find "{source_vault}" -type f \( -name "*.md" -o -name "*.pdf" -o -name "*.PDF" \) 2>/dev/null | sed 's|{source_vault}/||'
find "{source_vault}" -type f \( -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" -o -name "*.gif" -o -name "*.bmp" -o -name "*.tiff" -o -name "*.heic" \) 2>/dev/null | sed 's|{source_vault}/||'
```

Exclude `.obsidian/`, `.trash/`, `.cursor/` directories from discovery.

Collect into:
- `markdown_files[]`
- `pdf_files[]`
- `image_files[]`

Present summary:
```
Source vault: {source_vault}
  Markdown: {n} files
  PDFs: {m} files
  Images: {k} files
```

### Step 3: Load Classification Rules

Read the matching source entry from `migrate-sources.yaml`. Build a rule list (first-match wins).

If `wechat_ai_judgment: true` is set, prepare to dispatch inbox-processor for WeChat files.

### Step 4: Load State File (for migrate mode only)

Skip for `--scan-only`.

Read `~/Obsidian/PKOS/.state/migrate-state.yaml`:
- If file exists and `--force` not set: load `migrated[]` entries, set `already_migrated` set by `source_path`.
- If file exists and `--force` set: ignore existing entries, start fresh.
- If file does not exist: initialize empty.

### Step 5: Scan for Duplicates (for migrate mode only)

Skip for `--scan-only`.

Build deduplication hashes for all existing PKOS notes:
```bash
find ~/Obsidian/PKOS/10-Knowledge ~/Obsidian/PKOS/20-Ideas ~/Obsidian/PKOS/30-Projects ~/Obsidian/PKOS/40-People ~/Obsidian/PKOS/50-References -name "*.md" 2>/dev/null
```

For each existing PKOS note, compute `dedup_hash = md5(title + ":" + body_without_frontmatter)`. Store in `existing_hashes{}` map.

### Step 6: Classify and Process Files

#### 6a. Classify by Rules

For each `markdown_file`:

1. Apply first matching `classification_rules` pattern → get `type`, `source`, `quality`.
2. If `wechat_ai_judgment: true` AND path matches `WeChat/Channel/**` or `WeChat/Official Account/**`: dispatch `inbox-processor` agent for AI judgment.
3. Skip if already in `already_migrated` (migrate mode only, unless `--force`).

#### 6b. WeChat AI Dynamic Judgment

When `wechat_ai_judgment: true` and file is under `WeChat/`:

Dispatch `pkos:inbox-processor` agent with:
```yaml
items:
  - id: "{slug}"
    source: wechat-migrate
    raw_content: "{full file content}"
    raw_type: text
    metadata:
      source_vault: "{source_name}"
      relative_path: "{relative_path}"
      rule_type: "{rule_type}"
      rule_source: "{rule_source}"
      rule_quality: "{rule_quality}"
```

**Prompt override for WeChat judgment** (passed to inbox-processor):
```
Analyze this WeChat content and classify it as 素材 (source material) or 作品 (finished work).

素材 (source material): 原始转发/摘录、碎片化（单条记录、问答）、无深度加工、没有完整标题体系
作品 (finished work): 经过整理、有结构（多个文件组成系列）、有标题体系、章节分明、逻辑完整

Return:
- classification: "素材" or "作品"
- reasoning: brief explanation
- if 作品: type=knowledge, quality=3
- if 素材: type=reference, quality=1
- vault_subdirectory: suggested subdirectory under wechat-channel/ or wechat-oa/ based on content topic
```

Agent returns updated classification. Use this to override the rule-based classification.

#### 6c. Compute Dedup Hash

For Markdown files: `dedup_hash = md5(title + ":" + body_without_frontmatter)`.

- If `--scan-only`: add to candidate list.
- If migrate mode:
  - Check `already_migrated` set: skip if present (no `--force`).
  - Check `existing_hashes`: if found, record as `skipped_duplicates`.
  - Otherwise: add to `import_candidates[]`.

#### 6d. Determine Vault Path

Map source relative path to PKOS vault path:

```
source_relative_path = "AI & LLM/GPTs/Some Note.md"
source_dir = "AI & LLM"
source_filename = "Some Note.md"

if WeChat/Channel/** → "50-References/wechat-channel/{wechat_ai_subdir}/{filename}"
if WeChat/Official Account/** → "10-Knowledge/wechat-oa/{wechat_ai_subdir}/{filename}"
else → "10-Knowledge/{slugified_source_dir}/{filename}"
```

`slugified_source_dir`: lowercase, spaces→hyphens, special chars removed.

If collision with existing vault file: append `-{counter}` to filename.

#### 6e. PDF Processing

For each `pdf_file`:

1. Compute `relative_path` within source vault.
2. Determine `pdf_archive_path`: `{pdf_archive_prefix}/{relative_path}`
3. Compute `dedup_hash`.
4. Skip if already migrated (no `--force`).
5. Check duplicate in PKOS vault.
6. For `--scan-only`: add to candidate list.
7. For migrate mode: add to `import_candidates[]`.

### Step 7: Present Migration Report (--scan-only)

Present for `--scan-only`, or at the start of migrate mode before writing:

```
PKOS Migration Report — {source_name} → PKOS
  Source: {source_vault}
  Target: ~/Obsidian/PKOS/

  Scan results:
    Markdown: {n} files
    PDFs: {m} files
    Images: {k} files

  Classification preview:
    knowledge: {n1} → 10-Knowledge/
    idea: {n2} → 20-Ideas/
    reference: {n3} → 50-References/
    project: {n4} → 30-Projects/
    person: {n5} → 40-People/

  WeChat AI judgment: {n_wechat} files to be processed by inbox-processor

  Deduplication:
    Already in PKOS (will skip): {n_dup}
    Import candidates: {n_candidates}

  PDF archive:
    Target: {pdf_archive_prefix}/
    Files: {n_pdfs}
```

### Step 8: Execute Migration (migrate mode only)

Skip this step if `--scan-only`.

For each candidate (in order):

#### 8a. Markdown Migration

1. Read source file content.
2. Extract title (first `# ` heading or filename).
3. Build PKOS frontmatter:
   ```yaml
   ---
   type: {type}
   source: {source}
   created: {date from frontmatter or file mtime or filename prefix}
   tags: [{extracted or inferred}]
   quality: {quality}
   citations: 0
   related: []
   status: seed
   migrated_from: "{source_name}/{relative_path}"
   aliases: [{original filename}]
   ---
   ```
4. Convert body:
   - Strip frontmatter from source
   - Rewrite wikilinks per DP-007 (try to map paths, fallback to plain text)
   - Strip `![[embeds]]` (images handled separately)
5. Write to `~/Obsidian/PKOS/{vault_path}`.

#### 8b. PDF Migration

1. Copy original PDF to `{pdf_archive_prefix}/{relative_path}`:
   ```bash
   mkdir -p "{pdf_archive_prefix}/{relative_dir}"
   cp "{source_vault}/{relative_path}" "{pdf_archive_prefix}/{relative_path}"
   ```
2. Run OCR:
   ```bash
   ${CLAUDE_PLUGIN_ROOT}/../../mactools/1.0.1/skills/ocr/scripts/ocr "{source_vault}/{relative_path}"
   ```
   Or use mactools OCR: `${MACTools_ROOT}/skills/ocr/scripts/ocr.swift "{source_vault}/{relative_path}" --output -`
3. Write PKOS note at mapped vault path:
   ```yaml
   ---
   type: reference
   source: {source}
   created: {today's date}
   tags: [{inferred from path}]
   quality: 1
   citations: 0
   related: []
   status: seed
   migrated_from: "{source_name}/{relative_path}"
   pdf_archive: "{pdf_archive_prefix}/{relative_path}"
   pdf_text_extraction: success | failed
   aliases: []
   ---
   ```
   If OCR failed: set `pdf_text_extraction: failed`.

#### 8c. Image Copy

```bash
mkdir -p "~/Obsidian/PKOS/{mapped_parent_dir}"
cp "{source_vault}/{relative_path}" "~/Obsidian/PKOS/{mapped_parent_dir}/"
```

#### 8d. Update State

After each file is processed (not at end — interruption-safe):

Update `~/Obsidian/PKOS/.state/migrate-state.yaml`:
```yaml
source_name: "{source_name}"
source_vault: "{source_vault}"
migrated:
  - source_path: "{relative_path}"
    title: "{title}"
    dedup_hash: "{hash}"
    vault_path: "{vault_path}"
    type: "{type}"
    status: migrated
skipped_duplicates: [...]
errors: [...]
last_migration_path: "{relative_path}"
```

### Step 9: Ripple Compilation

Skip if `--skip-ripple`.

For each newly migrated Markdown note, dispatch `pkos:ripple-compiler` agent sequentially:

```yaml
note_path: "{vault_path}"
title: "{title}"
tags: [{tags}]
related_notes: []
```

### Step 10: Report

```
PKOS Migration — {source_name} → PKOS
  Migrated: {n} files
    knowledge: {n1} → 10-Knowledge/
    reference: {n2} → 50-References/
    project: {n3} → 30-Projects/
  Skipped (duplicate): {n_dup}
  Errors: {n_err}

  PDF archive:
    Archived: {n_pdf} → {pdf_archive_prefix}/
    OCR success: {n_success}
    OCR failed: {n_failed}

  Ripple compilation:
    MOCs updated: {count}
    Cross-references added: {count}
```

## Error Handling

- If source vault path does not exist: error and stop.
- If `migrate-sources.yaml` is malformed: error with specific YAML parse error.
- If a single file import fails → log error, continue with others.
- If PDF OCR fails → still archive PDF, write note with `pdf_text_extraction: failed`.
- If state file is corrupted → backup to `.state/migrate-state.yaml.bak`, reinitialize.
- Never modify source vault files.

## PDF OCR Dependency

PDF text extraction uses the mactools OCR skill. If OCR is unavailable, set `pdf_text_extraction: failed` and write the note without extracted text.

OCR command:
```bash
${MACTools_ROOT}/skills/ocr/scripts/ocr.swift "{pdf_path}" --output -
```

If mactools is not available, fall back to:
```bash
textutil -convert txt -stdout "{pdf_path}" 2>/dev/null || echo "(OCR unavailable)"
```

## Deduplication Hash

`dedup_hash = md5(title + ":" + body_without_frontmatter)`

- Title: first `# ` heading in file, or filename if no heading.
- Body: all content after frontmatter block (lines after closing `---`).
- Frontmatter changes alone do not trigger re-import.
