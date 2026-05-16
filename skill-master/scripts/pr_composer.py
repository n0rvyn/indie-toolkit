"""
pr_composer.py — Branch creation, candidate application, and PR creation for /master insights.

Public API:
    branch_name(candidates, today) -> str
    apply_candidates(candidates, repo_root) -> None
    commit(repo_root, message=None) -> str   (returns commit sha)
    push(branch) -> None
    render_pr_body(candidates, findings, lag_warning=None, commit_sha=None) -> str
    create_pr(branch, title, body) -> str    (returns PR URL)
    rollback(branch_name, push_succeeded, pr_created=False) -> None
    run(candidates, findings, lag_warning=None, dry_run=False) -> str | None
"""

import hashlib
import json
import os
import subprocess
import tempfile
from datetime import date
from pathlib import Path

from scripts.lock import acquire as _lock_acquire


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sanitize_for_markdown(text: str) -> str:
    """
    Sanitize a string for safe embedding in a PR body.

    - Strips lines starting with '>' (prevents raw quote block / prompt leak)
    - Strips markdown code fences (``` lines)
    - Escapes pipe characters to avoid breaking table cells
    """
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            continue
        if stripped.startswith("```"):
            continue
        # Escape pipe to prevent table injection
        line = line.replace("|", "\\|")
        lines.append(line)
    return "\n".join(lines)


def _run(cmd: list, check: bool = True, capture: bool = True, cwd=None) -> subprocess.CompletedProcess:
    """Wrapper around subprocess.run with consistent defaults."""
    return subprocess.run(
        cmd,
        check=check,
        capture_output=capture,
        text=True,
        cwd=cwd,
    )


# ---------------------------------------------------------------------------
# branch_name
# ---------------------------------------------------------------------------

def branch_name(candidates: list, today: date) -> str:
    """
    Return a deterministic branch name based on candidates content and date.

    Format: auto-insights/YYYY-MM-DD-{8-char-sha256-hash}
    """
    digest = hashlib.sha256(
        json.dumps(candidates, sort_keys=True).encode()
    ).hexdigest()[:8]
    return f"auto-insights/{today.isoformat()}-{digest}"


# ---------------------------------------------------------------------------
# apply_candidates  (DP-V2=A: temp-dir + batch rename pattern)
# ---------------------------------------------------------------------------

def apply_candidates(candidates: list, repo_root: Path) -> None:
    """
    Apply a list of Edit candidates to their target files using a
    temp-directory + batch rename pattern.

    All files are patched into a temp directory first; if ANY patch fails
    (old_string not found), the temp directory is discarded and no original
    file is modified.  Once all temp writes succeed, os.replace() renames
    each temp file to its target atomically (per-file).

    Raises RuntimeError if any old_string is not found in its target file.
    """
    repo_root = Path(repo_root)

    with tempfile.TemporaryDirectory(prefix="insights-apply-") as tmp:
        tmp_pairs = []  # [(tmp_path, target_path), ...]

        for i, c in enumerate(candidates):
            target = Path(c["file_path"])
            if not target.is_absolute():
                target = repo_root / target

            original = target.read_text(encoding="utf-8")
            patched = original.replace(c["old_string"], c["new_string"], 1)

            if patched == original:
                raise RuntimeError(
                    f"apply failed at candidate {i}: "
                    f"old_string not found in {c['file_path']}"
                )

            # Mangle path to avoid name collisions in the temp dir
            mangled = f"{i}_{c['file_path'].replace('/', '_').replace(os.sep, '_')}"
            tmp_file = Path(tmp) / mangled
            tmp_file.write_text(patched, encoding="utf-8")
            tmp_pairs.append((tmp_file, target))

        # All temp writes succeeded — batch rename
        written = []
        for tmp_file, target in tmp_pairs:
            os.replace(tmp_file, target)
            written.append(str(target))
        # written list available for diagnostics if caller needs it


# ---------------------------------------------------------------------------
# commit
# ---------------------------------------------------------------------------

def commit(repo_root: Path, message: str = None) -> str:
    """
    Stage modified files and create a git commit.

    message must start with 'chore(insights):' or 'docs(insights):'.
    Raises ValueError if message uses a forbidden prefix (feat/fix).

    Returns the short commit SHA.
    """
    _FORBIDDEN_PREFIXES = ("feat", "fix")
    _SAFE_PREFIXES = ("chore(insights):", "docs(insights):")

    if message is None:
        message = "chore(insights): auto-tune component descriptions based on usage data"

    # Validate prefix
    for fp in _FORBIDDEN_PREFIXES:
        if message.startswith(fp + ":") or message.startswith(fp + "!"):
            raise ValueError(
                f"commit message must not use '{fp}' prefix — "
                f"use 'chore(insights):' or 'docs(insights):' to avoid "
                f"triggering auto-version minor/patch bump. Got: {repr(message)}"
            )

    if not any(message.startswith(p) for p in _SAFE_PREFIXES):
        # Still allow other chore/docs variants — only block feat/fix
        pass

    repo_root = Path(repo_root)
    _run(["git", "add", "-u"], cwd=repo_root)
    result = _run(
        [
            "git",
            "-c", "user.name=auto-insights",
            "-c", "user.email=auto-insights@local",
            "commit",
            "-m", message,
        ],
        cwd=repo_root,
    )

    # Extract short SHA from commit output or via rev-parse
    sha_result = _run(["git", "rev-parse", "--short", "HEAD"], cwd=repo_root)
    return sha_result.stdout.strip()


# ---------------------------------------------------------------------------
# push
# ---------------------------------------------------------------------------

def push(branch: str, repo_root: Path = None) -> None:
    """Push branch to origin. Raises subprocess.CalledProcessError on failure."""
    cmd = ["git", "push", "-u", "origin", branch]
    _run(cmd, cwd=repo_root)


# ---------------------------------------------------------------------------
# render_pr_body
# ---------------------------------------------------------------------------

def render_pr_body(
    candidates: list,
    findings: list,
    lag_warning: str = None,
    commit_sha: str = None,
) -> str:
    """
    Render a markdown PR body for the auto-insights draft PR.

    Sections:
      - Optional lag warning (via <!--lag-meta--> sentinel)
      - Evidence table (plugin | component | finding | confidence)
      - Expected change in next window
      - Confidence per candidate (Sample N sessions · Confidence: X)
      - Revert instructions
    """
    parts = []

    # Header: lag warning (allowlisted by validate_proposal via <!--lag-meta--> sentinel)
    if lag_warning:
        parts.append("<!--lag-meta-->")
        parts.append(f"> ⚠️ {_sanitize_for_markdown(lag_warning)}")
        parts.append("")

    parts.append("## Auto-Insights: Proposed Skill Improvements")
    parts.append("")
    parts.append(
        "This draft PR was generated by `/master insights` based on real usage data. "
        "Please review each change before merging."
    )
    parts.append("")

    # Evidence table
    parts.append("## Evidence")
    parts.append("")
    parts.append("| plugin | component | finding | confidence |")
    parts.append("|--------|-----------|---------|------------|")
    for c in candidates:
        plugin = _sanitize_for_markdown(c.get("file_path", "").split("/")[0])
        component_parts = c.get("file_path", "").split("/")
        component = _sanitize_for_markdown(
            component_parts[2] if len(component_parts) > 2 else component_parts[-1]
        )
        summary = _sanitize_for_markdown(c.get("evidence_summary", ""))
        confidence = c.get("confidence", "unknown")
        parts.append(f"| {plugin} | {component} | {summary} | {confidence} |")
    parts.append("")

    # Confidence per candidate
    parts.append("## Candidates")
    parts.append("")
    for i, c in enumerate(candidates):
        sample = c.get("sample_size", "?")
        confidence = c.get("confidence", "unknown")
        change_type = c.get("change_type", "unknown")
        file_path = c.get("file_path", "unknown")
        parts.append(f"### Candidate {i + 1}: `{file_path}`")
        parts.append("")
        parts.append(f"**Change type:** {change_type}")
        parts.append(f"Sample {sample} sessions · Confidence: {confidence}")
        parts.append("")
        parts.append(f"**Expected change in next window:** {_sanitize_for_markdown(c.get('expected_metric_change', ''))}")
        parts.append("")

    # Expected change section (top-level for test_pr_body_contains_expected_metric_change)
    parts.append("## Expected change in next window:")
    parts.append("")
    for c in candidates:
        parts.append(f"- {_sanitize_for_markdown(c.get('expected_metric_change', ''))}")
    parts.append("")

    # Revert instructions
    parts.append("## Revert Instructions")
    parts.append("")
    if commit_sha:
        parts.append(f"To revert all changes in this PR:")
        parts.append(f"```")
        parts.append(f"git revert {commit_sha}")
        parts.append(f"```")
    else:
        parts.append("To revert all changes in this PR, use `git revert <commit-sha>` on the merge commit.")
    parts.append("")
    parts.append(
        "To prevent re-proposal of the same changes, edit "
        "`~/.claude/skill-master-insights-state.json` and add the relevant hash entry."
    )
    parts.append("")
    parts.append(
        "_You can also run `/review-execution` on this PR for an independent cross-check._"
    )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# create_pr
# ---------------------------------------------------------------------------

def create_pr(branch: str, title: str, body: str) -> str:
    """
    Create a draft PR via gh CLI.

    Returns the PR URL.
    Raises subprocess.CalledProcessError on failure.
    """
    result = _run(
        [
            "gh", "pr", "create",
            "--draft",
            "--base", "main",
            "--head", branch,
            "--title", title,
            "--body", body,
        ]
    )
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# rollback  (3-state per Threat Model)
# ---------------------------------------------------------------------------

def rollback(
    branch: str,
    push_succeeded: bool,
    pr_created: bool = False,
) -> None:
    """
    Rollback after failure or KeyboardInterrupt.

    Three states (per Threat Model Failure modes table):
      1. Local only (push_succeeded=False): delete local branch only
      2. Pushed but no PR (push_succeeded=True, pr_created=False):
         delete local branch AND remote branch
      3. PR created (pr_created=True): no action (PR already built; user decides)
    """
    if pr_created:
        # State 3: PR already created — leave everything for user
        return

    # Checkout main first to allow branch deletion
    try:
        _run(["git", "checkout", "main"], check=False)
    except Exception:
        pass

    # Delete local branch
    try:
        _run(["git", "branch", "-D", branch], check=False)
    except Exception:
        pass

    if push_succeeded:
        # State 2: also delete remote orphan
        try:
            _run(["git", "push", "origin", "--delete", branch], check=False)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# run  (top-level orchestrator)
# ---------------------------------------------------------------------------

def run(
    candidates: list,
    findings: list,
    lag_warning: str = None,
    dry_run: bool = False,
    repo_root: Path = None,
) -> str | None:
    """
    Orchestrate: lock → apply → commit → push → create PR.

    Returns PR URL on success, or None on dry_run.
    Handles KeyboardInterrupt with 3-state rollback.
    """
    if repo_root is None:
        repo_root = Path.cwd()

    today = date.today()
    br = branch_name(candidates, today)

    push_succeeded = False
    pr_created = False

    if dry_run:
        return None

    with _lock_acquire():
        try:
            # Create and checkout branch
            _run(["git", "checkout", "-b", br], cwd=repo_root)

            # Apply candidates
            apply_candidates(candidates, repo_root)

            # Commit
            commit_sha = commit(repo_root)

            # Push
            push(br, repo_root=repo_root)
            push_succeeded = True

            # Render PR body
            body = render_pr_body(candidates, findings, lag_warning, commit_sha)
            title = f"auto-insights: tune {len(candidates)} component description(s)"

            # Create PR
            url = create_pr(br, title, body)
            pr_created = True

            return url

        except KeyboardInterrupt:
            rollback(br, push_succeeded=push_succeeded, pr_created=pr_created)
            raise
        except Exception:
            if not pr_created:
                rollback(br, push_succeeded=push_succeeded, pr_created=False)
            raise
