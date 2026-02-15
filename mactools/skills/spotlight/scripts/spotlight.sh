#!/bin/bash
# Spotlight search helper — wraps mdfind with formatted output
# Usage: spotlight.sh <mode> [options] <query>
#
# Modes:
#   search   — search files by content or name
#   meta     — show metadata for a file
#   recent   — find recently modified files
#
# Options:
#   -d <dir>     scope to directory
#   -t <type>    file type filter (md, pdf, swift, py, txt, doc, xls, ppt, pages, keynote, numbers, code, image, audio, video)
#   -n <count>   max results (default: 20)
#   -name        match file name only (not content)

set -eo pipefail

MODE="${1:-search}"
shift || true

# Defaults
SCOPE=""
TYPE_FILTER=""
MAX_RESULTS=20
NAME_ONLY=false
QUERY=""

# Resolve content type from short name
resolve_type() {
  local key="$1"
  case "$key" in
    md)       echo "net.daringfireball.markdown" ;;
    pdf)      echo "com.adobe.pdf" ;;
    swift)    echo "public.swift-source" ;;
    py)       echo "public.python-script" ;;
    txt)      echo "public.plain-text" ;;
    doc)      echo "com.microsoft.word.doc" ;;
    docx)     echo "org.openxmlformats.wordprocessingml.document" ;;
    xls)      echo "com.microsoft.excel.xls" ;;
    xlsx)     echo "org.openxmlformats.spreadsheetml.sheet" ;;
    ppt)      echo "com.microsoft.powerpoint.ppt" ;;
    pptx)     echo "org.openxmlformats.presentationml.presentation" ;;
    pages)    echo "com.apple.iwork.pages.sffpages" ;;
    keynote)  echo "com.apple.iwork.keynote.sffkey" ;;
    numbers)  echo "com.apple.iwork.numbers.sffnumbers" ;;
    html)     echo "public.html" ;;
    json)     echo "public.json" ;;
    yaml)     echo "public.yaml" ;;
    csv)      echo "public.comma-separated-values-text" ;;
    # Broad type groups (use ContentTypeTree)
    code)     echo "GROUP:public.source-code" ;;
    image)    echo "GROUP:public.image" ;;
    audio)    echo "GROUP:public.audio" ;;
    video)    echo "GROUP:public.movie" ;;
    *)        echo "" ;;
  esac
}

# Parse options
while [[ $# -gt 0 ]]; do
  case "$1" in
    -d)  SCOPE="$2"; shift 2 ;;
    -t)  TYPE_FILTER="$2"; shift 2 ;;
    -n)  MAX_RESULTS="$2"; shift 2 ;;
    -name) NAME_ONLY=true; shift ;;
    *)   QUERY="${QUERY:+$QUERY }$1"; shift ;;
  esac
done

format_size() {
  local size=$1
  if (( size >= 1073741824 )); then
    printf "%.1f GB" "$(echo "scale=1; $size / 1073741824" | bc)"
  elif (( size >= 1048576 )); then
    printf "%.1f MB" "$(echo "scale=1; $size / 1048576" | bc)"
  elif (( size >= 1024 )); then
    printf "%.1f KB" "$(echo "scale=1; $size / 1024" | bc)"
  else
    printf "%d B" "$size"
  fi
}

format_results() {
  local count=0
  while IFS= read -r filepath; do
    [[ -z "$filepath" ]] && continue
    (( count >= MAX_RESULTS )) && break

    local fname
    fname=$(basename "$filepath")

    # Get metadata in one call
    local meta
    meta=$(mdls -name kMDItemFSSize -name kMDItemContentModificationDate -name kMDItemContentType "$filepath" 2>/dev/null) || true

    local size mdate ctype
    size=$(echo "$meta" | grep kMDItemFSSize | awk '{print $3}')
    mdate=$(echo "$meta" | grep kMDItemContentModificationDate | awk '{print $3, $4}' | cut -d'+' -f1 | xargs)
    ctype=$(echo "$meta" | grep kMDItemContentType | awk -F'"' '{print $2}')

    local size_str="?"
    if [[ "$size" =~ ^[0-9]+$ ]]; then
      size_str=$(format_size "$size")
    fi

    local date_str="${mdate:0:10}"
    [[ -z "$date_str" || "$date_str" == "(null)" ]] && date_str="?"

    printf "%d. %s\n   Path: %s\n   Type: %s | Size: %s | Modified: %s\n\n" \
      $((count + 1)) "$fname" "$filepath" "${ctype:-unknown}" "$size_str" "$date_str"

    ((count++))
  done

  if (( count == 0 )); then
    echo "No results found."
  else
    echo "--- $count result(s) shown (max $MAX_RESULTS) ---"
  fi
}

# Build type condition for mdfind query
build_type_condition() {
  local resolved="$1"
  if [[ "$resolved" == GROUP:* ]]; then
    local uti="${resolved#GROUP:}"
    echo "kMDItemContentTypeTree == '${uti}'"
  else
    echo "kMDItemContentType == '${resolved}'"
  fi
}

case "$MODE" in
  search)
    if [[ -z "$QUERY" ]]; then
      echo "Usage: spotlight.sh search [-d dir] [-t type] [-n count] [-name] <query>"
      exit 1
    fi

    SCOPE_ARGS=""
    [[ -n "$SCOPE" ]] && SCOPE_ARGS="-onlyin $SCOPE"

    if $NAME_ONLY; then
      if [[ -n "$TYPE_FILTER" ]]; then
        resolved=$(resolve_type "$TYPE_FILTER")
        if [[ -z "$resolved" ]]; then
          echo "Unknown type: $TYPE_FILTER"
          exit 1
        fi
        type_cond=$(build_type_condition "$resolved")
        mdfind $SCOPE_ARGS "kMDItemFSName == '*${QUERY}*'c && ${type_cond}" | format_results
      else
        mdfind $SCOPE_ARGS -name "$QUERY" | format_results
      fi
    else
      # Content search
      if [[ -n "$TYPE_FILTER" ]]; then
        resolved=$(resolve_type "$TYPE_FILTER")
        if [[ -z "$resolved" ]]; then
          echo "Unknown type: $TYPE_FILTER"
          exit 1
        fi
        type_cond=$(build_type_condition "$resolved")
        mdfind $SCOPE_ARGS "kMDItemTextContent == '*${QUERY}*'c && ${type_cond}" | format_results
      else
        mdfind $SCOPE_ARGS "$QUERY" | format_results
      fi
    fi
    ;;

  meta)
    if [[ -z "$QUERY" ]]; then
      echo "Usage: spotlight.sh meta <file_path>"
      exit 1
    fi
    if [[ ! -e "$QUERY" ]]; then
      echo "File not found: $QUERY"
      exit 1
    fi
    mdls "$QUERY"
    ;;

  recent)
    DAYS="${QUERY:-7}"
    if ! [[ "$DAYS" =~ ^[0-9]+$ ]]; then
      echo "Usage: spotlight.sh recent [-d dir] [-t type] [-n count] [days]"
      echo "  days: number of days to look back (default: 7)"
      exit 1
    fi

    SCOPE_ARGS=""
    [[ -n "$SCOPE" ]] && SCOPE_ARGS="-onlyin $SCOPE"

    MDFIND_QUERY="kMDItemContentModificationDate >= \$time.today(-${DAYS})"

    if [[ -n "$TYPE_FILTER" ]]; then
      resolved=$(resolve_type "$TYPE_FILTER")
      if [[ -n "$resolved" ]]; then
        type_cond=$(build_type_condition "$resolved")
        MDFIND_QUERY="$MDFIND_QUERY && ${type_cond}"
      fi
    fi

    mdfind $SCOPE_ARGS "$MDFIND_QUERY" | format_results
    ;;

  *)
    echo "Unknown mode: $MODE"
    echo "Available modes: search, meta, recent"
    exit 1
    ;;
esac
