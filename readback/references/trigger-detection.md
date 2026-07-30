# Trigger Detection — when readback fires

## Two paths, different contracts

| Path | Trigger | Output | Blocks? |
|---|---|---|---|
| **Automatic** (`user-prompt-submit.sh`, schema v3) | prompt has an ambiguous referent | one-line `[readback-hint]`: state your reading, keep working | no |
| **Explicit** (`/readback`, `/fix-bug` Step pre-0, `/write-plan` Step 2.5) | user invoked it | full 3-paragraph `intent-echoer` echo, wait for confirmation | `/fix-bug` yes (via `pre-tool-use.sh`), others no |

The explicit path is unchanged. Everything below describes the automatic path.

## Why v3 changed (2026-07-30)

v2 fired on **action-verb presence** (`fix` / `修` / `implement` / …) and injected a blocking mandate: dispatch `intent-echoer`, paste three paragraphs verbatim, STOP and wait.

Two structural problems:

1. **Wrong event.** `UserPromptSubmit` runs before the model has looked at anything, so the hook can only guess ambiguity from surface words. That is why v2 accumulated five skip groups and nine CJK idiom-stripping `sed` rules and *still* fired on discussion prompts — the observed leak was `你没有说修复建议？` (a question about a recommendation, matched because it contains `修复`).
2. **Wrong output.** Stop-and-confirm on every action prompt contradicts the harness instruction to reserve blocking questions for work that would be unsafe or wasted if the reading were wrong. The asymmetry runs the other way: a wrong reading costs one correction message, while stopping costs a round-trip on every single task.

v3 inverts both. The user's stop mechanism is ESC — always available, free when unused.

## v3 trigger

Fires when **all three** hold:

```
(an ambiguity signal is present)
  AND (no concrete target is named)
  AND (not a discussion prompt)
```

### Ambiguity signals

Each is a case where two or more readings are genuinely available and the wrong pick wastes the work. Derived from the referent-ambiguity rule in the user's global CLAUDE.md (`那个颜色 / 这个字号 / 那种风格`, and screenshots containing several differences).

| id | Signal | Example |
|---|---|---|
| A1 | `[Image` present, no locator | `[Image] 改成图里那样` |
| A2 | demonstrative + **attribute** noun | `把这个字号改小`, `那种风格换一下` |
| A2b | bare demonstrative as the target state | `改成那样`, `like that` |
| A3 | broad-scope verb with no boundary | `重构一下这块`, `统一一下间距` |

**A2 lists attributes only, never objects.** `这个字号` leaves the owning object unnamed — that is the failure mode. `这个按钮` names the object and is ambiguous only if several buttons exist. Object nouns in this list produced a false positive on `只重构这个按钮的样式`.

A locator (`顶部` / `左上` / `第 2 处` / `top` / `first`) suppresses A1, A2 and A2b alike — it pins the referent down even when a demonstrative is present.

### Concrete-target suppressors (checked before the signals)

Any of these means the referent is not in doubt:

- a file path with a known code extension
- a backticked identifier
- a call site `foo()`
- a CamelCase symbol
- a line reference (`:42`, `L42`, `第 3 行`)

### Discussion suppressors

The deliverable is an answer, not a change, so there is no work to misdirect. Matched anywhere in the prompt: `你(同意|觉得|认为|怎么看|怎么想|没有|没|忘了|漏了)`, `如何(改进|优化|设计|界定|判断|…)`, `我(觉得|认为|在想|想问|…)`, `(同意吗|对吗|行不行|是不是应该|有没有|要不要)`, `(讨论|方案对比|你的建议|什么意思)`, and the English equivalents.

### Structural skips

- any prompt starting with `/` (slash commands are flow control or explicit skill entry; `/readback` is the manual full-echo path)
- explicit bypass: `go` / `直接做` / `just do it` / `--no-questions` / `skip readback`
- empty prompt

### State suppression (minimal)

If `.claude/readback-state.json` has `user_confirmed: true`, the hint is suppressed — `/fix-bug` Step pre-0 and `/write-plan` Step 2.5 own the strict flow at that point and a second voice on top of theirs is noise. No TTL, no session-id matching: v2's 40 lines of two-phase identity logic existed to decide *whether the block still applies*, and v3 does not block.

## Output

```
[readback-hint] This request has an ambiguous referent: {signal}.

Open your reply with ONE sentence naming the reading you picked and the one you ruled
out, in the user's own words.

Then keep working in the same turn. Do NOT dispatch an agent for this, and do NOT stop
to wait for confirmation.

Stop and ask only if the work you would do before any feedback is destructive,
irreversible, or a real scope change.
```

No agent dispatch on this path, so `post-tool-use.sh` (the paste-verbatim reminder) no longer fires for it. That hook still guards the explicit paths, which do dispatch `intent-echoer`.

## Tests

`readback/tests/test-user-prompt-submit.sh` — 30 cases. Every case runs in a fresh tmpdir cwd; without that the hook reads whatever `.claude/readback-state.json` sits in the repo root, and a leftover `user_confirmed: true` silently suppresses every expected-fire case (this bit during v3 development).
