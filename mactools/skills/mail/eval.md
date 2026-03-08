# mail Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Show my unread emails"
- "Search for emails from John"
- "Move this email to Trash"
- "查看我的收件箱"
- "Mark this email as read"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Send an email"
- "Check my calendar"
- "Fix this bug"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output uses mail.sh script from skills/mail/scripts/
- [ ] Output supports accounts, mailboxes, list, search, mark, move, commands
- [ ] Output requires Mail.app to be running
- [ ] Output handles mailbox filtering and search queries
- [ ] Output presents emails with sender, subject, date, mailbox info
- [ ] Move command moves to Trash (not permanent delete)

## Redundancy Risk
Baseline comparison: Base model cannot access local macOS Mail.app data; this skill provides AppleScript integration
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
