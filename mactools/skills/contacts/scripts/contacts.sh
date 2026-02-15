#!/bin/bash
# Contacts.app helper — wraps AppleScript for contact lookup
# Usage: contacts.sh <command> [options] [args]
#
# Commands:
#   search "name"        — search contacts by name (partial match)
#   show "Full Name"     — show full contact details
#   list                 — list all contacts (name only)
#   groups               — list all groups
#   group "Group Name"   — list contacts in a group
#
# Options:
#   -n <count>   max results (default: 20)

set -eo pipefail

COMMAND="${1:-}"
shift || true

# Defaults
MAX_RESULTS=20

# Parse options, collecting remaining args
ARGS=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    -n) MAX_RESULTS="$2"; shift 2 ;;
    *)  ARGS+=("$1"); shift ;;
  esac
done

case "$COMMAND" in
  search)
    QUERY="${ARGS[0]:-}"
    if [[ -z "$QUERY" ]]; then
      echo "Usage: contacts.sh search [-n count] \"name\""
      exit 1
    fi

    osascript - "$QUERY" "$MAX_RESULTS" <<'APPLESCRIPT'
on run argv
  set query to item 1 of argv
  set maxResults to (item 2 of argv) as integer
  tell application "Contacts"
    set matchedPeople to every person whose name contains query
    set resultCount to count of matchedPeople
    if resultCount is 0 then
      return "No contacts found matching: " & query
    end if
    set maxCount to maxResults
    if resultCount < maxCount then set maxCount to resultCount
    set output to ""
    repeat with i from 1 to maxCount
      set p to item i of matchedPeople
      set pName to name of p
      -- Collect phones
      set phoneList to ""
      try
        set phoneNumbers to value of every phone of p
        set phoneLabels to label of every phone of p
        repeat with j from 1 to count of phoneNumbers
          set pNum to item j of phoneNumbers
          set pLabel to item j of phoneLabels
          -- Clean label
          set cleanLabel to pLabel
          try
            if pLabel contains "!" then
              set AppleScript's text item delimiters to "<"
              set parts to text items of pLabel
              if (count of parts) > 1 then
                set lastPart to item 2 of parts
                set AppleScript's text item delimiters to ">"
                set cleanLabel to text item 1 of lastPart
              end if
              set AppleScript's text item delimiters to ""
            end if
          end try
          if phoneList is "" then
            set phoneList to pNum & " (" & cleanLabel & ")"
          else
            set phoneList to phoneList & ", " & pNum & " (" & cleanLabel & ")"
          end if
        end repeat
      end try
      -- Collect emails
      set emailList to ""
      try
        set emailAddrs to value of every email of p
        set emailLabels to label of every email of p
        repeat with j from 1 to count of emailAddrs
          set eAddr to item j of emailAddrs
          set eLabel to item j of emailLabels
          set cleanLabel to eLabel
          try
            if eLabel contains "!" then
              set AppleScript's text item delimiters to "<"
              set parts to text items of eLabel
              if (count of parts) > 1 then
                set lastPart to item 2 of parts
                set AppleScript's text item delimiters to ">"
                set cleanLabel to text item 1 of lastPart
              end if
              set AppleScript's text item delimiters to ""
            end if
          end try
          if emailList is "" then
            set emailList to eAddr & " (" & cleanLabel & ")"
          else
            set emailList to emailList & ", " & eAddr & " (" & cleanLabel & ")"
          end if
        end repeat
      end try
      -- Company
      set comp to ""
      try
        set comp to organization of p
      end try
      -- Build summary line
      set line to (i as text) & ". " & pName
      if comp is not "" and comp is not missing value then
        set line to line & " — " & comp
      end if
      if phoneList is not "" then
        set line to line & return & "   Phone: " & phoneList
      end if
      if emailList is not "" then
        set line to line & return & "   Email: " & emailList
      end if
      set output to output & line & return
    end repeat
    set output to output & "---" & return & maxCount & " of " & resultCount & " result(s) shown (max " & maxResults & ")"
    return output
  end tell
end run
APPLESCRIPT
    ;;

  show)
    CONTACT_NAME="${ARGS[0]:-}"
    if [[ -z "$CONTACT_NAME" ]]; then
      echo "Usage: contacts.sh show \"Full Name\""
      exit 1
    fi

    osascript - "$CONTACT_NAME" <<'APPLESCRIPT'
on run argv
  set contactName to item 1 of argv
  tell application "Contacts"
    set matchedPeople to every person whose name is contactName
    if (count of matchedPeople) is 0 then
      -- Try partial match
      set matchedPeople to every person whose name contains contactName
      if (count of matchedPeople) is 0 then
        return "No contact found: " & contactName
      end if
    end if
    set p to item 1 of matchedPeople
    set output to "Name: " & name of p

    -- Company
    try
      set comp to organization of p
      if comp is not missing value and comp is not "" then
        set output to output & return & "Company: " & comp
      end if
    end try

    -- Title
    try
      set t to job title of p
      if t is not missing value and t is not "" then
        set output to output & return & "Title: " & t
      end if
    end try

    -- Department
    try
      set dept to department of p
      if dept is not missing value and dept is not "" then
        set output to output & return & "Department: " & dept
      end if
    end try

    -- Phones
    try
      set phoneNumbers to value of every phone of p
      set phoneLabels to label of every phone of p
      if (count of phoneNumbers) > 0 then
        set phoneList to ""
        repeat with j from 1 to count of phoneNumbers
          set pNum to item j of phoneNumbers
          set pLabel to item j of phoneLabels
          set cleanLabel to pLabel
          try
            if pLabel contains "!" then
              set AppleScript's text item delimiters to "<"
              set parts to text items of pLabel
              if (count of parts) > 1 then
                set lastPart to item 2 of parts
                set AppleScript's text item delimiters to ">"
                set cleanLabel to text item 1 of lastPart
              end if
              set AppleScript's text item delimiters to ""
            end if
          end try
          if phoneList is "" then
            set phoneList to pNum & " (" & cleanLabel & ")"
          else
            set phoneList to phoneList & ", " & pNum & " (" & cleanLabel & ")"
          end if
        end repeat
        set output to output & return & "Phone: " & phoneList
      end if
    end try

    -- Emails
    try
      set emailAddrs to value of every email of p
      set emailLabels to label of every email of p
      if (count of emailAddrs) > 0 then
        set emailList to ""
        repeat with j from 1 to count of emailAddrs
          set eAddr to item j of emailAddrs
          set eLabel to item j of emailLabels
          set cleanLabel to eLabel
          try
            if eLabel contains "!" then
              set AppleScript's text item delimiters to "<"
              set parts to text items of eLabel
              if (count of parts) > 1 then
                set lastPart to item 2 of parts
                set AppleScript's text item delimiters to ">"
                set cleanLabel to text item 1 of lastPart
              end if
              set AppleScript's text item delimiters to ""
            end if
          end try
          if emailList is "" then
            set emailList to eAddr & " (" & cleanLabel & ")"
          else
            set emailList to emailList & ", " & eAddr & " (" & cleanLabel & ")"
          end if
        end repeat
        set output to output & return & "Email: " & emailList
      end if
    end try

    -- Addresses
    try
      set addrList to every address of p
      if (count of addrList) > 0 then
        set addrOutput to ""
        repeat with a in addrList
          set addrLabel to label of a
          set cleanLabel to addrLabel
          try
            if addrLabel contains "!" then
              set AppleScript's text item delimiters to "<"
              set parts to text items of addrLabel
              if (count of parts) > 1 then
                set lastPart to item 2 of parts
                set AppleScript's text item delimiters to ">"
                set cleanLabel to text item 1 of lastPart
              end if
              set AppleScript's text item delimiters to ""
            end if
          end try
          set addrStr to ""
          try
            set s to street of a
            if s is not missing value and s is not "" then set addrStr to s
          end try
          try
            set c to city of a
            if c is not missing value and c is not "" then
              if addrStr is not "" then set addrStr to addrStr & ", "
              set addrStr to addrStr & c
            end if
          end try
          try
            set st to state of a
            if st is not missing value and st is not "" then
              if addrStr is not "" then set addrStr to addrStr & ", "
              set addrStr to addrStr & st
            end if
          end try
          try
            set z to zip of a
            if z is not missing value and z is not "" then
              if addrStr is not "" then set addrStr to addrStr & " "
              set addrStr to addrStr & z
            end if
          end try
          try
            set co to country of a
            if co is not missing value and co is not "" then
              if addrStr is not "" then set addrStr to addrStr & ", "
              set addrStr to addrStr & co
            end if
          end try
          if addrStr is not "" then
            if addrOutput is "" then
              set addrOutput to addrStr & " (" & cleanLabel & ")"
            else
              set addrOutput to addrOutput & "; " & addrStr & " (" & cleanLabel & ")"
            end if
          end if
        end repeat
        if addrOutput is not "" then
          set output to output & return & "Address: " & addrOutput
        end if
      end if
    end try

    -- Birthday
    try
      set bday to birth date of p
      if bday is not missing value then
        set y to year of bday
        set m to month of bday as integer
        set d to day of bday
        set mStr to text -2 thru -1 of ("0" & m)
        set dStr to text -2 thru -1 of ("0" & d)
        set output to output & return & "Birthday: " & y & "-" & mStr & "-" & dStr
      end if
    end try

    -- Notes
    try
      set n to note of p
      if n is not missing value and n is not "" then
        set output to output & return & "Notes: " & n
      end if
    end try

    return output
  end tell
end run
APPLESCRIPT
    ;;

  list)
    osascript - "$MAX_RESULTS" <<'APPLESCRIPT'
on run argv
  set maxResults to (item 1 of argv) as integer
  tell application "Contacts"
    set allPeople to every person
    set totalCount to count of allPeople
    if totalCount is 0 then
      return "No contacts found."
    end if
    set maxCount to maxResults
    if totalCount < maxCount then set maxCount to totalCount
    set output to ""
    repeat with i from 1 to maxCount
      set p to item i of allPeople
      set output to output & (i as text) & ". " & name of p & return
    end repeat
    set output to output & "---" & return & maxCount & " of " & totalCount & " contact(s) shown (max " & maxResults & ")"
    return output
  end tell
end run
APPLESCRIPT
    ;;

  groups)
    osascript -e "
      tell application \"Contacts\"
        set allGroups to every group
        if (count of allGroups) is 0 then
          return \"No groups found.\"
        end if
        set output to \"\"
        repeat with i from 1 to count of allGroups
          set g to item i of allGroups
          set memberCount to count of every person of g
          set output to output & (i as text) & \". \" & name of g & \" (\" & memberCount & \" contacts)\" & return
        end repeat
        return output
      end tell
    "
    ;;

  group)
    GROUP_NAME="${ARGS[0]:-}"
    if [[ -z "$GROUP_NAME" ]]; then
      echo "Usage: contacts.sh group \"Group Name\""
      exit 1
    fi

    osascript - "$GROUP_NAME" "$MAX_RESULTS" <<'APPLESCRIPT'
on run argv
  set groupName to item 1 of argv
  set maxResults to (item 2 of argv) as integer
  tell application "Contacts"
    try
      set g to first group whose name is groupName
    on error
      return "Group not found: " & groupName
    end try
    set members to every person of g
    set totalCount to count of members
    if totalCount is 0 then
      return "Group \"" & groupName & "\" has no contacts."
    end if
    set maxCount to maxResults
    if totalCount < maxCount then set maxCount to totalCount
    set output to "Group: " & groupName & return & return
    repeat with i from 1 to maxCount
      set p to item i of members
      set pName to name of p
      set comp to ""
      try
        set comp to organization of p
      end try
      set line to (i as text) & ". " & pName
      if comp is not "" and comp is not missing value then
        set line to line & " — " & comp
      end if
      set output to output & line & return
    end repeat
    set output to output & "---" & return & maxCount & " of " & totalCount & " contact(s) shown (max " & maxResults & ")"
    return output
  end tell
end run
APPLESCRIPT
    ;;

  *)
    echo "Usage: contacts.sh <command> [options] [args]"
    echo ""
    echo "Commands:"
    echo "  search \"name\"        Search contacts by name (partial match)"
    echo "  show \"Full Name\"     Show full contact details"
    echo "  list                 List all contacts (name only)"
    echo "  groups               List all groups"
    echo "  group \"Group Name\"   List contacts in a group"
    echo ""
    echo "Options:"
    echo "  -n <count>   Max results (default: 20)"
    exit 1
    ;;
esac
