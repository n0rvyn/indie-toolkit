---
name: notion-with-api
description: This skill should be used when the user asks to "connect to Notion", "search Notion pages", "create Notion page", "read Notion database", "update Notion content", or mentions Notion workspace operations. Keywords: Notion, notes, database, workspace.
disable-model-invocation: false
allowed-tools: Bash(python3*)
---

# Notion Operations

Connect to Notion workspace and perform authorized operations: search, read, create, update pages and databases.

## Prerequisites

Before first use, complete the setup:

1. Visit https://www.notion.so/my-integrations
2. Create a new integration, copy the "Internal Integration Secret"
3. Save to the skill directory's `.env` file (install location depends on how the plugin was installed):
   ```
   NOTION_TOKEN=your_internal_integration_secret
   NOTION_WORKSPACE=Collector
   NOTION_VERSION=2022-06-28
   ```
   Default load paths (first match wins):
   - `$NOTION_ENV_PATH` if set
   - `${plugin_install_dir}/skills/notion-with-api/.env`
   - `~/.claude/skills/notion-with-api/.env` (legacy global-skill location; kept for back-compat)
4. In Notion, add the integration connection to pages/databases that need access:
   - Open the page/database in Notion
   - Click `...` → `Connect to` → Select your integration

## Available Commands

### Verify Token

```bash
python3 ~/.claude/skills/notion/scripts/notion_api.py verify
```

### Search Content

```bash
python3 ~/.claude/skills/notion/scripts/notion_api.py search "keyword"
```

### List All Databases

```bash
python3 ~/.claude/skills/notion/scripts/notion_api.py list-databases
```

### Get Database Schema

**IMPORTANT: Always run this first before creating database items to understand available properties and their types.**

```bash
python3 ~/.claude/skills/notion/scripts/notion_api.py get-db-schema DATABASE_ID
```

Example output:
```
Database: Document Hub
ID: 2f4fd878-f624-8057-a70e-deaaf68d71ae

Properties:
  - Doc name (title)
  - Category (multi_select)
      Options: Proposal, Customer research, Strategy doc, Planning
  - Created by (created_by)
      (auto-populated)
```

### Read Page

```bash
python3 ~/.claude/skills/notion/scripts/notion_api.py read-page PAGE_ID
```

### Update Page (Replace Content)

Deletes all existing blocks, then appends new blocks from markdown. Page title is preserved.

```bash
# From file
python3 ~/.claude/skills/notion/scripts/notion_api.py update-page PAGE_ID --file /path/to/content.md

# From string
python3 ~/.claude/skills/notion/scripts/notion_api.py update-page PAGE_ID --content "## New content"
```

Leading `# H1` lines are stripped (page title is separate from body content in Notion).

### Query Database

```bash
python3 ~/.claude/skills/notion/scripts/notion_api.py query-db DATABASE_ID
```

### Create Page (under a page)

Use this when the parent is a **page** (not a database):

```bash
python3 ~/.claude/skills/notion/scripts/notion_api.py create-page PARENT_PAGE_ID "Page Title" "Page content"
```

### Create Database Item

Use this when creating an item in a **database**:

```bash
# From string
python3 ~/.claude/skills/notion/scripts/notion_api.py create-db-item DATABASE_ID "Item Title" \
  --props '{"PropertyName": "value"}' \
  --content "Optional page content"

# From file (overrides --content)
python3 ~/.claude/skills/notion/scripts/notion_api.py create-db-item DATABASE_ID "Item Title" \
  --props '{"PropertyName": "value"}' \
  --file /path/to/content.md
```

#### Property Types and Value Formats

| Type | Example Value | Notes |
|------|---------------|-------|
| title | `"My Title"` | Auto-detected from schema |
| rich_text | `"Some text"` | Plain text string |
| number | `42` or `3.14` | Numeric value |
| select | `"Option Name"` | Single option name |
| multi_select | `"Opt1, Opt2"` | Comma-separated options |
| date | `"2026-01-26"` or `"today"` | ISO date or "today" |
| checkbox | `true` or `false` | Boolean value |
| url | `"https://..."` | Full URL |
| email | `"user@example.com"` | Email address |
| phone_number | `"+1234567890"` | Phone number string |

**Auto-populated properties** (created_by, created_time, last_edited_by, last_edited_time) are set by Notion automatically.

#### Examples

**Create document with category:**
```bash
python3 ~/.claude/skills/notion/scripts/notion_api.py create-db-item \
  2f4fd878-f624-8057-a70e-deaaf68d71ae \
  "Q1 Marketing Plan" \
  --props '{"Category": "Strategy doc"}' \
  --content "This document outlines our Q1 marketing strategy."
```

**Create todo item:**
```bash
python3 ~/.claude/skills/notion/scripts/notion_api.py create-db-item \
  2b0fd878-f624-8011-98c2-ed0babd6beb4 \
  "Review pull requests" \
  --props '{"Due Date": "2026-01-27", "Done": false}'
```

**Create item with multiple categories:**
```bash
python3 ~/.claude/skills/notion/scripts/notion_api.py create-db-item \
  DATABASE_ID \
  "Research Report" \
  --props '{"Category": "Customer research, Strategy doc"}'
```

## Known Databases

| Name | ID | Properties |
|------|----|----|
| Document Hub | `2f4fd878-f624-8057-a70e-deaaf68d71ae` | Doc name, Category (multi_select) |
| To Do List DB | `2b0fd878-f624-8011-98c2-ed0babd6beb4` | Name, Due Date (date), Done (checkbox) |

## Common Errors

| Code | Description | Solution |
|------|-------------|----------|
| 401 | Invalid token | Check NOTION_TOKEN in .env |
| 403 | No permission | Add integration connection in Notion |
| 404 | Resource not found | Verify ID is correct AND integration is connected |
| 400 | Validation error | Check property names/types with `get-db-schema` |

## Workflow

1. **First time**: Run `verify` to check token
2. **Find resources**: Run `search` or `list-databases`
3. **Before creating**: Run `get-db-schema DATABASE_ID` to see properties
4. **Create items**: Use `create-db-item` with correct property names

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/users/me` | GET | Get current user info |
| `/v1/search` | POST | Search pages and databases |
| `/v1/pages/{id}` | GET | Get page |
| `/v1/pages` | POST | Create page |
| `/v1/databases/{id}` | GET | Get database schema |
| `/v1/databases/{id}/query` | POST | Query database |

## Documentation

Notion API: https://developers.notion.com/reference/introduction
