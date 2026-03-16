---
name: session-replay
description: "Use when the user says 'replay session', 'show session', 'session replay', or wants to review a specific past session's turns, tools, and file changes."
user_invocable: true
model: haiku
---

## Overview

Replay a past AI coding session showing turn-by-turn timeline, tool usage, and file changes. Reads the raw JSONL file for full fidelity.

## Arguments

- `<session-id>`: Required. Session ID from /session-search results or history.
- `--detail LEVEL`: summary | standard | verbose (default: standard)
  - **summary**: Header + task summary only
  - **standard**: Header + turn timeline (truncated) + tool sequence + file table
  - **verbose**: Everything + full tool inputs/outputs (truncated to 500 chars each)

## Process

### Step A: Locate Session File

1. Check `~/.claude/session-intel/index.json` for the session_id:
   - Load index, search `sessions` array for matching `session_id`
   - If found: use `file_path` and `source` from the index entry
2. If not in index: fall back to glob search:
   ```bash
   # Claude Code
   find ~/.claude/projects -name "{session_id}.jsonl" -type f 2>/dev/null
   # Codex
   find ~/.codex/sessions -name "*{session_id}*" -type f 2>/dev/null
   ```
3. If still not found: "Session {id} not found. Try /session-search to find the correct ID."

### Step B: Parse Session via Script

Run the replay parser script:
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/replay_session.py --input {file_path} --detail {detail_level}
```

This handles both Claude Code and Codex JSONL formats, returns structured JSON with header, turns, files, and tool_sequence.

### Step C: Format Output

**Header:**
```
Session: {session_id}
Project: {project} ({project_path})
Branch: {branch}
Model: {model}
Date: {time.start} → {time.end} ({duration_min} min)
Turns: {user} user / {assistant} assistant
Tokens: {input} in / {output} out (cache: {cache_hit_rate}%)
```

**For --detail summary:** Header + task_summary from index (if available) or first user prompt.

**For --detail standard:**
```
## Turn Timeline

### Turn 1 — {timestamp}
User: {message text, truncated to 200 chars}
Assistant:
  → Read: {file_path}
  → Edit: {file_path} (old: "...", new: "...")
  → Bash: {command, truncated to 100 chars}
  → Text: {response text, truncated to 200 chars}

### Turn 2 — {timestamp}
...

## Files Touched
| File | R | E | C | Edits |
|------|---|---|---|-------|
| auth.py | 2 | 5 | - | ⚠️ repeated |
| utils.py | 1 | 1 | - | |
| new_file.py | - | - | 1 | |

## Tool Sequence
Read → Read → Edit → Bash → Edit → Edit → Bash
```

**For --detail verbose:** Same as standard but with full tool inputs/outputs (each truncated to 500 chars).

## Error Handling

- Session file not found: "Session {id} not found. Try /session-search to find the correct session ID."
- Parse error: "Unable to read session file. The file may be corrupted."
- Permission error: "Cannot read session file at {path}. Check file permissions."
- Empty session: "Session file contains no conversation data."

## Integration with dev-workflow

Session replay output feeds into `/handoff` for session continuity:
- Header provides project, branch, and task context
- Turn timeline shows recent work
- File changes lists modified files
- Tool sequence reveals the approach

Suggest: "Use `/session-replay {session_id}` to get full context for `/handoff`."

## Completion Criteria

- Session replay rendered and displayed at the requested detail level
- Header, turn timeline, file changes, and tool sequence all present (for standard/verbose)
