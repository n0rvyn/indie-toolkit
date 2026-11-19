---
name: commit
description: "Use when the user says 'commit', 'commit or ignore', or wants to save completed work. Groups changes into conventional commits, applies scoped Git ignore rules, and cleans up verified disposable artifacts when the user also requests cleanup."
allowed-tools: Read Grep Bash(git add:*) Bash(git commit:*) Bash(git diff:*) Bash(git status:*) Bash(git log:*) Bash(git --literal-pathspecs ls-files:*) Bash(git rev-parse:*) Bash(git check-ignore:*) Bash(wc:*)
effort: medium
---

## Input

Carry out the requested commit workflow in the current conversation, where the user’s scope, artifact ownership, and cleanup authorization are available. “Commit” and “commit or ignore” both include applying justified ignore rules. Cleanup runs when the user also authorizes it for the current scope. Push, amend, global Git settings, and changes outside the requested scope require their own authorization.

## Process

1. **Check git status**
   - Read `git status --short --untracked-files=all`, `git diff --stat`, and `git diff --cached --stat`. Inspect relevant staged and unstaged diffs before assigning groups.
   - Include known task artifacts covered by existing ignore rules when assessing cleanup. Check their exact paths instead of scanning all ignored directories.
   - If there are no changes or in-scope artifacts to act on, report that and finish. Continue through the same workflow when there are ignore or cleanup items and no source changes.

2. **Group changes and artifacts before changing anything**
   - **To commit** groups related source, tests, docs, and config by concern using the existing grouping rules below.
   - **To ignore** lists verified untracked, in-scope paths to retain on disk and the appropriate rule file. **To clean up** lists verified disposable paths with the evidence and whether cleanup is authorized.
   - Read [Workspace artifact decisions](../../references/workspace-artifact-decisions.md) for the shared classification criteria. Keep uncertainty, evidence, and unrelated work visible. Give each path one action.
   - Before ignoring or cleaning up a file, confirm its parent directory resolves to the selected worktree with `git -C <parent-directory> rev-parse --show-toplevel`. Paths in nested repositories, submodules, or through symlinks stay outside these actions.

3. **Apply scoped ignore rules**
   - For shared, reproducible outputs, add a narrow, project-relative rule to the appropriate `.gitignore`. For private or machine-specific files use the path from `git rev-parse --git-path info/exclude`. Check existing rules first and leave global excludes alone. Prefer an exact path or an anchored, dedicated generated-output directory with verified scope. Escape Git ignore metacharacters in literal paths.
   - Recheck each candidate with `git --literal-pathspecs ls-files --stage -- <path>`. If Git already tracks or has staged it, leave it in place and report that an ignore rule cannot resolve it. Do not untrack or unstage it to make the rule work.
   - For each file, require `git check-ignore -q -- <path>` to succeed and confirm the file remains on disk. Use `git check-ignore -v -- <path>` to identify the rule, which can also show a negated rule. Before adding a directory rule, inspect all existing files it would hide, including unrelated work and evidence. Put shared ignore-rule changes in the appropriate commit group and audit them. Keep local exclude rules out of commits and preserve pre-existing edits in either rule file.
   - If writing or verifying a rule fails, leave that path out of the commit, report the failure, and continue with independent groups.

4. **Pre-commit audit**

   Audit the exact content intended for each commit, including new files and staged changes. Read only added lines for secret and debug pattern checks. Check size and type of new artifacts before staging. A blocked group stays out of commits and cannot be made eligible by hiding or cleaning up its files.

   **4a. Secrets & credentials**
   - API keys: `sk-[a-zA-Z0-9]{20,}`, `ghp_[a-zA-Z0-9]{20,}`, `gho_[a-zA-Z0-9]{20,}`, `AKIA[A-Z0-9]{16}`, `Bearer [a-zA-Z0-9._\-]{20,}`
   - Hardcoded secrets: `password\s*=\s*["']`, `secret\s*=\s*["']`, `token\s*=\s*["']` (with non-empty literal values, not placeholders like `<YOUR_TOKEN>`)
   - Private keys: `-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----`
   - .env files: any `.env`, `.env.*` file being committed (except `.env.example`)
   - Credential files: `credentials.json`, `serviceAccountKey.json`, `*.pem`, `*.p12`

   **4b. Debug residue**
   - JavaScript/TypeScript: `console.log(`, `debugger;`, `debugger `
   - Swift (`.swift` files only): standalone `print(` (not inside a function name like `printSomething`)
   - Python: `breakpoint()`, `pdb.set_trace()`, `import pdb`
   - Warn only (do not block): `TODO`, `FIXME`, `HACK`, `XXX`, `#if DEBUG` blocks

   **4c. Large files**
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

5. **Create commit messages**
   - Follow conventional commit format: `type(scope): description`
   - Types and bump mapping: see `references/conventional-commits.md` (authoritative). Canonical types are `feat`, `fix`, `docs`, `refactor`, `perf`, `test`, `chore` — note `style` is NOT in this project's list.
   - Scope: plugin name when in a plugin monorepo (e.g., `feat(dev-workflow):`, `fix(apple-dev):`); component/service name otherwise. See references for full guidance.
   - BREAKING CHANGE: append `!` after the type and scope (`feat(pkos)!:` or `fix!:`), NOT before the scope. Wrong form silently falls through to patch bump.
   - Description: concise summary of what changed
   - Multi-line body: explain why and how (if needed)

6. **Commit in logical order**
   - Start with foundational changes (models, protocols)
   - Then service layer changes
   - Then view/viewmodel changes
   - Finally documentation/comments
   - One commit per logical group
   - Verify the staged diff against that group immediately before committing. Preserve unrelated staged work. Use an audited path-limited commit only for selected whole-file changes, and leave groups that would absorb unrelated staged changes pending if they cannot be isolated safely.

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

7. **Clean up authorized artifacts**
   - For each authorized path, repeat the worktree and index checks from steps 2 and 3. Confirm it is the same artifact and still unused. If the file changed, permissions prevent the operation, or provenance is uncertain, leave it in place and report why.
   - Use the existing project cleanup command only if its effect is restricted to the approved paths. Otherwise remove only the exact approved files, using literal paths. Never recurse through directories, follow symlinks, run repository-wide cleanup, or remove artifacts from other tasks.
   - Verify each authorized removal. When cleanup was not requested, preserve the candidates and report them. Respect tool permissions for all writes and cleanup actions.

8. **Verify**
   - Compare the new commits and remaining staged, unstaged, and untracked paths with the original groups. Recheck applied ignore rules and cleanup results. Report discrepancies rather than equating a quiet `git status` with completed work.

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

See references/conventional-commits.md for full spec (type list, bump mapping, BREAKING CHANGE syntax, auto-version integration).

**Format:**
```
type(scope): brief description

Optional body explaining:
- What changed
- Why it changed
```

**Examples (plugin-monorepo scope convention — see references/conventional-commits.md for full list):**
- `fix(apple-dev): use healthKitWorkoutId for stable log binding`
- `feat(dev-workflow): auto-refresh on sync success`
- `docs(mactools): add setup instructions`
- `refactor(commit): check persistentModelID before inserting`
- `feat(pkos)!: breaking change to inbox routing` (note `!` after scope, not before)

**Grouping Rules:**
- Same file, same concern -> one commit
- Same file, different concerns -> separate commits
- Related files, same feature -> one commit
- Unrelated changes -> separate commits

## Output Format

After completing the workflow, provide:
1. **Audit findings** (if any):
   - Blocked groups with `⛔ BLOCKED` items (file, line, reason)
   - Warnings with `⚠️ NOTE` items
2. Summary of commits created (list with hashes)
3. Ignored paths and rule files, distinguishing shared and local rules
4. Paths actually cleaned up and any remaining cleanup candidates
5. Working tree status, including blocked or deliberately preserved items

## Completion Criteria

- Every approved path has its stated outcome verified, including ignore-only and cleanup-only runs
- Clean commit groups were audited and committed. Blocked groups, protected artifacts, and unrelated work are preserved
