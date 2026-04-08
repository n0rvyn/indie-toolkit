---
name: master
description: |
  Use when the user says 'master', 'build a plugin', 'create a skill', 'create an agent',
  'review plugin', 'audit plugin', 'iterate skill', 'improve trigger', 'package plugin',
  or wants to create, review, iterate, or package Claude Code plugins and components.

  Single entry with 4 routes:
  - create: brainstorm → design → scaffold (plugin-dev) → eval baseline (skill-creator) → review → iterate
  - review: 9-dimension audit from AI executor perspective + cross-plugin trigger conflict detection
  - iterate: fix → re-eval (skill-creator) → compare baseline → verify
  - package: full plugin or single component into target project
---

# Plugin Lifecycle Management

统一入口，编排 Claude Code 插件和组件的完整生命周期：创建、评估、审查、迭代、打包。

委托 `plugin-dev` 处理组件创建，`skill-creator` 处理 eval 循环，自建 9 维审查框架和跨插件冲突检测。

## Process

### Step 1: Intent Detection

从用户消息判断路由：

| Route | Signal keywords |
|-------|----------------|
| create | "build", "create", "new plugin", "new skill", "new agent", "new hook", "brainstorm", "I want to make" |
| review | "review", "audit", "check quality", "review plugin", "review skill", "plugin review" |
| iterate | "improve", "fix trigger", "iterate", "refine", "trigger is too broad", "trigger is too narrow", "quality" |
| package | "package", "export", "inject", "distribute", "marketplace-ready", "deploy to project" |

**Routing logic:**
1. If keywords match a single route → proceed to that route
2. If user just says "master" with no other context → AskUserQuestion: "Which workflow?" with 4 options (create / review / iterate / package)
3. If ambiguous (keywords match multiple routes) → dispatch `skill-master:intent-distiller` agent with user's message → use its `recommendation` field to determine route
4. If still ambiguous after intent-distiller → AskUserQuestion with 4 route options

---

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

#### 2a.4: Delegate Creation

Route by `component_type`:

**Full plugin:**
- If `plugin_dev_available`: invoke `Skill("plugin-dev:create-plugin")` (8-phase guided workflow)
- If not: manually scaffold the plugin structure (create `.claude-plugin/plugin.json`, `skills/`, `agents/` directories, README.md) and write components directly

After creation completes → continue to 2a.5.

**Single skill:**
1. If `plugin_dev_available`: invoke `Skill("plugin-dev:skill-development")` for structure guidance and SKILL.md drafting. If not: write SKILL.md directly following plugin-dev conventions (name/description frontmatter, Process section, Completion Criteria)
2. If `skill_creator_available`: invoke `Skill("skill-creator:skill-creator")` for eval loop (eval creation, parallel runs, grading, viewer, iteration). If not: write eval.md manually with trigger tests and negative tests
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

#### 2a.5: Auto-Review Gate

Collect the file paths of newly created artifacts (from the delegated skill's output, or Glob the target directory for recently created/modified .md files).

Execute the review route (Step 2b) on these artifacts, using Scope A (specific files).

#### 2a.6: Quality Decision

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

This route is migrated from `skill-audit:plugin-review` with one addition (trigger-arbiter).

#### 2b.1: Determine Scope

From user message, determine what to review:

**Scope A — Specific files:** User gives file paths directly.

**Scope B — Plugin:** User names a plugin or directory. Collect:
- Glob `{plugin}/skills/*/SKILL.md` → all skills
- Glob `{plugin}/agents/*.md` → all agents

**Scope C — Recent changes:** User says "review my changes" or no explicit target.
- `git diff --name-only HEAD` for uncommitted changes
- If clean: `git log --name-only -1 --pretty=format:""` for last commit
- Filter to skill/agent files only

**Scope D — All:** User says "review all" or "audit everything".
- Collect all installed plugin skills and agents

Present the file list to user for confirmation before proceeding.

#### 2b.2: Gather Context

For each plugin in scope, collect:
1. Plugin manifest — `.claude-plugin/plugin.json`
2. All skill files — `skills/*/SKILL.md`
3. All agent files — `agents/*.md`
4. Marketplace entry — check `marketplace.json`
5. Eval files — `skills/{name}/eval.md` for each skill

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
   - Eval files: {comma-separated paths or "none"}

   Supporting files to load: none
   Plugin agents dir: {skill-master agents directory path}
   (D1/D2 structural checks and baseline trigger/description checks are handled by plugin-dev agents.)

   Focus on: workflow logic, execution feasibility, edge cases, dispatch loops, spec compliance, metadata & docs, eval.md consumption, deep trigger conflict detection, and Trigger Health Score.
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
- Eval files: {comma-separated paths or "none"}

Supporting files to load: structural-validation.md, trigger-baseline.md
Plugin agents dir: {skill-master agents directory path}

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
| Missing eval | No eval.md, or eval coverage gaps | Draft eval cases, run eval loop |
| Agent issue | Agent frontmatter errors, tool mismatch | Edit agent, re-validate |

#### 2c.3: Check Dependency Availability

If not already detected (e.g., when iterate is called standalone, not from create route):

1. **skill-creator:** Glob `~/.claude/plugins/**/skill-creator/**/skills/skill-creator/SKILL.md`. Found → `skill_creator_available = true`. Also locate its scripts directory: Glob `~/.claude/plugins/**/skill-creator/**/skills/skill-creator/scripts/` → store as `$SC_SCRIPTS`.

#### 2c.4: Execute Fix

**Trigger quality issues (description optimization):**

This is the most common iterate case.

If `skill_creator_available`: use automated optimization. If not: apply manual description changes based on review findings, then skip to 2c.5.

2. If the skill has `eval.md`, convert trigger/negative trigger tests to `skill-creator` eval-set format:
   ```json
   [
     {"prompt": "<trigger test>", "should_trigger": true},
     {"prompt": "<negative test>", "should_trigger": false}
   ]
   ```
   Write to a temporary `evals.json` beside the skill.

3. Run description optimization:
   ```bash
   python -m scripts.run_loop \
     --eval-set <evals.json path> \
     --skill-path <SKILL.md path> \
     --max-iterations 5
   ```
   (Run from `$SC_SCRIPTS` parent directory)

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

1. Draft new eval cases based on the skill's description
2. Invoke `Skill("skill-creator:skill-creator")` for the full eval loop
3. This creates baseline measurements for future comparison

#### 2c.5: Verify Improvement

After fix is applied:

1. If eval baseline exists from a previous iteration:
   - Re-run eval loop with `--previous-workspace` to compare
   - Present delta (pass rate change, timing change)

2. Re-run review route (Step 2b) with Scope C (recent changes only)

3. Present before/after comparison summary

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

3. Every skill directory has `eval.md`

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
| eval.md coverage | pass/fail | {skills without eval if fail} |
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

## Dependency Notes

This skill requires these optional plugins for full functionality:
- `plugin-dev` — for component creation and structural validation (Strategy A review)
- `skill-creator` — for eval loop, description optimization, and packaging scripts

Without these plugins:
- Create route: will guide user through manual creation instead of delegating
- Review route: falls back to Strategy B (self-contained review)
- Iterate route: description optimization unavailable; manual fixes only
- Package route: quick_validate and package_skill unavailable; manual checklist only
