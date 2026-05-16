# State File Schema — `.claude/readback-state.json`

Schema version 2 (introduced 2026-05-17). v1 schema with `session_id: "unknown"` sentinel is auto-migrated by hooks — see `## Backward Compatibility` below.

## Path

- Location: `<project_root>/.claude/readback-state.json`
- Created by: `/readback` skill, `/fix-bug` Step pre-0, `/write-plan` Step 2.5
- Read by: `pre-tool-use.sh` hook, `stop.sh` hook, `user-prompt-submit.sh` hook (state-aware short-circuit), `/readback status` path
- Stamped by: `pre-tool-use.sh` hook (writes `session_id` from stdin into the file on first read of a `user_confirmed=true` state)
- Cleanup: not auto-deleted; stale state is handled by TTL (pending) or session-id mismatch (confirmed)

## Schema

```json
{
  "created_at": "string (ISO 8601, UTC; set when state is first created)",
  "session_id": "string | null (null when skill-written; hook stamps stdin sid into the file on first confirmed-state read)",
  "skill": "string | null  // 'fix-bug' | 'write-plan' | null (manual /readback)",
  "readback_done": "boolean",
  "readback_text": "string (3-paragraph agent output, verbatim)",
  "user_confirmed": "boolean (true after user says 'go' or equivalent)",
  "confirmed_at": "string | null (ISO 8601, set when confirmed)",
  "correction_count": "integer (incremented on user 'wrong' / correction; trigger /brainstorm at 2)"
}
```

## Lifecycle (two-phase identity model)

The state file goes through two distinct phases. Hooks decide staleness differently in each phase.

### Phase 1: Pending (`user_confirmed = false`)

- Skill writer creates state with `created_at` set and `session_id: null`.
- Hooks compute `now - created_at`. If the age exceeds **30 minutes** (1800 seconds), the hook treats the state as stale and falls open (allows the operation, emits warning where applicable but does not block).
- This window is sized to cover a single working session. A user who starts `/fix-bug`, walks away without saying "go", and returns 35+ minutes later is not locked out — the state has expired.
- Re-echo on user correction: writer increments `correction_count`, updates `readback_text`, keeps `user_confirmed: false`, may also refresh `created_at` to reset the TTL.

### Phase 2: Confirmed (`user_confirmed = true`)

- Writer sets `user_confirmed: true`, `confirmed_at: <now>`, but leaves `session_id` at its previous value (still `null` if skill wrote it).
- On first hook read after confirmation: hook reads `session_id` from stdin (Claude Code hook contract — stdin JSON has the real session id), and if the stored `session_id` is `null`, the hook stamps the stdin sid into the state file via atomic rewrite (`jq` + `mv`).
- On subsequent hook reads: hook compares stdin sid to stored sid. Match → same session, hook enforces or suppresses based on rule. Mismatch → different session, hook treats as stale (falls open).
- This gives confirmed state precise session identity without requiring skills (which have no stdin access) to know the session id.

## Failure modes (reader side)

- File missing → treat as fresh state (no readback done)
- File unreadable → fail-open (no enforcement)
- JSON parse error → fail-open
- `created_at` missing or unparseable → fail-open (cannot evaluate TTL, do not lock out)
- `session_id` mismatch in confirmed phase → treat as fresh
- Field missing → use default (false / null / 0)

## Backward Compatibility

Residual state files from plugin v0.1.0 may contain `session_id: "unknown"` (the v1 sentinel value that v1 skills wrote because `CLAUDE_SESSION_ID` is not exported to skill bash blocks). v2 hooks treat this value identically to `null`: they normalize `"unknown"` → `""` immediately after reading the stored sid, so it expires via the 30-minute TTL (if pending) or is stamped on first confirmed read.

**No manual cleanup required from end users** — v1 state will phase out within ~30 minutes of session start, or convert to v2-stamped form on the next confirmed-state edit. v1 files mid-confirmed will be re-stamped with the real sid on first PreToolUse read.
