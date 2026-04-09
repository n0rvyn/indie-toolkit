---
type: feature-spec
status: active
tags: [migration, pkos, obsidian, vault]
refs:
  - docs/06-plans/2026-03-21-pkos-design.md
  - docs/06-plans/2026-03-21-pkos-dev-guide.md
---

# migrate

> One-time migration of an external Obsidian vault into PKOS. Scans any source vault (configured via `--source-vault` or config file), discovers Markdown/PDF/image files, classifies content, deduplicates against existing PKOS notes, and imports with PKOS frontmatter. Source vault is archived after migration.

**Design sources:**
- `docs/06-plans/2026-03-21-pkos-design.md` § Layer 3 (pkos Plugin Skills), Layer 4 (Obsidian Vault), Layer 6 (Notion Operations Dashboard)
- `docs/06-plans/2026-03-21-pkos-dev-guide.md` Phase 10 (new addition)
- `pkos/skills/harvest/SKILL.md` — state file + hash-based change detection pattern
- `pkos/skills/inbox/SKILL.md` — frontmatter format + routing logic
- `pkos/skills/references/obsidian-format.md` — PKOS frontmatter + wikilink conventions
- `pkos/agents/inbox-processor.md` — classification + metadata extraction
- `mactools/skills/ocr/SKILL.md` — PDF OCR via Vision framework

---

## User Stories

- 用户可以指定源 vault 路径，migrate skill 从该路径扫描文件而不 hardcode 路径 → ❌ not implemented
- 用户可以通过配置文件预设多个源 vault 的映射规则，支持一键切换 → ❌ not implemented
- 用户可以运行 `/migrate --scan-only` 生成迁移摸底报告（文件数、分类预览、去重候选）而不写入任何文件 → ❌ not implemented
- 用户可以将源 vault 的 Markdown 文件迁移到 PKOS，文件夹结构映射到 PKOS type 类别 → ❌ not implemented
- 用户可以将 PDF 归档到 ~/Obsidian/PDFs/，将提取的文本作为 PKOS note 写入 → ❌ not implemented
- 用户可以通过 title + content hash 对现有 PKOS notes 去重 → ❌ not implemented
- 用户可以使用 .state/migrate-state.yaml 恢复中断的迁移 → ❌ not implemented
- 用户可以复制图片文件（仅复制，不处理）到 PKOS 对应目录 → ❌ not implemented
- 用户可以查看迁移摘要（新增、跳过、冲突数量） → ❌ not implemented
- 用户可以在迁移后对每个导入的 note 触发 ripple compilation → ❌ not implemented

## Expected Behavior

### Scenario 1: Dry-run Scan Report

A user runs `/migrate --scan-only --source-vault /path/to/vault`. The skill:

1. **Discovers** all Markdown, PDF, and image files in the source vault
2. **Classifies** each file by source directory and applies the correct PKOS type/source (using source-specific rules from config)
3. **Deduplicates** against existing PKOS vault notes (title + content hash)
4. **Presents** a migration report: file counts by type/category, duplicate candidates, WeChat content preview, PDF list
5. **Writes no files** — purely diagnostic

### Scenario 2: Full Vault Migration

A user runs `/migrate --source-vault /path/to/vault` (or uses a named source from config). The skill:

1. **Reads** source configuration (mapping rules for type/source classification)
2. **Discovers** all Markdown, PDF, and image files in the source vault
3. **Classifies** each file using source-specific rules + AI dynamic judgment (for WeChat content)
4. **Deduplicates** against existing PKOS vault notes (title + content hash)
5. **Migrates** Markdown files as-is (with converted frontmatter) to corresponding PKOS directories
6. **Archives** PDFs to `~/Obsidian/PDFs/`, runs OCR, writes extracted text as PKOS notes
7. **Copies** images to corresponding PKOS directories (no processing)
8. **Tracks** progress in `.state/migrate-state.yaml` for resume capability
9. **Dispatches** ripple compilation for each newly imported note

### Source Vault Configuration

The skill reads source vault definitions from `~/Obsidian/PKOS/.state/migrate-sources.yaml`:

```yaml
sources:
  99-Obsidian:
    path: "/Users/norvyn/Code/Scripts/99-Obsidian/"
    type: "obsidian"
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
        source: "external-vault"
        quality: 1
    pdf_archive_prefix: "~/Obsidian/PDFs/"
```

Users edit this file to define their own source vaults and classification rules. The skill is source-vault-agnostic — no paths are hardcoded.

### Directory-to-Type Mapping (Generic)

| Source Directory Pattern | PKOS Destination | PKOS `type` | PKOS `source` | Initial `quality` |
|-------------------------|------------------|-------------|---------------|-------------------|
| Configured `WeChat/Channel/**` | `50-References/` | `reference` | `wechat-ai` | 1 |
| Configured `WeChat/Official Account/**` | `10-Knowledge/` | `knowledge` | `wechat` | 3 |
| All other directories | Map folder name to best-fit PKOS category (see below) | `knowledge` | `external-vault` | 1 |

**General folder-to-category mapping:**
- Directories containing `idea`, `创意`, `想法` → `20-Ideas/` + `idea`
- Directories containing `project`, `项目` → `30-Projects/` + `project`
- Directories containing `people`, `人物`, `person` → `40-People/` + `person`
- Directories containing `reference`, `参考`, `articles` → `50-References/` + `reference`
- All others → `10-Knowledge/` + `knowledge`

### WeChat Subdirectory Classification

WeChat content is classified via AI dynamic judgment (inbox-processor agent). The agent is given explicit criteria:

> **素材 (source material):** 原始转发/摘录、碎片化（单条记录、问答）、无深度加工 → type: reference, source: wechat-ai
> **作品 (finished work):** 经过整理、有结构（多个文件组成系列）、有标题体系、逻辑完整 → type: knowledge, source: wechat, quality: 3

The inbox-processor analyzes each WeChat file and returns a classification decision. All WeChat files from `WeChat/Channel/` are pre-tagged as candidate AI-generated; the AI confirms or overrides this based on content structure.

### PDF Migration Flow

For each PDF found in 99-Obsidian:
1. Copy the original PDF to `~/Obsidian/PDFs/` preserving relative directory structure
2. Run OCR via `${SKILLS_ROOT}/ocr/scripts/ocr.swift` (or compiled binary) to extract text
3. Write a PKOS note at the corresponding vault path (same relative path, `.pdf` → `.md`) with:
   - `type: reference`, `source: wechat-ai` (if from WeChat/Channel) or `source: 99-obsidian` otherwise
   - `quality: 1`
   - `pdf_archive: "{path in ~/Obsidian/PDFs/}"` field pointing to archived original
4. If OCR fails: still archive the PDF, but write note with `pdf_archive` field and `pdf_text_extraction: failed`

### Image Migration Flow

For each image file found in 99-Obsidian:
- Copy to `~/Obsidian/PKOS/` preserving relative directory structure under the mapped category
- No frontmatter or note created (images are referenced from their parent Markdown notes)
- Supported formats: `png`, `jpg`, `jpeg`, `gif`, `bmp`, `tiff`, `heic`

### Deduplication Strategy

Before importing a note, compute `dedup_hash = md5(title + ":" + content_without_frontmatter)`. Check against:
1. State file entries in `.state/migrate-state.yaml` (already-migrated notes from this run)
2. Existing PKOS vault notes: scan all `10-Knowledge/`, `20-Ideas/`, `30-Projects/`, `40-People/`, `50-References/` for same `dedup_hash`

If duplicate found: skip importing this note, record in migration summary as "skipped (duplicate)".

### State File Format

`~/Obsidian/PKOS/.state/migrate-state.yaml`:
```yaml
source_name: "99-Obsidian"              # matches migrate-sources.yaml
source_vault: "/Users/norvyn/Code/Scripts/99-Obsidian/"
target_vault: "~/Obsidian/PKOS/"
started: "2026-04-09T10:00:00+08:00"
migrated:
  - source_path: "AI & LLM/find-tuning/LLM Fine Tuning.md"
    title: "LLM Fine Tuning"
    dedup_hash: "a1b2c3d4..."
    vault_path: "10-Knowledge/ai-llm/llm-fine-tuning.md"
    type: knowledge
    status: migrated
  - source_path: "WeChat/Channel/跑者学堂/Scripts/Published/第一讲：心率区间——“引擎”转速表，你真的看懂了吗？.md"
    title: "第一讲：心率区间"
    dedup_hash: "e5f6g7h8..."
    vault_path: "50-References/wechat-channel/跑者学堂/第一讲：心率区间——“引擎”转速表，你真的看懂了吗？.md"
    type: reference
    source: wechat-ai
    status: migrated
  - source_path: "Certification/K8S/CKA/QA/Kubernetes/4- CKA Simulator Kubernetes 1.25.pdf"
    title: "4- CKA Simulator Kubernetes 1.25"
    dedup_hash: "i9j0k1l2..."
    vault_path: "50-References/certification/k8s/cka/4- CKA Simulator Kubernetes 1.25.md"
    type: reference
    source: "external-vault"
    pdf_archive: "Certification/K8S/CKA/QA/Kubernetes/4- CKA Simulator Kubernetes 1.25.pdf"
    pdf_text_extraction: success
    status: migrated
skipped_duplicates:
  - source_path: "some/duplicate.md"
    dedup_hash: "m3n4o5p6..."
    matched_vault_path: "10-Knowledge/some/duplicate.md"
errors:
  - source_path: "some/failing-file.md"
    error: "Error description"
last_migration_path: "AI & LLM/find-tuning/"  # for resume
```

### Resume Capability

If the skill is re-run after interruption:
1. Read `.state/migrate-state.yaml` if it exists
2. Skip all entries already in `migrated[]` (by `source_path`)
3. Resume from the last partially-processed directory
4. Present: "Resuming migration from `{last_migration_path}`. Already migrated: {N}. Remaining: {M}."

### Arguments

- `--scan-only`: Generate migration report without writing any files. Equivalent to a dry-run report.
- `--dry-run`: Alias for `--scan-only` (show what would be migrated without writing)
- `--source-vault PATH`: Path to the source vault. If not provided, uses the source named in config or the only source defined.
- `--source-name NAME`: Use a named source from `migrate-sources.yaml` (e.g., `--source-name 99-Obsidian`)
- `--force`: Re-migrate all files (skip deduplication check against state file), but still check PKOS vault deduplication
- `--skip-ripple`: Skip ripple compilation after import
- `--resume`: Resume from interruption point (default behavior if state file exists)

### Frontmatter Conversion

Convert 99-Obsidian frontmatter to PKOS frontmatter:

```yaml
---
type: {mapped type}
source: {source}
created: {date from frontmatter or file mtime}
tags: [{extracted from frontmatter or inferred from directory context}]
quality: {initial quality per classification rules}
citations: 0
related: []
status: seed
migrated_from: "99-Obsidian/{relative_path}"
aliases: []
---
```

**Conversion rules:**
- `tags:` in source → keep as `tags:` (rename `topics:` if present)
- `created:` → extract date or infer from filename prefix `YYYY-MM-DD-` or file mtime
- `aliases:` → initialize empty, add original filename as alias
- Unknown frontmatter fields → drop (preserve body content only)

### Ripple Compilation

After each note is migrated (unless `--skip-ripple`), dispatch `pkos:ripple-compiler` agent with:
```yaml
note_path: "{vault_path}"
title: "{title}"
tags: [{tags from frontmatter}]
related_notes: []
```

Dispatch sequentially (not parallel) to avoid concurrent MOC edits. If ripple fails, log warning and continue.

### Error Handling

- If a single file import fails → log error with file path, continue with others
- If PDF OCR fails → still archive PDF, write note with `pdf_text_extraction: failed`
- If state file is corrupted → backup to `.state/migrate-state.yaml.bak`, reinitialize
- Never modify source vault files

### Report Summary

```
PKOS Migration — 99-Obsidian → PKOS
  Source: /Users/norvyn/Code/Scripts/99-Obsidian/
  Target: ~/Obsidian/PKOS/

  Scan results:
    Markdown: {N} files
    PDFs: {M} files
    Images: {K} files

  Migration:
    Migrated: {count}
      knowledge: {n1} → 10-Knowledge/
      idea: {n2} → 20-Ideas/
      reference: {n3} → 50-References/
      person: {n4} → 40-People/
      project: {n5} → 30-Projects/
    Skipped (duplicate): {count}
    Errors: {count}

  PDF archive:
    Archived: {count} → ~/Obsidian/PDFs/
    OCR success: {n}
    OCR failed: {n}

  Ripple compilation:
    MOCs updated: {count}
    MOCs created: {count}
    Cross-references added: {count}

Run /generate-bases-views --target cross-project to update Bases views.
```

## Key Files

| File | Responsibility |
|------|----------------|
| `pkos/skills/migrate/SKILL.md` | Skill entry point: argument parsing, source config loading, scan/migrate process |
| `pkos/agents/inbox-processor.md` | Classification + metadata extraction logic (reused for WeChat AI judgment) |
| `mactools/skills/ocr/scripts/ocr.swift` | PDF text extraction via Vision framework |
| `pkos/skills/references/obsidian-format.md` | PKOS frontmatter + wikilink conventions |
| `pkos/agents/ripple-compiler.md` | MOC update + cross-ref agent (reused) |
| `pkos/.state/migrate-sources.yaml` | User-configured source vault definitions and classification rules |

## Boundary Conditions / Constraints

- Source vault remains read-only during migration (never modify source vault files)
- State file must survive interruption: update after each file is processed, not at end
- Deduplication hash uses `title + ":" + body_without_frontmatter` — frontmatter changes alone do not trigger re-import
- Source-specific classification rules are loaded from `migrate-sources.yaml` — no hardcoded paths or directory names in skill code
- PDF notes are written to the same relative path structure as their parent directory would map to (not to `50-References/` unconditionally)
- Images are copied in-place alongside where their parent Markdown would land, not to a separate Images folder
- The skill is not user-invocable in normal workflow — it is a one-time migration tool, but supports `--scan-only` for pre-migration review

## Deviation Record

None (skill not yet implemented).

## Decisions

### [DP-004] PDF OCR Failure Handling

**Chosen:** A — Archive PDF + write note with `pdf_text_extraction: failed` + continue. User can manually retry OCR later via `/ocr` on the archived PDF path.

---

### [DP-005] WeChat Content Classification (blocking)

**Chosen:** AI dynamic judgment via inbox-processor agent. Each WeChat file is analyzed by inbox-processor, which determines whether it is source material (素材, fragmented, Q&A style, no structure) or a finished work (作品, has title hierarchy, chapters, logical completeness). The AI is given explicit criteria for this distinction in the prompt.

**Prompt guidance for inbox-processor:**
```
素材 (source material): 原始转发/摘录、碎片化（单条记录、问答）、无深度加工
作品 (finished work): 经过整理、有结构（多个文件组成系列）、有标题体系、逻辑完整
```

---

### [DP-006] Image Deduplication Strategy

**Chosen:** A — No deduplication. All images are copied to PKOS as-is. Obsidian handles vault-wide dedup if needed.

---

### [DP-007] Markdown wikilink Rewrite Rules

**Chosen:** B — Preserve wikilinks and attempt to rewrite paths. Build a source-to-target path mapping table during migration. For each wikilink `[[source-path]]` in the source note, if `source-path` maps to a migrated `vault_path`, rewrite to `[[vault_path|display text]]`. If no mapping found, strip brackets to plain text (fallback).

## Change History

| Date | Change |
|------|--------|
| 2026-04-09 | Initial spec (generated by /write-feature-spec) |
| 2026-04-09 | DP-005 revised: WeChat classification changed from hardcoded (B: preserve 2 levels) to AI dynamic judgment via inbox-processor, with explicit 素材/作品 prompt |
| 2026-04-09 | DP-004 → A, DP-006 → A, DP-007 → B |
| 2026-04-09 | Architecture change: skill is now source-vault-agnostic; source paths and classification rules loaded from `migrate-sources.yaml` config; added `--scan-only` for dry-run report; no hardcoded user paths in skill code |
