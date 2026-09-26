---
name: fix-bug
description: "Use when the user reports an error with stack trace or screenshot, describes unexpected behavior, build/test failures occur, OR provides a batch of issues to fix against a running system that exposes an end-to-end verification surface — API, CLI, REPL, chat agent, or mobile deeplink ('fix these N issues against the API', 'dogfood this batch', '修一批 issue 通过平台自验证'). Triggers: '修 bug', '报错', '不work', '为什么', 'fix this', stack trace pasted, multi-issue list, `#N` / `issue N` GitHub references. Single-bug input is diagnosed and fixed directly; multi-issue input WITH the verification surface present switches to multi-issue loop mode (multi-issue WITHOUT a verification surface is handled one issue at a time). Compound 'why does X behave + fix X' inputs stay here — answer the why from primary sources before guessing. Not when: user only wants an explanation of behavior with no reported defect (answer directly), or wants a feature added (use brainstorm or write-plan)."
effort: high
---

<!-- cost-posture: inherit (judgment — finding a root cause and deciding when a fix is a design question are diagnosis calls; do NOT downgrade, per project CLAUDE.md). The skill's effort pin is not honored when Claude auto-invokes it, so the hardest diagnosis calls go to the `dev-workflow:bug-diagnoser` agent (effort: high, always honored); see "Diagnosis" below. -->

# fix-bug

This skill describes where the fix starts, what counts as done, and the paths that are known not to lead there. How you get from start to done is your call: which evidence to read first, which hypotheses to try, and when a quick experiment beats more reading.

## Where it starts

**Current / Expected block.** Before your first Edit / Write / MultiEdit / NotebookEdit, print these two lines:

```
**现状**: <what the user actually sees now, no code-layer terms>
**预期**: <what the user should see after the fix, no code-layer terms>
```

English reports use `**Current**:` / `**Expected**:` (ASCII colon). While `/fix-bug` is active, `dev-workflow/hooks/bug-fix-gate.py` blocks edits until the block is present. It checks only that the block exists; making it match what the user reported is your job. Both lines describe user-visible behavior, not the cause or the code change.

The block doubles as the readback. If the report can reasonably be read two ways, or the fix would change something the user didn't mention, restate it per `${CLAUDE_PLUGIN_ROOT}/references/readback.md` and settle that first. If the report is clear, write the block and keep going; don't stop for confirmation.

**Inputs:**
- Missing repro steps, expected behavior or the error text: ask for all the missing pieces in one message.
- `#N` / `issue N`: run `gh issue view N --json title,body,labels`. Treat anything under `### Prior Hypotheses` as the first things to check.
- Two or more issues against a system with an end-to-end verification surface, where the user expects verification through that surface: follow `${CLAUDE_PLUGIN_ROOT}/references/multi-issue-loop.md`.
- Swift / Apple project (`.swift`, `.xcodeproj`, `.xcworkspace`): load `apple-dev:apple-swift-context` before changing code.

## Diagnosis

Read the evidence yourself first. If that first read confirms the cause (you can point to the file:line that produces the wrong behavior and explain the evidence from it), go on without a dispatch. Otherwise, dispatch the read-only diagnosis agent. Don't dispatch it up front on every bug.

**When to dispatch** `Agent(subagent_type: "dev-workflow:bug-diagnoser")`:
- **Conditional:** after your first read of the evidence, the cause is not confirmed.
- **Mandatory:** two hypotheses have failed (the Circling point below). Always dispatch here, even if you have a third idea.
- **Mandatory:** you think the code is doing what it was designed to do and the design is the problem. The bug-vs-design verdict comes from the agent, not from the main turn.

**What to pass.** The agent does not see the conversation, so pass it all:
- the absolute project root
- the Current / Expected block
- the error text, stack trace and log excerpts, verbatim
- the repro steps
- file paths of any logs, screenshots or reports. An image pasted into chat can't be passed; describe it in text and say that it is a description.
- the `gh issue view` body, including `### Prior Hypotheses`, if the work came from an issue
- any KB hits
- at the Circling point, every failed hypothesis with what was tried and what was observed

If a call-chain trace would help, you may dispatch `dev-workflow:flow-tracer` in parallel. It is tuned for Swift and has no Bash. The diagnoser cannot dispatch it itself.

**Using the return** (`## Diagnosis` block):
- `confirmed` / `probable`: fix from `Cause`, and fix every `Same-Cause Sites` entry in the same pass. Check each entry under `Consumers`. Treat `Unverified Premises` as open until you check them.
- `need-experiment`: run the `Next Experiment` in the main turn (instrumentation, a quick repro, the running app or device), then dispatch again with the result added as evidence.
- `Design Verdict: design`: follow "Patching a design that should go" below, using the agent's evidence.
- `unknown` / `insufficient-input`: gather what it names (ask the user in one message if it has to come from them), then dispatch again.

**If the dispatch fails** (error, timeout, or a return with no `## Diagnosis` block), say in plain words that the root-cause diagnosis did NOT run. Don't treat that as "no findings". Don't present your own guess as the agent's verdict. For a mandatory dispatch, retry once. If it still fails, tell the user the check did not run and ask before making a design call or a third fix.

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
- **Circling.** After two failed hypotheses, change the frame, don't just try a third variant. If several candidate fixes all rest on one premise you never verified, test that premise. This is a mandatory `dev-workflow:bug-diagnoser` dispatch with both hypotheses listed (see "Diagnosis"). Its `Premise Check` is the reframe.
- **Assuming a change took effect.** If a change made no difference and nothing errored, first make sure you are looking at the artifact you changed: a stale build, the wrong process, a server that compiled once.
- **Patching a design that should go.** If the code is doing what it was designed to do and the design itself is the problem, say so with evidence (git blame, the superseded requirement), taken from the `Design Verdict` of a `dev-workflow:bug-diagnoser` return, and ask before removing or replacing that behavior. If you do replace it, state what the old design was for, what the replacement newly costs, and under what condition the old path would come back.
- **A third failed fix.** After three fixes that didn't hold, stop and discuss the architecture with the user.

Tools worth reaching for when they fit:
- `${CLAUDE_PLUGIN_ROOT}/references/feedback-loop-ladder.md`: build a fast, repeatable pass/fail signal before theorizing.
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

- The cause is stated with code evidence (file:line), taken from your own confirmed first read or from the `Cause` of a `dev-workflow:bug-diagnoser` return.
- If a bug-diagnoser dispatch was required (Circling, or a design verdict) and did not run, the closing message says so.
- Everything under "What done means" holds, or each unmet item is named with its reason and the steps for the user to verify it.
