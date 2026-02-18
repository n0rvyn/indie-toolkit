# dev-workflow

Cross-stack development workflow plugin for Claude Code. Provides skills for committing, session handoff, rules auditing, bug fixing, plan verification, architecture review, and design decisions.

## Skills

| Skill | Trigger | Model | Description |
|-------|---------|-------|-------------|
| committing-changes | Manual (`/committing-changes`) | Haiku (fork) | Analyze and commit changes with conventional format |
| handing-off | Manual (`/handing-off`) | Haiku (fork) | Generate cold-start prompt for session transfer |
| reviewing-rules | Manual (`/reviewing-rules`) | Opus | Audit CLAUDE.md rules for conflicts and loopholes |
| fixing-bugs | Auto-trigger | Opus | Systematic bug diagnosis with value domain tracing |
| verifying-plans | Auto-trigger | Opus | Verification-First plan validation |
| reviewing-architecture | Auto-trigger | Opus | Entry point uniqueness and data flow checks |
| making-design-decisions | Auto-trigger | Opus | Trade-off analysis with complexity separation |

## Design Principles

- Bug fix, plan verification, architecture review, and design decision skills use universal methodology (value domain tracing, reverse reasoning, entry point uniqueness, complexity analysis) that works across tech stacks.
- iOS-specific checks (Design Token consistency, Swift concurrency) are provided by the `ios-development` plugin's references. Claude loads both when working on iOS projects.
