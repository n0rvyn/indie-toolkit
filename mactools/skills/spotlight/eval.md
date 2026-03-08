# spotlight Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Search my Mac for PDF files about design"
- "Find documents containing 'budget'"
- "Read this file's content"
- "搜索本地文件"
- "查找电脑上的 Excel 文件"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Search the web"
- "Create a new file"
- "Fix this bug"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output uses spotlight.sh and extract_text.py from skills/spotlight/scripts/
- [ ] Output supports mdfind-based search and text extraction
- [ ] Output extracts text from: doc/docx (textutil), xlsx (openpyxl), pptx (zipfile XML), pdf (pdftotext), txt/md/csv (direct read)
- [ ] Output presents search results with path, kind, date
- [ ] Text extraction has --max-chars limit (default 50000)
- [ ] Output supports content type filtering (documents, images, etc.)

## Redundancy Risk
Baseline comparison: Base model cannot search local macOS file system or extract content from Office/PDF formats; this skill provides Spotlight + multi-format text extraction
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
