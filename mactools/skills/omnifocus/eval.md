# omnifocus Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "List my OmniFocus tasks"
- "What's in my OmniFocus inbox?"
- "Mark this task as complete"
- "查看我的 OmniFocus 待办"
- "Show flagged tasks"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Create a reminder"
- "Send an email"
- "Fix this bug"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output uses omnifocus_cli.py from skills/omnifocus/scripts/
- [ ] Output supports status, list, inbox, flagged, due, complete, create commands
- [ ] Output requires OmniFocus 4 to be installed and running
- [ ] Output presents tasks with project, context, due date, flagged status
- [ ] Status command shows overview (inbox count, flagged count, due count)
- [ ] Complete command marks tasks done without deleting

## Redundancy Risk
Baseline comparison: Base model cannot access OmniFocus 4 data; this skill provides OmniFocus CLI integration
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
