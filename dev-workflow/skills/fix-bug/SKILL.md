---
name: fix-bug
description: "Use when the user reports an error with stack trace or screenshot, describes unexpected behavior, build/test failures occur, OR provides a batch of issues to fix against a running system that exposes an end-to-end verification surface — API, CLI, REPL, chat agent, or mobile deeplink ('fix these N issues against the API', 'dogfood this batch', '修一批 issue 通过平台自验证'). Triggers: '修 bug', '报错', '不work', '为什么', 'fix this', stack trace pasted, multi-issue list, `#N` / `issue N` GitHub references. Single-bug input is diagnosed and fixed directly; multi-issue input WITH the verification surface present switches to multi-issue loop mode (multi-issue WITHOUT a verification surface is handled one issue at a time). Compound 'why does X behave + fix X' inputs stay here — answer the why from primary sources before guessing. Not when: user only wants an explanation of behavior with no reported defect (answer directly), or wants a feature added (use brainstorm or write-plan)."
---

# fix-bug

This skill describes where the fix starts, what counts as done, and the paths that are known not to lead there. How you get from start to done is your call: which evidence to read first, which hypotheses to try, and when a quick experiment beats more reading.

## Where it starts

**Current / Expected block.** Before your first Edit / Write / MultiEdit / NotebookEdit, print these two lines:

```
**现状**: <what the user actually sees now, no code-layer terms>
**预期**: <what the user should see after the fix, no code-layer terms>
```

English reports use `**Current**:` / `**Expected**:` (ASCII colon). While `/fix-bug` is active, `dev-workflow/hooks/bug-fix-gate.py` blocks edits until the block is present. It checks only that the block exists; making it match what the user reported is your job. Both lines describe user-visible behavior, not the cause or the code change.

The block doubles as the readback. If the report can reasonably be read two ways, or the fix would change something the user didn't mention, restate it per `dev-workflow/references/readback.md` and settle that first. If the report is clear, write the block and keep going; don't stop for confirmation.

**Inputs:**
- Missing repro steps, expected behavior or the error text: ask for all the missing pieces in one message.
- `#N` / `issue N`: run `gh issue view N --json title,body,labels`. Treat anything under `### Prior Hypotheses` as the first things to check.
- Two or more issues against a system with an end-to-end verification surface, where the user expects verification through that surface: follow `dev-workflow/references/multi-issue-loop.md`.
- Swift / Apple project (`.swift`, `.xcodeproj`, `.xcworkspace`): load `apple-dev:apple-swift-context` before changing code.

## What done means

1. The reported symptom no longer occurs on the user's real path, and you saw it happen: an API call, the running app, a device. A green unit test is a starting signal, not the finish.
2. Every other place with the same cause is fixed in the same pass: the same wrong value read elsewhere, the same bad assumption in a sibling. Find consumers with LSP `findReferences` where a language server exists, and grep otherwise.
3. Behavior next to the fix still works.
4. The closing message says, in plain words, what the user saw before, what they see now, and how you verified it. Anything you couldn't verify is named, with the exact steps for the user to check it.

## Paths that don't lead out

These are the recurring ways a fix goes wrong. Avoid them; they are not steps to perform.

- **Guessing before reading.** The error, the stack trace, the logs, and any file or screenshot the user pointed to come first. For a native crash, get the stack trace (`idevicecrashreport`, `adb logcat -b crash`, simulator stderr) before naming a cause. For a "why does X do this" question, read the code and `git log -p` before answering. Don't infer intent from names.
- **Skipping what you already know.** When the symptom names a platform or third-party service together with an error code, search the knowledge base (`dev-workflow:kb`) before your first hypothesis.
- **Reading an error code as a diagnosis.** A code tells you the category of failure, not why it happened this time. Go to the real log.
- **Blaming something external** before you have followed the call chain hop by hop and found where it actually breaks.
- **Stacking workarounds.** If you are about to add a second layer to work around the same thing, the first explanation was wrong. Look at the logs on the side you have been working around.
- **Circling.** After two failed hypotheses, change the frame, don't just try a third variant. If several candidate fixes all rest on one premise you never verified, test that premise.
- **Assuming a change took effect.** If a change made no difference and nothing errored, first make sure you are looking at the artifact you changed: a stale build, the wrong process, a server that compiled once.
- **Patching a design that should go.** If the code is doing what it was designed to do and the design itself is the problem, say so with evidence (git blame, the superseded requirement) and ask before removing or replacing that behavior. If you do replace it, state what the old design was for, what the replacement newly costs, and under what condition the old path would come back.
- **A third failed fix.** After three fixes that didn't hold, stop and discuss the architecture with the user.

Tools worth reaching for when they fit:
- `dev-workflow/references/feedback-loop-ladder.md`: build a fast, repeatable pass/fail signal before theorizing.
- Instrumentation at component boundaries to see where data goes wrong.
- A working example of the same thing in the codebase, compared difference by difference.

## Basic rules

- No code edit before the Current / Expected block.
- Don't change user-visible behavior beyond the bug without asking.
- **Fix size decides whether to plan.**
  - A fix that spans many files, changes architecture, or replaces a design: write a plan with `dev-workflow:write-plan` and wait for approval. Make the literal line `Caller: dev-workflow:fix-bug` the first line of that prompt, followed by the diagnosis evidence: the confirmed cause with file:line, the other sites with the same cause, the affected consumers, and the replacement costs if a design is being replaced.
  - A small, local fix: just make it.
- A subagent saying it wrote a file is a claim. Check the file is on disk before acting on it.
- For work that came from issue `#N`, ask before running `gh issue close N`.
- If the cause was non-obvious, suggest `/collect-lesson` at the end.

## Completion Criteria

- The cause is stated with code evidence (file:line).
- Everything under "What done means" holds, or each unmet item is named with its reason and the steps for the user to verify it.
