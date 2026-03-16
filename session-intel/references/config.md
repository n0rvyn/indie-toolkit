# Session Intel Configuration

User configuration is stored in `~/.claude/session-intel.local.md` with YAML frontmatter.

## Configuration Fields

```yaml
---
# Number of days to look back by default
default_days: 1

# Include Codex sessions
include_codex: true

# Filter to specific projects (empty = all)
projects: []

# Auto-save retro reports
auto_save: true

# Retro report save path
save_path: ~/.claude/retro/

# Enable SessionEnd hook for auto-summaries
auto_summary: true

# Session index location
index_path: ~/.claude/session-intel/index.json

# Token pricing (USD per 1M tokens)
pricing:
  claude-opus-4-6: { input: 15, output: 75, cache_read: 1.5 }
  claude-sonnet-4-6: { input: 3, output: 15, cache_read: 0.3 }
  claude-haiku-4-5: { input: 0.8, output: 4, cache_read: 0.1 }
  gpt-5.4: { input: 10, output: 30, cache_read: 1.0 }

# SessionDNA classification thresholds
dna_thresholds:
  explore: 3
  build: 2
  fix: 2
  chat: 0
---
```

## File Locations

| File | Purpose | Created By |
|------|---------|-----------|
| `~/.claude/session-intel/index.json` | Session search index | `build_index.py` |
| `~/.claude/retro/YYYY-MM-DD.md` | Daily retro reports | `/retro` skill |
| `~/.claude/retro/summaries/*.json` | Auto session summaries | SessionEnd hook |
| `~/.claude/session-intel.local.md` | User config | User (manual) |
