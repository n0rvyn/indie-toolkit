# readback

_Before-action read-back protocol — for Claude Code._

## What

This plugin makes the assistant say what it thinks you asked for, in plain language, before it acts on it.

Inspired by closed-loop communication in aviation and medicine:

> Tower: "Descend to 3000 feet."
> Pilot: "Descending to 3000 feet."  ← required readback before action

Two paths, and they behave differently on purpose:

| Path | When | What you get | Blocks? |
|---|---|---|---|
| **Automatic** | your prompt has an ambiguous referent | one line naming the reading it picked, then it keeps working | no |
| **Explicit** (`/readback`, `/fix-bug`, `/write-plan`) | you invoked it | full 3-paragraph echo, waits for you | `/fix-bug` yes |

## How it triggers

1. **`UserPromptSubmit` hook** (automatic path) — fires only when your prompt has a genuinely ambiguous referent: a demonstrative plus an attribute with no owner (`把这个字号改小`), a bare demonstrative standing in for the target state (`改成那样`), a screenshot with no locator, or a broad-scope verb with no boundary (`重构一下这块`). It then asks the assistant to open its reply with one sentence naming the reading it chose — and to keep working. It does **not** stop the turn and does **not** dispatch an agent.

   It stays silent when you name a concrete target (file path, backticked identifier, `foo()`, CamelCase symbol, line number), when a locator pins the referent down (`顶部那个间距`), and on questions or discussion. Full rule set: `references/trigger-detection.md`.

   **Why not stop and confirm?** Because the costs are asymmetric. A wrong reading costs one correction message; stopping costs a round-trip on every task. Your stop mechanism is ESC — always there, free when you don't use it. (Earlier versions fired on any action verb and blocked; that is what this replaced.)

2. **`PreToolUse` hook** — when you invoke `/fix-bug`, the skill writes a state file marking readback-required. This hook then *hard-blocks* any `Write` / `Edit` / `MultiEdit` until the state file says you've confirmed the readback. Scoped to `/fix-bug` only: running that command is an explicit choice to take the stricter flow.

3. **`PostToolUse` hook** (Agent matcher) — fires right after `intent-echoer` returns on an explicit path. The instruction to paste the output distance-decays across long dispatch turns, so the main model sometimes acknowledges dispatch ("回读已发出") without pasting the agent's 3-paragraph output into the reply body — leaving you staring at a collapsed tool panel. This hook re-injects the paste-verbatim requirement at the exact moment the agent output is in the immediate prior turn.

4. **`Stop` hook** — silent tally. If a turn writes ≥3 files without a confirmed readback, the next turn gets a quiet warning. Doesn't block the session.

The `intent-echoer` agent (explicit paths only) runs in a fresh context (`model: sonnet`) with strict rules: no function names / file paths / class names as sentence subjects (only as parenthetical references). 3 paragraphs: situation / approach / what you'll see. Reuses your vocabulary verbatim.

## When the automatic path stays silent

- You named a concrete target: a file path, `` `identifier` ``, `foo()`, a CamelCase symbol, `第 3 行`
- A locator already disambiguates: `顶部那个间距`, `左上那个圆角`, `[Image] … 第 2 处`
- Questions and discussion: `你觉得…行不行`, `如何界定…`, `你同意吗`, `what do you think`
- Any slash command (`/run-phase`, `/commit`, … — and `/readback` itself is the manual entry)
- Explicit bypass: `go` / `直接做` / `--no-questions` / `skip readback`
- An explicit readback is already confirmed (`.claude/readback-state.json` has `user_confirmed: true`)

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

- `hooks/user-prompt-submit.sh` — ambiguous-referent detection + non-blocking hint injection
- `hooks/pre-tool-use.sh` — hard-block enforcement (scoped to fix-bug)
- `hooks/post-tool-use.sh` — paste-verbatim reminder when `intent-echoer` returns
- `hooks/stop.sh` — quiet threshold warning
- `agents/intent-echoer.md` — sonnet agent, 3-paragraph plain-language generator
- `skills/readback/` — manual `/readback` entry
- `references/` — speak-rules, trigger-detection, state-schema

## Tests

Each hook has a self-contained test in `tests/`. Run all:
```bash
for t in readback/tests/test-*.sh; do bash "$t"; done
```
