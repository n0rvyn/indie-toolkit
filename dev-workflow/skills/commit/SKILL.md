---
name: commit
description: "Use when the user says 'commit' or wants to save progress after completing a task. Analyzes uncommitted changes, groups them logically, and commits with conventional format messages."
context: fork
model: haiku
allowed-tools: Bash(git add:*, git commit:*, git diff:*, git status:*, git log:*, wc -c *)
---

## Input

Trigger this command when:
- User says "commit", "提交", or similar
- After completing a task, user wants to save progress

On trigger:
1. Run `git status` and `git diff --stat` to understand current state
2. If no uncommitted changes, inform user and stop
3. If changes exist, proceed with analysis

## Process

1. **Check git status**
   - Run `git status` to see uncommitted files
   - Run `git diff --stat` to see summary of changes
   - Identify all modified, added, or deleted files

2. **Analyze changes**
   - For each modified file, understand the changes
   - Use `git diff <file>` to see exact changes if needed
   - Group related changes logically:
     - Same feature/component -> same commit
     - Different concerns -> separate commits
     - Bug fixes vs features -> separate commits
     - Documentation -> separate commit

3. **Pre-commit audit**

   Before committing, scan `git diff <file>` for each file in the group. This is a **blocking gate** — groups with findings are held back. Only scan added lines (lines starting with `+` in diff output).

   **3a. Secrets & credentials**
   - API keys: `sk-[a-zA-Z0-9]{20,}`, `ghp_[a-zA-Z0-9]{20,}`, `gho_[a-zA-Z0-9]{20,}`, `AKIA[A-Z0-9]{16}`, `Bearer [a-zA-Z0-9._\-]{20,}`
   - Hardcoded secrets: `password\s*=\s*["']`, `secret\s*=\s*["']`, `token\s*=\s*["']` (with non-empty literal values, not placeholders like `<YOUR_TOKEN>`)
   - Private keys: `-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----`
   - .env files: any `.env`, `.env.*` file being committed (except `.env.example`)
   - Credential files: `credentials.json`, `serviceAccountKey.json`, `*.pem`, `*.p12`

   **3b. Debug residue**
   - JavaScript/TypeScript: `console.log(`, `debugger;`, `debugger `
   - Swift (`.swift` files only): standalone `print(` (not inside a function name like `printSomething`)
   - Python: `breakpoint()`, `pdb.set_trace()`, `import pdb`
   - Warn only (do not block): `TODO`, `FIXME`, `HACK`, `XXX`, `#if DEBUG` blocks

   **3c. Large files**
   - Any file > 500KB: check with `git diff --stat` or file size in diff header
   - Binary files (images, archives, compiled artifacts) that are not in `.gitignore`

   **Audit behavior:**
   - **Blocking findings** (secrets, debug statements, large files): Do NOT commit the affected group. Report each finding as:
     ```
     ⛔ BLOCKED: <file>:<line> — <reason>
     ```
   - **Warn-only findings** (TODO/FIXME): Commit proceeds, but include in summary:
     ```
     ⚠️ NOTE: <file>:<line> — <reason>
     ```
   - If ALL groups are blocked, commit nothing and report the full audit result
   - If SOME groups are clean, commit those and report blocked groups separately

4. **Create commit messages**
   - Follow conventional commit format: `type(scope): description`
   - Types: `feat`, `fix`, `docs`, `refactor`, `style`, `test`, `chore`
   - Scope: component/service name (e.g., `sync`, `home`, `repository`)
   - Description: concise summary of what changed
   - Multi-line body: explain why and how (if needed)

5. **Commit in logical order**
   - Start with foundational changes (models, protocols)
   - Then service layer changes
   - Then view/viewmodel changes
   - Finally documentation/comments
   - One commit per logical group

   **CRITICAL: Execute add+commit per group, NOT batch add then batch commit**
   ```
   # CORRECT (per-group cycle):
   git add <group1-files> && git commit -m "..."
   git add <group2-files> && git commit -m "..."
   git add <group3-files> && git commit -m "..."

   # WRONG (batch add, then separate commits):
   git add <all-files>
   git commit -m "..."  # <-- commits EVERYTHING staged
   git commit -m "..."  # <-- nothing left to commit!
   ```

6. **Verify**
   - After all commits, run `git log --oneline -5` to show recent commits
   - Run `git status` to confirm working tree is clean
   - Report summary of commits created

## Special Cases

**Xcode project files**: `*.xcodeproj` directory contents (e.g., `project.pbxproj`) must always be staged and committed with related changes. Never skip, ignore, or exclude these files; Xcode Cloud relies on them to locate the project.

**Merge commits**: When merging branches, use default merge message. Do not re-split changes.

**Fixup previous commit**: If user says "add to last commit" or "amend":
- Use `git commit --amend` only when explicitly requested
- Warn user this rewrites history

**Partial staging**: If user wants to commit only some files:
- Stage only specified files with `git add <file>`
- Leave other changes unstaged

## Commit Message Guidelines

**Format:**
```
type(scope): brief description

Optional body explaining:
- What changed
- Why it changed
```

**Examples:**
- `fix(sync): use healthKitWorkoutId for stable log binding`
- `feat(home): auto-refresh on sync success`
- `docs(readme): add setup instructions`
- `refactor(repository): check persistentModelID before inserting`

**Grouping Rules:**
- Same file, same concern -> one commit
- Same file, different concerns -> separate commits
- Related files, same feature -> one commit
- Unrelated changes -> separate commits

## Output Format

After completing commits, provide:
1. **Audit findings** (if any):
   - Blocked groups with `⛔ BLOCKED` items (file, line, reason)
   - Warnings with `⚠️ NOTE` items
2. Summary of commits created (list with hashes)
3. Total number of commits
4. Number of blocked groups (if any), with instructions to fix and re-run
5. Confirmation that working tree is clean (or list of remaining unstaged changes from blocked groups)

## Completion Criteria

- Pre-commit audit executed for all groups
- All clean groups committed; blocked groups reported with actionable details
- `git status` shows clean working tree (or only blocked/intentionally unstaged files)
- Commit summary with hashes presented
- No secrets, credentials, or debug statements committed
