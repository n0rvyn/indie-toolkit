# contacts Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Find John's phone number"
- "Search for contacts with email '@gmail.com'"
- "Show me all contacts in Work group"
- "查找张三的联系方式"
- "List all my contacts"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Send an email to John"
- "Create a calendar event"
- "Fix this bug"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output uses contacts.sh script from skills/contacts/scripts/
- [ ] Output supports search and show commands
- [ ] Output returns phone numbers, emails, addresses for contacts
- [ ] Output handles group filtering and result limits
- [ ] Search is fuzzy/partial match on contact names

## Redundancy Risk
Baseline comparison: Base model cannot access local macOS Contacts app data; this skill provides Contacts.app integration
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
