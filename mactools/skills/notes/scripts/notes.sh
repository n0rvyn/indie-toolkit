#!/bin/bash
# Apple Notes helper — wraps AppleScript for Notes.app CRUD operations
# Usage: notes.sh <command> [options] [arguments]
#
# Commands:
#   list [folder]              — list notes, optionally in a specific folder
#   folders                    — list all folders
#   read "Note Name"           — read full content of a note (plain text)
#   search "keyword"           — search notes by keyword in name or body
#   create "Title" "Body" [folder] — create a new note
#   append "Note Name" "Text"  — append text to an existing note
#   delete "Note Name"         — move note to Recently Deleted
#
# Options:
#   -n <count>   max results for list/search (default: 20)

set -eo pipefail

COMMAND="${1:-}"
shift || true

# Defaults
MAX_RESULTS=20

# Parse -n option from remaining args
ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -n) MAX_RESULTS="$2"; shift 2 ;;
    *)  ARGS+=("$1"); shift ;;
  esac
done

# Restore positional args
set -- "${ARGS[@]}"

# Strip HTML tags from text, converting <br> and block tags to newlines
strip_html() {
  # Replace <br>, </p>, </div>, </li> with newlines, then strip remaining tags, then clean up entities
  sed -E '
    s/<br[[:space:]]*\/?>/\n/gi
    s/<\/(p|div|li|tr|h[1-6])>/\n/gi
    s/<[^>]+>//g
    s/&amp;/\&/g
    s/&lt;/</g
    s/&gt;/>/g
    s/&quot;/"/g
    s/&#39;/'"'"'/g
    s/&nbsp;/ /g
  ' | sed '/^[[:space:]]*$/{ N; /^\n[[:space:]]*$/d; }'
}

# HTML-escape a string for safe embedding in note HTML body
html_escape() {
  local s="$1"
  s="${s//&/&amp;}"
  s="${s//</&lt;}"
  s="${s//>/&gt;}"
  s="${s//\"/&quot;}"
  printf '%s' "$s"
}

case "$COMMAND" in
  folders)
    osascript -e '
      tell application "Notes"
        set folderList to every folder
        set output to ""
        repeat with f in folderList
          set output to output & name of f & linefeed
        end repeat
        return output
      end tell
    '
    ;;

  list)
    FOLDER="${1:-}"
    if [[ -n "$FOLDER" ]]; then
      osascript - "$FOLDER" "$MAX_RESULTS" <<'APPLESCRIPT'
on run argv
  set folderName to item 1 of argv
  set maxN to (item 2 of argv) as integer
  tell application "Notes"
    try
      set theFolder to folder folderName
    on error
      return "Error: Folder \"" & folderName & "\" not found."
    end try
    set noteList to every note of theFolder
    set output to ""
    set i to 0
    repeat with n in noteList
      if i >= maxN then exit repeat
      set noteName to name of n
      set noteDate to modification date of n as text
      set noteBody to plaintext of n
      if length of noteBody > 100 then
        set noteBody to text 1 thru 100 of noteBody & "..."
      end if
      set folderLabel to name of container of n
      set output to output & (i + 1) & ". " & noteName & linefeed & "   Folder: " & folderLabel & " | Modified: " & noteDate & linefeed & "   " & noteBody & linefeed & linefeed
      set i to i + 1
    end repeat
    if i = 0 then
      return "No notes found in folder \"" & folderName & "\"."
    else
      return output & "--- " & i & " note(s) shown (max " & maxN & ") ---"
    end if
  end tell
end run
APPLESCRIPT
    else
      osascript - "$MAX_RESULTS" <<'APPLESCRIPT'
on run argv
  set maxN to (item 1 of argv) as integer
  tell application "Notes"
    set noteList to every note
    set output to ""
    set i to 0
    repeat with n in noteList
      if i >= maxN then exit repeat
      set noteName to name of n
      set noteDate to modification date of n as text
      set noteBody to plaintext of n
      if length of noteBody > 100 then
        set noteBody to text 1 thru 100 of noteBody & "..."
      end if
      set folderName to name of container of n
      set output to output & (i + 1) & ". " & noteName & linefeed & "   Folder: " & folderName & " | Modified: " & noteDate & linefeed & "   " & noteBody & linefeed & linefeed
      set i to i + 1
    end repeat
    if i = 0 then
      return "No notes found."
    else
      return output & "--- " & i & " note(s) shown (max " & maxN & ") ---"
    end if
  end tell
end run
APPLESCRIPT
    fi
    ;;

  read)
    NOTE_NAME="${1:-}"
    if [[ -z "$NOTE_NAME" ]]; then
      echo "Usage: notes.sh read \"Note Name\""
      exit 1
    fi
    # Use AppleScript to find note by name and return its HTML body, then strip HTML
    RESULT=$(osascript - "$NOTE_NAME" <<'APPLESCRIPT'
on run argv
  set noteName to item 1 of argv
  tell application "Notes"
    try
      set theNotes to (every note whose name is noteName)
      if (count of theNotes) = 0 then
        return "Error: Note \"" & noteName & "\" not found."
      end if
      set theNote to item 1 of theNotes
      set noteTitle to name of theNote
      set noteFolder to name of container of theNote
      set noteDate to modification date of theNote as text
      set noteBody to body of theNote
      return "Title: " & noteTitle & linefeed & "Folder: " & noteFolder & linefeed & "Modified: " & noteDate & linefeed & "---" & linefeed & noteBody
    on error errMsg
      return "Error: " & errMsg
    end try
  end tell
end run
APPLESCRIPT
    2>&1)
    # Check if result starts with Error:
    if [[ "$RESULT" == Error:* ]]; then
      echo "$RESULT"
      exit 1
    fi
    # Split header (first 4 lines) and body (rest), strip HTML from body only
    HEADER=$(echo "$RESULT" | head -4)
    BODY=$(echo "$RESULT" | tail -n +5 | strip_html)
    echo "$HEADER"
    echo "$BODY"
    ;;

  search)
    KEYWORD="${1:-}"
    if [[ -z "$KEYWORD" ]]; then
      echo "Usage: notes.sh search \"keyword\""
      exit 1
    fi
    osascript - "$KEYWORD" "$MAX_RESULTS" <<'APPLESCRIPT'
on run argv
  set keyword to item 1 of argv
  set maxN to (item 2 of argv) as integer
  tell application "Notes"
    set allNotes to every note
    set output to ""
    set i to 0
    repeat with n in allNotes
      if i >= maxN then exit repeat
      set noteName to name of n
      set noteText to plaintext of n
      -- case-insensitive search in name and body
      set lcName to do shell script "echo " & quoted form of noteName & " | tr '[:upper:]' '[:lower:]'"
      set lcBody to do shell script "echo " & quoted form of noteText & " | tr '[:upper:]' '[:lower:]'"
      set lcKey to do shell script "echo " & quoted form of keyword & " | tr '[:upper:]' '[:lower:]'"
      if lcName contains lcKey or lcBody contains lcKey then
        set noteDate to modification date of n as text
        if length of noteText > 100 then
          set noteText to text 1 thru 100 of noteText & "..."
        end if
        set folderName to name of container of n
        set output to output & (i + 1) & ". " & noteName & linefeed & "   Folder: " & folderName & " | Modified: " & noteDate & linefeed & "   " & noteText & linefeed & linefeed
        set i to i + 1
      end if
    end repeat
    if i = 0 then
      return "No notes found matching \"" & keyword & "\"."
    else
      return output & "--- " & i & " result(s) shown (max " & maxN & ") ---"
    end if
  end tell
end run
APPLESCRIPT
    ;;

  create)
    TITLE="${1:-}"
    BODY="${2:-}"
    FOLDER="${3:-}"
    if [[ -z "$TITLE" ]]; then
      echo "Usage: notes.sh create \"Title\" \"Body\" [folder]"
      exit 1
    fi
    # HTML-escape user input before embedding in note HTML
    SAFE_TITLE=$(html_escape "$TITLE")
    HTML_BODY=$(echo "$BODY" | while IFS= read -r line; do html_escape "$line"; printf '<br>'; done)
    if [[ -n "$FOLDER" ]]; then
      osascript - "$FOLDER" "$TITLE" "$SAFE_TITLE" "$HTML_BODY" <<'APPLESCRIPT'
on run argv
  set folderName to item 1 of argv
  set noteTitle to item 2 of argv
  set safeTitle to item 3 of argv
  set htmlBody to item 4 of argv
  tell application "Notes"
    try
      set theFolder to folder folderName
    on error
      return "Error: Folder \"" & folderName & "\" not found."
    end try
    set noteHTML to "<html><head></head><body><h1>" & safeTitle & "</h1>" & htmlBody & "</body></html>"
    set newNote to make new note at theFolder with properties {name:noteTitle, body:noteHTML}
    return "Created note \"" & noteTitle & "\" in folder \"" & folderName & "\"."
  end tell
end run
APPLESCRIPT
    else
      osascript - "$TITLE" "$SAFE_TITLE" "$HTML_BODY" <<'APPLESCRIPT'
on run argv
  set noteTitle to item 1 of argv
  set safeTitle to item 2 of argv
  set htmlBody to item 3 of argv
  tell application "Notes"
    set noteHTML to "<html><head></head><body><h1>" & safeTitle & "</h1>" & htmlBody & "</body></html>"
    -- Try "Notes" folder first (standard default), then try each folder until one works
    set targetFolder to missing value
    try
      set targetFolder to folder "Notes" of default account
    end try
    if targetFolder is missing value then
      repeat with f in folders of default account
        try
          make new note at f with properties {name:noteTitle, body:noteHTML}
          return "Created note \"" & noteTitle & "\" in folder \"" & name of f & "\"."
        end try
      end repeat
      return "Error: Could not find a writable folder."
    end if
    set newNote to make new note at targetFolder with properties {name:noteTitle, body:noteHTML}
    return "Created note \"" & noteTitle & "\" in folder \"Notes\"."
  end tell
end run
APPLESCRIPT
    fi
    ;;

  append)
    NOTE_NAME="${1:-}"
    TEXT="${2:-}"
    if [[ -z "$NOTE_NAME" || -z "$TEXT" ]]; then
      echo "Usage: notes.sh append \"Note Name\" \"Text\""
      exit 1
    fi
    # HTML-escape and convert newlines to <br> for HTML append
    HTML_TEXT=$(echo "$TEXT" | while IFS= read -r line; do html_escape "$line"; printf '<br>'; done)
    osascript - "$NOTE_NAME" "$HTML_TEXT" <<'APPLESCRIPT'
on run argv
  set noteName to item 1 of argv
  set htmlText to item 2 of argv
  tell application "Notes"
    try
      set theNotes to (every note whose name is noteName)
      if (count of theNotes) = 0 then
        return "Error: Note \"" & noteName & "\" not found."
      end if
      set theNote to item 1 of theNotes
      set currentBody to body of theNote
      set body of theNote to currentBody & "<br>" & htmlText
      return "Appended text to note \"" & noteName & "\"."
    on error errMsg
      return "Error: " & errMsg
    end try
  end tell
end run
APPLESCRIPT
    ;;

  delete)
    NOTE_NAME="${1:-}"
    if [[ -z "$NOTE_NAME" ]]; then
      echo "Usage: notes.sh delete \"Note Name\""
      exit 1
    fi
    osascript - "$NOTE_NAME" <<'APPLESCRIPT'
on run argv
  set noteName to item 1 of argv
  tell application "Notes"
    try
      set theNotes to (every note whose name is noteName)
      if (count of theNotes) = 0 then
        return "Error: Note \"" & noteName & "\" not found."
      end if
      set theNote to item 1 of theNotes
      delete theNote
      return "Moved note \"" & noteName & "\" to Recently Deleted."
    on error errMsg
      return "Error: " & errMsg
    end try
  end tell
end run
APPLESCRIPT
    ;;

  *)
    echo "Apple Notes CLI"
    echo ""
    echo "Usage: notes.sh <command> [options] [arguments]"
    echo ""
    echo "Commands:"
    echo "  list [folder]                  List notes, optionally in a specific folder"
    echo "  folders                        List all folders"
    echo "  read \"Note Name\"              Read full content of a note (plain text)"
    echo "  search \"keyword\"              Search notes by keyword in name or body"
    echo "  create \"Title\" \"Body\" [folder] Create a new note"
    echo "  append \"Note Name\" \"Text\"     Append text to an existing note"
    echo "  delete \"Note Name\"            Move note to Recently Deleted"
    echo ""
    echo "Options:"
    echo "  -n <count>   Max results for list/search (default: 20)"
    exit 1
    ;;
esac
