#!/bin/bash
# Mail.app helper — wraps AppleScript for macOS Mail operations
# Usage: mail.sh <command> [options]
#
# Commands:
#   accounts                                    — List mail accounts
#   mailboxes [account]                         — List mailboxes (optionally for specific account)
#   inbox [account] [-n count]                  — List inbox messages (default 20)
#   read <account> <mailbox> <index>            — Read full message content
#   unread [account] [-n count]                 — List unread messages only
#   search "keyword" [account]                  — Search messages by subject or content
#   flag <account> <mailbox> <index>            — Toggle flag on message
#   mark-read <account> <mailbox> <index>       — Mark message as read
#   move <account> <mailbox> <index> <target>   — Move message to another mailbox
#   trash <account> <mailbox> <index>           — Move message to Trash (recoverable)
#   batch-trash <account> <mailbox> <start> <end> — Move range of messages to Trash

set -eo pipefail

COMMAND="${1:-help}"
shift || true

# --- Helper functions ---

ensure_mail_running() {
  if ! osascript -e 'tell application "System Events" to (name of processes) contains "Mail"' 2>/dev/null | grep -q "true"; then
    echo "[Error] Mail.app is not running. Please launch Mail first."
    exit 1
  fi
}

# --- Commands ---

cmd_accounts() {
  ensure_mail_running
  osascript <<'APPLESCRIPT'
tell application "Mail"
  set acctList to every account
  set output to ""
  repeat with i from 1 to count of acctList
    set acct to item i of acctList
    set acctName to name of acct
    set acctEnabled to enabled of acct
    set acctType to account type of acct as string
    if acctEnabled then
      set statusStr to "enabled"
    else
      set statusStr to "disabled"
    end if
    set output to output & i & ". " & acctName & " (" & acctType & ", " & statusStr & ")" & linefeed
  end repeat
  if output is "" then
    return "No mail accounts found."
  end if
  return output
end tell
APPLESCRIPT
}

cmd_mailboxes() {
  ensure_mail_running
  local account_name="$1"

  if [[ -n "$account_name" ]]; then
    osascript - "$account_name" <<'APPLESCRIPT'
on run argv
  set accountName to item 1 of argv
  tell application "Mail"
    set acct to account accountName
    set mboxes to every mailbox of acct
    set output to "Mailboxes for account: " & accountName & linefeed & linefeed
    repeat with i from 1 to count of mboxes
      set mbox to item i of mboxes
      set mboxName to name of mbox
      set msgCount to count of messages of mbox
      set unreadCount to unread count of mbox
      set output to output & i & ". " & mboxName & " (" & msgCount & " messages, " & unreadCount & " unread)" & linefeed
    end repeat
    if (count of mboxes) is 0 then
      set output to output & "No mailboxes found." & linefeed
    end if
    return output
  end tell
end run
APPLESCRIPT
  else
    osascript <<'APPLESCRIPT'
tell application "Mail"
  set acctList to every account
  set output to ""
  repeat with acct in acctList
    set acctName to name of acct
    set output to output & "== " & acctName & " ==" & linefeed
    set mboxes to every mailbox of acct
    repeat with i from 1 to count of mboxes
      set mbox to item i of mboxes
      set mboxName to name of mbox
      set msgCount to count of messages of mbox
      set unreadCount to unread count of mbox
      set output to output & "  " & i & ". " & mboxName & " (" & msgCount & " messages, " & unreadCount & " unread)" & linefeed
    end repeat
    set output to output & linefeed
  end repeat
  return output
end tell
APPLESCRIPT
  fi
}

cmd_inbox() {
  ensure_mail_running
  local account_name=""
  local max_count=20

  # Parse arguments
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -n) max_count="$2"; shift 2 ;;
      *)  account_name="$1"; shift ;;
    esac
  done

  if [[ -n "$account_name" ]]; then
    osascript - "$account_name" "$max_count" <<'APPLESCRIPT'
on run argv
  set accountName to item 1 of argv
  set limit to (item 2 of argv) as integer
  tell application "Mail"
    set mbox to mailbox "INBOX" of account accountName
    set msgs to messages of mbox
    set msgCount to count of msgs
    if msgCount < limit then set limit to msgCount
    set output to "Inbox for " & accountName & " (" & msgCount & " total, showing " & limit & "):" & linefeed & linefeed
    repeat with i from 1 to limit
      set msg to item i of msgs
      set subj to subject of msg
      set sndr to sender of msg
      set dt to date received of msg
      set isRead to read status of msg
      if isRead then
        set statusStr to "read"
      else
        set statusStr to "unread"
      end if
      set dtStr to (year of dt as string) & "-"
      set m to (month of dt as integer)
      if m < 10 then
        set dtStr to dtStr & "0" & (m as string)
      else
        set dtStr to dtStr & (m as string)
      end if
      set dtStr to dtStr & "-"
      set d to (day of dt as integer)
      if d < 10 then
        set dtStr to dtStr & "0" & (d as string)
      else
        set dtStr to dtStr & (d as string)
      end if
      set dtStr to dtStr & " "
      set h to (hours of dt as integer)
      if h < 10 then
        set dtStr to dtStr & "0" & (h as string)
      else
        set dtStr to dtStr & (h as string)
      end if
      set dtStr to dtStr & ":"
      set mn to (minutes of dt as integer)
      if mn < 10 then
        set dtStr to dtStr & "0" & (mn as string)
      else
        set dtStr to dtStr & (mn as string)
      end if
      set output to output & i & ". [" & statusStr & "] " & subj & linefeed & "   From: " & sndr & " | Date: " & dtStr & linefeed
    end repeat
    return output
  end tell
end run
APPLESCRIPT
  else
    osascript - "$max_count" <<'APPLESCRIPT'
on run argv
  set limit to (item 1 of argv) as integer
  tell application "Mail"
    set acctList to every account
    set output to ""
    repeat with acct in acctList
      set acctName to name of acct
      try
        set mbox to mailbox "INBOX" of acct
        set msgs to messages of mbox
        set msgCount to count of msgs
        set acctLimit to limit
        if msgCount < acctLimit then set acctLimit to msgCount
        set output to output & "== " & acctName & " (" & msgCount & " total, showing " & acctLimit & ") ==" & linefeed & linefeed
        repeat with i from 1 to acctLimit
          set msg to item i of msgs
          set subj to subject of msg
          set sndr to sender of msg
          set dt to date received of msg
          set isRead to read status of msg
          if isRead then
            set statusStr to "read"
          else
            set statusStr to "unread"
          end if
          set dtStr to (year of dt as string) & "-"
          set m to (month of dt as integer)
          if m < 10 then
            set dtStr to dtStr & "0" & (m as string)
          else
            set dtStr to dtStr & (m as string)
          end if
          set dtStr to dtStr & "-"
          set d to (day of dt as integer)
          if d < 10 then
            set dtStr to dtStr & "0" & (d as string)
          else
            set dtStr to dtStr & (d as string)
          end if
          set dtStr to dtStr & " "
          set h to (hours of dt as integer)
          if h < 10 then
            set dtStr to dtStr & "0" & (h as string)
          else
            set dtStr to dtStr & (h as string)
          end if
          set dtStr to dtStr & ":"
          set mn to (minutes of dt as integer)
          if mn < 10 then
            set dtStr to dtStr & "0" & (mn as string)
          else
            set dtStr to dtStr & (mn as string)
          end if
          set output to output & i & ". [" & statusStr & "] " & subj & linefeed & "   From: " & sndr & " | Date: " & dtStr & linefeed
        end repeat
        set output to output & linefeed
      on error
        set output to output & "== " & acctName & " (no INBOX) ==" & linefeed & linefeed
      end try
    end repeat
    return output
  end tell
end run
APPLESCRIPT
  fi
}

cmd_read() {
  ensure_mail_running
  local account_name="$1"
  local mailbox_name="$2"
  local msg_index="$3"

  if [[ -z "$account_name" || -z "$mailbox_name" || -z "$msg_index" ]]; then
    echo "Usage: mail.sh read <account> <mailbox> <index>"
    exit 1
  fi

  osascript - "$account_name" "$mailbox_name" "$msg_index" <<'APPLESCRIPT'
on run argv
  set accountName to item 1 of argv
  set mailboxName to item 2 of argv
  set msgIndex to (item 3 of argv) as integer
  tell application "Mail"
    set mbox to mailbox mailboxName of account accountName
    set msg to message msgIndex of mbox
    set subj to subject of msg
    set sndr to sender of msg
    set rcpts to address of every to recipient of msg
    set ccList to address of every cc recipient of msg
    set dt to date received of msg
    set isRead to read status of msg
    set isFlagged to flagged status of msg

    -- Format date
    set dtStr to (year of dt as string) & "-"
    set m to (month of dt as integer)
    if m < 10 then
      set dtStr to dtStr & "0" & (m as string)
    else
      set dtStr to dtStr & (m as string)
    end if
    set dtStr to dtStr & "-"
    set d to (day of dt as integer)
    if d < 10 then
      set dtStr to dtStr & "0" & (d as string)
    else
      set dtStr to dtStr & (d as string)
    end if
    set dtStr to dtStr & " "
    set h to (hours of dt as integer)
    if h < 10 then
      set dtStr to dtStr & "0" & (h as string)
    else
      set dtStr to dtStr & (h as string)
    end if
    set dtStr to dtStr & ":"
    set mn to (minutes of dt as integer)
    if mn < 10 then
      set dtStr to dtStr & "0" & (mn as string)
    else
      set dtStr to dtStr & (mn as string)
    end if

    -- Build To list
    set toStr to ""
    repeat with i from 1 to count of rcpts
      if i > 1 then set toStr to toStr & ", "
      set toStr to toStr & (item i of rcpts as string)
    end repeat

    -- Build CC list
    set ccStr to ""
    repeat with i from 1 to count of ccList
      if i > 1 then set ccStr to ccStr & ", "
      set ccStr to ccStr & (item i of ccList as string)
    end repeat

    -- Status flags
    set flags to ""
    if isRead then
      set flags to flags & "read"
    else
      set flags to flags & "unread"
    end if
    if isFlagged then
      set flags to flags & ", flagged"
    end if

    -- Get plain text content
    set bodyContent to ""
    try
      set bodyContent to content of msg
    on error
      set bodyContent to "[Unable to extract message body]"
    end try

    set output to "Subject: " & subj & linefeed
    set output to output & "From: " & sndr & linefeed
    set output to output & "To: " & toStr & linefeed
    if ccStr is not "" then
      set output to output & "CC: " & ccStr & linefeed
    end if
    set output to output & "Date: " & dtStr & linefeed
    set output to output & "Status: " & flags & linefeed
    set output to output & "---" & linefeed
    set output to output & bodyContent
    return output
  end tell
end run
APPLESCRIPT
}

cmd_unread() {
  ensure_mail_running
  local account_name=""
  local max_count=20

  # Parse arguments
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -n) max_count="$2"; shift 2 ;;
      *)  account_name="$1"; shift ;;
    esac
  done

  if [[ -n "$account_name" ]]; then
    osascript - "$account_name" "$max_count" <<'APPLESCRIPT'
on run argv
  set accountName to item 1 of argv
  set maxCount to (item 2 of argv) as integer
  tell application "Mail"
    set mbox to mailbox "INBOX" of account accountName
    set allMsgs to messages of mbox
    set output to "Unread messages for " & accountName & ":" & linefeed & linefeed
    set unreadIdx to 0
    repeat with i from 1 to count of allMsgs
      if unreadIdx >= maxCount then exit repeat
      set msg to item i of allMsgs
      if read status of msg is false then
        set unreadIdx to unreadIdx + 1
        set subj to subject of msg
        set sndr to sender of msg
        set dt to date received of msg
        set dtStr to (year of dt as string) & "-"
        set m to (month of dt as integer)
        if m < 10 then
          set dtStr to dtStr & "0" & (m as string)
        else
          set dtStr to dtStr & (m as string)
        end if
        set dtStr to dtStr & "-"
        set d to (day of dt as integer)
        if d < 10 then
          set dtStr to dtStr & "0" & (d as string)
        else
          set dtStr to dtStr & (d as string)
        end if
        set dtStr to dtStr & " "
        set h to (hours of dt as integer)
        if h < 10 then
          set dtStr to dtStr & "0" & (h as string)
        else
          set dtStr to dtStr & (h as string)
        end if
        set dtStr to dtStr & ":"
        set mn to (minutes of dt as integer)
        if mn < 10 then
          set dtStr to dtStr & "0" & (mn as string)
        else
          set dtStr to dtStr & (mn as string)
        end if
        set output to output & unreadIdx & ". (index " & i & ") [unread] " & subj & linefeed & "   From: " & sndr & " | Date: " & dtStr & linefeed
      end if
    end repeat
    if unreadIdx is 0 then
      set output to output & "No unread messages." & linefeed
    else
      set output to output & linefeed & "--- " & unreadIdx & " unread message(s) shown (max " & maxCount & ") ---" & linefeed
    end if
    return output
  end tell
end run
APPLESCRIPT
  else
    osascript - "$max_count" <<'APPLESCRIPT'
on run argv
  set maxCount to (item 1 of argv) as integer
  tell application "Mail"
    set acctList to every account
    set output to ""
    repeat with acct in acctList
      set acctName to name of acct
      try
        set mbox to mailbox "INBOX" of acct
        set allMsgs to messages of mbox
        set output to output & "== " & acctName & " ==" & linefeed & linefeed
        set unreadIdx to 0
        repeat with i from 1 to count of allMsgs
          if unreadIdx >= maxCount then exit repeat
          set msg to item i of allMsgs
          if read status of msg is false then
            set unreadIdx to unreadIdx + 1
            set subj to subject of msg
            set sndr to sender of msg
            set dt to date received of msg
            set dtStr to (year of dt as string) & "-"
            set m to (month of dt as integer)
            if m < 10 then
              set dtStr to dtStr & "0" & (m as string)
            else
              set dtStr to dtStr & (m as string)
            end if
            set dtStr to dtStr & "-"
            set d to (day of dt as integer)
            if d < 10 then
              set dtStr to dtStr & "0" & (d as string)
            else
              set dtStr to dtStr & (d as string)
            end if
            set dtStr to dtStr & " "
            set h to (hours of dt as integer)
            if h < 10 then
              set dtStr to dtStr & "0" & (h as string)
            else
              set dtStr to dtStr & (h as string)
            end if
            set dtStr to dtStr & ":"
            set mn to (minutes of dt as integer)
            if mn < 10 then
              set dtStr to dtStr & "0" & (mn as string)
            else
              set dtStr to dtStr & (mn as string)
            end if
            set output to output & unreadIdx & ". (index " & i & ") [unread] " & subj & linefeed & "   From: " & sndr & " | Date: " & dtStr & linefeed
          end if
        end repeat
        if unreadIdx is 0 then
          set output to output & "No unread messages." & linefeed
        end if
        set output to output & linefeed
      on error
        set output to output & "== " & acctName & " (no INBOX) ==" & linefeed & linefeed
      end try
    end repeat
    return output
  end tell
end run
APPLESCRIPT
  fi
}

cmd_search() {
  ensure_mail_running
  local keyword=""
  local account_name=""
  local max_count=20

  # Parse arguments
  while [[ $# -gt 0 ]]; do
    case "$1" in
      -n) max_count="$2"; shift 2 ;;
      *)
        if [[ -z "$keyword" ]]; then
          keyword="$1"
        else
          account_name="$1"
        fi
        shift
        ;;
    esac
  done

  if [[ -z "$keyword" ]]; then
    echo "Usage: mail.sh search \"keyword\" [account] [-n count]"
    exit 1
  fi

  if [[ -n "$account_name" ]]; then
    osascript - "$account_name" "$keyword" "$max_count" <<'APPLESCRIPT'
on run argv
  set accountName to item 1 of argv
  set searchKeyword to item 2 of argv
  set maxCount to (item 3 of argv) as integer
  tell application "Mail"
    set mbox to mailbox "INBOX" of account accountName
    set allMsgs to messages of mbox
    set output to "Search results for \"" & searchKeyword & "\" in " & accountName & ":" & linefeed & linefeed
    set matchCount to 0
    repeat with i from 1 to count of allMsgs
      if matchCount >= maxCount then exit repeat
      set msg to item i of allMsgs
      set subj to subject of msg
      set sndr to sender of msg
      set bodyText to ""
      try
        set bodyText to content of msg
      end try
      if subj contains searchKeyword or sndr contains searchKeyword or bodyText contains searchKeyword then
        set matchCount to matchCount + 1
        set dt to date received of msg
        set isRead to read status of msg
        if isRead then
          set statusStr to "read"
        else
          set statusStr to "unread"
        end if
        set dtStr to (year of dt as string) & "-"
        set m to (month of dt as integer)
        if m < 10 then
          set dtStr to dtStr & "0" & (m as string)
        else
          set dtStr to dtStr & (m as string)
        end if
        set dtStr to dtStr & "-"
        set d to (day of dt as integer)
        if d < 10 then
          set dtStr to dtStr & "0" & (d as string)
        else
          set dtStr to dtStr & (d as string)
        end if
        set dtStr to dtStr & " "
        set h to (hours of dt as integer)
        if h < 10 then
          set dtStr to dtStr & "0" & (h as string)
        else
          set dtStr to dtStr & (h as string)
        end if
        set dtStr to dtStr & ":"
        set mn to (minutes of dt as integer)
        if mn < 10 then
          set dtStr to dtStr & "0" & (mn as string)
        else
          set dtStr to dtStr & (mn as string)
        end if
        set output to output & matchCount & ". (index " & i & ") [" & statusStr & "] " & subj & linefeed & "   From: " & sndr & " | Date: " & dtStr & linefeed
      end if
    end repeat
    if matchCount is 0 then
      set output to output & "No messages matching \"" & searchKeyword & "\"." & linefeed
    else
      set output to output & linefeed & "--- " & matchCount & " result(s) shown (max " & maxCount & ") ---" & linefeed
    end if
    return output
  end tell
end run
APPLESCRIPT
  else
    osascript - "$keyword" "$max_count" <<'APPLESCRIPT'
on run argv
  set searchKeyword to item 1 of argv
  set maxCount to (item 2 of argv) as integer
  tell application "Mail"
    set acctList to every account
    set output to "Search results for \"" & searchKeyword & "\":" & linefeed & linefeed
    repeat with acct in acctList
      set acctName to name of acct
      try
        set mbox to mailbox "INBOX" of acct
        set allMsgs to messages of mbox
        set output to output & "== " & acctName & " ==" & linefeed
        set matchCount to 0
        repeat with i from 1 to count of allMsgs
          if matchCount >= maxCount then exit repeat
          set msg to item i of allMsgs
          set subj to subject of msg
          set sndr to sender of msg
          set bodyText to ""
          try
            set bodyText to content of msg
          end try
          if subj contains searchKeyword or sndr contains searchKeyword or bodyText contains searchKeyword then
            set matchCount to matchCount + 1
            set dt to date received of msg
            set isRead to read status of msg
            if isRead then
              set statusStr to "read"
            else
              set statusStr to "unread"
            end if
            set dtStr to (year of dt as string) & "-"
            set m to (month of dt as integer)
            if m < 10 then
              set dtStr to dtStr & "0" & (m as string)
            else
              set dtStr to dtStr & (m as string)
            end if
            set dtStr to dtStr & "-"
            set d to (day of dt as integer)
            if d < 10 then
              set dtStr to dtStr & "0" & (d as string)
            else
              set dtStr to dtStr & (d as string)
            end if
            set dtStr to dtStr & " "
            set h to (hours of dt as integer)
            if h < 10 then
              set dtStr to dtStr & "0" & (h as string)
            else
              set dtStr to dtStr & (h as string)
            end if
            set dtStr to dtStr & ":"
            set mn to (minutes of dt as integer)
            if mn < 10 then
              set dtStr to dtStr & "0" & (mn as string)
            else
              set dtStr to dtStr & (mn as string)
            end if
            set output to output & matchCount & ". (index " & i & ") [" & statusStr & "] " & subj & linefeed & "   From: " & sndr & " | Date: " & dtStr & linefeed
          end if
        end repeat
        if matchCount is 0 then
          set output to output & "  No matches." & linefeed
        end if
        set output to output & linefeed
      on error
        set output to output & "== " & acctName & " (no INBOX) ==" & linefeed & linefeed
      end try
    end repeat
    return output
  end tell
end run
APPLESCRIPT
  fi
}

cmd_flag() {
  ensure_mail_running
  local account_name="$1"
  local mailbox_name="$2"
  local msg_index="$3"

  if [[ -z "$account_name" || -z "$mailbox_name" || -z "$msg_index" ]]; then
    echo "Usage: mail.sh flag <account> <mailbox> <index>"
    exit 1
  fi

  osascript - "$account_name" "$mailbox_name" "$msg_index" <<'APPLESCRIPT'
on run argv
  set accountName to item 1 of argv
  set mailboxName to item 2 of argv
  set msgIndex to (item 3 of argv) as integer
  tell application "Mail"
    set mbox to mailbox mailboxName of account accountName
    set msg to message msgIndex of mbox
    set currentFlag to flagged status of msg
    if currentFlag then
      set flagged status of msg to false
      return "Message " & msgIndex & " unflagged: " & subject of msg
    else
      set flagged status of msg to true
      return "Message " & msgIndex & " flagged: " & subject of msg
    end if
  end tell
end run
APPLESCRIPT
}

cmd_mark_read() {
  ensure_mail_running
  local account_name="$1"
  local mailbox_name="$2"
  local msg_index="$3"

  if [[ -z "$account_name" || -z "$mailbox_name" || -z "$msg_index" ]]; then
    echo "Usage: mail.sh mark-read <account> <mailbox> <index>"
    exit 1
  fi

  osascript - "$account_name" "$mailbox_name" "$msg_index" <<'APPLESCRIPT'
on run argv
  set accountName to item 1 of argv
  set mailboxName to item 2 of argv
  set msgIndex to (item 3 of argv) as integer
  tell application "Mail"
    set mbox to mailbox mailboxName of account accountName
    set msg to message msgIndex of mbox
    set read status of msg to true
    return "Message " & msgIndex & " marked as read: " & subject of msg
  end tell
end run
APPLESCRIPT
}

cmd_move() {
  ensure_mail_running
  local account_name="$1"
  local mailbox_name="$2"
  local msg_index="$3"
  local target_mailbox="$4"

  if [[ -z "$account_name" || -z "$mailbox_name" || -z "$msg_index" || -z "$target_mailbox" ]]; then
    echo "Usage: mail.sh move <account> <mailbox> <index> <target-mailbox>"
    exit 1
  fi

  osascript - "$account_name" "$mailbox_name" "$msg_index" "$target_mailbox" <<'APPLESCRIPT'
on run argv
  set accountName to item 1 of argv
  set mailboxName to item 2 of argv
  set msgIndex to (item 3 of argv) as integer
  set targetMailboxName to item 4 of argv
  tell application "Mail"
    set srcMbox to mailbox mailboxName of account accountName
    set targetMbox to mailbox targetMailboxName of account accountName
    set msg to message msgIndex of srcMbox
    set subj to subject of msg
    move msg to targetMbox
    return "Moved message " & msgIndex & " to " & targetMailboxName & ": " & subj
  end tell
end run
APPLESCRIPT
}

cmd_trash() {
  ensure_mail_running
  local account_name="$1"
  local mailbox_name="$2"
  local msg_index="$3"

  if [[ -z "$account_name" || -z "$mailbox_name" || -z "$msg_index" ]]; then
    echo "Usage: mail.sh trash <account> <mailbox> <index>"
    exit 1
  fi

  # Mail's "delete" command moves to Trash (does NOT permanently delete)
  osascript - "$account_name" "$mailbox_name" "$msg_index" <<'APPLESCRIPT'
on run argv
  set accountName to item 1 of argv
  set mailboxName to item 2 of argv
  set msgIndex to (item 3 of argv) as integer
  tell application "Mail"
    set mbox to mailbox mailboxName of account accountName
    set msg to message msgIndex of mbox
    set subj to subject of msg
    delete msg
    return "Moved to Trash (recoverable): " & subj
  end tell
end run
APPLESCRIPT
}

cmd_batch_trash() {
  ensure_mail_running
  local account_name="$1"
  local mailbox_name="$2"
  local start_index="$3"
  local end_index="$4"

  if [[ -z "$account_name" || -z "$mailbox_name" || -z "$start_index" || -z "$end_index" ]]; then
    echo "Usage: mail.sh batch-trash <account> <mailbox> <start-index> <end-index>"
    exit 1
  fi

  if (( start_index > end_index )); then
    echo "[Error] start-index ($start_index) must be <= end-index ($end_index)"
    exit 1
  fi

  # Delete from highest index to lowest to avoid index shifting
  osascript - "$account_name" "$mailbox_name" "$start_index" "$end_index" <<'APPLESCRIPT'
on run argv
  set accountName to item 1 of argv
  set mailboxName to item 2 of argv
  set startIdx to (item 3 of argv) as integer
  set endIdx to (item 4 of argv) as integer
  tell application "Mail"
    set mbox to mailbox mailboxName of account accountName
    set totalMsgs to count of messages of mbox
    if endIdx > totalMsgs then set endIdx to totalMsgs
    set trashCount to 0
    set output to "Batch trash for " & mailboxName & " (" & accountName & "), range " & startIdx & "-" & endIdx & ":" & linefeed
    -- Delete from end to start to preserve indices
    repeat with i from endIdx to startIdx by -1
      set msg to message i of mbox
      set subj to subject of msg
      delete msg
      set trashCount to trashCount + 1
      set output to output & "  Trashed: " & subj & linefeed
    end repeat
    set output to output & linefeed & "--- " & trashCount & " message(s) moved to Trash (recoverable) ---"
    return output
  end tell
end run
APPLESCRIPT
}

# --- Main dispatch ---

case "$COMMAND" in
  accounts)
    cmd_accounts
    ;;
  mailboxes)
    cmd_mailboxes "$@"
    ;;
  inbox)
    cmd_inbox "$@"
    ;;
  read)
    cmd_read "$@"
    ;;
  unread)
    cmd_unread "$@"
    ;;
  search)
    cmd_search "$@"
    ;;
  flag)
    cmd_flag "$@"
    ;;
  mark-read)
    cmd_mark_read "$@"
    ;;
  move)
    cmd_move "$@"
    ;;
  trash)
    cmd_trash "$@"
    ;;
  batch-trash)
    cmd_batch_trash "$@"
    ;;
  help|--help|-h)
    echo "Mail.app CLI helper"
    echo ""
    echo "Usage: mail.sh <command> [options]"
    echo ""
    echo "Commands:"
    echo "  accounts                                      List mail accounts"
    echo "  mailboxes [account]                           List mailboxes"
    echo "  inbox [account] [-n count]                    List inbox messages (default 20)"
    echo "  read <account> <mailbox> <index>              Read full message"
    echo "  unread [account] [-n count]                   List unread messages"
    echo "  search \"keyword\" [account] [-n count]         Search messages"
    echo "  flag <account> <mailbox> <index>              Toggle flag"
    echo "  mark-read <account> <mailbox> <index>         Mark as read"
    echo "  move <account> <mailbox> <index> <target>     Move to mailbox"
    echo "  trash <account> <mailbox> <index>             Move to Trash (recoverable)"
    echo "  batch-trash <account> <mailbox> <start> <end> Batch move to Trash"
    echo ""
    echo "Note: trash/batch-trash move messages to Trash. They do NOT permanently delete."
    ;;
  *)
    echo "Unknown command: $COMMAND"
    echo "Run 'mail.sh help' for usage."
    exit 1
    ;;
esac
