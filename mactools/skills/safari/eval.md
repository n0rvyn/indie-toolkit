# safari Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Show my Safari history from last week"
- "Search my browsing history for 'recipe'"
- "List my Safari bookmarks"
- "查看我的 Safari 浏览历史"
- "What's in my reading list?"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Open this website"
- "Send an email"
- "Fix this bug"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output uses safari.sh script from skills/safari/scripts/
- [ ] Output supports history, search, bookmarks, reading-list commands
- [ ] Output requires Full Disk Access for Safari data access
- [ ] Output queries Safari SQLite database directly (read-only)
- [ ] Output presents history with title, URL, visit date
- [ ] History command defaults to 7 days, 20 results
- [ ] Search command queries history by keyword in title/URL

## Redundancy Risk
Baseline comparison: Base model cannot access Safari browsing history or bookmarks; this skill provides SQLite database integration
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
