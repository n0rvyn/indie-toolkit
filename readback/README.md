# readback

_Before-action read-back protocol — for Claude Code._

## What

This plugin makes the assistant restate your intent in plain language **before** writing any code or plan. You confirm the restatement (or correct it). Only then does the assistant proceed.

Inspired by closed-loop communication in aviation and medicine:

> Tower: "Descend to 3000 feet."
> Pilot: "Descending to 3000 feet."  ← required readback before action

Same idea, applied to AI coding sessions.

## How it triggers

Three layers, each covering a different gap:

1. **`UserPromptSubmit` hook** — detects action verbs (`fix` / `implement` / `修` / `改` / …) in your prompt and tells the assistant to dispatch the `intent-echoer` agent before responding. Soft trigger, fails open. Covers conversational prompts without slash commands.

2. **`PreToolUse` hook** — when you invoke `/fix-bug`, the skill writes a state file marking readback-required. This hook then *hard-blocks* any `Write` / `Edit` / `MultiEdit` until the state file says you've confirmed the readback. fix-bug = stable > fast.

3. **`Stop` hook** — silent tally. If a turn writes ≥3 files without a confirmed readback, the next turn gets a quiet warning. Doesn't block the session.

The `intent-echoer` agent runs in a fresh context with strict rules: no function names / file paths / class names as sentence subjects (only as parenthetical references). 3 paragraphs: situation / approach / what you'll see. Reuses your vocabulary verbatim.

## When it skips

- Trivial verbs: `rename` / `format` / `import organize` / `remove unused` / `move code`
- Orchestration commands: `/run-phase` / `/execute-plan` / `/verify-plan` / `/commit` / `/test-changes`
- Pure questions: `how does X work?` / `what is Y?` (no action verb)
- Explicit bypass: `go` / `直接做` / `--no-questions` / `skip readback`

## User-invocable commands

- `/readback` — manually trigger a readback (use when you want to verify AI understanding before substantial work)
- `/readback status` — show current readback state (session, skill, confirmed flag)

## State

The plugin writes one file: `.claude/readback-state.json`. Schema in `references/state-schema.md`.

Two-phase lifecycle:
1. **Pending** — created by `/readback` / `/fix-bug` / `/write-plan` with `user_confirmed: false`. Expires automatically after 30 minutes (hooks treat expired state as fresh).
2. **Confirmed** — set after the user says "go" / "OK" / "对". The `PreToolUse` hook stamps the current session id into the file on first read; subsequent same-session edits proceed, cross-session edits are treated as fresh.

No manual cleanup needed.

## Upgrading from 0.1.0

v0.1.0 wrote state with `session_id: "unknown"` (skills cannot read hook stdin, so the real session id was unavailable). The new hooks treat `"unknown"` identically to `null`: they expire it via the 30-minute TTL or stamp the real sid on first confirmed read. **No action required from end users** — stale state will phase out within ~30 minutes of session start.

## Required system tools

- `jq` — all hooks parse stdin / state files with jq. macOS: `brew install jq`. Linux: `apt install jq` / `dnf install jq`. **Missing jq → plugin silently no-ops** (fail-open by design; no error surface). If your readback never seems to fire, check `which jq` first.

## Failure modes

Every hook fails open. Bad JSON, missing files, parse errors, missing jq → the hook silently allows the operation. The plugin is alignment optimization, not a security gate.

## Components

- `hooks/user-prompt-submit.sh` — keyword detection + mandate injection
- `hooks/pre-tool-use.sh` — hard-block enforcement (scoped to fix-bug)
- `hooks/stop.sh` — quiet threshold warning
- `agents/intent-echoer.md` — opus agent, 3-paragraph plain-language generator
- `skills/readback/` — manual `/readback` entry
- `references/` — speak-rules, trigger-detection, state-schema

## Tests

Each hook has a self-contained test in `tests/`. Run all:
```bash
for t in readback/tests/test-*.sh; do bash "$t"; done
```
