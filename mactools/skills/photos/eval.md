# photos Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Search my photos for 'beach'"
- "Show recent photos from last week"
- "List my photo albums"
- "查找我的照片"
- "Export this photo"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Edit this photo"
- "Take a screenshot"
- "Fix this image"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output uses photos.py script from skills/photos/scripts/
- [ ] Output supports search, recent, albums, export commands
- [ ] Output requires Full Disk Access for Photos library access
- [ ] Output queries Photos SQLite database directly (read-only)
- [ ] Output presents photos with filename, date, album info, path
- [ ] Recent command defaults to last 7 days, supports custom range
- [ ] Search matches on filename and titles

## Redundancy Risk
Baseline comparison: Base model cannot access macOS Photos library; this skill provides SQLite database query integration
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
