#!/bin/bash
# Safari history & bookmarks query tool — read-only operations only
# Usage: safari.sh <subcommand> [options]
#
# Subcommands:
#   history [days] [-n count]         Show browsing history (default: 7 days, 20 results)
#   search "keyword" [-n count]       Search history by URL or title
#   top [-n count]                    Most visited sites
#   bookmarks [-n count]              List bookmarks (title, URL, folder)
#   search-bookmarks "keyword"        Search bookmarks by title or URL
#   reading-list                      Show Safari reading list items
#
# Safari data locations:
#   History:   ~/Library/Safari/History.db
#   Bookmarks: ~/Library/Safari/Bookmarks.plist
#
# NOTE: Requires Full Disk Access for the terminal app running this script.
#       System Preferences > Privacy & Security > Full Disk Access

set -eo pipefail

HISTORY_DB="$HOME/Library/Safari/History.db"
BOOKMARKS_PLIST="$HOME/Library/Safari/Bookmarks.plist"

SUBCOMMAND="${1:-}"
shift || true

# Defaults
MAX_RESULTS=20
QUERY=""
DAYS=7

# Parse options and positional args
parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -n) MAX_RESULTS="$2"; shift 2 ;;
      *)  QUERY="${QUERY:+$QUERY }$1"; shift ;;
    esac
  done
}

parse_args "$@"

# Validate numeric parameters to prevent SQL injection
if ! [[ "$MAX_RESULTS" =~ ^[0-9]+$ ]]; then
  echo "Error: -n value must be a positive integer." >&2
  exit 1
fi

# --- Helpers ---

check_history_db() {
  if [[ ! -f "$HISTORY_DB" ]]; then
    echo "Error: Safari history database not found at $HISTORY_DB"
    exit 1
  fi
}

check_bookmarks_plist() {
  if [[ ! -f "$BOOKMARKS_PLIST" ]]; then
    echo "Error: Safari bookmarks plist not found at $BOOKMARKS_PLIST"
    exit 1
  fi
}

# Run a read-only query against Safari History.db
# Uses a copy to avoid locking issues with Safari
query_history() {
  local sql="$1"
  local tmpdb
  tmpdb=$(mktemp /tmp/safari_history_XXXXXX)
  trap "rm -f '$tmpdb'" RETURN
  if ! cp "$HISTORY_DB" "$tmpdb" 2>/dev/null; then
    echo "Error: Cannot read Safari history database." >&2
    echo "Grant Full Disk Access to your terminal app:" >&2
    echo "  System Settings > Privacy & Security > Full Disk Access" >&2
    return 1
  fi
  sqlite3 -separator '|' "$tmpdb" "$sql"
}

format_history_rows() {
  local count=0
  while IFS='|' read -r title url visit_date visit_count; do
    [[ -z "$url" ]] && continue
    ((count++))

    # Clean up title
    [[ -z "$title" || "$title" == "(null)" ]] && title="(no title)"

    printf "%d. %s\n   URL: %s\n   Visited: %s | Visits: %s\n\n" \
      "$count" "$title" "$url" "$visit_date" "$visit_count"
  done

  if (( count == 0 )); then
    echo "No results found."
  else
    echo "--- $count result(s) shown (max $MAX_RESULTS) ---"
  fi
}

format_top_rows() {
  local count=0
  while IFS='|' read -r title url visit_count last_visit; do
    [[ -z "$url" ]] && continue
    ((count++))

    [[ -z "$title" || "$title" == "(null)" ]] && title="(no title)"

    printf "%d. %s\n   URL: %s\n   Total visits: %s | Last visit: %s\n\n" \
      "$count" "$title" "$url" "$visit_count" "$last_visit"
  done

  if (( count == 0 )); then
    echo "No results found."
  else
    echo "--- $count result(s) shown (max $MAX_RESULTS) ---"
  fi
}

# --- Subcommands ---

cmd_history() {
  check_history_db

  # If QUERY is a number, treat it as days
  if [[ "$QUERY" =~ ^[0-9]+$ ]]; then
    DAYS="$QUERY"
  fi

  local sql
  sql="SELECT
    hi.title,
    hi.url,
    datetime(hv.visit_time + 978307200, 'unixepoch', 'localtime') AS visit_date,
    hi.visit_count
  FROM history_visits hv
  JOIN history_items hi ON hv.history_item = hi.id
  WHERE hv.visit_time > (strftime('%s', 'now', '-${DAYS} days') - 978307200)
  ORDER BY hv.visit_time DESC
  LIMIT ${MAX_RESULTS};"

  local result
  result=$(query_history "$sql") || return
  echo "$result" | format_history_rows
}

cmd_search() {
  check_history_db

  if [[ -z "$QUERY" ]]; then
    echo "Usage: safari.sh search \"keyword\" [-n count]"
    exit 1
  fi

  local escaped_query
  escaped_query=$(printf '%s' "$QUERY" | sed "s/'/''/g")

  local sql
  sql="SELECT
    hi.title,
    hi.url,
    datetime(hv.visit_time + 978307200, 'unixepoch', 'localtime') AS visit_date,
    hi.visit_count
  FROM history_visits hv
  JOIN history_items hi ON hv.history_item = hi.id
  WHERE (hi.url LIKE '%${escaped_query}%' OR hi.title LIKE '%${escaped_query}%')
  ORDER BY hv.visit_time DESC
  LIMIT ${MAX_RESULTS};"

  local result
  result=$(query_history "$sql") || return
  echo "$result" | format_history_rows
}

cmd_top() {
  check_history_db

  local sql
  sql="SELECT
    hi.title,
    hi.url,
    hi.visit_count,
    datetime(MAX(hv.visit_time) + 978307200, 'unixepoch', 'localtime') AS last_visit
  FROM history_items hi
  JOIN history_visits hv ON hv.history_item = hi.id
  GROUP BY hi.id
  ORDER BY hi.visit_count DESC
  LIMIT ${MAX_RESULTS};"

  local result
  result=$(query_history "$sql") || return
  echo "$result" | format_top_rows
}

cmd_bookmarks() {
  check_bookmarks_plist

  python3 - "$BOOKMARKS_PLIST" "$MAX_RESULTS" "" "list" << 'PYEOF'
import sys
import plistlib
import os

plist_path = sys.argv[1]
max_results = int(sys.argv[2])
keyword = sys.argv[3] if len(sys.argv) > 3 else ""
mode = sys.argv[4] if len(sys.argv) > 4 else "list"

try:
    with open(plist_path, "rb") as f:
        plist = plistlib.load(f)
except PermissionError:
    print("Error: Cannot read Safari bookmarks plist.")
    print("Grant Full Disk Access to your terminal app:")
    print("  System Settings > Privacy & Security > Full Disk Access")
    sys.exit(1)

results = []

def walk_bookmarks(node, folder_path=""):
    if isinstance(node, dict):
        node_type = node.get("WebBookmarkType", "")
        title = node.get("URIDictionary", {}).get("title", node.get("Title", ""))

        if node_type == "WebBookmarkTypeLeaf":
            url = node.get("URLString", "")
            if not url:
                return

            # Skip reading list items in bookmark listing (they have ReadingList key)
            if mode == "list" and "ReadingList" in node:
                return

            # For reading-list mode, only include reading list items
            if mode == "reading-list" and "ReadingList" not in node:
                return

            entry = {
                "title": title or "(no title)",
                "url": url,
                "folder": folder_path or "(root)",
            }

            if mode == "reading-list":
                rl = node.get("ReadingList", {})
                entry["date_added"] = str(rl.get("DateAdded", ""))[:19]
                entry["preview"] = rl.get("PreviewText", "")[:120]

            if keyword:
                kw = keyword.lower()
                if kw not in entry["title"].lower() and kw not in entry["url"].lower():
                    return

            results.append(entry)

        elif node_type == "WebBookmarkTypeList":
            current_folder = title if title else folder_path
            if folder_path and title:
                current_folder = f"{folder_path}/{title}"
            children = node.get("Children", [])
            for child in children:
                walk_bookmarks(child, current_folder)

walk_bookmarks(plist)

if not results:
    print("No results found.")
    sys.exit(0)

shown = results[:max_results]
for i, entry in enumerate(shown, 1):
    print(f"{i}. {entry['title']}")
    print(f"   URL: {entry['url']}")
    if mode == "reading-list":
        date_str = entry.get("date_added", "")
        if date_str:
            print(f"   Added: {date_str}")
        preview = entry.get("preview", "")
        if preview:
            print(f"   Preview: {preview}")
    else:
        print(f"   Folder: {entry['folder']}")
    print()

print(f"--- {len(shown)} result(s) shown (max {max_results}) ---")
PYEOF
}

cmd_search_bookmarks() {
  check_bookmarks_plist

  if [[ -z "$QUERY" ]]; then
    echo "Usage: safari.sh search-bookmarks \"keyword\" [-n count]"
    exit 1
  fi

  python3 - "$BOOKMARKS_PLIST" "$MAX_RESULTS" "$QUERY" "list" << 'PYEOF'
import sys
import plistlib
import os

plist_path = sys.argv[1]
max_results = int(sys.argv[2])
keyword = sys.argv[3] if len(sys.argv) > 3 else ""
mode = sys.argv[4] if len(sys.argv) > 4 else "list"

try:
    with open(plist_path, "rb") as f:
        plist = plistlib.load(f)
except PermissionError:
    print("Error: Cannot read Safari bookmarks plist.")
    print("Grant Full Disk Access to your terminal app:")
    print("  System Settings > Privacy & Security > Full Disk Access")
    sys.exit(1)

results = []

def walk_bookmarks(node, folder_path=""):
    if isinstance(node, dict):
        node_type = node.get("WebBookmarkType", "")
        title = node.get("URIDictionary", {}).get("title", node.get("Title", ""))

        if node_type == "WebBookmarkTypeLeaf":
            url = node.get("URLString", "")
            if not url:
                return

            if "ReadingList" in node:
                return

            entry = {
                "title": title or "(no title)",
                "url": url,
                "folder": folder_path or "(root)",
            }

            if keyword:
                kw = keyword.lower()
                if kw not in entry["title"].lower() and kw not in entry["url"].lower():
                    return

            results.append(entry)

        elif node_type == "WebBookmarkTypeList":
            current_folder = title if title else folder_path
            if folder_path and title:
                current_folder = f"{folder_path}/{title}"
            children = node.get("Children", [])
            for child in children:
                walk_bookmarks(child, current_folder)

walk_bookmarks(plist)

if not results:
    print("No results found.")
    sys.exit(0)

shown = results[:max_results]
for i, entry in enumerate(shown, 1):
    print(f"{i}. {entry['title']}")
    print(f"   URL: {entry['url']}")
    print(f"   Folder: {entry['folder']}")
    print()

print(f"--- {len(shown)} result(s) shown (max {max_results}) ---")
PYEOF
}

cmd_reading_list() {
  check_bookmarks_plist

  python3 - "$BOOKMARKS_PLIST" "$MAX_RESULTS" "" "reading-list" << 'PYEOF'
import sys
import plistlib
import os

plist_path = sys.argv[1]
max_results = int(sys.argv[2])
keyword = sys.argv[3] if len(sys.argv) > 3 else ""
mode = sys.argv[4] if len(sys.argv) > 4 else "list"

try:
    with open(plist_path, "rb") as f:
        plist = plistlib.load(f)
except PermissionError:
    print("Error: Cannot read Safari bookmarks plist.")
    print("Grant Full Disk Access to your terminal app:")
    print("  System Settings > Privacy & Security > Full Disk Access")
    sys.exit(1)

results = []

def walk_bookmarks(node, folder_path=""):
    if isinstance(node, dict):
        node_type = node.get("WebBookmarkType", "")
        title = node.get("URIDictionary", {}).get("title", node.get("Title", ""))

        if node_type == "WebBookmarkTypeLeaf":
            url = node.get("URLString", "")
            if not url:
                return

            if mode == "reading-list" and "ReadingList" not in node:
                return

            entry = {
                "title": title or "(no title)",
                "url": url,
                "folder": folder_path or "(root)",
            }

            if mode == "reading-list":
                rl = node.get("ReadingList", {})
                entry["date_added"] = str(rl.get("DateAdded", ""))[:19]
                entry["preview"] = rl.get("PreviewText", "")[:120]

            if keyword:
                kw = keyword.lower()
                if kw not in entry["title"].lower() and kw not in entry["url"].lower():
                    return

            results.append(entry)

        elif node_type == "WebBookmarkTypeList":
            current_folder = title if title else folder_path
            if folder_path and title:
                current_folder = f"{folder_path}/{title}"
            children = node.get("Children", [])
            for child in children:
                walk_bookmarks(child, current_folder)

walk_bookmarks(plist)

if not results:
    print("No reading list items found.")
    sys.exit(0)

shown = results[:max_results]
for i, entry in enumerate(shown, 1):
    print(f"{i}. {entry['title']}")
    print(f"   URL: {entry['url']}")
    date_str = entry.get("date_added", "")
    if date_str:
        print(f"   Added: {date_str}")
    preview = entry.get("preview", "")
    if preview:
        print(f"   Preview: {preview}")
    print()

print(f"--- {len(shown)} result(s) shown (max {max_results}) ---")
PYEOF
}

# --- Main dispatch ---

case "$SUBCOMMAND" in
  history)
    cmd_history
    ;;
  search)
    cmd_search
    ;;
  top)
    cmd_top
    ;;
  bookmarks)
    cmd_bookmarks
    ;;
  search-bookmarks)
    cmd_search_bookmarks
    ;;
  reading-list)
    cmd_reading_list
    ;;
  ""|help|-h|--help)
    echo "Safari history & bookmarks query tool (read-only)"
    echo ""
    echo "Usage: safari.sh <subcommand> [options]"
    echo ""
    echo "Subcommands:"
    echo "  history [days] [-n count]         Show browsing history (default: 7 days, 20 results)"
    echo "  search \"keyword\" [-n count]       Search history by URL or title"
    echo "  top [-n count]                    Most visited sites"
    echo "  bookmarks [-n count]              List bookmarks (title, URL, folder)"
    echo "  search-bookmarks \"keyword\"        Search bookmarks by title or URL"
    echo "  reading-list [-n count]           Show Safari reading list items"
    echo ""
    echo "Options:"
    echo "  -n <count>   Max results (default: 20)"
    echo ""
    echo "Requires Full Disk Access for the terminal app."
    ;;
  *)
    echo "Unknown subcommand: $SUBCOMMAND"
    echo "Run 'safari.sh help' for usage."
    exit 1
    ;;
esac
