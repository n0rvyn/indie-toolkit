# product-lens

Product decision plugin for indie developers. It helps answer whether to pursue an idea, evaluate a product, review recent features, reprioritize projects, and refresh earlier verdicts. `product-lens` produces structured local facts first; PKOS ingests and organizes them; Notion is the management projection.

## Start Here

Tell `product-lens` what decision you need to make:

- "Is this idea worth pursuing?"
- "Should I build this feature?"
- "Which project should I focus on?"
- "I got new evidence; should I change my decision?"

Examples:

```text
/product-lens "Is this idea worth pursuing? AI habit tracker for ADHD adults"
/product-lens "Should I build this feature? Add tags to my notes app"
/product-lens "Which project should I focus on? /path/to/app1 /path/to/app2"
/product-lens "I got new evidence; should I change my decision? App A now has 12 paid users"
```

## AI Entry

AI systems should prefer a structured request shape:

```json
{
  "intent": "portfolio_scan",
  "project_root": "~/Code",
  "mode": "summary",
  "save_report": true,
  "sync_notion": false
}
```

`product-lens` returns a machine-readable summary first, then the Markdown report body.

PKOS boundary:
- `product-lens` publishes structured exchange artifacts
- PKOS ingests them into canonical vault notes
- Notion receives summary fields only

Smoke-test path:

```bash
python3 product-lens/scripts/publish_exchange.py ... --exchange-root /tmp/pkos-e2e/.exchange/product-lens
python3 pkos/skills/ingest-exchange/scripts/ingest_exchange.py --source /tmp/pkos-e2e/.exchange/product-lens/reprioritize/<file>.md --vault-root /tmp/pkos-e2e
```

Live Notion projection:

- Exchange artifact must carry `notion_sync_requested: true`
- The simplest way is publishing with `--sync-notion`
- PKOS ingests first, then projects the canonical note to Notion
- Current verified database:
  - Workspace: `Knowledge Base`
  - Database: `Product Lens Summary DB`
  - Database ID: `3401bde4-ddac-8143-80aa-d65ca05ff26c`

Live path:

```bash
python3 product-lens/scripts/publish_exchange.py \
  --intent recent_feature_review \
  --decision polish \
  --project AppA \
  --feature "smart tagging" \
  --risk "Tag discoverability is still weak." \
  --reason "Recent commits strengthen the core flow." \
  --action "Keep tagging in the main compose flow." \
  --evidence "Recent tagging commits touched compose and list surfaces only." \
  --exchange-root /tmp/pkos-live/.exchange/product-lens \
  --sync-notion

python3 pkos/skills/ingest-exchange/scripts/ingest_exchange.py \
  --source /tmp/pkos-live/.exchange/product-lens/recent-feature-review/<file>.md \
  --vault-root /tmp/pkos-live \
  --sync-notion
```

## Commands

| Command | Description |
|---------|-------------|
| `/product-lens` | Unified human and AI entry point; routes to the correct decision workflow |
| `/evaluate` | Full evaluation of a single product (local project or external app) |
| `/compare` | Compare multiple products; produces scoring matrix and recommendations |
| `/demand-check` | Quick first-pass demand validation (5-minute filter) |
| `/teardown` | Deep dive into a single evaluation dimension |
| `/feature-assess` | Evaluate whether an existing app should add a specific feature (local projects only) |
| `portfolio-scan` | Periodic root-level scan over many projects; emits exchange artifacts for PKOS |
| `project-progress-pulse` | Observable project progress read without fake completion percentages |
| `repo-reprioritize` | Converts recent signals into focus / maintain / freeze / stop decisions |
| `recent-feature-review` | Reviews recent commit windows and feature slices |
| `verdict-refresh` | Re-checks older conclusions against new evidence |

## Evaluation Dimensions

| Dimension | Core Question |
|-----------|--------------|
| **Demand Authenticity (需求真伪)** | Is this pain point painful enough to make people pay an unknown indie? |
| **Journey Completeness (逻辑闭环)** | Is the core journey maintainable by one person and free of dead ends? |
| **Market Space (市场空间)** | Is the niche big enough for indie revenue but small enough to avoid incumbents? |
| **Business Viability (商业可行)** | After platform cuts, can this generate sustainable indie income? |
| **Moat (护城河)** | What stops a well-funded competitor or AI from replicating this? |
| **Execution Quality (执行质量)** | Is tech debt within one person's control? Is it appropriately engineered? |

Each dimension's sub-questions are split into **universal** (always apply) and **platform-specific** (vary by platform; iOS overlay included).

### Extra Modules

- **Kill Criteria** — auto-generated "stop if" conditions to combat sunk cost fallacy
- **Feature Necessity Audit** — must-keep / simplify / cut analysis (local projects only)
- **Elevator Pitch Test** — can you describe value in a tagline + one sentence?
- **Pivot Directions** — adjacent opportunities based on existing code assets and domain knowledge
- **Validation Playbook** — lowest-cost experiments to validate uncertain signals (indie-specific methods)

## Feature Assessment

For evaluating whether an existing app should add a specific feature. Uses 4 custom dimensions designed for what AI + code analysis can assess:

| Dimension | Core Question |
|-----------|--------------|
| **Demand Fit (需求契合)** | Is there evidence users want this feature, and what type of need does it address? |
| **Journey Contribution (旅程贡献)** | Does this feature strengthen the core loop or create a side branch? |
| **Build Cost (实现代价)** | What is the architectural invasiveness, maintenance burden, and opportunity cost? |
| **Strategic Value (战略价值)** | Does this feature deepen the moat, open revenue paths, or create lock-in? |

Each dimension produces a **signal** (Positive / Neutral / Negative) with a **confidence level** (High / Medium / Low). Final verdict: **GO / DEFER / KILL** -- one fatal flaw vetoes everything; no weighted aggregate.

### Conditional Follow-up

- **GO** → **Integration Map**: code-level integration points, reusable infrastructure, modification scope, implementation sequence
- **DEFER/KILL** → **Alternative Directions**: lower-cost variants, complementary features, signal clarification paths

## Architecture

### Pipeline

The evaluation uses a multi-step pipeline to ensure framework compliance:

Product evaluation pipeline:
```
market-scanner → pre-merge sub-questions → 6x dimension-evaluator (parallel) → validate → extras-generator → assemble → present
```

Feature assessment pipeline:
```
app-context-scanner + market-scanner (parallel) → pre-merge sub-questions → 4x feature-dimension-evaluator (parallel) → verdict → feature-followup-generator → validate → assemble → present
```

Each dimension is evaluated by a separate agent call that receives **only** its own sub-questions, scoring/signal anchors, and output template. The skill layer handles reference file reading, platform overlay merging, parallel dispatch, validation, and report assembly.

### Agents

| Agent | Model | Purpose |
|-------|-------|---------|
| `dimension-evaluator` | Opus | Evaluates one dimension; receives pre-merged sub-questions and strict output template |
| `extras-generator` | Sonnet | Generates Kill Criteria, Feature Audit, Elevator Pitch, Pivot Directions, Validation Playbook |
| `market-scanner` | Sonnet | Market research; gathers competitor data, pricing, and market signals |
| `app-context-scanner` | Sonnet | Scans local codebase; produces structured app context summary |
| `feature-dimension-evaluator` | Opus | Evaluates one feature dimension; signal + confidence format |
| `feature-followup-generator` | Sonnet | Generates Integration Map (GO) or Alternative Directions (DEFER/KILL) |
| `repo-activity-scanner` | Sonnet | Gathers repo facts only: activity, tests, docs, TODO density, shipping clues |
| `feature-change-clusterer` | Sonnet | Groups recent changes into likely feature slices |
| `verdict-delta-analyzer` | Sonnet | Compares old verdict reasoning with new evidence |
| `ingress-publisher` | Sonnet | Formats PKOS exchange artifacts without choosing final vault destinations |

### Skills

| Skill | Type | Auto-trigger |
|-------|------|-------------|
| `product-lens` | Router: human natural-language entry + AI structured entry | Yes |
| `evaluate` | Pipeline: market-scanner → 6x dimension-evaluator (parallel) → extras-generator → assembly | No |
| `compare` | N x parallel pipelines + comparison matrix + maturity signals | No |
| `demand-check` | Demand dimension + elevator pitch only; runs in main context | Yes |
| `teardown` | Single dimension-evaluator in deep mode | No |
| `feature-assess` | Pipeline: app-context-scanner + market-scanner → 4x feature-dimension-evaluator (parallel) → verdict → feature-followup-generator → assembly | No |
| `portfolio-scan` | Root-level periodic portfolio scan; publishes exchange artifacts for PKOS | No |
| `project-progress-pulse` | Per-project observable progress scan with normalized states | No |
| `repo-reprioritize` | Portfolio decision skill using current signals and blockers | No |
| `recent-feature-review` | Recent-commit feature slice review with normalized recommendations | No |
| `verdict-refresh` | Prior verdict delta analysis against new evidence | No |

### Reference Files

```
references/
  _calibration.md              # Indie vs enterprise calibration + scoring rubric
  _scoring.md                  # Weight presets, formula, significance threshold
  dimensions/
    01-demand-authenticity.md   # Self-contained: universal + platform variants + anchors
    02-journey-completeness.md
    03-market-space.md
    04-business-viability.md
    05-moat.md
    06-execution-quality.md
  modules/
    kill-criteria.md            # Generation rules + iOS triggers
    feature-audit.md            # Methodology + output format
    elevator-pitch.md           # Constraints + iOS App Store variant
    pivot-directions.md         # Methodology + output format
    validation-playbook.md     # Indie-specific validation experiments + selection logic
  pkos/
    ai-entry-contract.md        # Human + AI invocation contract, summary envelope, intent routing
    note-schemas.md             # signal / verdict / feature-review / exchange artifact schemas
    notion-summary-schema.md    # downstream Notion projection fields and sync status rules
  feature-assess/
    _calibration.md              # Feature-level evaluation framing + signal format
    _verdict.md                  # Verdict computation rules (GO/DEFER/KILL)
    dimensions/
      01-demand-fit.md           # Self-contained: universal + platform variants + signal anchors
      02-journey-contribution.md
      03-build-cost.md
      04-strategic-value.md
    modules/
      integration-map.md         # GO follow-up: code-level integration analysis
      alternative-directions.md  # DEFER/KILL follow-up: lower-cost variants + alternatives
```

Each dimension file is self-contained with platform variants as sections within the file. Adding a new platform overlay means adding a `### [Platform]` section to each dimension file — not creating separate overlay files.

## Platform Overlays

When evaluating iOS apps, the skill extracts the `### iOS` sections from each dimension file, replacing the `### Default` platform-specific sub-questions. Universal sub-questions are always retained. iOS-specific features include:

- Sherlock risk assessment with 5-factor scoring methodology
- App Store category saturation analysis
- WWDC annual maintenance burden
- Apple's 30% revenue cut impact
- CloudKit data lock-in as moat
- ATT impact on ad-supported models
- visionOS/watchOS early-mover opportunities
- Privacy label maintenance burden

The overlay is auto-detected via project files (`.xcodeproj`, `Package.swift`) or user specification.

## Scoring

Each dimension receives a 1-5 star score with evidence-based justification and mandatory anchor match. Scores are combined using configurable weights:

- **Default:** equal weights across all dimensions
- **Validation phase:** demand and market weighted higher
- **Growth phase:** business viability and moat weighted higher
- **Maintenance phase:** execution quality and moat weighted higher

Significance threshold: when comparing products, score differences <= 0.5 are not meaningful.

## Usage Examples

```
# Unified router
/product-lens "Is this idea worth pursuing? AI note app for lawyers"

# Evaluate a local iOS project
/evaluate /path/to/my-ios-app

# Evaluate an external app
/evaluate "Bear"

# Quick demand check on an idea
/demand-check "A markdown note app for developers"

# Compare your projects to decide focus
/compare /path/to/app1 /path/to/app2 "Competitor"

# Deep dive into one dimension
/teardown moat /path/to/my-app

# Evaluate whether to add a feature
/feature-assess /path/to/my-app "Add a tagging system for notes"

# Feature assessment using current directory
/feature-assess "Add social sharing"

# AI structured entry
/product-lens '{"intent":"portfolio_scan","project_root":"~/Code","mode":"summary","save_report":true,"sync_notion":false}'
```

## Notion Notes

- `publish_exchange.py --sync-notion` requests downstream Notion projection
- `ingest_exchange.py --sync-notion` performs the live apply after canonical PKOS note creation
- If the artifact does not request sync, ingest stops at the local PKOS note by design
- Database ID can be read from `~/.claude/pkos/config.yaml` under `product_lens_notion.database_id`
