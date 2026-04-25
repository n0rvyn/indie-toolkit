---
name: notion-page-sync
description: Use this skill to sync local markdown files or a directory to Notion pages under a configured parent page. Trigger phrases include "sync to Notion", "push docs to Notion", "同步到 Notion", "/notion-page-sync <path>". Project-level config lives in .claude/notion-sync.local.md.
disable-model-invocation: false
allowed-tools: Bash(NOTION_TOKEN=*), Bash(python3*), Read, Write, Edit
---

# Notion Page Sync

Sync local markdown files to Notion pages under a configured parent page. Generic — usable from any project that has a `.claude/notion-sync.local.md` config file.

API operations are delegated to the sibling `notion-with-api` skill; this skill describes only the sync workflow. For full CLI reference (`verify`, `list-children`, `update-page`, `create-page`, etc.), see `notion-with-api`.

## Inputs

The invoker supplies one or more paths via the skill's `args` (when called as `Skill(skill="notion-page-sync", args="...")`) or in the user message. Accept any of:

- A single file: `docs/10-app-store-connect/privacy-policy.md`
- A directory: `docs/10-app-store-connect/` (sync every `.md` inside, non-recursive)
- Multiple files separated by spaces: `docs/a.md docs/b.md` (used when another skill delegates a subset of changed files)

Resolve each input independently. If a directory is mixed in with explicit files, expand the directory first then deduplicate.

## Configuration (must read first)

Project config: `.claude/notion-sync.local.md` with YAML frontmatter:

```yaml
---
token: "ntn_..."           # Notion API token (sole token source for this skill)
workspace: "Delphi"        # Expected workspace name (verify check)
parent_page_id: "..."      # Target parent page; all synced files become its children
pages:                     # Auto-maintained mapping; do not edit by hand
  privacy-policy.md: "2fefad3c-..."
  terms-of-use.md: "302fad3c-..."
---
```

If the file is absent, stop and tell the user to create it. Do not fall back to environment variables, do not read tokens from any other location.

## Workflow

State files are not written until Step 5. Steps 1–4 build the result in memory; Step 5 is the sole writer to `.claude/notion-sync.local.md`. This avoids partial writes if a mid-loop create/update fails.

### 1. Verify token and parent reachability

```bash
NOTION_TOKEN="<token>" python3 ${CLAUDE_PLUGIN_ROOT}/skills/notion-with-api/scripts/notion_api.py verify
```

The returned user/workspace name must match the `workspace` field. On mismatch, stop and report.

Then confirm `parent_page_id` is reachable through the integration (catches typos and missing connections before any create/update):

```bash
NOTION_TOKEN="<token>" python3 ${CLAUDE_PLUGIN_ROOT}/skills/notion-with-api/scripts/notion_api.py read-page <parent_page_id>
```

A 404 here means the page ID is wrong, or the integration was not connected to the parent in Notion. Stop and report — do not fall through to Step 3.

### 2. Determine target files

- If the input path is a file, sync that single `.md`
- If the input path is a directory, sync every top-level `.md` inside

### 3. Discover page-ID mapping (in memory)

```bash
NOTION_TOKEN="<token>" python3 ${CLAUDE_PLUGIN_ROOT}/skills/notion-with-api/scripts/notion_api.py list-children --json <parent_page_id>
```

Returns `[{id, title}, ...]`. Build the filename→page_id mapping in memory:

- Filename → expected title: drop `.md`, replace `-` with space, title-case. Example: `privacy-policy.md` → `Privacy Policy`.
- Normalize each Notion child title the same way: take the part before `|` (if present), trim whitespace.
- **Unique match required**: the normalized expected title must match exactly one Notion child. If zero matches → treat the file as new (Step 4 create branch). If two or more match → stop and report all candidate `(title, id)` pairs; do not guess. The user resolves the ambiguity by renaming or by editing `pages` in `.claude/notion-sync.local.md` manually.

Do not write to disk in this step. Hold the resolved mapping (and unresolved files) in memory for Step 4.

### 4. Sync each file (collect results in memory)

For each file with a known page ID (from Step 3 or the existing `pages` map in config):

```bash
NOTION_TOKEN="<token>" python3 ${CLAUDE_PLUGIN_ROOT}/skills/notion-with-api/scripts/notion_api.py update-page <page_id> --file <filepath>
```

For each file with no matching Notion page:

```bash
NOTION_TOKEN="<token>" python3 ${CLAUDE_PLUGIN_ROOT}/skills/notion-with-api/scripts/notion_api.py create-page <parent_page_id> "<Page Title>" "$(cat <filepath>)"
```

Caveat for `create-page`: the script accepts content only as a positional argument, so the file is shell-substituted via `$(cat ...)`. This is safe for typical legal/marketing docs (well under 100KB, plain prose). For long content (>100KB) or content with shell metacharacters that break quoting, prefer creating an empty page first then using `update-page --file` (which streams the file directly).

Capture the new page ID from the create response into the in-memory mapping. Record per-file outcome (`created` / `updated` / `failed: <reason>` + URL) in memory. Do not write `.claude/notion-sync.local.md` yet.

### 5. Persist updated config (single atomic write)

This is the only step that writes to `.claude/notion-sync.local.md`. Merge the in-memory `pages` mapping (from Steps 3 and 4) into the existing config and write the file back once. Preserve all other frontmatter fields (`token`, `workspace`, `parent_page_id`) verbatim. If Step 4 had partial failures, still write the successes — they are real Notion-side state and must be recorded so the next run does not duplicate.

### 6. Report

Per file, print:
- Status: `created` / `updated` / `failed: <reason>`
- Notion edit URL
- Public URL if the page returns a `public_url` field (already published)

Final summary table:

| File | Status | Blocks | Public URL |
|------|--------|--------|------------|
| privacy-policy.md | updated | 42 | https://... |

## Notes

- Within this skill's workflow, the token comes from `.claude/notion-sync.local.md` only. Inline `NOTION_TOKEN="<token>" python3 ...` overrides any `.env` the script would otherwise load (the python script's `load_dotenv` does not pass `override=True`). The sibling `notion-with-api` skill still reads its own `.env` for ad-hoc operations; that is unchanged.
- `${CLAUDE_PLUGIN_ROOT}` is render-time substitution by Claude Code, resolved to the installed plugin path (typically `~/.claude/plugins/cache/indie-toolkit/shared-utils`). It is not a shell environment variable. See `shared-utils/README.md` for the substitution pattern.
- If running this workflow from a context where render-time substitution does not apply (manual terminal invocation outside Claude Code), use the absolute path: `~/.claude/plugins/cache/indie-toolkit/shared-utils/skills/notion-with-api/scripts/notion_api.py`.
