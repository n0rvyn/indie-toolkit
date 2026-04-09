# mactools Plugin

macOS automation toolkit for Apple apps and local workflows.

## Install

```bash
/plugin install mactools@indie-toolkit
```

## Skills

| Skill | Description |
|-------|-------------|
| `/notes` | Apple Notes: list, search, read, create, append, delete |
| `/calendar` | macOS Calendar: today, upcoming, search, create, delete events |
| `/reminders` | Apple Reminders: list, today, upcoming, overdue, search, create, complete, delete |
| `/mail` | Mail.app: inbox, unread, search, read, flag, move, trash |
| `/safari` | Safari: history, bookmarks, reading list (read-only) |
| `/spotlight` | Local file search with content extraction: Word, Excel, PDF, Markdown, and more |
| `/photos` | Apple Photos: search, albums, info, export |
| `/contacts` | macOS Contacts: search, show, list, groups |
| `/omnifocus` | OmniFocus 4: tasks, projects, contexts, perspectives, due dates, repetition |
| `/ocr` | Vision OCR: extract text from images, screenshots, scanned PDFs |

## Architecture

All skills are haiku fork skills that execute shell scripts or Swift/Python binaries via `Bash` tool. The scripts use native macOS frameworks (AppleScript, EventKit, Vision) and do not require additional dependencies beyond what's on a standard macOS system.

## File Structure

```
mactools/
├── skills/
│   ├── notes/          # Apple Notes via AppleScript
│   ├── calendar/       # Calendar via EventKit
│   ├── reminders/      # Reminders via EventKit
│   ├── mail/           # Mail via AppleScript
│   ├── safari/         # Safari history/bookmarks via sqlite3 + plistlib
│   ├── spotlight/      # File search via mdfind + text extraction
│   ├── photos/         # Photos via SQLite + export
│   ├── contacts/       # Contacts via AppleScript
│   ├── omnifocus/      # OmniFocus 4 via JXA/AppleScript
│   └── ocr/            # Vision OCR via Swift
├── agents/
│   └── spotlight-search.md  # Sub-agent for RAG fallback
└── README.md
```

## Spotlight File Support

| Format | Extraction Method |
|--------|-------------------|
| doc/docx/rtf/pages | textutil |
| xlsx | openpyxl |
| pptx | zipfile XML |
| pdf | pdftotext (or Vision OCR for scanned) |
| txt/md/csv/json/yaml/code | direct read |

## Common Workflows

### Daily Standup
```
/reminders today      # What needs to be done today?
/calendar today       # What's on the calendar?
```

### Clean Up Mail
```
/mail inbox "account"        # Review inbox
/mail read "account" INBOX N # Read specific email
/mail trash "account" INBOX N # Move to trash
```

### Find a File
```
/spotlight search "keyword"   # Search by content
/spotlight search -t pdf ...   # Limit to PDF
```

### Extract Text from Image
```
/ocr ~/Desktop/screenshot.png
```

## Prerequisites

- macOS required for all skills
- Calendar/Reminders: grant Calendar/Reminders privacy permissions
- Safari: grant Full Disk Access for history and bookmarks
- Photos: grant Full Disk Access for photo database
- Mail: Mail.app must be running for Mail skill
- OmniFocus: OmniFocus 4 must be installed and running
- OCR: Xcode Command Line Tools (for first-run compilation)
