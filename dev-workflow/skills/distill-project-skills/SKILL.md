---
name: distill-project-skills
description: "Use when a project has accumulated cost in (no skill) main-session turns and you want to identify repeat patterns worth crystallizing as NEW skills, OR the user says 'distill skills', 'mine project patterns', '找重复模式', '看哪些值得做成 skill', 'distill-project-skills', '提炼项目 skill', '挖项目模式'. Scans recent session jsonl + cost-hint.log, surfaces candidate skill patterns with frequency, estimated wasted spend, and suggested cost-posture. User approves which to build. Side effect: archives .claude/cost-hint.log and empties primary log on real project runs. Not when: project is new — needs ≥7 days of session data. Not when: changing an existing skill — use skill-master instead. Not when: tuning existing skill descriptions from logged invocations — use skill-master:master insights (that one improves WHAT EXISTS from telemetry; this one identifies WHAT'S MISSING from no-skill main-session patterns)."
user-invocable: true
model: sonnet
context: fork
argument-hint: "[project-path] (default: cwd)"
allowed-tools: Bash(python3:*), Read, Write
---

# Distill Project Skills

Identifies recurring patterns in (no skill) main-session work and proposes them as skill candidates.

## Side effects

- On real project invocations (with `project_path`, no `--jsonl-dir` override, no `--no-archive`): after producing candidates, the primary `${CLAUDE_PROJECT_DIR:-.}/.claude/cost-hint.log` is appended to a monthly archive `cost-hint-archive-YYYY-MM.log` then emptied. This is intentional — the log feeds into this skill, then gets rotated.
- **When NOT to archive** (pass `--no-archive` to scan.py): debugging against an unowned project path, or any exploratory scan where you do not want the existing log rotated. Archiving is also skipped automatically when the log file does not exist or is empty (no-op rotation has zero risk).

## Process

### Step 1: Run scanner

```bash
PROJECT="${1:-$(pwd)}"
python3 ${CLAUDE_SKILL_DIR}/scripts/scan.py "$PROJECT" /tmp/distill-candidates.json
```

### Step 2: Present candidates inline

Read `/tmp/distill-candidates.json` and return a markdown table inline to the main session:

| Pattern | Freq | Est Wasted | Suggested Skill | Suggested Posture |
|---|---|---|---|---|

If candidates list is empty: return "No patterns above threshold yet — project may need ≥7 days of session data, or all recent work was already skill-attributed."

### Step 3: Hand back to main session

Return the table verbatim as this skill's output. The MAIN session (after this forked skill returns) prompts the user for selection — this forked context has no user channel.

Suggested follow-up phrasing for the main session to use when prompting the user:
> "Of the N candidates above, which would you like to crystallize into skills? Reply with pattern names. For each, I'll invoke `skill-master:master create <suggested-name>` with the pattern context."

## Completion criteria

- Candidates JSON written to `/tmp/distill-candidates.json`
- Candidates table returned to main session
- `.claude/cost-hint.log` archived and emptied (real project runs only)
