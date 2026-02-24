# dev-workflow

Cross-stack development workflow plugin for Claude Code. Provides a full plan-execute-review lifecycle with context-efficient agent dispatching.

## Architecture

Heavy document-generation and analysis tasks run as **agents** (separate context windows) dispatched via the Task tool. Interactive tasks that need user input or write code stay as **skills** in the main context. The `run-phase` orchestrator dispatches agents and coordinates the sequence.

```
run-phase (orchestrator, main context)
  → plan-writer agent (sonnet)        → plan file on disk
  → plan-verifier agent (opus)        → verification report
  → execute-plan skill                → code changes (main context)
  → feature-spec-writer agent (sonnet) → spec file
  → review agents (parallel)          → consolidated findings
  → fix gaps                          → Phase done
```

## Agents

| Agent | Model | Tools | Purpose |
|-------|-------|-------|---------|
| implementation-reviewer | opus | Glob, Grep, Read, Bash | Plan-vs-code verification and design fidelity audit |
| plan-writer | sonnet | Glob, Grep, Read, Write | Structured implementation plan generation |
| plan-verifier | opus | Glob, Grep, Read, Bash | Verification-first plan validation (S1/S2/U1/DF/AR) |
| dev-guide-writer | sonnet | Glob, Grep, Read, Write | Phased project development guide creation |
| feature-spec-writer | sonnet | Glob, Grep, Read, Write | Design-vs-implementation feature spec generation |
| rules-auditor | sonnet | Glob, Grep, Read | CLAUDE.md rules audit for conflicts and loopholes |

## Skills

| Skill | Type | Description |
|-------|------|-------------|
| run-phase | orchestrator | Phase lifecycle: dispatch agents, coordinate sequence, manage state |
| execute-plan | interactive | Batch code execution with checkpoint approval |
| brainstorm | interactive | Design exploration before implementation |
| design-decision | interactive | Trade-off analysis with essential/accidental complexity |
| fix-bug | interactive | Systematic diagnosis with value domain tracing |
| finish-branch | interactive | Test, document, merge/PR/discard |
| parallel-agents | guide | Pattern for concurrent agent dispatch |
| use-worktree | guide | Git worktree setup and safety |
| commit | fork (haiku) | Conventional commit analysis and execution |
| handoff | fork (haiku) | Cold-start prompt generation for session transfer |
| write-plan | dispatcher | Gathers context, dispatches plan-writer agent |
| verify-plan | dispatcher | Gathers context, dispatches plan-verifier agent |
| write-dev-guide | dispatcher | Gathers context, dispatches dev-guide-writer agent |
| write-feature-spec | dispatcher | Gathers context, dispatches feature-spec-writer agent |
| reviewing-rules | dispatcher | Gathers context, dispatches rules-auditor agent |
| collect-lesson | interactive | Capture development lessons learned |
| docs-rag | interactive | Documentation search and retrieval |

## Hooks

| Event | Script | Purpose |
|-------|--------|---------|
| SessionStart | check-workflow-state.sh | Detects in-progress phase, prompts resume |

## Workflow State

`run-phase` persists progress to `.claude/dev-workflow-state.yml`, enabling cross-session resume. The SessionStart hook detects this file and prompts the user to continue.

## Design Principles

- Bug fix, plan verification, and design decision skills use universal methodology (value domain tracing, reverse reasoning, entry point uniqueness, complexity analysis) that works across tech stacks.
- iOS-specific checks (Design Token consistency, Swift concurrency) are provided by the `ios-development` plugin's references.
- Document-generation tasks (plans, specs, guides, audits) run in separate agent contexts to preserve main context for code execution.
