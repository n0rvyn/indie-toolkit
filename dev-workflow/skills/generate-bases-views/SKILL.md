---
name: generate-bases-views
description: "Generate Obsidian Bases (.base) views for structured querying of crystals, lessons, and vault notes. Use when the user says 'generate views', 'create base files', 'make queryable', or after crystallize/collect-lesson."
user-invocable: true
---

## Overview

Generates Obsidian Bases `.base` files that provide structured table/board/list views over dev-workflow documents (crystals, lessons) and PKOS vault notes. These files live in the PKOS vault and enable powerful filtering, sorting, and grouping without writing code.

## Arguments

- `--target TARGET`: Which views to generate (crystals | lessons | vault-knowledge | vault-all | cross-project | all). Default: all
- `--output DIR`: Output directory. Default: `~/Obsidian/PKOS/99-System/bases/`

## Process

### Step 1: Scan Source Documents

Based on `--target`, scan the relevant directories:

**crystals:**
```
Glob(pattern="*-crystal.md", path="docs/11-crystals/")
```
For each crystal, extract frontmatter: `type`, `status`, `tags`, `refs`, date from filename.

**lessons:**
```
Glob(pattern="*.md", path="~/.claude/knowledge/")
```
For each lesson, extract frontmatter: `category`, `keywords`, `date`.

**vault-knowledge:**
```
Glob(pattern="**/*.md", path="~/Obsidian/PKOS/10-Knowledge")
Glob(pattern="**/*.md", path="~/Obsidian/PKOS/50-References")
```
For each note, extract frontmatter: `type`, `tags`, `quality`, `status`, `created`.

**cross-project:**
```
Glob(pattern="**/*.md", path="~/Obsidian/PKOS/30-Projects")
```
For each note, extract frontmatter: `type`, `tags`, `harvest_project`, `harvest_type`, `created`.

### Step 2: Generate Base Files

**crystals.base** — decision history across all projects:
```yaml
filters:
  and:
    - 'file.inFolder("docs/11-crystals") || file.inFolder("10-Knowledge")'
    - 'type == "crystal"'

properties:
  file.name:
    displayName: "Crystal"
  status:
    displayName: "Status"
  file.cday:
    displayName: "Date"

views:
  - type: table
    name: "All Decisions"
    order:
      - file.name
      - status
      - tags
      - file.cday
    filters:
      and:
        - 'type == "crystal"'

  - type: table
    name: "Active Decisions"
    order:
      - file.name
      - tags
      - file.cday
    filters:
      and:
        - 'status == "active"'
```

**knowledge-quality.base** — vault knowledge by quality score:
```yaml
filters:
  or:
    - file.inFolder("10-Knowledge")
    - file.inFolder("50-References")

formulas:
  age_days: '(now() - prop("created")).days'

views:
  - type: table
    name: "Quality Dashboard"
    order:
      - file.name
      - type
      - quality
      - citations
      - status
      - formula.age_days
      - file.cday
    filters:
      and: []

  - type: table
    name: "Seeds (need nurturing)"
    order:
      - file.name
      - tags
      - formula.age_days
    filters:
      and:
        - 'status == "seed"'
        - 'formula.age_days > 7'

  - type: table
    name: "High Quality"
    order:
      - file.name
      - quality
      - citations
      - tags
    filters:
      and:
        - 'quality >= 3'
```

**tags-overview.base** — notes grouped by topic:
```yaml
filters:
  or:
    - file.inFolder("10-Knowledge")
    - file.inFolder("20-Ideas")
    - file.inFolder("50-References")

views:
  - type: table
    name: "All Notes by Topic"
    order:
      - file.name
      - type
      - tags
      - quality
      - status
    groupBy:
      property: type
      direction: ASC

  - type: cards
    name: "Topic Cards"
    order:
      - file.name
      - tags
      - status
    groupBy:
      property: status
```

**cross-project-decisions.base** — all crystals across all projects:
```yaml
filters:
  and:
    - file.inFolder("30-Projects")
    - 'harvest_type == "crystal"'

properties:
  file.name:
    displayName: "Decision"
  harvest_project:
    displayName: "Project"
  tags:
    displayName: "Tags"
  file.cday:
    displayName: "Date"

views:
  - type: table
    name: "All Decisions"
    order:
      - file.name
      - harvest_project
      - tags
      - file.cday
    groupBy:
      property: harvest_project
      direction: ASC

  - type: table
    name: "Recent Decisions"
    order:
      - file.name
      - harvest_project
      - tags
    filters:
      and:
        - 'file.cday >= date(today) - dur(30 days)'
```

**cross-project-lessons.base** — all lessons across all projects:
```yaml
filters:
  and:
    - file.inFolder("30-Projects")
    - 'harvest_type == "lesson"'

properties:
  file.name:
    displayName: "Lesson"
  harvest_project:
    displayName: "Project"
  tags:
    displayName: "Tags"

views:
  - type: table
    name: "All Lessons"
    order:
      - file.name
      - harvest_project
      - tags
      - file.cday
    groupBy:
      property: harvest_project
      direction: ASC

  - type: cards
    name: "By Tag"
    order:
      - file.name
      - harvest_project
    groupBy:
      property: tags
```

**project-activity.base** — which projects have recent knowledge activity:
```yaml
filters:
  and:
    - file.inFolder("30-Projects")

formulas:
  age_days: '(now() - prop("created")).days'

views:
  - type: table
    name: "Project Activity"
    order:
      - harvest_project
      - harvest_type
      - file.name
      - file.cday
    groupBy:
      property: harvest_project
      direction: ASC

  - type: table
    name: "Last 30 Days"
    order:
      - file.name
      - harvest_project
      - harvest_type
    filters:
      and:
        - 'formula.age_days <= 30'
```

**kb-lessons.base** — cross-project knowledge base view:
```yaml
# This base file should be placed where it can see ~/.claude/knowledge/ files
# Since Obsidian can only query within its vault, this base queries
# PKOS notes that were bridged FROM the KB (have pkos_source field)

filters:
  or:
    - file.inFolder("10-Knowledge")
    - file.inFolder("50-References")

views:
  - type: table
    name: "KB-Bridged Notes"
    order:
      - file.name
      - source
      - tags
      - file.cday
    filters:
      and:
        - 'source == "domain-intel"'

  - type: table
    name: "Recent Imports"
    order:
      - file.name
      - source
      - quality
    filters:
      and:
        - 'file.cday >= date(today) - dur(7 days)'
```

### Step 3: Write Base Files

```bash
mkdir -p ~/Obsidian/PKOS/99-System/bases/
```

Write each `.base` file to the output directory.

### Step 4: Report

```
Generated Obsidian Bases views:
  crystals.base — {N} crystals indexed
  knowledge-quality.base — {N} notes indexed
  tags-overview.base — {N} notes indexed
  kb-lessons.base — {N} bridged notes indexed
  cross-project-decisions.base — {N} decisions across {P} projects
  cross-project-lessons.base — {N} lessons across {P} projects
  project-activity.base — {N} documents across {P} projects

Open in Obsidian: navigate to 99-System/bases/ and click any .base file.
```

## Notes

- Bases files are YAML. Validate before writing.
- Bases can only query notes within the same vault. Cross-vault queries are not supported.
- The `formulas` section uses Obsidian's built-in formula language (similar to Dataview).
- For crystals that live in the git project (not in PKOS vault): the user would need to symlink `docs/11-crystals/` into the PKOS vault, or we copy crystal files to the vault. See DP-001.
