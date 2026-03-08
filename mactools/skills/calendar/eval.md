# calendar Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "What's on my calendar today?"
- "Create a meeting for tomorrow at 3pm"
- "Search for events with 'team' in the title"
- "查看我今天的日程"
- "Add an event to my calendar"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Set a reminder"
- "Send an email"
- "Fix this bug"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output uses calendar.sh script from skills/calendar/scripts/
- [ ] Output supports today, upcoming, search, create, delete commands
- [ ] Output handles date ranges and result limits (-n flag)
- [ ] Output requires Calendar app authorization (System Settings > Privacy > Calendars)
- [ ] Output presents events with title, date, time, calendar info

## Redundancy Risk
Baseline comparison: Base model cannot access local macOS Calendar app data; this skill provides EventKit integration
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
