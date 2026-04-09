---
name: inbox
description: "Internal skill — processes captured items from iOS (Reminders, Notes, voice memos). Reads from all PKOS input sources, classifies, routes to Obsidian/Notion, and triggers ripple compilation. Triggered by Adam cron or via /pkos ingest."
model: sonnet
---

## Overview

Process all pending items in the PKOS inbox. Reads from Reminders "PKOS Inbox" list, Notes "PKOS Inbox" folder, and iCloud voice files. Each item is classified, enriched, and routed to the appropriate destination.

## Arguments

Parse from user input:
- `--dry-run`: Show what would be processed without making changes
- `--source SOURCE`: Process only from specific source (reminders | notes | voice | getnote | all). Default: all

## Process

### Step 1: Collect

Collect pending items from all sources (or filtered by `--source`).

**Reminders:**
```bash
${CLAUDE_PLUGIN_ROOT}/../../mactools/1.0.1/skills/reminders/scripts/reminders.sh list "PKOS Inbox"
```
Parse output lines. Each reminder with title and notes becomes an inbox item with `source: reminder`, `raw_type: text` (or `url` if notes contain a URL).

**Notes:**
```bash
${CLAUDE_PLUGIN_ROOT}/../../mactools/1.0.1/skills/notes/scripts/notes.sh list "PKOS Inbox"
```
For each note found, read its full content:
```bash
${CLAUDE_PLUGIN_ROOT}/../../mactools/1.0.1/skills/notes/scripts/notes.sh read "Note Title"
```
Each note becomes an inbox item with `source: note`, `raw_type: text`.

**Voice files:**
```bash
ls ~/Library/Mobile\ Documents/com~apple~CloudDocs/PKOS/voice/*.m4a 2>/dev/null | grep -v '/processed/'
```
Each unprocessed .m4a file becomes an inbox item with `source: voice_memo`, `raw_type: audio`.

**Get笔记:**
```bash
GETNOTE_SCRIPT="${CLAUDE_PLUGIN_ROOT}/../../pkos/skills/getnote/scripts/getnote.sh"

# 读取 sync state
SYNC_FILE=~/Obsidian/PKOS/.state/getnote-sync.yaml
if [ -f "$SYNC_FILE" ]; then
  SYNC_MODE=$(python3 -c "import yaml; d=yaml.safe_load(open('$SYNC_FILE')); print(d.get('sync_mode','tag'))" 2>/dev/null || echo "tag")
  LAST_SINCE_ID=$(python3 -c "import yaml; d=yaml.safe_load(open('$SYNC_FILE')); print(d.get('since_id','0'))" 2>/dev/null || echo "0")
else
  SYNC_MODE="tag"
  LAST_SINCE_ID="0"
fi

if [ "$SYNC_MODE" = "tag" ]; then
  # Tag 模式：列出所有笔记，由 add_tags 标记已处理
  NOTES_JSON=$($GETNOTE_SCRIPT list_notes 0 2>/dev/null)
else
  # Cursor 模式：用 since_id 增量拉取
  NOTES_JSON=$($GETNOTE_SCRIPT list_notes "$LAST_SINCE_ID" 2>/dev/null)
fi

# 解析 notes[]，过滤 #pkos-synced，并填充 PROCESSED_GETNOTE_IDS 数组
PROCESSED_GETNOTE_IDS=()
GETNOTE_TEMP_FILE=~/Obsidian/PKOS/.state/getnote-collect-temp.txt
: > "$GETNOTE_TEMP_FILE"  # 截断 temp 文件

while IFS= read -r line; do
  NOTE_ID=$(echo "$line" | cut -f1)
  NOTE_TITLE=$(echo "$line" | cut -f2)
  NOTE_TYPE=$(echo "$line" | cut -f3)
  if [[ -n "$NOTE_ID" ]]; then
    PROCESSED_GETNOTE_IDS+=("$NOTE_ID")
    echo -e "${NOTE_ID}\t${NOTE_TITLE}\t${NOTE_TYPE}" >> "$GETNOTE_TEMP_FILE"
  fi
done < <(echo "$NOTES_JSON" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for note in data.get('notes', []):
    tag_names = [t.get('name','') for t in note.get('tags', [])]
    if 'pkos-synced' not in tag_names:
        print(f\"{note['id']}\t{note.get('title','Untitled')}\t{note.get('note_type','plain_text')}\")
" 2>/dev/null || true)
```
Each untagged note becomes an inbox item with `source: getnote`, `raw_type: text`. Link/img types: extract task_id, poll_task until completed (max 30 retries, 2s interval).

Present a summary to the user:
```
📥 PKOS Inbox: {N} items pending
  🔔 Reminders: {count}
  📝 Notes: {count}
  🎤 Voice: {count}
  🌐 Web (cleaned): {count}
  📓 Get笔记: {count}
```

If zero items found, report "Inbox is empty." and stop.

### Step 1.5: Clean Web Content (URL items only)

For each inbox item where `raw_type` is `url` or `raw_content` contains a URL (http:// or https://):

1. Extract the URL from the content
2. Run defuddle to get clean markdown:
   ```bash
   defuddle parse "{url}" --md
   ```
3. If defuddle succeeds (exit code 0):
   - Replace `raw_content` with defuddle output
   - Set `raw_type` to `cleaned_web`
   - Preserve the original URL in a new field `source_url`
4. If defuddle fails (URL unreachable, timeout, etc.):
   - Keep original `raw_content` unchanged
   - Log: `[inbox] defuddle failed for {url}: {error}. Using raw content.`

> Defuddle removes navigation, ads, and boilerplate from web pages, reducing noise before classification. Install: `npm install -g defuddle`

### Step 2: Transcribe Voice Files

For each voice item (raw_type: audio):

```bash
bash ${CLAUDE_PLUGIN_ROOT}/scripts/voice-transcribe.sh "{file_path}"
```

- Update `raw_content` with the transcription text
- Update `raw_type` to `voice_transcript`
- If transcription fails, log warning and set `raw_content` to "(transcription failed)"

### Step 3: Classify and Extract (dispatch inbox-processor agent)

Dispatch the `pkos:inbox-processor` agent with all collected items. The agent receives the items and returns routing decisions for each:

```yaml
items:
  - id: "reminder-{title-slug}"
    source: reminder
    raw_content: "the reminder text and notes"
    raw_type: text
  - id: "voice-en-2026-03-22"
    source: voice_memo
    raw_content: "transcribed text..."
    raw_type: voice_transcript
```

The agent returns:
```yaml
decisions:
  - id: "reminder-{slug}"
    classification: knowledge
    title: "Generated Title"
    keywords: [k1, k2, k3]
    tags: [tag1, tag2]
    urgency: low
    related_notes: ["10-Knowledge/related-note.md"]
    obsidian_path: "10-Knowledge/generated-title.md"
```

Present classification results to user for review before routing.

If `--dry-run`: display results and stop here.

### Step 4: Route to Destinations

Route each item based on its classification. Different types go to different destinations.

**A. knowledge / idea / reference → Obsidian + Notion**

1. Write Obsidian note at `~/Obsidian/PKOS/{obsidian_path}`:
```yaml
---
type: {classification}
source: {source}
created: {today's date}
tags: [{tags}]
quality: 0
citations: 0
related: [{related_notes}]
status: seed               # OR needs-reconciliation if conflict detected (see below)
aliases: []
---

# {title}

> [!insight] Source
> Captured from {source} on {today's date}.

{raw_content}

## Connections

{For each item in related_notes, output: `- [[{note-title}]]` using just the filename without path or extension}
{If inbox-processor identified a matching MOC topic, add: `- See also: [[MOC-{topic}]]`}
```

2. Write to Get笔记 (for cross-tool sync — only if Get笔记 credentials are configured):
```bash
GETNOTE_SCRIPT="${CLAUDE_PLUGIN_ROOT}/../../pkos/skills/getnote/scripts/getnote.sh"
GETNOTE_NOTE_ID=""
TOPIC_MAP=$(python3 -c "import yaml; d=yaml.safe_load(open('~/.claude/pkos/config.yaml')); print(d.get('getnote_api',{}).get('topic_map',''))" 2>/dev/null || echo "")
if [ -n "$TOPIC_MAP" ] && [ -n "$GETNOTE_SCRIPT" ]; then
  TAGS_ARG=""
  [[ -n "{tags_csv}" ]] && TAGS_ARG="{tags_csv}"
  SAVE_RESULT=$($GETNOTE_SCRIPT save_note "{title}" "{raw_content}" "$TAGS_ARG" 2>/dev/null)
  GETNOTE_NOTE_ID=$(echo "$SAVE_RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('note',{}).get('id',''))" 2>/dev/null || echo "")
  if [ -n "$GETNOTE_NOTE_ID" ] && [ -n "$TOPIC_MAP" ]; then
    python3 -c "
import yaml, sys, subprocess, os
topic_map = yaml.safe_load(open(os.path.expanduser('~/.claude/pkos/config.yaml')))
tag_map = topic_map.get('getnote_api', {}).get('topic_map', {})
tags = '{tags}'.split(',') if '{tags}' else []
script = os.environ.get('GETNOTE_SCRIPT', '')
note_id = os.environ.get('GETNOTE_NOTE_ID', '')
for tag in tags:
    tag = tag.strip()
    topic_id = tag_map.get(tag, '')
    if topic_id and script and note_id:
        subprocess.run([script, 'batch_add_to_topic', topic_id, note_id], capture_output=True)
" GETNOTE_SCRIPT="$GETNOTE_SCRIPT" GETNOTE_NOTE_ID="$GETNOTE_NOTE_ID" && \
      echo "[inbox] Get笔记: wrote note ${GETNOTE_NOTE_ID}" || true
  fi
fi
```
If Get笔记 credentials are missing or save_note fails, log warning and continue (graceful degradation — Obsidian note is already written).

> Format reference: see `references/obsidian-format.md` for wikilink and callout conventions.

**Conflict handling:** If the inbox-processor returned `conflict_status: needs-reconciliation` for this item:
- Set `status: needs-reconciliation` (instead of `seed`) in the frontmatter
- Add `conflicts_with: [{conflicts_with paths}]` to the frontmatter
- Add `conflict_description: "{conflict_description}"` to the frontmatter
- The note is still written and routed normally — conflicts flag for human review, they do not block ingest.

> [!warning] Conflict Detected
> Conflicts with [[{conflicts_with note title}]]: {conflict_description}

3. Create Notion Pipeline DB entry via Python API (token and proxy from env):
```bash
NO_PROXY="*" python3 ~/.claude/skills/notion-with-api/scripts/notion_api.py create-db-item \
  32a1bde4-ddac-81ff-8f82-f2d8d7a361d7 \
  "{title}" \
  --props '{"status": "inbox", "source": "{source}", "type": "{classification}", "topics": "{tags_csv}", "priority": "{urgency}"}'
```

4. Update Notion status after Obsidian note written:
```bash
NO_PROXY="*" python3 ~/.claude/skills/notion-with-api/scripts/notion_api.py update-db-item-properties \
  {notion_page_id} \
  --props '{"status": "processed", "obsidian_link": "obsidian://open?vault=PKOS&file={obsidian_path_encoded}"}'
```

**B. task → Notion only (no Obsidian note)**

1. Create Notion Pipeline DB entry with Status "actionable":
```bash
NO_PROXY="*" python3 ~/.claude/skills/notion-with-api/scripts/notion_api.py create-db-item \
  32a1bde4-ddac-81ff-8f82-f2d8d7a361d7 \
  "{title}" \
  --props '{"Status": "actionable", "Source": "{source}", "Type": "task", "Topics": "{tags_csv}", "Priority": "{urgency}"}'
```

2. If urgency is high or a due date is mentioned, create a Reminder:
```bash
${CLAUDE_PLUGIN_ROOT}/../../mactools/1.0.1/skills/reminders/scripts/reminders.sh create "{title}" --list "Tasks" --due "{due_date}"
```

**C. feedback → .signals/ only (no Obsidian, no Notion)**

Write feedback signal to `.signals/` directory:
```bash
echo "- source: {source}
  content: \"{raw_content}\"
  timestamp: {today}T{now}" >> ~/Obsidian/PKOS/.signals/$(date +%Y-%m-%d)-feedback.yaml
```

### Step 5: Mark Source Items as Processed

**Reminders:**
```bash
${CLAUDE_PLUGIN_ROOT}/../../mactools/1.0.1/skills/reminders/scripts/reminders.sh complete "{title}" --list "PKOS Inbox"
```

**Notes:**
```bash
${CLAUDE_PLUGIN_ROOT}/../../mactools/1.0.1/skills/notes/scripts/notes.sh delete "{note_title}"
```

**Voice files:**
```bash
mkdir -p ~/Library/Mobile\ Documents/com~apple~CloudDocs/PKOS/voice/processed/
mv "{voice_file_path}" ~/Library/Mobile\ Documents/com~apple~CloudDocs/PKOS/voice/processed/
```

**Get笔记:**
```bash
# Get笔记 — 标记已处理
# 调用 add_tags(note_id, ['#pkos-synced']) 标记笔记已被 PKOS 处理
for NOTE_ID in "${PROCESSED_GETNOTE_IDS[@]}"; do
  $GETNOTE_SCRIPT add_tags "$NOTE_ID" "pkos-synced" 2>/dev/null && \
    echo "[inbox] Get笔记 note ${NOTE_ID} marked pkos-synced" || \
    echo "[inbox] Get笔记 tag write failed for ${NOTE_ID}" >&2
done
```

### Step 5.5: Ripple Compilation

For each item that was routed to Obsidian (classification: knowledge, idea, or reference):

Dispatch `pkos:ripple-compiler` agent with:
```yaml
note_path: "{obsidian_path}"
title: "{title}"
tags: [{tags from inbox-processor decision}]
related_notes: [{related_notes from inbox-processor decision}]
```

If processing multiple items, dispatch ripple for each sequentially (not parallel) to avoid concurrent MOC edits.

If ripple fails for an item, log warning and continue — the source note is already saved, ripple can be retried later.

### Step 6: Report

Present final summary:
```
PKOS Inbox processed: {N} items
  knowledge: {count} → Obsidian 10-Knowledge/
  idea: {count} → Obsidian 20-Ideas/
  reference: {count} → Obsidian 50-References/
  task: {count} → Notion
  feedback: {count} → .signals/

Wiki compilation:
  MOCs updated: {count}
  MOCs created: {count}
  Cross-references added: {count}
  Conflicts flagged: {count} (need human reconciliation)

All items synced to Notion Pipeline DB.

Get笔记 sync:
  New notes captured: {count}
  Written back to Get笔记: {count}
  Marked pkos-synced: {count}
  Async tasks pending: {count}
```

## Error Handling

- If mactools scripts fail (Reminders/Notes not found), log warning and continue with other sources
- If Notion API fails, log error but keep the Obsidian note (data is not lost)
- If voice transcription fails, skip that file and log warning
- If Get笔记 API returns 401/403 → log `[inbox] Get笔记 auth failed` → skip Get笔记 source
- If Get笔记 API returns 429 (quota exceeded) → log `[inbox] Get笔记 quota exceeded` → skip source, do not update since_id
- If Get笔记 API returns 5xx → log `[inbox] Get笔记 API error {code}` → wait 5s retry once; if still fails, skip
- If add_tags fails → log warning, note still captured to Obsidian (graceful degradation)
- Never block the entire pipeline for Get笔记 failure

## Notion Configuration

- Pipeline DB ID: `32a1bde4-ddac-81ff-8f82-f2d8d7a361d7`
- Access method: Python API (`~/.claude/skills/notion-with-api/scripts/notion_api.py`)
- Token + proxy: provided via Adam template env (`NOTION_TOKEN`, `NO_PROXY`)
- Topics multi_select: use existing options from DB schema
