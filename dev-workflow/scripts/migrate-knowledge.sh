#!/bin/bash
# One-time migration: consolidate project lessons into ~/.claude/knowledge/
#
# Usage:
#   bash migrate-knowledge.sh              # Execute migration
#   bash migrate-knowledge.sh --dry-run    # Preview only, no writes
#
# Sources:
#   ~/Code/Projects/*/docs/09-lessons-learned/*.md
#   ~/.claude/rag/lessons/*.md

set -uo pipefail

TARGET="$HOME/.claude/knowledge"
DRY_RUN=false
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=true
  echo "=== DRY RUN — no files will be written ==="
  echo
fi

# Counters
migrated=0
skipped_dup=0
skipped_readme=0
errors=0

# Track MD5 hashes for dedup
declare -A seen_hashes

# --- Helper: slugify a string ---
slugify() {
  local input="$1"
  # Remove .md extension if present
  input="${input%.md}"
  # Transliterate, lowercase, replace non-alnum with hyphens
  echo "$input" \
    | sed 's/[^a-zA-Z0-9 -]/-/g' \
    | tr '[:upper:]' '[:lower:]' \
    | sed 's/[^a-z0-9]/-/g; s/--*/-/g; s/^-//; s/-$//' \
    | cut -c1-40
}

# --- Helper: extract title from markdown ---
extract_title() {
  local file="$1"
  # Try YAML frontmatter title field
  local title=""
  if head -1 "$file" | grep -q '^---$'; then
    title=$(sed -n '/^---$/,/^---$/{ /^title:/s/^title:[[:space:]]*//p; }' "$file" 2>/dev/null)
  fi
  if [[ -n "$title" ]]; then
    echo "$title"
    return
  fi
  # Try first H1 heading
  title=$(grep -m1 '^# ' "$file" 2>/dev/null | sed 's/^# //')
  if [[ -n "$title" ]]; then
    echo "$title"
    return
  fi
  # Fallback to filename without extension
  basename "$file" .md
}

# --- Helper: extract date ---
extract_date() {
  local file="$1"
  local date=""

  # Try YAML frontmatter date field
  if head -1 "$file" | grep -q '^---$'; then
    date=$(sed -n '/^---$/,/^---$/{ /^date:/s/^date:[[:space:]]*//p; }' "$file" 2>/dev/null)
    if [[ -n "$date" && "$date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2} ]]; then
      echo "${date:0:10}"
      return
    fi
    # Try created field
    date=$(sed -n '/^---$/,/^---$/{ /^created:/s/^created:[[:space:]]*//p; }' "$file" 2>/dev/null)
    if [[ -n "$date" && "$date" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2} ]]; then
      echo "${date:0:10}"
      return
    fi
  fi

  # Try date in filename
  local bn
  bn=$(basename "$file" .md)
  if [[ "$bn" =~ ^([0-9]{4}-[0-9]{2}-[0-9]{2}) ]]; then
    echo "${BASH_REMATCH[1]}"
    return
  fi

  # Try > 创建日期: pattern in content
  date=$(grep -m1 '创建日期' "$file" 2>/dev/null | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}' || true)
  if [[ -n "$date" ]]; then
    echo "$date"
    return
  fi

  # Fallback to file modification date
  stat -f '%Sm' -t '%Y-%m-%d' "$file" 2>/dev/null || date '+%Y-%m-%d'
}

# --- Helper: infer category from content ---
infer_category() {
  local file="$1"
  local content
  content=$(tr '[:upper:]' '[:lower:]' < "$file")

  # Try YAML frontmatter category field first
  if head -1 "$file" | grep -q '^---$'; then
    local cat
    cat=$(sed -n '/^---$/,/^---$/{ /^category:/s/^category:[[:space:]]*//p; }' "$file" 2>/dev/null)
    if [[ -n "$cat" ]]; then
      echo "$cat"
      return
    fi
  fi

  # Content-based inference
  if echo "$content" | grep -qiE 'api|sdk|framework|migration|deprecated|undocumented|协议|引擎'; then
    echo "api-usage"
  elif echo "$content" | grep -qiE 'bug|crash|error|symptom|root.cause|根因|报错|修复|pitfall'; then
    echo "bug-postmortem"
  elif echo "$content" | grep -qiE 'architect|design|debt|pattern|adr|决策|架构'; then
    echo "architecture"
  elif echo "$content" | grep -qiE 'audit|stability|稳定性'; then
    echo "stability-audit"
  elif echo "$content" | grep -qiE 'platform|constraint|entitlement|sandbox|extension|sms.filter|share.extension'; then
    echo "platform-constraints"
  elif echo "$content" | grep -qiE 'data|research|科学性|数据'; then
    echo "data-research"
  else
    echo "uncategorized"
  fi
}

# --- Helper: extract existing keywords ---
extract_keywords() {
  local file="$1"
  if ! head -1 "$file" | grep -q '^---$'; then
    echo ""
    return
  fi
  local kw
  kw=$(sed -n '/^---$/,/^---$/{ /^keywords:/s/^keywords:[[:space:]]*//p; }' "$file" 2>/dev/null)
  if [[ -n "$kw" ]]; then
    # Clean up YAML list format: [a, b, c] -> a, b, c
    echo "$kw" | sed 's/^\[//;s/\]$//;s/,  */, /g'
    return
  fi
  echo ""
}

# --- Helper: extract project name from path ---
extract_project() {
  local file="$1"
  echo "$file" | sed -n 's|.*/Code/Projects/\([^/]*\)/.*|\1|p'
}

# --- Helper: check if file has YAML frontmatter ---
has_frontmatter() {
  head -1 "$1" | grep -q '^---$'
}

# --- Helper: extract body (after frontmatter if present) ---
extract_body() {
  local file="$1"
  if has_frontmatter "$file"; then
    # Skip everything between first --- and second ---
    awk 'BEGIN{n=0} /^---$/{n++; next} n>=2{print}' "$file"
  else
    cat "$file"
  fi
}

# --- Main migration ---
echo "Scanning sources..."
echo

# Collect all source files
sources=()

# Project lessons (top-level files only)
for f in ~/Code/Projects/*/docs/09-lessons-learned/*.md; do
  [[ -f "$f" ]] || continue
  sources+=("$f")
done

# Subdirectory files (e.g., Runetic's rules-system-evolution/)
for f in ~/Code/Projects/*/docs/09-lessons-learned/*/*.md; do
  [[ -f "$f" ]] || continue
  sources+=("$f")
done

# Global RAG lessons
for f in ~/.claude/rag/lessons/*.md; do
  [[ -f "$f" ]] || continue
  sources+=("$f")
done

echo "Found ${#sources[@]} source files"
echo

for file in "${sources[@]}"; do
  bn=$(basename "$file")

  # Skip READMEs
  if [[ "$bn" == "README.md" ]]; then
    ((skipped_readme++))
    continue
  fi

  # Dedup by MD5
  hash=$(md5 -q "$file" 2>/dev/null || md5sum "$file" 2>/dev/null | cut -d' ' -f1)
  if [[ -n "${seen_hashes[$hash]:-}" ]]; then
    echo "  SKIP (duplicate of $(basename "${seen_hashes[$hash]}")): $file"
    ((skipped_dup++))
    continue
  fi
  seen_hashes[$hash]="$file"

  # Extract metadata
  title=$(extract_title "$file")
  entry_date=$(extract_date "$file")
  category=$(infer_category "$file")
  keywords=$(extract_keywords "$file")
  project=$(extract_project "$file")

  # Generate slug and target path
  slug=$(slugify "$title")
  if [[ -z "$slug" || ${#slug} -lt 3 ]]; then
    slug=$(slugify "$bn")
  fi
  if [[ -z "$slug" || ${#slug} -lt 3 ]]; then
    # Chinese-only title: use pinyin-like fallback from filename chars
    slug="entry-$(echo "$bn" | md5 -q 2>/dev/null | cut -c1-8 || echo "unknown")"
  fi
  target_dir="$TARGET/$category"
  target_file="$target_dir/${entry_date}-${slug}.md"

  # Handle filename collision
  if [[ -f "$target_file" ]]; then
    counter=2
    while [[ -f "${target_dir}/${entry_date}-${slug}-${counter}.md" ]]; do
      ((counter++))
    done
    target_file="${target_dir}/${entry_date}-${slug}-${counter}.md"
  fi

  if $DRY_RUN; then
    echo "  MIGRATE: $file"
    echo "       ->  $target_file"
    echo "           category=$category  date=$entry_date  project=${project:-global}"
    if [[ -n "$keywords" ]]; then
      echo "           keywords=$keywords"
    fi
    echo
  else
    mkdir -p "$target_dir"

    body=$(extract_body "$file")

    # Build the normalized file
    {
      echo "---"
      echo "category: $category"
      if [[ -n "$keywords" ]]; then
        echo "keywords: [$keywords]"
      fi
      echo "date: $entry_date"
      if [[ -n "$project" ]]; then
        echo "source_project: $project"
      fi
      echo "---"

      # If body doesn't start with a heading, add the title as H1
      first_content_line=$(echo "$body" | sed '/^[[:space:]]*$/d' | head -1)
      if [[ ! "$first_content_line" =~ ^#\  ]]; then
        echo ""
        echo "# $title"
      fi

      echo "$body"
    } > "$target_file"

    echo "  OK: $(basename "$file") -> $target_file"
  fi

  ((migrated++))
done

echo
echo "=== Summary ==="
echo "  Migrated:         $migrated"
echo "  Skipped (dup):    $skipped_dup"
echo "  Skipped (readme): $skipped_readme"
echo "  Errors:           $errors"
if $DRY_RUN; then
  echo
  echo "This was a dry run. Run without --dry-run to execute."
fi
