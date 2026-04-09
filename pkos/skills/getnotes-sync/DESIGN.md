# Get笔记 Knowledge Base Sync — Design Document

## Context

**Get笔记** (getnotes.cn) is an external knowledge base with topics (knowledge bases) and notes. Each topic is conceptually similar to an Obsidian MOC — a collection/index page pointing to related notes.

**Goal:** Read-only mapping from Get笔记 topics to Obsidian MOC pages in PKOS. External notes are referenced but not duplicated in the vault.

---

## 1. Get笔记 API Reference

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/resource/knowledge/list` | List all topics |
| `GET` | `/resource/knowledge/notes?topic_id=X&page=N` | Notes in a topic (paginated) |

### Auth Headers
```
Authorization: Bearer {api_key}
X-Client-ID: {client_id}
```

### Response Shapes

**Topic list** (`/resource/knowledge/list`):
```json
{
  "topics": [
    {
      "id": "kt1234567890",
      "name": "Architecture Patterns",
      "description": "Software architecture patterns and their trade-offs",
      "cover": "https://example.com/cover.jpg",
      "note_count": 42
    }
  ]
}
```

**Notes in topic** (`/resource/knowledge/notes?topic_id=X&page=N`):
```json
{
  "notes": [
    {
      "id": "n9876543210",
      "title": "Event Sourcing in Practice",
      "content": "Long-form note content...",
      "created_at": "2026-03-15T10:30:00Z"
    }
  ],
  "has_more": true,
  "next_cursor": "cursor_value"
}
```

### Rate Limits
- Topic creation: 50/day (not used in this design — read-only)
- No explicit read limits stated

---

## 2. MOC Page Template for Get笔记 Topics

**Location:** `~/Obsidian/PKOS/80-MOCs/getnotes-{topic-slug}.md`

**Slug construction:** `getnotes-{topic_name_lowercase_hyphenated}` (e.g., `getnotes-architecture-patterns`)

```markdown
---
type: moc
topic: getnotes-{topic-slug}
tags: [getnotes, external, {first-word-of-topic-name}, {second-word}]
source: getnotes
getnotes_topic_id: "{topic_id}"
getnotes_topic_name: "{topic_name}"
getnotes_description: "{topic_description}"
note_count: {N}
last_synced: {YYYY-MM-DD}
---

# {Topic Name}

> [!abstract] Get笔记 Knowledge Base
> This MOC maps the **"{topic_name}"** topic from Get笔记. {note_count} notes are referenced below.
> - Source: [Open in Get笔记](getnotes://topic/{topic_id})
> - Last synced: {YYYY-MM-DD}

## Overview

{If description is available: 2-3 sentences summarizing the topic's focus, from Get笔记 description field.}
{If no description: "Overview coming soon."}

## Notes (External References)

These notes reside in Get笔记. Click any link to open in the Get笔记 app.

{For each note (paginate through all):}
- [{note-title}](getnotes://note/{note_id}) — {truncated one-line summary, first 80 chars of content or "No preview available"} ({YYYY-MM-DD})

## Contradictions & Open Questions

None detected. _(Populated if overlapping notes in vault contradict each other.)_

## Related MOCs

{List MOC links that share any tag with this topic. Use `[[MOC-{tag}]]` format. If none: "None yet."}
```

**Key design decisions:**
- `type: moc` — identifies this as a compiled MOC page (ripple-compiler and other tools rely on this)
- `source: getnotes` — distinguishes from organically-grown vault MOCs
- `tags: [getnotes, external, ...]` — enables `getnotes` tag filtering
- `getnotes://` URL scheme — custom scheme to open notes in Get笔记 app (iOS/macOS)
- Notes section shows **external references** only, not duplicated content
- Each note shows: title link, first 80 chars of content as summary, creation date

---

## 3. Sync Mechanism

### 3a. State File

**Location:** `~/Obsidian/PKOS/.state/getnotes-sync-state.yaml`

```yaml
last_full_sync: "2026-04-09T10:00:00"
last_incremental_sync: "2026-04-09T14:30:00"
api_key_hash: "{sha256 of api_key (for drift detection)}"
topics:
  - topic_id: "kt1234567890"
    topic_name: "Architecture Patterns"
    topic_slug: "architecture-patterns"
    note_count: 42
    last_note_hash: "{sha256 of last_note_id+created_at string}"
    last_synced: "2026-04-09"
  - topic_id: "kt0987654321"
    topic_name: "SwiftUI Patterns"
    topic_slug: "swiftui-patterns"
    note_count: 18
    last_note_hash: "{sha256 of last_note_id+created_at string}"
    last_synced: "2026-04-09"
```

**Note hash computation:** For each topic, hash the concatenation of `(note_id + created_at)` for all notes, sorted by `created_at` descending. This detects additions, deletions, and reordering.

### 3b. Initial Full Sync (First Run)

```
FOR each topic in GET /resource/knowledge/list:
  1. Fetch all pages of GET /resource/knowledge/notes?topic_id=X&page=N
     - Follow has_more / next_cursor until all notes retrieved
  2. Compute note_hash from all notes
  3. Create MOC page at 80-MOCs/getnotes-{slug}.md
  4. Record topic in state file

Update state: last_full_sync = now
```

**Pagination handling:**
- Default page size: unspecified by API (assume 20, adjust if `has_more` is true after first page)
- Max pages per topic: 100 (safety limit; Get笔记 has low limits in practice)
- Exponential backoff on 429: wait 60s, retry, up to 3 attempts

### 3c. Incremental Sync (Subsequent Runs)

```
1. GET /resource/knowledge/list → current_topics

2. FOR each topic in current_topics:
   a. Fetch first page of notes (or use cached note list if state exists)
   b. Compute current note_hash
   c. Read note_hash from state for this topic
   d. IF hashes differ:
      - Fetch all pages (detect which notes changed)
      - Update MOC page
      - Update state entry
   e. IF hashes match: skip (no changes)

3. FOR each topic in state that is NOT in current_topics:
   - Mark MOC page as "archived" (add `status: archived` to frontmatter)
   - Log: topic removed from Get笔记

4. Update state: last_incremental_sync = now
```

**Change detection granularity:**
- If note_hash differs but note_count is same → a note was edited (updated `created_at` or content changed)
- If note_hash differs and note_count increased → new notes added
- If note_hash differs and note_count decreased → notes deleted from Get笔记
- Full resync of changed topics (re-fetch all pages) ensures MOC is always accurate

### 3d. Sync Frequency

- **Scheduled (cron):** Every 6 hours via Adam cron
- **Manual trigger:** `pkos sync getnotes` via pkos skill entry point
- **On-demand:** After user returns from Get笔记 app (future enhancement — not implemented in v1)

---

## 4. Handling Notes That Don't Exist in Obsidian

**Design principle:** Read-only, no duplication.

| Get笔记 note state | Treatment in PKOS MOC |
|--------------------|-----------------------|
| Note exists in Get笔记 but NOT in Obsidian | Link via `getnotes://note/{id}`, no content duplication |
| Note migrated to Obsidian manually | Keep MOC link, update frontmatter to show vault note exists |
| Note deleted from Get笔记 | Remove from MOC, update `note_count` |

**MOC page notes section always shows:**
- Title linked with `getnotes://` scheme
- Content preview (first 80 chars from Get笔记 API `content` field)
- Creation date

**If vault note exists for same topic (via inbox or harvest):**
- The vault note has its own life in 10-Knowledge/ or appropriate directory
- MOC in 80-MOCs/ includes it in Related MOCs section
- No merge attempted (OUT scope for v1)

---

## 5. File Locations

```
PKOS vault structure:
  ~/Obsidian/PKOS/
    80-MOCs/
      getnotes-{topic-slug}.md    # One MOC per Get笔记 topic
    .state/
      getnotes-sync-state.yaml      # Sync state and topic registry

PKOS skill structure:
  ~/Code/Skills/indie-toolkit/pkos/
    skills/
      getnotes-sync/
        SKILL.md                   # This skill
        references/
          api-reference.md         # Get笔记 API details (optional, can document inline)
```

---

## 6. Skill Architecture: Separate vs Integrated

### Decision: Separate `pkos:getnotes-sync` Skill

**Rationale:**

| Factor | Separate Skill | Integrated into inbox | Integrated into ripple |
|--------|---------------|----------------------|------------------------|
| Trigger | Cron-scheduled | Event-triggered (on ingest) | Event-triggered (on note write) |
| API coupling | Isolated | Inbox doesn't need Get笔记 API | ripple-compiler handles vault notes, not external APIs |
| Complexity | Self-contained | Inbox already complex | Would add external API to ripple-compiler |
| Rate limiting | Handled in sync | Would complicate inbox | N/A |
| Scope fit | Pulls external → internal | Processes internal captures | MOC updates for vault notes |

**Conclusion:** Separate skill is cleaner. Get笔记 sync is a pull-based integration (external → PKOS), fundamentally different from inbox (capture → filing) and ripple (filing → compilation).

### Skill Entry Points

- **Cron trigger:** `adam poll 3600 --skill pkos:getnotes-sync` (every 6h)
- **Manual:** `/pkos sync getnotes`
- **First run:** `/pkos sync getnotes --full`

---

## 7. Implementation: Draft SKILL.md

```markdown
---
name: getnotes-sync
description: "Read-only sync from Get笔记 knowledge bases to PKOS MOC pages. Polls Get笔记 API, creates/updates MOC pages in 80-MOCs/. Triggered via Adam cron (every 6h) or manually via /pkos sync getnotes."
model: sonnet
tools: [Read, Write, Edit, Grep, Glob, Bash]
allowed-tools: Write(~/Obsidian/PKOS/80-MOCs/*) Edit(~/Obsidian/PKOS/80-MOCs/*) Write(~/Obsidian/PKOS/.state/*)
user-invocable: false
---

## Overview

Sync Get笔记 topics (knowledge bases) to PKOS MOC pages. This is a **read-only** mapping — Get笔记 notes are referenced via `getnotes://` URL scheme, not duplicated in the vault.

## Arguments

- `--full`: Force full resync of all topics (default: incremental)
- `--dry-run`: Show what would change without writing files
- `--topic TOPIC_ID`: Sync only a specific topic (by Get笔记 topic ID)

## Prerequisites

1. Get笔记 API credentials in `~/.claude/pkos/config.yaml`:
   ```yaml
   getnotes:
     api_key: "{your_api_key}"
     client_id: "{your_client_id}"
     base_url: "https://api.getnotes.cn"  # or self-hosted
   ```
2. `~/Obsidian/PKOS/80-MOCs/` directory must exist

## Process

### Step 1: Load Credentials and State

Read credentials from `~/.claude/pkos/config.yaml`.

Read state file `~/Obsidian/PKOS/.state/getnotes-sync-state.yaml`:
- If not found, this is a first run → full sync required
- If found, determine sync type (full vs incremental)

### Step 2: Fetch Topic List

```bash
curl -s -X GET "https://api.getnotes.cn/resource/knowledge/list" \
  -H "Authorization: Bearer {api_key}" \
  -H "X-Client-ID: {client_id}"
```

Parse JSON response. Extract `topics[]`.

### Step 3: Determine Sync Scope

**If `--full`:** Process all topics.

**If `--topic TOPIC_ID`:** Filter to only that topic.

**Otherwise (incremental):**
- Compare current topic list against state file topics
- Detect: new topics, deleted topics, topics with changed note_hash
- Collect list of topics needing sync

### Step 4: Fetch Notes for Each Topic (with Pagination)

For each topic requiring sync:

```
page = 1
all_notes = []
REPEAT:
  response = GET "/resource/knowledge/notes?topic_id={id}&page={page}"
  all_notes += response.notes
  IF response.has_more AND page < 100:
    page += 1
  ELSE:
    BREAK
```

**Rate limit handling:**
- On 429: wait 60s, retry, max 3 retries
- On 5xx: log error, skip topic, continue with next

### Step 5: Compute Note Hash

```python
# Sort notes by created_at descending
sorted_notes = sorted(all_notes, key=lambda n: n.created_at, reverse=True)
# Hash concatenation of id + created_at
hash_input = "|".join(f"{n.id}:{n.created_at}" for n in sorted_notes)
note_hash = sha256(hash_input)
```

### Step 6: Determine MOC Action

**New topic (not in state):**
- Create new MOC page at `~/Obsidian/PKOS/80-MOCs/getnotes-{slug}.md`
- Log: topic created

**Existing topic (note_hash changed):**
- Update existing MOC page
- Log: topic updated

**Existing topic (note_hash unchanged):**
- Skip (no changes)

**Topic removed from Get笔记:**
- Add `status: archived` to MOC frontmatter
- Log: topic archived

### Step 7: Write/Update MOC Page

Use template in DESIGN.md Section 2.

**Note list formatting:**
- Each note: `[{title}](getnotes://note/{id}) — {preview} ({date})`
- Preview: first 80 chars of `content` field, stripped of markdown
- Sort: by `created_at` descending (newest first)

### Step 8: Update State File

Write updated `getnotes-sync-state.yaml` with:
- `last_full_sync` or `last_incremental_sync`
- Updated topic entries (id, name, slug, note_count, note_hash, last_synced)

### Step 9: Report

```
Get笔记 Sync Report — {date}
  Mode: {full|incremental}
  Topics processed: {N}
    Created: {new}
    Updated: {updated}
    Unchanged: {unchanged}
    Archived: {archived}
  Errors: {errors}
  Next scheduled sync: {time}
```

---

## Error Handling

| Error | Action |
|-------|--------|
| API key invalid (401) | Log fatal: "Invalid Get笔记 credentials. Check config." Stop. |
| Topic not found (404) | Skip topic, log warning |
| Rate limited (429) | Wait 60s, retry, up to 3 times |
| Server error (5xx) | Skip topic, log error, continue |
| Network timeout | Retry once after 10s |
| MOC write failure | Log error, skip MOC, continue |

---

## Integration Points

| Component | Integration |
|-----------|-------------|
| ripple-compiler | None — ripple-compiler handles vault notes, this skill creates MOC shells only |
| inbox | None — inbox processes PKOS captures, this skill pulls from external API |
| pkos entry point | Manual trigger: `pkos sync getnotes` |
| Adam cron | Scheduled: `pkos:getnotes-sync` every 6 hours |
| 80-MOCs/ | MOC pages written here |
| `.state/getnotes-sync-state.yaml` | State tracking |

---

## What This Skill Does NOT Do

- Import Get笔记 notes as individual Obsidian notes
- Write back to Get笔记
- Sync deletions from Obsidian to Get笔记
- Handle Get笔记 authentication beyond read-only API

---

## v1 Out of Scope (Future Enhancements)

1. Bidirectional sync (write vault notes → Get笔记)
2. Real-time sync (webhook from Get笔记 — not available)
3. Merge detection (same note exists in both systems)
4. Per-topic sync frequency (high-value topics sync more often)
5. Integration with Bases for Get笔记 notes querying
```

---

## 8. Integration with PKOS Entry Point

To enable `/pkos sync getnotes`, add to `pkos/skills/pkos/SKILL.md`:

```markdown
### Route: getnotes Sync

Trigger: user says "sync getnotes", "getnotes sync", "知识库同步"

Invoke the `getnotes-sync` skill:
- No args → incremental sync
- `--full` → full resync
- `--dry-run` → preview only
```

---

## 9. Open Questions for User Decision

1. **Topic slug collision:** If a Get笔记 topic name maps to a slug that already exists as a vault MOC (e.g., `getnotes-swiftui-patterns` collides with a manually-created `MOC-swiftui-patterns`), which takes precedence?
   - **Recommendation:** Get笔记 MOC wins, rename vault MOC to `MOC-swiftui-patterns-legacy` or merge content.

2. **Content preview length:** Show 80 chars of content in MOC notes list. Acceptable?
   - **Recommendation:** 80 chars is enough for recognition without cluttering the MOC.

3. **Sync frequency:** 6 hours seems reasonable. Adjustable via cron schedule.

4. **Migrated notes handling:** If a Get笔记 note is later created in Obsidian (via inbox/harvest), should the MOC link update to point to the vault note?
   - **Recommendation:** v1: No. MOC always shows Get笔记 reference. Future: check if vault note with same title exists, link to both.
