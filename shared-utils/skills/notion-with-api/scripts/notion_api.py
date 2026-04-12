#!/usr/bin/env python3
"""Notion API CLI tool for Claude Code skill.

Supports:
- Token verification
- Search pages and databases
- Read page content
- Query database
- Get database schema
- Create page (under page or database)
- Create database item with properties
"""

import argparse
import json
import os
import sys
import re
from datetime import datetime

import requests
from dotenv import load_dotenv

# Load environment
# Resolution order:
#   1. $NOTION_ENV_PATH if set (explicit override)
#   2. ../.env relative to this script (plugin install: shared-utils/skills/notion-with-api/.env)
#   3. ~/.claude/skills/notion-with-api/.env (legacy global-skill location, back-compat)
SKILL_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
_env_candidates = []
if os.environ.get("NOTION_ENV_PATH"):
    _env_candidates.append(os.environ["NOTION_ENV_PATH"])
_env_candidates.append(os.path.join(SKILL_DIR, ".env"))
_env_candidates.append(os.path.expanduser("~/.claude/skills/notion-with-api/.env"))

for _candidate in _env_candidates:
    if os.path.exists(_candidate):
        load_dotenv(_candidate)
        break

TOKEN = os.getenv("NOTION_TOKEN")
VERSION = os.getenv("NOTION_VERSION", "2022-06-28")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Notion-Version": VERSION,
    "Content-Type": "application/json",
}

BASE_URL = "https://api.notion.com"


# Notion code block language mapping
CODE_LANG_MAP = {
    "python": "py",
    "javascript": "javascript",
    "js": "javascript",
    "typescript": "typescript",
    "ts": "typescript",
    "java": "java",
    "c": "c",
    "cpp": "c++",
    "c++": "c++",
    "c#": "c#",
    "go": "go",
    "rust": "rust",
    "swift": "swift",
    "kotlin": "kotlin",
    "scala": "scala",
    "ruby": "ruby",
    "php": "php",
    "bash": "shell",
    "sh": "shell",
    "shell": "shell",
    "zsh": "shell",
    "powershell": "powershell",
    "sql": "sql",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "xml": "xml",
    "html": "html",
    "css": "css",
    "scss": "scss",
    "less": "less",
    "markdown": "markdown",
    "md": "markdown",
    "latex": "latex",
    "tex": "latex",
    "r": "r",
}


def parse_inline_formatting(text: str) -> list:
    """Parse inline markdown formatting into Notion rich_text array.

    Supports: **bold**, *italic*, `code`, [link](url), ***bold italic***

    Args:
        text: Markdown text with inline formatting

    Returns:
        list: Notion rich_text objects
    """
    if not text:
        return []

    rich_text = []
    # Pattern matches: ***bold italic***, **bold**, *italic*, `code`, [text](url)
    pattern = re.compile(
        r'(\*\*\*(.+?)\*\*\*)'     # ***bold italic***
        r'|(\*\*(.+?)\*\*)'         # **bold**
        r'|(\*(.+?)\*)'             # *italic*
        r'|(`(.+?)`)'               # `code`
        r'|(\[(.+?)\]\((.+?)\))'    # [text](url)
    )

    last_end = 0
    for m in pattern.finditer(text):
        # Add plain text before this match
        if m.start() > last_end:
            plain = text[last_end:m.start()]
            if plain:
                rich_text.append({"type": "text", "text": {"content": plain}})

        if m.group(2):  # ***bold italic***
            rich_text.append({
                "type": "text",
                "text": {"content": m.group(2)},
                "annotations": {"bold": True, "italic": True}
            })
        elif m.group(4):  # **bold**
            rich_text.append({
                "type": "text",
                "text": {"content": m.group(4)},
                "annotations": {"bold": True}
            })
        elif m.group(6):  # *italic*
            rich_text.append({
                "type": "text",
                "text": {"content": m.group(6)},
                "annotations": {"italic": True}
            })
        elif m.group(8):  # `code`
            rich_text.append({
                "type": "text",
                "text": {"content": m.group(8)},
                "annotations": {"code": True}
            })
        elif m.group(10):  # [text](url)
            rich_text.append({
                "type": "text",
                "text": {"content": m.group(10), "link": {"url": m.group(11)}}
            })

        last_end = m.end()

    # Add remaining plain text
    if last_end < len(text):
        remaining = text[last_end:]
        if remaining:
            rich_text.append({"type": "text", "text": {"content": remaining}})

    # If no formatting found, return plain text
    if not rich_text:
        rich_text = [{"type": "text", "text": {"content": text}}]

    return rich_text


def parse_table_row(line: str) -> list:
    """Parse a markdown table row into cell strings.

    Args:
        line: A markdown table row like "| a | b | c |"

    Returns:
        list: Cell content strings
    """
    # Strip leading/trailing pipes and split
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def is_table_separator(line: str) -> bool:
    """Check if a line is a markdown table separator (|---|---|)."""
    stripped = line.strip()
    if not stripped.startswith("|"):
        return False
    # Remove pipes and check if remaining is only dashes, colons, spaces
    content = stripped.replace("|", "").replace("-", "").replace(":", "").replace(" ", "")
    return len(content) == 0 and "-" in stripped


def markdown_to_notion_blocks(markdown: str) -> list:
    """Convert markdown text to Notion block structure.

    Supports:
    - Headings: #, ##, ###
    - Lists: - (bullet), 1. (numbered)
    - Code blocks: ```lang```
    - Blockquotes: >
    - Horizontal rules: ---
    - Tables: | col1 | col2 |
    - Inline formatting: **bold**, *italic*, `code`, [link](url)
    - Paragraphs (plain text)

    Args:
        markdown: The markdown string

    Returns:
        list: Notion block objects
    """
    if not markdown:
        return []

    blocks = []
    lines = markdown.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]

        # Empty line (skip)
        if not line.strip():
            i += 1
            continue

        # Code block ```lang
        if line.strip().startswith("```"):
            lang = line.strip()[3:].strip().lower() or "plain text"
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            code_content = "\n".join(code_lines)
            blocks.append({
                "object": "block",
                "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": code_content}}],
                    "language": lang
                }
            })
            i += 1
            continue

        # Table detection: line starts with | and next line is separator
        if line.strip().startswith("|") and i + 1 < len(lines) and is_table_separator(lines[i + 1]):
            header_cells = parse_table_row(line)
            table_width = len(header_cells)
            i += 2  # skip header and separator

            # Build table rows (header first)
            table_rows = []
            # Header row
            table_rows.append({
                "type": "table_row",
                "table_row": {
                    "cells": [[{"type": "text", "text": {"content": cell}}] if cell else [{"type": "text", "text": {"content": ""}}] for cell in header_cells]
                }
            })

            # Data rows
            while i < len(lines) and lines[i].strip().startswith("|"):
                if is_table_separator(lines[i]):
                    i += 1
                    continue
                row_cells = parse_table_row(lines[i])
                # Pad or trim to match table_width
                while len(row_cells) < table_width:
                    row_cells.append("")
                row_cells = row_cells[:table_width]

                table_rows.append({
                    "type": "table_row",
                    "table_row": {
                        "cells": [parse_inline_formatting(cell) if cell else [{"type": "text", "text": {"content": ""}}] for cell in row_cells]
                    }
                })
                i += 1

            blocks.append({
                "object": "block",
                "type": "table",
                "table": {
                    "table_width": table_width,
                    "has_column_header": True,
                    "has_row_header": False,
                    "children": table_rows
                }
            })
            continue

        # Heading 1
        if line.strip().startswith("# ") and not line.strip().startswith("##"):
            text = line.strip()[2:].strip()
            blocks.append({
                "object": "block",
                "type": "heading_1",
                "heading_1": {
                    "rich_text": parse_inline_formatting(text)
                }
            })
            i += 1
            continue

        # Heading 2
        if line.strip().startswith("## ") and not line.strip().startswith("###"):
            text = line.strip()[3:].strip()
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": parse_inline_formatting(text)
                }
            })
            i += 1
            continue

        # Heading 3
        if line.strip().startswith("### "):
            text = line.strip()[4:].strip()
            blocks.append({
                "object": "block",
                "type": "heading_3",
                "heading_3": {
                    "rich_text": parse_inline_formatting(text)
                }
            })
            i += 1
            continue

        # Blockquote
        if line.strip().startswith("> "):
            text = line.strip()[2:].strip()
            blocks.append({
                "object": "block",
                "type": "quote",
                "quote": {
                    "rich_text": parse_inline_formatting(text)
                }
            })
            i += 1
            continue

        # Horizontal rule
        if line.strip() in ["---", "***", "___"]:
            blocks.append({
                "object": "block",
                "type": "divider",
                "divider": {}
            })
            i += 1
            continue

        # Numbered list (1.)
        numbered_match = re.match(r'^\s*(\d+)\.\s+(.+)', line)
        if numbered_match:
            text = numbered_match.group(2)
            blocks.append({
                "object": "block",
                "type": "numbered_list_item",
                "numbered_list_item": {
                    "rich_text": parse_inline_formatting(text)
                }
            })
            i += 1
            continue

        # Bullet list (-)
        bullet_match = re.match(r'^\s*[-*+]\s+(.+)', line)
        if bullet_match:
            text = bullet_match.group(1)
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": parse_inline_formatting(text)
                }
            })
            i += 1
            continue

        # Paragraph (collect consecutive non-empty lines)
        para_lines = []
        while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith(("# ", "## ", "### ", "```", "> ", "---", "***", "___")):
            # Stop at table rows
            if lines[i].strip().startswith("|"):
                break
            if lines[i].strip().startswith(("- ", "* ", "+ ")) and not lines[i].startswith("    "):
                break
            if re.match(r'^\s*\d+\.\s+', lines[i]):
                break
            para_lines.append(lines[i])
            i += 1
        if para_lines:
            para_text = "\n".join(para_lines).strip()
            blocks.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {
                    "rich_text": parse_inline_formatting(para_text)
                }
            })
        else:
            i += 1

    return blocks


def verify():
    """Verify token validity."""
    resp = requests.get(f"{BASE_URL}/v1/users/me", headers=HEADERS)
    if resp.status_code == 200:
        data = resp.json()
        print(f"Token valid. User: {data.get('name', 'Unknown')}")
        print(f"Type: {data.get('type', 'Unknown')}")
        return True
    else:
        print(f"Token invalid: {resp.status_code}")
        print(resp.text)
        return False


def search(query: str):
    """Search pages and databases."""
    resp = requests.post(
        f"{BASE_URL}/v1/search",
        headers=HEADERS,
        json={"query": query},
    )
    if resp.status_code != 200:
        print(f"Error: {resp.status_code}")
        print(resp.text)
        return

    results = resp.json().get("results", [])
    print(f"Found {len(results)} results:")
    for item in results:
        obj_type = item.get("object", "unknown")
        item_id = item.get("id", "")

        # Extract title
        title = ""
        if obj_type == "page":
            props = item.get("properties", {})
            # Try common title property names
            for prop_name in ["title", "Title", "Name", "name", "Doc name"]:
                title_prop = props.get(prop_name, {})
                if isinstance(title_prop, dict) and title_prop.get("type") == "title":
                    title_list = title_prop.get("title", [])
                    if title_list:
                        title = title_list[0].get("plain_text", "")
                        break
        elif obj_type == "database":
            title_list = item.get("title", [])
            if title_list:
                title = title_list[0].get("plain_text", "")

        print(f"  [{obj_type}] {item_id}: {title or '(no title)'}")


def read_page(page_id: str):
    """Read page content."""
    # Get page metadata
    resp = requests.get(f"{BASE_URL}/v1/pages/{page_id}", headers=HEADERS)
    if resp.status_code != 200:
        print(f"Error getting page: {resp.status_code}")
        print(resp.text)
        return

    page = resp.json()
    props = page.get("properties", {})

    # Extract title
    title = ""
    for prop_name, prop_val in props.items():
        if prop_val.get("type") == "title":
            title_list = prop_val.get("title", [])
            if title_list:
                title = title_list[0].get("plain_text", "")
            break

    print(f"Page: {title or '(no title)'}")
    print(f"ID: {page_id}")
    print(f"URL: {page.get('url', 'N/A')}")
    print()

    # Get blocks (content)
    resp = requests.get(f"{BASE_URL}/v1/blocks/{page_id}/children", headers=HEADERS)
    if resp.status_code != 200:
        print(f"Error getting blocks: {resp.status_code}")
        return

    blocks = resp.json().get("results", [])
    print("Content:")
    for block in blocks:
        block_type = block.get("type", "unknown")
        content = block.get(block_type, {})

        # Extract text from rich_text
        if "rich_text" in content:
            text_parts = [rt.get("plain_text", "") for rt in content.get("rich_text", [])]
            text = "".join(text_parts)
            print(f"  [{block_type}] {text}")
        elif "text" in content:
            text_parts = [rt.get("plain_text", "") for rt in content.get("text", [])]
            text = "".join(text_parts)
            print(f"  [{block_type}] {text}")
        else:
            print(f"  [{block_type}] (non-text block)")


def query_db(database_id: str, filter_json: str = None, sort_json: str = None, page_size: int = 100):
    """Query database with optional filter, sort, and pagination.

    Args:
        database_id: The database ID
        filter_json: JSON string of Notion filter object
        sort_json: JSON string of Notion sort array
        page_size: Number of results per page (default 100, max 100)
    """
    payload = {"page_size": min(page_size, 100)}

    if filter_json:
        try:
            payload["filter"] = json.loads(filter_json)
        except json.JSONDecodeError as e:
            print(f"Error parsing filter JSON: {e}")
            return

    if sort_json:
        try:
            payload["sorts"] = json.loads(sort_json)
        except json.JSONDecodeError as e:
            print(f"Error parsing sort JSON: {e}")
            return

    all_results = []
    url = f"{BASE_URL}/v1/databases/{database_id}/query"

    while True:
        try:
            resp = requests.post(url, headers=HEADERS, json=payload)
        except requests.RequestException as e:
            print(f"Request error: {e}")
            return
        if resp.status_code != 200:
            print(f"Error: {resp.status_code}")
            try:
                print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
            except (json.JSONDecodeError, ValueError):
                print(resp.text)
            return

        data = resp.json()
        results = data.get("results", [])
        all_results.extend(results)

        if data.get("has_more") and data.get("next_cursor"):
            payload["start_cursor"] = data["next_cursor"]
        else:
            break

    print(f"Found {len(all_results)} items:")

    for item in all_results:
        item_id = item.get("id", "")
        props = item.get("properties", {})

        title = ""
        for prop_name, prop_val in props.items():
            if prop_val.get("type") == "title":
                title_list = prop_val.get("title", [])
                if title_list:
                    title = title_list[0].get("plain_text", "")
                break

        print(f"  {item_id}: {title or '(no title)'}")


def get_db_schema(database_id: str, output_format: str = "human"):
    """Get database schema with property types and options.

    Args:
        database_id: The database ID
        output_format: 'human' for readable output, 'json' for raw JSON
    """
    resp = requests.get(f"{BASE_URL}/v1/databases/{database_id}", headers=HEADERS)
    if resp.status_code != 200:
        print(f"Error: {resp.status_code}")
        print(resp.text)
        return None

    data = resp.json()

    if output_format == "json":
        print(json.dumps(data, indent=2, ensure_ascii=False))
        return data

    # Human-readable output
    title_list = data.get("title", [])
    db_title = title_list[0].get("plain_text", "") if title_list else "(no title)"

    print(f"Database: {db_title}")
    print(f"ID: {database_id}")
    print(f"URL: {data.get('url', 'N/A')}")
    print()
    print("Properties:")

    properties = data.get("properties", {})
    for prop_name, prop_info in properties.items():
        prop_type = prop_info.get("type", "unknown")
        print(f"  - {prop_name} ({prop_type})")

        # Show options for select/multi_select
        if prop_type == "select":
            options = prop_info.get("select", {}).get("options", [])
            if options:
                opt_names = [opt.get("name", "") for opt in options]
                print(f"      Options: {', '.join(opt_names)}")
        elif prop_type == "multi_select":
            options = prop_info.get("multi_select", {}).get("options", [])
            if options:
                opt_names = [opt.get("name", "") for opt in options]
                print(f"      Options: {', '.join(opt_names)}")
        elif prop_type in ["created_by", "created_time", "last_edited_by", "last_edited_time"]:
            print(f"      (auto-populated)")

    return data


def create_page(parent_id: str, title: str, content: str = ""):
    """Create a new page under a page (not database).

    For creating items in a database, use create_db_item instead.
    """
    # Build children blocks from markdown
    children = markdown_to_notion_blocks(content) if content else []

    payload = {
        "parent": {"page_id": parent_id},
        "properties": {
            "title": {"title": [{"text": {"content": title}}]}}
    }
    if children:
        payload["children"] = children

    resp = requests.post(f"{BASE_URL}/v1/pages", headers=HEADERS, json=payload)
    if resp.status_code == 200:
        page = resp.json()
        print(f"Page created successfully!")
        print(f"ID: {page.get('id')}")
        print(f"URL: {page.get('url')}")
    else:
        print(f"Error: {resp.status_code}")
        error_data = resp.json()
        print(json.dumps(error_data, indent=2, ensure_ascii=False))

        # Helpful hints
        if resp.status_code == 404:
            print("\nHint: Make sure the integration is connected to the parent page in Notion.")
        elif "validation_error" in str(error_data):
            print("\nHint: If parent is a database, use 'create-db-item' command instead.")


def build_property_value(prop_type: str, value, prop_info: dict = None):
    """Build property value based on type.

    Args:
        prop_type: Property type (title, rich_text, number, select, multi_select, date, checkbox, url, email, phone_number)
        value: The value to set
        prop_info: Optional property info for validation

    Returns:
        dict: Notion API property value format
    """
    if prop_type == "title":
        return {"title": [{"text": {"content": str(value)}}]}

    elif prop_type == "rich_text":
        return {"rich_text": [{"text": {"content": str(value)}}]}

    elif prop_type == "number":
        return {"number": float(value) if value else None}

    elif prop_type == "select":
        return {"select": {"name": str(value)} if value else None}

    elif prop_type == "multi_select":
        # Accept comma-separated string or list
        if isinstance(value, str):
            names = [v.strip() for v in value.split(",") if v.strip()]
        else:
            names = value
        return {"multi_select": [{"name": name} for name in names]}

    elif prop_type == "date":
        # Accept ISO date string or "today"
        if value == "today":
            value = datetime.now().strftime("%Y-%m-%d")
        return {"date": {"start": str(value)} if value else None}

    elif prop_type == "checkbox":
        # Accept bool, "true"/"false", 1/0
        if isinstance(value, bool):
            bool_val = value
        elif isinstance(value, str):
            bool_val = value.lower() in ("true", "yes", "1")
        else:
            bool_val = bool(value)
        return {"checkbox": bool_val}

    elif prop_type == "url":
        return {"url": str(value) if value else None}

    elif prop_type == "email":
        return {"email": str(value) if value else None}

    elif prop_type == "phone_number":
        return {"phone_number": str(value) if value else None}

    else:
        # Unsupported or auto-populated types
        return None


def create_database(parent_page_id: str, title: str, schema_json: str):
    """Create a new database under a parent page.

    Args:
        parent_page_id: The parent page ID
        title: Database title
        schema_json: JSON string defining the database schema (properties).
            Each key is the property name, value is property config.
            Example: '{"Status": {"select": {"options": [{"name": "inbox"}, {"name": "done"}]}}, "URL": {"url": {}}}'
    """
    try:
        schema = json.loads(schema_json)
    except json.JSONDecodeError as e:
        print(f"Error parsing schema JSON: {e}")
        return

    # Title property is required; add if not in schema
    has_title = any(
        isinstance(v, dict) and v.get("title") is not None
        for v in schema.values()
    )
    if not has_title:
        schema["Title"] = {"title": {}}

    payload = {
        "parent": {"type": "page_id", "page_id": parent_page_id},
        "title": [{"type": "text", "text": {"content": title}}],
        "properties": schema,
    }

    resp = requests.post(f"{BASE_URL}/v1/databases", headers=HEADERS, json=payload)

    if resp.status_code == 200:
        db = resp.json()
        print(f"Database created successfully!")
        print(f"ID: {db.get('id')}")
        print(f"URL: {db.get('url', 'N/A')}")
        print(f"Properties: {', '.join(db.get('properties', {}).keys())}")
    else:
        print(f"Error: {resp.status_code}")
        try:
            print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
        except (json.JSONDecodeError, ValueError):
            print(resp.text)


def create_db_item(database_id: str, title: str, properties_json: str = None, content: str = None):
    """Create a new item in a database.

    Args:
        database_id: The database ID
        title: The title/name of the item
        properties_json: JSON string of additional properties, e.g. '{"Category": "Proposal", "Done": true}'
        content: Optional page content (text)
    """
    # First, get the database schema to know property types
    resp = requests.get(f"{BASE_URL}/v1/databases/{database_id}", headers=HEADERS)
    if resp.status_code != 200:
        print(f"Error getting database schema: {resp.status_code}")
        print(resp.text)
        return

    db_schema = resp.json()
    db_properties = db_schema.get("properties", {})

    # Find the title property name
    title_prop_name = None
    for prop_name, prop_info in db_properties.items():
        if prop_info.get("type") == "title":
            title_prop_name = prop_name
            break

    if not title_prop_name:
        print("Error: Could not find title property in database schema")
        return

    # Build properties
    properties = {
        title_prop_name: build_property_value("title", title)
    }

    # Parse and add additional properties
    if properties_json:
        try:
            extra_props = json.loads(properties_json)
        except json.JSONDecodeError as e:
            print(f"Error parsing properties JSON: {e}")
            print("Expected format: '{\"Category\": \"Proposal\", \"Done\": true}'")
            return

        for prop_name, prop_value in extra_props.items():
            if prop_name not in db_properties:
                print(f"Warning: Property '{prop_name}' not found in database schema, skipping")
                continue

            prop_info = db_properties[prop_name]
            prop_type = prop_info.get("type")

            # Skip auto-populated properties
            if prop_type in ["created_by", "created_time", "last_edited_by", "last_edited_time", "formula", "rollup"]:
                print(f"Warning: Property '{prop_name}' is auto-populated, skipping")
                continue

            built_value = build_property_value(prop_type, prop_value, prop_info)
            if built_value:
                properties[prop_name] = built_value
            else:
                print(f"Warning: Unsupported property type '{prop_type}' for '{prop_name}', skipping")

    # Build children blocks from markdown
    children = markdown_to_notion_blocks(content) if content else []

    # Create the page
    payload = {
        "parent": {"database_id": database_id},
        "properties": properties,
    }
    if children:
        payload["children"] = children

    resp = requests.post(f"{BASE_URL}/v1/pages", headers=HEADERS, json=payload)
    if resp.status_code == 200:
        page = resp.json()
        print(f"Database item created successfully!")
        print(f"ID: {page.get('id')}")
        print(f"URL: {page.get('url')}")
    else:
        print(f"Error: {resp.status_code}")
        error_data = resp.json()
        print(json.dumps(error_data, indent=2, ensure_ascii=False))

        # Helpful hints
        if resp.status_code == 404:
            print("\nHint: Make sure the integration is connected to the database in Notion.")
        elif resp.status_code == 400:
            print("\nHint: Check property names and values. Use 'get-db-schema' to see available properties.")


def update_page(page_id: str, content: str = "", content_file: str = ""):
    """Update a page by replacing all content.

    Deletes all existing blocks, then appends new blocks from markdown.

    Args:
        page_id: The page ID to update
        content: Markdown content string
        content_file: Path to a markdown file (used if content is empty)
    """
    # Read content from file if provided
    if not content and content_file:
        with open(content_file, "r") as f:
            content = f.read()

    if not content:
        print("Error: No content provided. Use --content or --file.")
        return

    # Strip leading H1 (page title is separate from body)
    lines = content.split("\n")
    if lines and lines[0].startswith("# "):
        content = "\n".join(lines[1:])

    # Step 1: Get existing blocks
    resp = requests.get(f"{BASE_URL}/v1/blocks/{page_id}/children?page_size=100", headers=HEADERS)
    if resp.status_code != 200:
        print(f"Error getting blocks: {resp.status_code}")
        print(resp.text)
        return

    old_blocks = resp.json().get("results", [])
    print(f"Deleting {len(old_blocks)} existing blocks...")

    # Step 2: Delete all existing blocks
    for block in old_blocks:
        bid = block["id"]
        r = requests.delete(f"{BASE_URL}/v1/blocks/{bid}", headers=HEADERS)
        if r.status_code != 200:
            print(f"  Warning: failed to delete block {bid}: {r.status_code}")

    # Step 3: Convert markdown to blocks
    new_blocks = markdown_to_notion_blocks(content)
    print(f"Appending {len(new_blocks)} new blocks...")

    # Step 4: Append in batches of 100
    total = 0
    for i in range(0, len(new_blocks), 100):
        batch = new_blocks[i:i + 100]
        resp = requests.patch(
            f"{BASE_URL}/v1/blocks/{page_id}/children",
            headers=HEADERS,
            json={"children": batch}
        )
        if resp.status_code != 200:
            print(f"Error appending blocks (batch {i // 100}): {resp.status_code}")
            print(resp.text[:300])
            return
        total += len(batch)

    # Step 5: Report
    resp = requests.get(f"{BASE_URL}/v1/pages/{page_id}", headers=HEADERS)
    if resp.status_code == 200:
        page = resp.json()
        print(f"Page updated successfully!")
        print(f"Blocks: {total}")
        print(f"URL: {page.get('url', 'N/A')}")
        pub = page.get("public_url")
        if pub:
            print(f"Public URL: {pub}")
    else:
        print(f"Updated {total} blocks (could not fetch page info)")


def update_page_properties(page_id: str, properties_json: str):
    """Update page properties via PATCH /v1/pages/{id}.

    Args:
        page_id: The page ID to update
        properties_json: JSON string of properties to update,
            e.g. '{"Status": "done", "Priority": "high"}'
    """
    resp = requests.get(f"{BASE_URL}/v1/pages/{page_id}", headers=HEADERS)
    if resp.status_code != 200:
        print(f"Error getting page: {resp.status_code}")
        try:
            print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
        except (json.JSONDecodeError, ValueError):
            print(resp.text)
        return

    page = resp.json()
    parent = page.get("parent", {})
    parent_type = parent.get("type", "")

    database_id = None
    if parent_type == "database_id":
        database_id = parent.get("database_id")

    try:
        properties_dict = json.loads(properties_json)
    except json.JSONDecodeError as e:
        print(f"Error parsing properties JSON: {e}")
        print('Expected format: \'{"Status": "done", "Priority": "high"}\'')
        return

    built_properties = {}
    db_properties = {}

    if database_id:
        resp = requests.get(f"{BASE_URL}/v1/databases/{database_id}", headers=HEADERS)
        if resp.status_code == 200:
            db_properties = resp.json().get("properties", {})
        else:
            print(f"Warning: Could not fetch database schema: {resp.status_code}")

    for prop_name, prop_value in properties_dict.items():
        if prop_name.lower() in ["title", "name"]:
            print(f"Warning: Title property cannot be updated directly, skipping '{prop_name}'")
            continue

        prop_type = None
        if db_properties and prop_name in db_properties:
            prop_info = db_properties[prop_name]
            prop_type = prop_info.get("type")

            if prop_type in ["created_by", "created_time", "last_edited_by", "last_edited_time", "formula", "rollup"]:
                print(f"Warning: Property '{prop_name}' is auto-populated, skipping")
                continue
        elif db_properties:
            print(f"Warning: Property '{prop_name}' not found in database schema")

        if not prop_type:
            if isinstance(prop_value, bool):
                prop_type = "checkbox"
            elif isinstance(prop_value, (int, float)):
                prop_type = "number"
            else:
                prop_type = "rich_text"

        built_value = build_property_value(prop_type, prop_value)
        if built_value:
            built_properties[prop_name] = built_value
        else:
            print(f"Warning: Could not build value for property '{prop_name}' (type: {prop_type}), skipping")

    if not built_properties:
        print("Error: No valid properties to update")
        return

    payload = {"properties": built_properties}
    resp = requests.patch(f"{BASE_URL}/v1/pages/{page_id}", headers=HEADERS, json=payload)

    if resp.status_code == 200:
        updated_page = resp.json()
        print("Page properties updated successfully!")
        print(f"ID: {updated_page.get('id')}")
        print(f"URL: {updated_page.get('url', 'N/A')}")
        print("\nUpdated properties:")
        for prop_name in built_properties.keys():
            print(f"  - {prop_name}")
    else:
        print(f"Error: {resp.status_code}")
        try:
            error_data = resp.json()
            print(json.dumps(error_data, indent=2, ensure_ascii=False))
        except (json.JSONDecodeError, ValueError):
            print(resp.text)
        if resp.status_code == 400:
            print("\nHint: Check property names and values. Use 'get-db-schema' to see available properties.")


def list_children(page_id: str, output_format: str = "human"):
    """List child pages of a given page.

    Uses the blocks API to find child_page blocks, then fetches each page's title.

    Args:
        page_id: Parent page ID
        output_format: 'human' for readable output, 'json' for machine-readable
    """
    # Get all blocks (paginated)
    all_blocks = []
    url = f"{BASE_URL}/v1/blocks/{page_id}/children?page_size=100"
    while url:
        resp = requests.get(url, headers=HEADERS)
        if resp.status_code != 200:
            print(f"Error: {resp.status_code}")
            print(resp.text)
            return
        data = resp.json()
        all_blocks.extend(data.get("results", []))
        url = f"{BASE_URL}/v1/blocks/{page_id}/children?page_size=100&start_cursor={data['next_cursor']}" if data.get("has_more") else None

    # Filter child_page blocks
    child_pages = [b for b in all_blocks if b.get("type") == "child_page"]

    if output_format == "json":
        result = []
        for block in child_pages:
            title = block.get("child_page", {}).get("title", "")
            result.append({"id": block["id"], "title": title})
        print(json.dumps(result, ensure_ascii=False))
        return

    # Human-readable
    print(f"Found {len(child_pages)} child pages:")
    for block in child_pages:
        title = block.get("child_page", {}).get("title", "")
        # Also fetch public_url
        page_resp = requests.get(f"{BASE_URL}/v1/pages/{block['id']}", headers=HEADERS)
        public_url = ""
        if page_resp.status_code == 200:
            public_url = page_resp.json().get("public_url", "") or ""
        print(f"  {block['id']}: {title}")
        if public_url:
            print(f"    Public: {public_url}")


def list_databases():
    """List all accessible databases."""
    resp = requests.post(
        f"{BASE_URL}/v1/search",
        headers=HEADERS,
        json={"filter": {"property": "object", "value": "database"}},
    )
    if resp.status_code != 200:
        print(f"Error: {resp.status_code}")
        print(resp.text)
        return

    results = resp.json().get("results", [])
    print(f"Found {len(results)} databases:")
    for db in results:
        db_id = db.get("id", "")
        title_list = db.get("title", [])
        title = title_list[0].get("plain_text", "") if title_list else "(no title)"
        print(f"  {db_id}: {title}")


def main():
    parser = argparse.ArgumentParser(description="Notion API CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # verify
    subparsers.add_parser("verify", help="Verify token")

    # search
    p_search = subparsers.add_parser("search", help="Search content")
    p_search.add_argument("query", help="Search query")

    # read-page
    p_read = subparsers.add_parser("read-page", help="Read page content")
    p_read.add_argument("page_id", help="Page ID")

    # query-db
    p_query = subparsers.add_parser("query-db", help="Query database")
    p_query.add_argument("database_id", help="Database ID")
    p_query.add_argument("--filter", "-F", help='Filter JSON, e.g. \'{"property": "Status", "select": {"equals": "done"}}\'')
    p_query.add_argument("--sort", "-S", help='Sort JSON, e.g. \'[{"property": "Created", "direction": "descending"}]\'')
    p_query.add_argument("--page-size", type=int, default=100, help="Results per page (default 100, max 100)")

    # get-db-schema
    p_schema = subparsers.add_parser("get-db-schema", help="Get database schema")
    p_schema.add_argument("database_id", help="Database ID")
    p_schema.add_argument("--json", action="store_true", help="Output raw JSON")

    # list-children
    p_children = subparsers.add_parser("list-children", help="List child pages of a page")
    p_children.add_argument("page_id", help="Parent page ID")
    p_children.add_argument("--json", action="store_true", help="Output JSON for machine parsing")

    # list-databases
    subparsers.add_parser("list-databases", help="List all accessible databases")

    # update-page
    p_update = subparsers.add_parser("update-page", help="Replace all page content")
    p_update.add_argument("page_id", help="Page ID")
    p_update.add_argument("--content", "-c", default="", help="Markdown content string")
    p_update.add_argument("--file", "-f", dest="content_file", default="", help="Path to markdown file")

    # create-page (for creating under a page, not database)
    p_create = subparsers.add_parser("create-page", help="Create page under a page")
    p_create.add_argument("parent_id", help="Parent page ID")
    p_create.add_argument("title", help="Page title")
    p_create.add_argument("content", nargs="?", default="", help="Page content")

    # create-database
    p_create_db = subparsers.add_parser("create-database", help="Create a new database under a parent page")
    p_create_db.add_argument("parent_page_id", help="Parent page ID")
    p_create_db.add_argument("title", help="Database title")
    p_create_db.add_argument("--schema", "-s", help='Schema JSON defining properties')
    p_create_db.add_argument("--file", "-f", dest="schema_file", help="Read schema JSON from file instead of --schema")

    # create-db-item (for creating in a database)
    p_db_item = subparsers.add_parser("create-db-item", help="Create item in database")
    p_db_item.add_argument("database_id", help="Database ID")
    p_db_item.add_argument("title", help="Item title/name")
    p_db_item.add_argument("--props", "-p", dest="properties", help='Properties as JSON, e.g. \'{"Category": "Proposal"}\'')
    p_db_item.add_argument("--content", "-c", help="Page content (text)")
    p_db_item.add_argument("--file", "-f", dest="content_file", help="Path to markdown file (overrides --content)")

    # update-db-item-properties
    p_update_props = subparsers.add_parser("update-db-item-properties", help="Update page/database item properties")
    p_update_props.add_argument("page_id", help="Page ID to update")
    p_update_props.add_argument("--props", "-p", help='Properties as JSON, e.g. \'{"Status": "done", "Priority": "high"}\'')
    p_update_props.add_argument("--file", "-f", dest="props_file", help="Read properties JSON from file instead of --props")

    args = parser.parse_args()

    if args.command == "verify":
        verify()
    elif args.command == "search":
        search(args.query)
    elif args.command == "read-page":
        read_page(args.page_id)
    elif args.command == "query-db":
        query_db(args.database_id, getattr(args, "filter", None), getattr(args, "sort", None), getattr(args, "page_size", 100))
    elif args.command == "get-db-schema":
        get_db_schema(args.database_id, "json" if args.json else "human")
    elif args.command == "list-children":
        list_children(args.page_id, "json" if args.json else "human")
    elif args.command == "list-databases":
        list_databases()
    elif args.command == "update-page":
        update_page(args.page_id, args.content, args.content_file)
    elif args.command == "create-page":
        create_page(args.parent_id, args.title, args.content)
    elif args.command == "create-database":
        schema_json = getattr(args, "schema", None)
        if hasattr(args, "schema_file") and args.schema_file:
            with open(args.schema_file, "r") as f:
                schema_json = f.read()
        if not schema_json:
            print("Error: provide --schema or --file")
            sys.exit(1)
        create_database(args.parent_page_id, args.title, schema_json)
    elif args.command == "create-db-item":
        content = args.content
        if args.content_file:
            with open(args.content_file, "r") as f:
                content = f.read()
        create_db_item(args.database_id, args.title, args.properties, content)
    elif args.command == "update-db-item-properties":
        props_json = args.props
        if hasattr(args, "props_file") and args.props_file:
            with open(args.props_file, "r") as f:
                props_json = f.read()
        if not props_json:
            print("Error: provide --props or --file")
            sys.exit(1)
        update_page_properties(args.page_id, props_json)


if __name__ == "__main__":
    main()
