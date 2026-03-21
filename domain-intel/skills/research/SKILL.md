---
name: research
description: "Use when the user says 'research', 'deep research', 'research topic', or wants comprehensive internet-wide investigation of a specific topic. Supports full deep research, incremental updates, and evolving focus profiles. Entry point for targeted topic intelligence."
model: sonnet
user-invocable: true
---

## Overview

Targeted deep research on a specific topic. Searches as many internet sources as possible, produces comprehensive reports, and supports incremental updates with an evolving focus profile (FOCUS.md).

Uses sonnet because the 3-tier filter requires precise arithmetic (Jaccard similarity, weighted scoring) and the multi-phase pipeline requires careful orchestration.

## Process

### Step 0: Resolve Working Directory

```
Bash(command="pwd")
```

Store the result as `WD`. **All file paths in this skill are relative to `WD`** — prefix every `./` path with `{WD}/` when calling Read, Write, Glob, or Grep. Bash commands can use relative paths as-is.

### Step 1: Parse Input

Extract from user input:
- `topic` — the research subject (e.g., "OpenCLaw"). If no topic provided, go to **Action: help**.
- `subcommand` — optional: `refine` or `update`. If absent, no subcommand.

### Step 2: Slugify and Route

1. Slugify the topic for directory name:
   - Lowercase
   - Replace spaces and special characters with hyphens
   - Collapse consecutive hyphens
   - Strip leading/trailing hyphens
   - Store as `slug`

2. Set `RESEARCH_DIR` = `{WD}/Research/{slug}`

3. Check if `{RESEARCH_DIR}/FOCUS.md` exists → route:

| State | Subcommand | Action |
|---|---|---|
| No profile | (none) | → **Action: init + full research** |
| Has profile | (none) | → **Action: status** |
| Has profile | refine | → **Action: refine** |
| Has profile | update | → **Action: update** |
| No profile | refine/update | → Error: `[research] No research profile for "{topic}". Run /research {topic} first.` → **stop** |
| No topic | (none) | → **Action: help** |

---

## Action: help

Output directly:

```
[research] Deep topic research with evolving focus

Usage:
  /research <topic>          — Start new research (or show status if exists)
  /research <topic> refine   — Update research focus based on your interests
  /research <topic> update   — Incremental scan with evolved focus

Concepts:
  FOCUS.md — your research profile for a topic (evolves over time)
  Findings — collected and analyzed items in ./Research/<topic>/findings/
  Reports — comprehensive research reports in ./Research/<topic>/reports/
```

Then list active research profiles:
```
Glob(pattern="{WD}/Research/*/FOCUS.md")
```

For each found FOCUS.md:
- Read the frontmatter to extract `topic` and `created`
- Output: `  {topic} (created {date}) — ./Research/{slug}/`

If no profiles found: `  No active research profiles in this directory.`

→ **stop**

---

## Action: status

Show overview of existing research profile.

1. Read `{RESEARCH_DIR}/FOCUS.md`:
   - Parse frontmatter: `topic`, `created`, `aliases`, `key_entities`
   - Parse body: extract "Angles of Interest", "Active Questions" sections

2. Read `{RESEARCH_DIR}/state.yaml`:
   - Extract `last_scan`, `total_findings`, `total_scans`

3. Count findings:
   ```
   Grep(pattern="read: false", path="{RESEARCH_DIR}/findings/", output_mode="count")
   ```
   ```
   Glob(pattern="{RESEARCH_DIR}/findings/**/*.md")
   ```

4. Find latest report:
   ```
   Glob(pattern="{RESEARCH_DIR}/reports/*.md")
   ```
   Take the most recent by filename.

5. Check pending signals:
   Read `{RESEARCH_DIR}/.focus-signals.yaml` if it exists, count entries.

6. Output:
```
[research] {topic}
  Created: {date}
  Aliases: {comma-separated aliases}
  Last scan: {last_scan}
  Total scans: {total_scans}
  Findings: {total} ({unread} unread)
  Key entities: {N} people, {N} orgs, {N} projects, {N} papers
  Latest report: {path} ({date})

  Angles of Interest:
    {list from FOCUS.md}

  Active Questions:
    {list from FOCUS.md}
```

If signals pending: `  Evolution signals: {N} pending — run /research {topic} refine to review`

→ **stop**

---

## Action: init + full research

### Step 3: Initialize Research Directory

1. Create directories:
   ```
   Bash(command="mkdir -p \"./Research/{slug}/findings\" \"./Research/{slug}/reports\"")
   ```

2. Ask for core research question:
   ```
   AskUserQuestion: "What's your core question about {topic}? What are you trying to understand?"
   ```

3. Ask for initial angles:
   ```
   AskUserQuestion: "What specific angles or dimensions do you want to explore? (List the aspects you care about most, in priority order)"
   ```

4. Auto-discover aliases:
   ```
   WebSearch(query="{topic}" also known as OR abbreviation OR alias OR alternative name)
   ```
   Extract candidate aliases (alternative names, abbreviations, translations).
   Present discovered aliases via AskUserQuestion for user confirmation (multiSelect).
   Add confirmed aliases to the list. Always include the original topic name.

5. Read templates:
   ```
   Read ${CLAUDE_PLUGIN_ROOT}/templates/default-focus.md
   Read ${CLAUDE_PLUGIN_ROOT}/templates/default-research-config.yaml
   ```

6. Generate `{RESEARCH_DIR}/FOCUS.md` from template:
   - Fill `topic` with display name, `created` with today's date
   - Fill `aliases` with confirmed aliases
   - Fill "Core Question" with user's answer
   - Fill "Angles of Interest" with user's angles (as bullet list)
   - Leave "Active Questions" and "De-prioritized" empty

7. Copy default config:
   Write `{RESEARCH_DIR}/config.yaml` from template (no modifications needed — all sources enabled by default).

8. Initialize state:
   Write `{RESEARCH_DIR}/state.yaml`:
   ```yaml
   last_scan: "never"
   total_findings: 0
   total_scans: 0
   seen_urls: []
   ```

9. Create empty timeline:
   Write `{RESEARCH_DIR}/timeline.md`:
   ```markdown
   # {topic} — Timeline

   *Auto-generated and updated by /research. Newest entries first.*

   ---
   ```

### Step 4: Resolve Script Paths

```
Bash(command="echo ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_url.py")
```
Store as `fetch_script_path`.

```
Bash(command="echo ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_rendered.py")
```
Store as `fallback_script_path`.

Read `{RESEARCH_DIR}/config.yaml` to get `browser_fallback` setting.

### Step 5: Dispatch research-scanner

Read `{RESEARCH_DIR}/FOCUS.md`:
- Parse frontmatter: `aliases`
- Parse body: extract "Angles of Interest" items, "Active Questions" items, "De-prioritized" items

Dispatch the `research-scanner` agent with:
- **topic**: display name from FOCUS.md `topic` field
- **aliases**: from FOCUS.md frontmatter
- **angles**: extracted "Angles of Interest" items
- **active_questions**: extracted "Active Questions" items (empty on first run)
- **deprioritized**: extracted "De-prioritized" items (empty on first run)
- **seen_urls**: empty list (first run)
- **fetch_script_path**: resolved path
- **fallback_script_path**: resolved path
- **browser_fallback**: from config
- **max_items_per_source**: from config (default 30)
- **scan_mode**: `"broad"`

Wait for completion. The agent returns:
```yaml
items:
  - url, title, source, snippet, metadata, collected_at
failed_sources:
  - url, source_type, error
stats:
  search: N, github: N, academic: N, youtube: N, community: N, media: N, official: N, institution: N, failed: N, total: N
```

If total items == 0 → output `[research] No items collected for "{topic}". Check your topic name and try again.` → **stop**

Output progress: `[research] Collected {total} items from {N} sources. Filtering...`

### Step 6: 3-Tier Filter

Apply filters sequentially. Track counts at each stage.

#### Tier 1: URL Deduplication

**Skip Tier 1 on first run** (no prior findings exist). Set `after_url_dedup = total items` and proceed to Tier 2.

For subsequent runs (update action):

For each item, normalize the URL:
- Strip protocol (http:// or https://)
- Lowercase the hostname
- Remove trailing slash
- Remove query parameters matching `utm_*`, `ref=`, `source=`

**Regex-escape the normalized URL**: replace `.` with `\\.`, `+` with `\\+`, `?` with `\\?`, `[` with `\\[`, `]` with `\\]`.

Check if the normalized URL exists in existing findings:
```
Grep(pattern="{escaped_url}", path="{RESEARCH_DIR}/findings/", output_mode="files_with_matches", head_limit=1)
```

Also check against `seen_urls` from state.yaml (catches items that were previously collected but didn't pass analysis threshold).

Remove items whose URL already exists. Track: `after_url_dedup = N`

#### Tier 2: Title Deduplication

Get titles from existing findings:
```
Grep(pattern="^title:", path="{RESEARCH_DIR}/findings/", output_mode="content")
```

For each remaining item, compare its title against existing titles:
- Lowercase both titles
- Split into words, remove common stop words (the, a, an, is, of, for, in, on, to, and, with)
- Calculate word overlap: `|intersection| / |union|`
- If overlap > 0.80 → mark as duplicate

Remove duplicates. Track: `after_title_dedup = N`

#### Tier 3: Relevance Scoring

For each remaining item, compute relevance score:

```
score = 1  # Baseline: all research-scanner items were query-targeted for this topic

# Topic/alias matching
For each alias in FOCUS.md aliases[]:
  if alias appears in item.title OR item.snippet (case-insensitive):
    score += 1

# Angle of Interest matching
For each angle in FOCUS.md "Angles of Interest":
  if any keyword from angle appears in item.title OR item.snippet (case-insensitive):
    score += 1

# Active Question matching (higher weight)
For each question in FOCUS.md "Active Questions":
  if any keyword from question appears in item.title OR item.snippet (case-insensitive):
    score += 2

# De-prioritized blacklist
For each deprioritized in FOCUS.md "De-prioritized":
  if deprioritized appears in item.title OR item.snippet (case-insensitive):
    score -= 3
```

Drop items with score <= 0. Sort remaining by score descending.

Take top 50 items. Hard cap at 50 to stay within agent turn budgets while allowing deeper research than `/scan`'s 30.

Track: `after_relevance = N`

Output progress: `[research] Filtered: {after_url_dedup} → {after_title_dedup} → {after_relevance} items. Analyzing...`

### Step 7: Dispatch insight-analyzer

Get today's date:
```
Bash(command="date +%Y-%m-%d")
```
Store as `today`. Also get month: `Bash(command="date +%Y-%m")`

Ensure findings month directory:
```
Bash(command="mkdir -p \"./Research/{slug}/findings/{YYYY-MM}\"")
```

Map research source categories to insight-analyzer source types:

| Research source | Analyzer source_type |
|---|---|
| search | web |
| github | github |
| academic | academic |
| youtube | youtube |
| community | community |
| media | web |
| official | web |
| institution | web |
| figure | figure |

Group filtered items by their mapped source_type.

Read FOCUS.md body and **remap section names to LENS.md format** so insight-analyzer's LENS-aware screening activates correctly:
- `## Angles of Interest` → `## What I Care About`
- `## Active Questions` → `## Current Questions`
- `## De-prioritized` → `## What I Don't Care About`
- `## Core Question` → prepend to `## What I Care About` as context

Store the remapped text as `focus_context`.

For each non-empty group, dispatch one `insight-analyzer` agent with:
- **items**: filtered items for that source type
- **source_type**: mapped type (github, web, academic, youtube, community)
- **domains**: `[{name: "{topic}"}]` (research uses topic as the primary domain)
- **significance_threshold**: from config (default 2)
- **date**: today
- **lens_context**: remapped FOCUS.md body content (LENS-compatible section names)

Dispatch all groups **in parallel** (multiple Agent tool calls in one message).

Wait for all to complete. Merge results. Each analyzer returns:
```yaml
insights:
  - id, source, url, title, significance, tags, category, domain,
    problem, technology, insight, difference, selection_reason
dropped:
  - url, reason
```

### Step 8: Store Findings

For each insight with `significance >= significance_threshold`:

1. Verify the ID doesn't collide with existing files. If collision, increment sequence number.

2. Write finding file to `{RESEARCH_DIR}/findings/{YYYY-MM}/{id}.md`:

```markdown
---
id: {id}
source: {source}
url: "{url}"
title: "{title}"
significance: {N}
tags: [{tags joined by comma}]
category: {category}
domain: {topic}
date: {YYYY-MM-DD}
read: false
---

# {title}

**Problem:** {problem}

**Technology:** {technology}

**Insight:** {insight}

**Difference:** {difference}

---

*Selection reason: {selection_reason}*
```

Track: `stored = N`

3. Collect all stored finding URLs → append to `seen_urls` list for state.yaml.

Output progress: `[research] Stored {stored} findings. Running depth pass...`

### Step 8.5: Recursive Depth — Entity-Driven Second Pass

**Skip this step if fewer than 5 findings were stored in Step 8.**

1. Extract key entities from stored findings:
   - Scan `problem`, `technology`, `insight`, `difference` fields
   - Identify people names (capitalized multi-word names referencing persons)
   - Identify organizations (capitalized names referencing companies/institutions)
   - Identify projects (named tools, frameworks, products)

2. Filter to high-signal entities: mentioned in 2+ findings OR found in a finding with significance >= 4.

3. For each high-signal entity (budget: max 10 WebSearch calls + 5 fetch calls total):

   **For people:**
   ```
   WebSearch(query="{entity_name}" "{topic}" opinion OR perspective OR position OR interview)
   ```
   ```
   WebSearch(query="{entity_name}" blog OR talk OR keynote about "{topic}")
   ```

   **For orgs/projects:**
   ```
   WebSearch(query="{entity_name}" "{topic}" announcement OR analysis OR report)
   ```
   If a URL was discovered in findings, fetch with:
   ```
   Bash(command="python3 \"{fetch_script_path}\" \"{url}\" --timeout 30")
   ```

4. Collect second-pass items. Apply Tier 1 + Tier 2 filtering against existing findings (URL + title dedup).

5. If second-pass items remain after filtering:
   - Dispatch insight-analyzer for second-pass items
   - source_type: `figure` for people, `web` for orgs/projects
   - Store resulting findings (same Step 8 format)
   - Append to `seen_urls` and `stored` count

Output progress: `[research] Depth pass: found {N} additional findings from {M} key entities.`

### Step 9: Dispatch research-synthesizer

Collect all stored findings (first pass + second pass).

Read them from files (use `**` to capture all months):
```
Glob(pattern="{RESEARCH_DIR}/findings/**/*.md")
```
Read all matching files.

Dispatch the `research-synthesizer` agent with:
- **topic**: display name
- **focus_context**: FOCUS.md body content
- **findings**: all finding contents
- **key_entities**: from FOCUS.md frontmatter (empty on first run)
- **previous_report**: empty (first run)
- **mode**: `"comprehensive"`

Wait for completion. The agent returns the structured report data (overview, findings_by_category, entity_graph, opinion_spectrum, timeline, information_gaps, suggested_next_steps).

### Step 10: Generate Report and Update State

1. **Update FOCUS.md key_entities** with discovered entities from synthesizer's `entity_graph`:
   - Read current FOCUS.md
   - Update `key_entities` in frontmatter: merge new people, orgs, projects, papers
   - Write updated FOCUS.md

2. **Write timeline**:
   Read existing `{RESEARCH_DIR}/timeline.md`.
   Prepend new timeline entries from synthesizer output (newest first, after the header).

3. **Write report** to `{RESEARCH_DIR}/reports/{YYYY-MM-DD}-report.md`:

```markdown
---
date: {YYYY-MM-DD}
topic: "{topic}"
finding_count: {N}
mode: comprehensive
---

# Research Report — {topic}

*Generated: {YYYY-MM-DD} | Findings: {N} | Sources: {source_count}*

## Overview

{overview from synthesizer}

## Key Findings

{For each category in findings_by_category:}
### {category}

{For each finding: significance badge + title + summary}

## Entity Graph

### Key People
| Name | Role/Affiliation | Referenced In |
|------|-----------------|---------------|
{people entries}

### Organizations
| Name | Type | Referenced In |
|------|------|---------------|
{org entries}

### Projects
| Name | Description | URL | Referenced In |
|------|-------------|-----|---------------|
{project entries}

### Papers
| Title | Authors | Year | URL |
|-------|---------|------|-----|
{paper entries}

## Opinion Spectrum

### Supportive
{supportive positions with evidence}

### Neutral
{neutral positions with evidence}

### Critical
{critical positions with evidence}

## Timeline

{timeline entries, newest first}

## Information Gaps

{list of what couldn't be found or verified}

## Suggested Next Steps

{specific actions for deeper research}

---
*Generated by /research — domain-intel*
```

4. **Update state.yaml**:
```yaml
last_scan: "{YYYY-MM-DD}T{HH:MM:SS}"
total_findings: {stored count}
total_scans: 1
seen_urls:
  - {all collected URLs}
last_scan_stats:
  collected: {raw items from scanner}
  after_url_dedup: {N}
  after_title_dedup: {N}
  after_relevance: {N}
  analyzed: {sent to analyzers}
  stored: {above threshold}
  depth_pass_findings: {N}
  failed_sources: {N}
```

5. **Output report summary**:

```
[research] Research complete — {topic}
  Collected: {N} → Filtered: {N} → Analyzed: {N} → Stored: {N}
  Depth pass: {N} additional findings from {M} entities
  Key entities: {N} people, {N} orgs, {N} projects, {N} papers
  Report: {report_path}
  Failed sources: {N}

Next steps:
  Read the full report: {report_path}
  Refine your focus: /research {topic} refine
  Run incremental update: /research {topic} update
```

→ **stop**

---

## Action: refine

Interactive FOCUS.md update based on user's evolving interests.

### Step 3r: Load Context

1. Read `{RESEARCH_DIR}/FOCUS.md` (full content)
2. Find and read latest report:
   ```
   Glob(pattern="{RESEARCH_DIR}/reports/*.md")
   ```
   Read the most recent by filename.
3. Read `{RESEARCH_DIR}/.focus-signals.yaml` if it exists.

### Step 4r: Present Current Focus

Output current focus summary:
```
[research] Current focus for "{topic}"

Core Question:
  {from FOCUS.md}

Angles of Interest:
  {numbered list from FOCUS.md}

Active Questions:
  {list from FOCUS.md, or "(none)"}

De-prioritized:
  {list from FOCUS.md, or "(none)"}

Key Entities:
  People: {names}
  Orgs: {names}
  Projects: {names}
```

If `.focus-signals.yaml` has entries:
```
  Pending evolution signals: {N}
```

Then prompt the user:
```
What aspects interest you more? What do you want to explore further, or stop tracking? Express your thoughts naturally.
```

### Step 5r: Process User Feedback

After user responds with natural language feedback:

Dispatch the `focus-evolver` agent with:
- **focus_content**: full FOCUS.md content
- **latest_report**: latest report content
- **user_feedback**: the user's natural language response
- **focus_signals**: .focus-signals.yaml content (or empty)

Wait for completion. The agent returns:
```yaml
proposed_changes:
  - section, action, current (for remove/reword), proposed, reason
summary: "..."
```

### Step 6r: Present and Apply Changes

For each proposed change, present using AskUserQuestion:
- Show the change: "{action} in {section}: {proposed}" with reason
- Options: "Apply", "Skip"

For approved changes:
- Read current FOCUS.md
- Apply modifications:
  - **add** to a section: append the proposed text as a new bullet
  - **remove** from a section: remove the matching bullet
  - **reword** in a section: replace the `current` text with `proposed`
  - **add** to key_entities: append to the appropriate frontmatter list
  - **add** to aliases: append to the frontmatter aliases list
- Write updated FOCUS.md

Clear processed signals from `.focus-signals.yaml` (remove entries that were presented, whether approved or skipped).

### Step 7r: Confirm

Output:
```
[research] Focus updated for "{topic}"
  Applied: {N} changes
  Skipped: {N}

Updated focus:
  Angles: {updated list}
  Questions: {updated list}
  De-prioritized: {updated list}

Run /research {topic} update to scan with your refined focus.
```

→ **stop**

---

## Action: update

Incremental scan based on evolved FOCUS.

### Step 3u: Load State

1. Read `{RESEARCH_DIR}/FOCUS.md`:
   - Parse frontmatter: `topic`, `aliases`, `key_entities`
   - Parse body: "Angles of Interest", "Active Questions", "De-prioritized"
2. Read `{RESEARCH_DIR}/config.yaml`
3. Read `{RESEARCH_DIR}/state.yaml`:
   - Extract `seen_urls`, `total_findings`, `total_scans`
4. Find latest report:
   ```
   Glob(pattern="{RESEARCH_DIR}/reports/*.md")
   ```

### Step 4u: Resolve Script Paths

Same as Step 4 in full research:
```
Bash(command="echo ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_url.py")
Bash(command="echo ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_rendered.py")
```

### Step 5u: Compute Search Budget

Weight angles of interest by position (first = highest weight):
- If N angles: weight_i = (N - i) / sum(1..N), where i is 0-indexed position
- De-prioritized angles get weight 0
- Active Questions get bonus: distribute 20% of total budget across questions

This weighting shapes the `angles` input passed to the scanner — include weight hints so the scanner allocates its query budget accordingly.

### Step 6u: Dispatch research-scanner (targeted)

Dispatch `research-scanner` with:
- **topic**: from FOCUS.md
- **aliases**: from FOCUS.md
- **angles**: weighted angles (include weight hints)
- **active_questions**: from FOCUS.md
- **deprioritized**: from FOCUS.md
- **seen_urls**: from state.yaml
- **fetch_script_path**, **fallback_script_path**, **browser_fallback**: resolved
- **max_items_per_source**: from config
- **scan_mode**: `"targeted"`

Output progress: `[research] Incremental scan for "{topic}"...`

### Step 7u: Filter

Apply 3-tier filtering (same as Step 6 in full research), with one addition:

**Tier 1 enhancement**: In addition to Grep against existing findings, also check each normalized URL against `seen_urls` from state.yaml. This catches items that were previously collected but didn't pass analysis threshold.

### Step 8u: Analyze

Same as Step 7 in full research: group by source_type, dispatch insight-analyzer in parallel, store findings.

### Step 8.5u: Recursive Depth

Same as Step 8.5 in full research: extract entities from new findings, do targeted second pass. Skip if fewer than 3 new findings stored (lower threshold for incremental since we have existing context).

### Step 9u: Dispatch research-synthesizer (incremental)

Read previous report (latest from Step 3u).

Dispatch `research-synthesizer` with:
- **topic**: display name
- **focus_context**: FOCUS.md body
- **findings**: only new findings from this scan
- **key_entities**: from FOCUS.md frontmatter
- **previous_report**: latest report content
- **mode**: `"incremental"`

The agent returns:
```yaml
new_findings_summary: "..."
connections_to_previous: [{new_finding_id, previous_finding_id, relationship}]
entity_updates: {new_people: [], new_orgs: [], ...}
focus_signals: [{type, value, evidence}]
updated_timeline_entries: [{date, event, source_id}]
```

### Step 10u: Update Everything

1. **Update FOCUS.md key_entities**: merge new entities from `entity_updates`.

2. **Append timeline**: Prepend new entries to `{RESEARCH_DIR}/timeline.md` (after header, before existing entries).

3. **Write incremental report** to `{RESEARCH_DIR}/reports/{YYYY-MM-DD}-update.md`:

```markdown
---
date: {YYYY-MM-DD}
topic: "{topic}"
finding_count: {N}
mode: incremental
---

# Research Update — {topic}

*Generated: {YYYY-MM-DD} | New findings: {N}*

## New Findings Summary

{new_findings_summary}

## Connections to Previous Research

{For each connection: new finding → previous finding, relationship}

## New Entities Discovered

{people, orgs, projects added}

## New Timeline Entries

{entries}

---
*Generated by /research update — domain-intel*
```

4. **Collect focus signals**: Append `focus_signals` from synthesizer to `{RESEARCH_DIR}/.focus-signals.yaml`.

5. **Update state.yaml**:
   - Append new URLs to `seen_urls`
   - Increment `total_findings` and `total_scans`
   - Update `last_scan` and `last_scan_stats`

6. **Output summary**:
```
[research] Update complete — {topic}
  New findings: {N}
  Connections to previous: {N}
  New entities: {N}
  Report: {report_path}
```

If focus_signals > 0:
```
  Focus signals: {N} — run /research {topic} refine to review
```

→ **stop**

## Error Handling

- If research-scanner returns 0 items: report and stop gracefully
- If all insight-analyzers return 0 findings above threshold: report "no significant findings" and stop
- If a single analyzer fails: report the failure, continue with others
- Never leave state.yaml in an inconsistent state — write it as the last step
- If FOCUS.md write fails during entity update: log warning, continue (non-critical)
