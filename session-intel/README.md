# session-intel

AI session analytics: extract, analyze, and correlate Claude Code and Codex sessions with git history.

## Skills

### /retro
Daily/weekly retrospective from session data.
```
/retro --days 7 --project indie-toolkit
```

### /session-search
Search past sessions by keyword, project, tool, DNA type, or date range.
```
/session-search --query "caching bug" --days 30
/session-search --project Adam --dna fix
/session-search --tool Edit --semantic
```

### /session-replay
Replay a past session with turn-by-turn timeline.
```
/session-replay abc123de --detail standard
/session-replay abc123de --detail verbose
```

### /trends
Cross-session trend analysis with ASCII charts.
```
/trends --days 30 --metric efficiency
/trends --days 7 --analyze
```

### /cost-report
Token cost breakdown by project, model, and time period.
```
/cost-report --days 7
/cost-report --project indie-toolkit --breakdown model
```

### /collab-health
Collaboration health score (0-100) with dimensional breakdown.
```
/collab-health --days 7
/collab-health --days 30 --recommend
```

## Data Sources

- Claude Code sessions: `~/.claude/projects/*/*.jsonl`
- Codex sessions: `~/.codex/sessions/YYYY/MM/DD/*.jsonl`
- Git history: per-project `.git/`

## Configuration

Copy `references/session-intel.local.md.example` to `~/.claude/session-intel.local.md` and customize:
- `default_days`: lookback window (default: 1)
- `pricing`: token costs per model (USD/1M tokens)
- `auto_summary`: enable SessionEnd hook

## Emotion Analysis

The session-parser agent detects user emotion signals during retro analysis:
- **frustration**: aggressive language, repeated failures
- **impatience**: demands for speed, repeated instructions
- **satisfaction**: positive feedback, task completion acknowledgment

Emotion signals are factored into the collaboration health score and generate targeted improvement suggestions.

## Architecture

```
Session JSONL → Python scripts (deterministic) → LLM agents (semantic) → Reports
```

- **Scripts**: Python stdlib only, no external dependencies
- **Agents**: session-parser (sonnet), retro-writer (sonnet), pattern-miner (sonnet), trend-analyzer (sonnet), health-advisor (sonnet)
- **Hook**: SessionEnd auto-summarization
