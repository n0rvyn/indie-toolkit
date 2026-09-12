---
name: plugin-master
description: |
  Use when the user says 'plugin-master', 'orchestrate plugin creation', 'manage plugin lifecycle',
  'review plugin', 'audit plugin', 'iterate skill quality', 'package plugin for marketplace',
  or wants to orchestrate the full lifecycle (create / review / iterate / package / insights) of Claude Code plugins.
  (also: insights based on real usage to propose plugin improvements)
  Not when: user wants only atomic builder guidance for a component (skill / agent / hook / command structure) without eval cases or a review gate — use `/plugin-dev:skill-development` / `agent-development` / `hook-development` / `command-development` / `plugin-structure` directly. plugin-master orchestrates creation with eval cases and a review gate; plugin-dev provides the atomic builders.
  Not when: user wants an uncommitted DIFF reviewed for correctness / test coverage / breaking changes — use `/review-execution`. This skill audits plugin artifacts (trigger quality, dispatch wiring, eval coverage); that one reviews code changes. In a plugin monorepo both fire on the same words, so route on the question being asked, not on the file type.
---

# Plugin Lifecycle Management

统一入口，编排 Claude Code 插件和组件的完整生命周期：创建、评估、审查、迭代、打包。

委托 `plugin-dev` 处理组件创建；eval 用例由 `claude plugin eval` 运行（布局与规则见 `eval-rules.md`），`skill-creator` 负责 description 优化；自建 9 维审查框架和跨插件冲突检测。

单一入口 `/plugin-master`，5 条路由：
- create: intent (intent-distiller) → scaffold (plugin-dev) → eval cases (claude plugin eval) → review → iterate
- review: 9-dimension audit from AI executor perspective + cross-plugin trigger conflict detection
- iterate: fix → re-eval (claude plugin eval, scoped by what changed; skill-creator for description tuning) → compare → verify
- package: full plugin or single component into target project
- insights: analyze real usage data → propose evidence-based skill improvements → open draft PR

## Process

### Step 1: Intent Detection

从用户消息判断路由：

| Route | Signal keywords |
|-------|----------------|
| create | "build", "create", "new plugin", "new skill", "new agent", "new hook", "brainstorm", "I want to make" |
| review | "review", "audit", "check quality", "review plugin", "review skill", "plugin review" |
| iterate | "improve", "fix trigger", "iterate", "refine", "trigger is too broad", "trigger is too narrow", "quality" |
| package | "package", "export", "inject", "distribute", "marketplace-ready", "deploy to project" |
| insights | "insights", "usage data", "propose improvements", "auto-tune", "skill improvements from usage" |

**Routing logic:**
1. If keywords match a single route → proceed to that route
2. If user just says "plugin-master" with no other context → AskUserQuestion: "Which workflow?" with 5 options (create / review / iterate / package / insights)
3. If ambiguous (keywords match multiple routes) → dispatch `skill-master:intent-distiller` agent with user's message → use its `recommendation` field to determine route
4. If still ambiguous after intent-distiller → AskUserQuestion with 5 route options

### Step 2a: Create Route

Goal: produce a high-quality plugin component with eval baseline and review gate.

#### 2a.1: Extract Intent

If intent-distiller was already dispatched in Step 1 (ambiguous routing path), reuse its output here and skip the dispatch.

Otherwise, dispatch `skill-master:intent-distiller` agent:
```
Extract structured plugin/skill development intent from the following user request.

User description: {user's message}
```

The agent returns a structured YAML block with: `capability`, `component_type`, `target_audience`, `success_criteria`, `delegation_targets`, `existing_overlap`, `recommendation`.

#### 2a.2: Confirm Intent

Present the intent summary to the user:
- Capability: {what it does}
- Component type: {skill / agent / hook / command / plugin}
- Existing overlap: {list or "none found"}
- Recommendation: {create new / extend existing / skip}

If `recommendation` is "extend existing" or "skip", explain why and ask user how to proceed.

If `recommendation` is "create new" or user overrides, continue.

#### 2a.3: Check Dependency Availability

Before delegating, detect which optional dependencies are installed:

1. **plugin-dev:** Glob `~/.claude/plugins/**/plugin-dev/**/.claude-plugin/plugin.json`. Found → `plugin_dev_available = true`.
2. **skill-creator:** Glob `~/.claude/plugins/**/skill-creator/**/skills/skill-creator/SKILL.md`. Found → `skill_creator_available = true`. Also store its scripts directory path as `$SC_SCRIPTS`.
3. **claude plugin eval:** run `claude plugin eval --help`. Exit 0 → `plugin_eval_available = true`. Otherwise record `claude --version` and report "claude plugin eval unavailable (needs Claude Code ≥ 2.1.269)" — cases are still written in 2a.4, just not run. Never skip the report.

#### 2a.4: Delegate Creation

Route by `component_type`:

**Full plugin:**
- If `plugin_dev_available`: invoke `Skill("plugin-dev:create-plugin")` (8-phase guided workflow)
- If not: manually scaffold the plugin structure (create `.claude-plugin/plugin.json`, `skills/`, `agents/` directories, README.md) and write components directly

After creation completes, apply step 2 of **Single skill** below (eval rules) to every skill the plugin ships, and make sure the repo's `.gitignore` covers `evals/results/`. Then continue to 2a.5.

**Single skill:**
1. If `plugin_dev_available`: invoke `Skill("plugin-dev:skill-development")` for structure guidance and SKILL.md drafting. If not: write SKILL.md directly following plugin-dev conventions (name/description frontmatter, Process section, Completion Criteria)
2. Eval — Read `${CLAUDE_PLUGIN_ROOT}/skills/plugin-master/eval-rules.md` first, then:
   - Sort each trigger and output behavior into observable (→ a case under `<plugin>/evals/<skill>/`) or not observable (→ `eval.md` spec, with a reason from the closed list). Write `skills/<skill>/eval.md` in pointer, mixed, or spec form, and `evals/<skill>/NOTE.md` if no case was possible.
   - If `plugin_eval_available`: run the load check (`--max-cost-usd 0`) and fix every load error before continuing. Otherwise report "load check not run (claude plugin eval unavailable)".
   - Make sure the repo's `.gitignore` covers `evals/results/`.
   - If `plugin_eval_available`: state the case count and flags of the "New skill" depth tier, then AskUserQuestion "Run the new skill's eval now?" / "Skip the run" — run only on yes.
   - If `skill_creator_available` and the user wants description tuning: invoke `Skill("skill-creator:skill-creator")`, feeding it the eval set built per eval-rules.md §Trigger prompts for skill-creator.
3. After complete → continue to 2a.5

**Agent:**
1. If `plugin_dev_available`: invoke `Skill("plugin-dev:agent-development")` for guidance, then dispatch `plugin-dev:agent-creator` via the Agent tool for generation. If not: write agent .md directly (name/description/model/tools frontmatter, system prompt, constraint section)
2. After created → continue to 2a.5

**Hook:**
- If `plugin_dev_available`: invoke `Skill("plugin-dev:hook-development")`. If not: write hooks.json and hook script directly
- After created → continue to 2a.5

**Command:**
- If `plugin_dev_available`: invoke `Skill("plugin-dev:command-development")`. If not: write command .md directly
- After created → continue to 2a.5

#### 2a.5: Cost Posture Recommendation

Before auto-review, classify the new artifact's dominant work and recommend `model` / `effort` / `context` frontmatter.

1. Read `${CLAUDE_PLUGIN_ROOT}/skills/plugin-master/cost-posture.md` for the classification heuristic, decision questions, and recommended configs. If the file cannot be located, skip this step.

2. Apply the heuristic to the newly created artifact:
   - Read the artifact's description and body
   - Walk the decision questions (writes spec vs follows / output consumed downstream / needs CLAUDE.md / failure cost)
   - Determine the class: Mechanical / Retrieval / Tool wrapper / Judgment / Synthesis / Orchestration

3. If the artifact already has `model:` or `context:` set: verify it matches the recommended config for its class.
   - If it matches: no action, note "cost posture: aligned"
   - If it conflicts with the heuristic (e.g. mechanical skill on inherit, or synthesis skill set to haiku): present the conflict and ask the user to confirm or override

4. If the artifact has no `model:` / `context:` set: present the recommendation as an AskUserQuestion:
   - Class: {detected}
   - Recommended frontmatter: `model: {sonnet|haiku}` + optional `context: fork agent: {Explore|...}`
   - Reason: cite the relevant row from cost-posture.md
   - Options: "Apply recommendation" / "Keep inherit (default Opus)" / "Custom"
   - If "Apply recommendation": Edit the artifact's frontmatter
   - If "Keep inherit": continue without changes
   - If "Custom": ask for explicit values

5. Note the cost posture decision in the **Completion (create)** summary at the end of this route, so the user has it on record.

#### 2a.6: Auto-Review Gate

Collect the file paths of newly created artifacts (from the delegated skill's output, or Glob the target directory for recently created/modified .md files, excluding `evals/**` — those are cases, not artifacts).

Execute the review route (Step 2b) on these artifacts, using Scope A (specific files).

#### 2a.7: Quality Decision

If review finds **Bug-severity** issues:
- Present the findings to user
- AskUserQuestion: "Auto-fix and re-review?" / "Accept as-is" / "Manual fix"
- If auto-fix → execute iterate route (Step 2c) with the Bug items as input, then re-review
- If accept → mark as needs-fix and finish
- If manual fix → pause, user fixes, then re-run review

If review finds only Logic/Minor issues or no issues:
- Present quality gate summary: **pass**

#### Completion (create)
- Artifact created at specified location
- Review report presented
- Quality gate: pass or needs-fix (with specific items listed)

---

### Step 2b: Review Route

Goal: 9-dimension plugin quality audit from the AI executor perspective, plus cross-plugin trigger conflict detection.

#### 2b.1: Determine Scope

From user message, determine what to review:

**Scope A — Specific files:** User gives file paths directly.

**Scope B — Plugin:** User names a plugin or directory. Collect:
- Glob `{plugin}/skills/*/SKILL.md` → all skills
- Glob `{plugin}/agents/*.md` → all agents

**Scope C — Recent changes:** User says "review my changes" or no explicit target.
- `git diff --name-only HEAD` for uncommitted changes
- If clean: `git log --name-only -1 --pretty=format:""` for last commit
- Filter to skill/agent files. Map a changed `evals/<skill>/**` or `skills/<skill>/eval.md` to that skill's `SKILL.md`, so an eval-only change still has a review target

**Scope D — All:** User says "review all" or "audit everything".
- Collect all installed plugin skills and agents

Present the file list to user for confirmation before proceeding.

#### 2b.2: Gather Context

For each plugin in scope, collect:
1. Plugin manifest — `.claude-plugin/plugin.json`
2. All skill files — `skills/*/SKILL.md`
3. All agent files — `agents/*.md`
4. Marketplace entry — check `marketplace.json`
5. Eval sources — for each skill, `evals/{name}/` (cases or `NOTE.md`) and `skills/{name}/eval.md`, per `eval-rules.md`

#### 2b.3: Detect plugin-dev Availability

Check whether `plugin-dev` is installed:
- Glob: `~/.claude/plugins/*/plugin-dev/.claude-plugin/plugin.json` or `~/.claude/plugins/cache/*/plugin-dev/*/.claude-plugin/plugin.json`
- Found → **Strategy A**
- Not found → **Strategy B**

#### 2b.4: Dispatch Review Agents

**Strategy A — plugin-dev available (3 parallel dispatches in a single turn):**

1. `plugin-dev:plugin-validator` agent:
   ```
   Validate this Claude Code plugin's structure.
   Plugin manifest: {path}
   Skills: {comma-separated paths}
   Agents: {comma-separated paths}
   ```

2. `plugin-dev:skill-reviewer` agent:
   ```
   Review these skill descriptions for trigger quality and routing clarity.
   Skills: {comma-separated paths}
   ```

3. `skill-master:plugin-reviewer` agent with `model: "opus"`:
   ```
   Review these Claude Code plugin artifacts from the AI executor perspective.

   Scope: {A/B/C/D}
   Files to review:
   - Skills: {comma-separated paths}
   - Agents: {comma-separated paths}
   - Plugin manifest: {path}

   Also read these for cross-reference checking:
   - Other skills in same plugin(s): {paths}
   - Other agents in same plugin(s): {paths}
   - Eval sources: {per skill: `evals/<skill>/` directory and `skills/<skill>/eval.md` path, or "none"}

   Supporting files to load: none
   Plugin agents dir: {skill-master agents directory path}
   (D1/D2 structural checks and baseline trigger/description checks are handled by plugin-dev agents.)

   Focus on: workflow logic, execution feasibility, edge cases, dispatch loops, spec compliance, metadata & docs, eval source consumption (cases + eval.md, per eval-rules.md), deep trigger conflict detection, and Trigger Health Score.
   ```

**Strategy B — plugin-dev not available (1 dispatch):**

`skill-master:plugin-reviewer` agent with `model: "opus"`:
```
Review these Claude Code plugin artifacts from the AI executor perspective.

Scope: {A/B/C/D}
Files to review:
- Skills: {comma-separated paths}
- Agents: {comma-separated paths}
- Plugin manifest: {path}

Also read these for cross-reference checking:
- Other skills in same plugin(s): {paths}
- Other agents in same plugin(s): {paths}
- Eval sources: {per skill: `evals/<skill>/` directory and `skills/<skill>/eval.md` path, or "none"}

Supporting files to load: structural-validation.md, trigger-baseline.md
  (Resolve via `${CLAUDE_PLUGIN_ROOT}/agents/` if executing inside skill-master plugin context, otherwise Glob `**/skill-master/agents/{structural-validation,trigger-baseline}.md`. These are non-agent reference fragments stored under `agents/` for historical reasons; load with Read, not Task dispatch.)

Focus on: logic bugs, trigger mechanism issues, execution feasibility, and edge cases.
```

#### 2b.5: Cross-Plugin Trigger Conflict Detection

After main review agents complete, if scope includes skills:

Dispatch `skill-master:trigger-arbiter` agent:
```
Scan for cross-plugin trigger conflicts.

Target skill path(s): {comma-separated paths of reviewed skills}
Scope: all
```

#### 2b.6: Present Results

**Strategy A — merge results:**
1. If any agent dispatch failed: mark those dimensions as "Error: agent did not return results"
2. Collect findings from all agents, tag each with source agent
3. Deduplicate: same file + same location → keep the more specific finding
4. Map findings to 9-dimension summary

**Both strategies — unified output:**

1. Group findings by severity: **Bug** / **Logic** / **Minor**
2. For each Bug-severity finding, include the suggested fix inline
3. Append trigger-arbiter results as **Cross-Plugin Conflicts** section
4. If fixes exist: ask user "Apply suggested fixes?" and apply if approved

#### Completion (review)
- Full review report with findings grouped by severity
- Every finding has file:line reference
- Bug-severity findings have actionable fix suggestions
- Cross-plugin conflict section (if skills were reviewed)
- Trigger Health Score per skill

---

### Step 2c: Iterate Route

Goal: improve an existing skill or agent and verify the improvement.

#### 2c.1: Identify Target

Determine the target artifact:
- From user's message: explicit file path or skill/agent name
- From recent review findings: Bug or Logic items from Step 2b

#### 2c.2: Classify Issue Type

| Issue Type | Detection | Action |
|------------|-----------|--------|
| Trigger quality | "trigger too broad/narrow", description quality warnings | Description optimization via skill-creator |
| Logic bug | Bug-severity review findings in workflow steps | Edit SKILL.md, re-validate |
| Missing eval | A side missing (`evals/<skill>/` or `eval.md`), a `NOTE.md` / `Not observable:` reason outside the closed list, or coverage gaps | Write cases / spec per `eval-rules.md`, load check, run |
| Agent issue | Agent frontmatter errors, tool mismatch | Edit agent, re-validate |

#### 2c.3: Check Dependency Availability

If not already detected (e.g., when iterate is called standalone, not from create route):

1. **skill-creator:** Glob `~/.claude/plugins/**/skill-creator/**/skills/skill-creator/SKILL.md`. Found → `skill_creator_available = true`. Also locate its scripts directory: Glob `~/.claude/plugins/**/skill-creator/**/skills/skill-creator/scripts/` → store as `$SC_SCRIPTS`.
2. **claude plugin eval:** same probe as 2a.3 item 3 → `plugin_eval_available`.

#### 2c.4: Execute Fix

**Trigger quality issues (description optimization):**

This is the most common iterate case.

If `skill_creator_available` is false: apply manual description changes based on review findings, then skip to 2c.5.

Otherwise (skill_creator_available = true), automated optimization:

1. Build the eval set per `eval-rules.md` §Trigger prompts for skill-creator: from the skill's cases under `evals/<skill>/` first; from the `eval.md` Trigger sections only for a skill whose triggering stays on the spec side. If neither exists, run **Missing eval coverage** below first, then build the set from the cases it wrote.
2. Write it to `evals.json` in a fresh temp directory (`mktemp -d`) — never inside the skill directory, which 2d.3 copies whole — in the shape `run_eval.py` reads (`item["query"]`):
   ```json
   [
     {"query": "<trigger prompt>", "should_trigger": true},
     {"query": "<negative prompt>", "should_trigger": false}
   ]
   ```

3. Run description optimization:
   ```bash
   python -m scripts.run_loop \
     --eval-set <evals.json path> \
     --skill-path <skill directory> \
     --model <model id, e.g. the session's model> \
     --max-iterations 5 \
     --results-dir <the temp directory from step 2>/runs
   ```
   (Run from `$SC_SCRIPTS` parent directory. `--skill-path` takes the directory — `run_loop.py` checks `<skill-path>/SKILL.md`; `--model` is required.)

4. Present results: `best_description`, `best_train_score`, `best_test_score`

5. AskUserQuestion: "Apply this improved description?" → if yes, update the SKILL.md description frontmatter

**Logic bug / Agent issue:**

1. Apply the fix directly (Edit the SKILL.md or agent .md file)
2. Validate:
   ```bash
   python -m scripts.quick_validate <skill directory>
   ```
   (From skill-creator scripts directory)

**Missing eval coverage:**

1. Write the missing cases / spec per `eval-rules.md` — both sides must exist
2. If `plugin_eval_available`: run the load check (`--max-cost-usd 0`) and fix every load error; otherwise report it as not run
3. If `plugin_eval_available`: state case count and flags, confirm the cost with the user, then run the tier from the depth table — this run is the baseline for future comparison

#### 2c.5: Verify Improvement

After fix is applied:

1. If `plugin_eval_available` and the skill has cases: pick the tier from `eval-rules.md` §Running (depth follows what changed), state case count and flags, confirm the cost with the user, run it, and compare its `aggregate-result.json` with the previous run (overall score, mean Δ, per-case score). Check `NOTES` for rate-limit errors before reading a drop as a regression.

2. If a skill-creator description loop ran: re-run `run_loop` with the same `--eval-set` and `--results-dir`, then compare the two timestamped `results.json` files (`best_train_score`, `best_test_score`). `run_loop` has no `--previous-workspace` flag — that belongs to `eval-viewer/generate_review.py`.

3. Re-run review route (Step 2b) with Scope C (recent changes only)

4. Present before/after comparison summary

#### Completion (iterate)
- Fix applied
- Improvement verified (eval delta or review improvement)
- Before/after comparison presented

---

### Step 2d: Package Route

Goal: prepare output for distribution or injection.

#### 2d.1: Determine Output Mode

AskUserQuestion if not clear from context:
- **Full plugin** — marketplace-ready validation
- **Single component** — inject into a target project

#### 2d.2: Full Plugin — Marketplace Readiness Check

Run these checks in sequence:

1. `.claude-plugin/plugin.json` exists with required fields:
   - `name` (string, non-empty)
   - `version` (semver string)
   - `description` (string, non-empty)
   - `author.name` (string, non-empty)

2. `README.md` exists and documents all components:
   - Every agent in `agents/` is listed
   - Every skill in `skills/` is listed
   - Hook events from `hooks/hooks.json` (if exists) are listed

3. Eval layout per `eval-rules.md` (probe `plugin_eval_available` as in 2a.3 item 3):
   - Every skill has both `skills/<skill>/eval.md` and `evals/<skill>/` (cases or `NOTE.md`)
   - Every `NOTE.md` and `Not observable:` line uses only the closed reasons
   - Every `Cases:` pointer names an `evals/<skill>/` that exists
   - The repo's `.gitignore` covers `evals/results/`
   - `test -d <plugin>/evals` succeeds, then `grep -rnE '/Users/|/home/' <plugin>/evals --exclude-dir=results` exits 1 (no match); exit 2 is an error, not a pass
   - If `plugin_eval_available`: the load check (`--max-cost-usd 0`, whole plugin) passes — or prints `No eval cases found` when every skill is in spec form

4. All agent references in skills resolve to actual files:
   - Grep each skill for agent dispatch patterns
   - Verify referenced agent files exist

5. Dispatch `plugin-dev:plugin-validator` for structural validation

6. For each skill, run quick_validate:
   ```bash
   python -m scripts.quick_validate <skill directory>
   ```
   (From skill-creator scripts directory)

Present readiness checklist:
```
## Marketplace Readiness

| Check | Status | Details |
|-------|--------|---------|
| plugin.json | pass/fail | {missing fields if fail} |
| README.md | pass/fail | {missing entries if fail} |
| Eval layout | pass/fail | {skills missing a side, bad reasons, broken pointers, leaked paths, load errors} |
| Reference integrity | pass/fail | {broken refs if fail} |
| Structural validation | pass/fail | {issues if fail} |
| Skill validation | pass/fail | {issues per skill if fail} |
```

#### 2d.3: Single Component — Inject into Target

1. User specifies target project directory
2. Check for existing plugin structure in target:
   - Glob: `{target}/.claude-plugin/plugin.json`
3. If no plugin structure:
   - AskUserQuestion: "Target has no plugin structure. Scaffold one?" → if yes, invoke `Skill("plugin-dev:create-plugin")` in target
4. Copy component files to target:
   - Skill: copy entire `skills/{name}/` directory
   - Agent: copy agent `.md` file to `agents/`
   - Hook: merge hook entries into `hooks/hooks.json`
5. If skill: optionally create a `.skill` archive:
   ```bash
   python -m scripts.package_skill <skill directory> <output directory>
   ```
   (From skill-creator scripts directory)
6. Validate: Glob target directory to confirm files landed correctly

#### Completion (package)
- Full plugin: readiness checklist presented (all pass = ready)
- Single component: files copied, validated in target

---

### Step 2e: Insights Route

See `insights.md` for the full 8-step process (preflight → Reader → Proposer → validate → judge → AskUserQuestion → pr_composer → record state).

---

## Dependency Notes

This skill requires these optional plugins for full functionality:
- `plugin-dev` — for component creation and structural validation (Strategy A review)
- `skill-creator` — for description optimization and packaging scripts
- `claude plugin eval` — built into Claude Code ≥ 2.1.269, not a plugin; runs the eval cases (rules in `eval-rules.md`)

Without these:
- Create route: will guide user through manual creation instead of delegating
- Review route: falls back to Strategy B (self-contained review)
- Iterate route: description optimization unavailable; manual fixes only
- Package route: quick_validate and package_skill unavailable; manual checklist only
- Without `claude plugin eval`: cases and specs are still written and the layout is still checked; load checks and runs are reported as not run
