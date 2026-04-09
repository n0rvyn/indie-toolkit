# pkos — Personal Knowledge Operating System

Automated knowledge compilation system for Obsidian vaults. Ingests, links, evolves, and surfaces your knowledge.

## Quick Start

```
/pkos                  # Status dashboard
/pkos {topic}          # Query your knowledge base
/pkos ingest {url}     # Ingest a URL into your vault
/pkos review           # Today's wiki changes
/pkos lint             # Latest health report
```

## Skills

| Skill | Trigger | Description |
|-------|---------|-------------|
| `/pkos` | Auto (natural language routing) | Unified entry point: status, query, ingest, review |
| `/harvest` | "harvest", "scan projects", "收割" | Import knowledge from ~/Code/Projects/\*/docs/ |
| `/intel-sync` | Internal | Import insights from domain-intel IEF exports |
| `/digest` | Internal (cron) | Generate daily/weekly digest reports |
| `/signal` | Internal (cron) | Cross-source signal aggregation for weekly review |
| `/inbox` | Internal | Process captured items: classify, route, ripple |
| `/lint` | Internal (cron, Sundays) | Wiki health check: orphans, broken links, frontmatter |
| `/evolve` | Internal | Generate LENS/FOCUS profile updates |
| `/vault` | Internal | Obsidian vault operations (atomic writes, state management) |
| `/serendipity` | Internal | Cross-domain connection discovery |
| `/kb-bridge` | Internal | Export PKOS knowledge to external systems |

## Agents

| Agent | Purpose |
|-------|---------|
| inbox-processor | Classify, extract metadata, route inbox items to Obsidian + Notion |
| ripple-compiler | Propagate new note knowledge across MOCs, add cross-references, update entity pages |
| digest-writer | Compose daily/weekly digest content from pipeline data |
| signal-aggregator | Cross-source pattern detection and trend synthesis |
| wiki-linter | Detect orphan notes, broken wikilinks, frontmatter issues |
| graph-analyzer | Analyze vault as knowledge graph for serendipity discovery |
| knowledge-prefetch | Search vault for notes related to a topic |

## Architecture

```
Inbox (captured items: URLs, voice, text)
  → inbox-processor (classify + route)
      → Obsidian write
      → Notion write (optional)
      → ripple-compiler (propagate to MOCs)
          → MOC updates / creation
          → Cross-reference additions
          → Entity page updates
          → ripple-log.yaml

Harvest (~/Code/Projects/*/docs/)
  → scan + parse
  → inbox-processor (per-file)
  → ripple-compiler (batch)

Intel Sync (IEF imports from domain-intel)
  → inbox-processor (IEF → inbox item)
  → ripple-compiler

Cron (daily/weekly)
  → signal-aggregator (weekly) → signal report
  → digest-writer (daily/weekly) → digest file
  → lint (Sundays) → health report
```

## Vault Directory Structure

PKOS uses a numbered folder structure:

```
~/Obsidian/PKOS/
├── 10-Knowledge/     # Permanent notes (atomic concepts)
├── 20-Ideas/         # Transient ideas and drafts
├── 30-Projects/      # Project-specific notes
├── 40-People/        # Person/entity pages
├── 50-References/     # Reference material (articles, papers)
├── 60-Digests/       # Generated digest reports
├── 70-Reviews/       # Health reports, signal reports
├── 80-MOCs/          # Map of Contents (synthesized topics)
├── 90-Inbox/         # Pending items not yet processed
├── .state/           # Internal state (ripple-log.yaml, last-review-marker)
└── .claude/          # Config and scripts
```

## Configuration

Edit `~/.claude/pkos/config.yaml`:

```yaml
vault:
  path: ~/Obsidian/PKOS

notion:
  enabled: true
  database_id: your-notion-database-id

harvest:
  projects_path: ~/Code/Projects
  docs_pattern: "**/docs/**/*.md"

migrate:
  sources: ~/.claude/pkos/.state/migrate-sources.yaml
```

## Migrate Skill

Import an external Obsidian vault:

```
/pkos migrate                           # Interactive migrate
/pkos migrate --scan-only               # Preview without writing
/pkos migrate --source-vault /path/to/vault
/pkos migrate --source-name github-notes
/pkos migrate --force                   # Re-import all
/pkos migrate --resume                  # Resume from interruption
```

## Cron Setup

```
# Daily digest at 9am
CronCreate(cron="0 9 * * *", prompt="cd ~/Obsidian/PKOS && /digest [cron]")

# Weekly signal aggregation Sundays at 10am
CronCreate(cron="0 10 * * 0", prompt="cd ~/Obsidian/PKOS && /signal [cron]")

# Wiki health check Sundays at 11am
CronCreate(cron="0 11 * * 0", prompt="cd ~/Obsidian/PKOS && /lint [cron]")
```

Note: Cron jobs auto-expire after 7 days. Recreate in new sessions.

## Inbox Processing

When `/pkos ingest <url>` or harvest finds new content:

1. **Classify** — inbox-processor determines type (article, video, podcast, tweet)
2. **Extract** — pulls title, summary, key quotes, tags
3. **Route** — writes to appropriate folder (10-Knowledge, 50-References, etc.)
4. **Ripple** — ripple-compiler propagates knowledge to relevant MOCs, adds cross-references

## MOC (Map of Contents)

MOCs are synthesized topic pages in 80-MOCs/. They aggregate notes on a topic into:
- **Overview**: 2-3 sentence synthesis citing specific notes
- **Notes**: List of related notes with one-line summaries
- **Contradictions & Open Questions**: Detected conflicts between notes
- **Related MOCs**: Links to overlapping MOCs

MOCs are auto-created when a topic has 3+ notes without one.

## Hooks

- **SessionStart**: Reports inbox count and recent vault activity if CWD is the vault directory
