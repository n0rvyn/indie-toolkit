# reminders Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "List my reminders"
- "Create a reminder for tomorrow"
- "Mark this reminder as complete"
- "查看我的提醒事项"
- "What's in my Work reminders list?"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Create a calendar event"
- "Send an email"
- "Fix this bug"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output uses reminders.sh script from skills/reminders/scripts/
- [ ] Output supports lists, list, show, create, complete, delete commands
- [ ] Output requires Reminders app authorization (System Settings > Privacy > Reminders)
- [ ] Output compiles Swift binary on first use
- [ ] Output presents reminders with list name, due date, priority, notes
- [ ] Lists command shows list names with incomplete reminder counts

## Redundancy Risk
Baseline comparison: Base model cannot access macOS Reminders.app data; this skill provides EventKit integration
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
