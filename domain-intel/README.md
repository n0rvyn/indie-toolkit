# domain-intel

Domain intelligence engine for Claude Code. Automated collection, AI analysis, and trend synthesis from GitHub (via API), Product Hunt, RSS, official changelogs, notable figures, and company news. Includes targeted deep research with evolving focus profiles.

## Quick Start

```
cd ~/Knowledge/ai-ml       # Each directory is a separate profile
/intel setup                # Initialize this directory
/scan                       # Run collection pipeline
/intel brief                # Get a briefing on unread insights
/digest                     # Generate summary report
/intel evolve               # Review and update your preferences
```

## Directory = Profile

Each initialized directory is a self-contained domain-intel workspace. Different directories track different interests:

```
~/Knowledge/ai-ml/          # AI/ML tracking
~/Knowledge/ios-dev/        # iOS development tracking
~/Knowledge/indie-biz/      # Indie business tracking
```

Switch profiles by switching directories. No global config needed.

### Directory Structure

```
./
├── config.yaml             # Source URLs and scan parameters
├── LENS.md                 # Your interests, figures, companies (evolves over time)
├── state.yaml              # Scan statistics
├── .lens-signals.yaml      # Accumulated preference evolution signals
├── insights/YYYY-MM/       # Individual insight files
├── briefings/              # Saved briefings
├── digests/                # Generated digest reports
└── trends/                 # Trend snapshots for continuity tracking
```

## Skills

| Skill | Model | Purpose |
|-------|-------|---------|
| `/scan` | sonnet | Pipeline orchestrator: collect, filter, analyze, store |
| `/digest` | sonnet | Generate daily/weekly digest with trend synthesis |
| `/intel` | sonnet | Human entry point: status, briefing, Q&A, config, evolve |
| `/research` | sonnet | Targeted deep research: full scan, incremental updates, evolving focus |

## Agents

| Agent | Model | Purpose |
|-------|-------|---------|
| source-scanner | sonnet | Collection from GitHub (gh API), Product Hunt (GraphQL API), RSS, official changelogs, figures, companies (optional Playwright fallback for JS-rendered pages) |
| research-scanner | sonnet | Multi-source topic-focused collection: search engines, GitHub, academic, YouTube, community, media, official, institutions |
| insight-analyzer | sonnet | Deep analysis with source-specific prompts, LENS/FOCUS-aware |
| trend-synthesizer | sonnet | Cross-insight pattern detection and synthesis |
| research-synthesizer | sonnet | Report-oriented synthesis with entity extraction, opinion spectrum, timeline |
| focus-evolver | sonnet | Research focus evolution from user feedback and signals |

## Deep Research (`/research`)

Targeted deep research on a specific topic across the entire internet.

```
/research OpenCLaw              # First run: init + full deep research
/research OpenCLaw              # Subsequent: show status
/research OpenCLaw refine       # Update focus based on your interests
/research OpenCLaw update       # Incremental scan with evolved focus
```

### How It Works

1. **Init**: Ask for your core question and angles of interest, auto-discover aliases
2. **Broad scan**: Search engines, GitHub, arXiv, YouTube, Reddit/HN, industry media, official sites, institutions
3. **3-tier filter**: URL dedup, title dedup, relevance scoring against your FOCUS
4. **Deep analysis**: Source-specific prompts extract structured findings
5. **Recursive depth**: Discover key entities in first pass, then search specifically for their positions
6. **Comprehensive report**: Overview, entity graph, opinion spectrum, timeline, information gaps

### FOCUS.md

Each research topic has its own evolving profile:
- **Core Question**: What you're trying to understand
- **Angles of Interest**: Ordered dimensions to explore (position = search budget weight)
- **Active Questions**: Concrete questions to prioritize
- **De-prioritized**: Aspects to skip
- **Key Entities**: Discovered people, orgs, projects, papers

After reading a report, run `/research <topic> refine` to express your interests naturally. The system proposes FOCUS.md updates for your approval.

### Research Directory Structure

```
./Research/<topic-slug>/
├── FOCUS.md                    # Your research profile (evolves over time)
├── config.yaml                 # Source toggles and scan parameters
├── state.yaml                  # Scan stats and seen URLs
├── .focus-signals.yaml         # Accumulated evolution signals
├── findings/YYYY-MM/           # Individual finding files
├── reports/                    # Comprehensive and incremental reports
└── timeline.md                 # Chronological timeline
```

### Research Pipeline

```
Topic + FOCUS.md
    | research-scanner (sonnet) — 8 source categories
    v
Raw Items
    | 3-tier filter (URL dedup → title dedup → FOCUS-aware scoring)
    v
Filtered Items
    | insight-analyzer (sonnet) × N source types (parallel)
    v
First-Pass Findings
    | entity-driven second pass (depth)
    v
All Findings
    | research-synthesizer (sonnet)
    v
Report + Entity Graph + Timeline
```

## LENS.md

Your information filtering profile. Contains:
- **Frontmatter**: structured data (figures to track, companies to monitor)
- **Body**: natural language interests, current questions, anti-interests

LENS.md drives personalized relevance scoring and evolves over time through `/intel evolve`.

## Evolution

Both your preferences (LENS.md) and sources (config.yaml) evolve over time:

1. **Signal collection** — each `/scan` detects patterns not reflected in your profile:
   - New interests (frequent tags not in LENS.md)
   - New figures/companies (names appearing across insights)
   - New RSS feeds (figure blogs, high-value domains)
   - New official paths (discovered company pages)
   - New domains (emerging tag clusters)

2. **Signal storage** — accumulated in `.lens-signals.yaml`

3. **User review** — `/intel evolve` presents each signal for approval or rejection. Approved changes are written to LENS.md or config.yaml.

No changes are ever applied automatically. All evolution requires explicit user approval.

## Automated Scanning (Cron)

With external sources configured, a single `/scan` drives the full pipeline:

```
# Pipeline: pre-collect (youtube-scan) → scan → import → (digest if auto_digest enabled)
CronCreate(cron="47 8 * * *", prompt="cd ~/Knowledge/ai-ml && /scan [cron]")
```

The `[cron]` tag enables non-interactive mode: parameters from config, failures logged not prompted.

To include auto-digest after scan, set `scan.auto_digest: true` in config.yaml.

Note: Cron jobs auto-expire after 3 days. Recreate in new sessions.

## External Sources (IEF)

domain-intel can consume pre-analyzed insights from other plugins via the Insight Exchange Format.

Configure in `config.yaml`:
```yaml
sources:
  external:
    - name: YouTube Scout
      path: ~/.youtube-scout/exports
      pre_collect: /youtube-scan
```

When `/scan` runs:
1. Pre-collect: invokes `/youtube-scan` to produce fresh exports
2. Import: reads IEF files from the export directory
3. Imported insights participate in convergence detection, lens signals, and digests

See project-level CLAUDE.md for the full IEF specification.

## Optional: Browser Fallback

Some company pages and official changelogs use JavaScript rendering (SPA). `fetch_url.py` returns empty content for these (exit code 2). Enable browser fallback for better collection:

```bash
pip install playwright && playwright install chromium
```

Then in your `config.yaml`:

```yaml
scan:
  browser_fallback: true
```

When enabled, the source-scanner retries failed `fetch_url.py` calls (exit code 1 or 2) using a headless Chromium browser (up to 5 pages per scan). Pages that work with `fetch_url.py` are not affected.

## Hooks

- **SessionStart**: Reports unread insight count if CWD is an initialized directory
- **PreToolUse (Write)**: Guards against writing intel data outside the current directory

## Pipeline

```
External Feeders (YouTube Scout / other IEF producers)
    │ pre-collect (Step 1.5)
    ▼
Sources (GitHub API/Product Hunt/RSS/Official/Figures/Companies)
    │ source-scanner (sonnet)
    ▼
Raw Items
    │ 3-tier filter (URL dedup → title dedup → relevance scoring)
    ▼
Filtered Items
    │ insight-analyzer (sonnet) × N source types (parallel)
    ▼
Structured Insights + External IEF Import (Step 5.5)
    │ convergence signal detection + lens signal collection
    ▼
Stored Insights + Signals
    │ trend-synthesizer (sonnet)
    ▼
Digest / Briefing / Query Answer
```
