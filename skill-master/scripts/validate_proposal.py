"""
validate_proposal.py — Mechanical whitelist enforcement for /master insights proposals.

validate(proposal, repo_root) -> (bool, str)
validate_pr_body(body) -> (bool, str)
"""

import re
from pathlib import Path

# Sections whose content must not be modified
_PROTECTED_SECTIONS = re.compile(
    r"^##\s+(Process|Steps|Inputs|Outputs|Contract|Rules)\s*$",
    re.MULTILINE,
)

# Anchored frontmatter delimiter: must be on its own line
_FM_DELIM = re.compile(r"^---$", re.MULTILINE)


def _get_frontmatter_line_range(text: str) -> tuple[int, int] | None:
    """
    Return (start_line, end_line) of the frontmatter block (1-indexed, inclusive),
    or None if the file has no valid frontmatter.

    Uses anchored ^---$ regex to find the first and second delimiter lines.
    This correctly ignores body horizontal rules that are part of markdown prose.
    """
    lines = text.splitlines()
    matches = list(_FM_DELIM.finditer(text))
    if len(matches) < 2:
        return None

    # Convert match positions to line numbers
    def pos_to_line(pos: int) -> int:
        return text[:pos].count("\n") + 1  # 1-indexed

    start_line = pos_to_line(matches[0].start())
    end_line = pos_to_line(matches[1].start())
    return (start_line, end_line)


def _find_string_line_range(text: str, substring: str) -> tuple[int, int] | None:
    """
    Return the (first_line, last_line) range (1-indexed) where `substring` appears
    in `text`, or None if not found.
    """
    idx = text.find(substring)
    if idx == -1:
        return None
    before = text[:idx]
    start_line = before.count("\n") + 1
    end_line = start_line + substring.count("\n")
    return (start_line, end_line)


def _is_in_frontmatter(text: str, substring: str) -> bool:
    """Return True if `substring` occurs within the frontmatter block of `text`."""
    fm_range = _get_frontmatter_line_range(text)
    if fm_range is None:
        return False
    str_range = _find_string_line_range(text, substring)
    if str_range is None:
        return False
    fm_start, fm_end = fm_range
    str_start, str_end = str_range
    # The substring overlaps frontmatter if any of its lines fall within [fm_start, fm_end]
    return str_start <= fm_end and str_end >= fm_start


def _is_in_protected_section(text: str, substring: str) -> bool:
    """
    Return True if `substring` appears under a protected section header
    (## Process, ## Steps, etc.) and before the next ## header.
    """
    # Find all section headers and their line positions
    header_pattern = re.compile(r"^##\s+\S", re.MULTILINE)
    headers = [(m.start(), m.group(0)) for m in header_pattern.finditer(text)]

    str_range = _find_string_line_range(text, substring)
    if str_range is None:
        return False
    str_start, str_end = str_range

    # Find which section each line of the substring falls under
    lines = text.splitlines()

    def line_to_pos(line_num: int) -> int:
        """Convert 1-indexed line number to character position."""
        return sum(len(l) + 1 for l in lines[: line_num - 1])

    str_pos = text.find(substring)
    if str_pos == -1:
        return False

    # Find the nearest preceding section header
    preceding_headers = [(pos, hdr) for pos, hdr in headers if pos < str_pos]
    if not preceding_headers:
        return False

    nearest_pos, nearest_hdr = preceding_headers[-1]
    nearest_line = text[:nearest_pos].count("\n") + 1

    # Extract header name
    header_text = text[nearest_pos:].split("\n")[0]
    return bool(_PROTECTED_SECTIONS.match(header_text))


def check_path_in_repo(file_path: str, repo_root: str | Path) -> tuple[bool, str]:
    """Return (True, '') if file_path is inside repo_root, else (False, reason)."""
    try:
        resolved = Path(file_path).resolve()
        root_resolved = Path(repo_root).resolve()
        resolved.relative_to(root_resolved)
        return True, ""
    except ValueError:
        return False, f"path '{file_path}' is outside repo root '{repo_root}'"


def validate(proposal: dict, repo_root: str | Path) -> tuple[bool, str]:
    """
    Validate a single Edit candidate proposal.

    proposal keys:
        file_path   str  — absolute or relative path to the target file
        old_string  str  — the text being replaced
        new_string  str  — the replacement text
        change_type str  — 'description_update' | 'append_examples_section'

    Returns (allow: bool, reason: str).
    """
    file_path = proposal.get("file_path", "")
    old_string = proposal.get("old_string", "")
    new_string = proposal.get("new_string", "")

    # 1. Path must be inside the repo
    ok, reason = check_path_in_repo(file_path, repo_root)
    if not ok:
        return False, f"path check failed: {reason}"

    # 2. Must not delete existing content (new_string must not be shorter in a way
    #    that removes prose — simplest mechanical check: new_string must be non-empty
    #    OR old_string must be empty)
    if old_string.strip() and not new_string.strip():
        return False, "deletion of existing content is not allowed"

    # 3. Read the target file to check frontmatter and protected sections
    try:
        text = Path(file_path).read_text(encoding="utf-8")
    except (FileNotFoundError, OSError) as e:
        return False, f"cannot read file: {e}"

    # 4. old_string must not be in the frontmatter (except description field)
    if old_string and _is_in_frontmatter(text, old_string):
        # Allow only description field changes
        stripped = old_string.strip()
        if not stripped.startswith("description:"):
            return False, "modification of frontmatter fields other than 'description' is not allowed"

    # Also check if new_string introduces frontmatter-like content
    # (e.g., adding allowed-tools entries). If old_string is in frontmatter,
    # we already handled above. Check if new_string would land in frontmatter:
    if new_string and _is_in_frontmatter(text, old_string):
        # It's a frontmatter edit — only description allowed (checked above)
        pass

    # 5. old_string must not be in a protected section (## Process, ## Steps, etc.)
    if old_string and _is_in_protected_section(text, old_string):
        return False, "modification of protected sections (## Process, ## Steps, etc.) is not allowed"

    return True, ""


def validate_pr_body(body: str) -> tuple[bool, str]:
    """
    Validate PR body text — must not contain raw quote blocks (> lines)
    except immediately after the <!--lag-meta--> sentinel.

    Returns (allow: bool, reason: str).
    """
    lines = body.splitlines()
    lag_meta_next = False

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()

        if stripped == "<!--lag-meta-->":
            lag_meta_next = True
            continue

        if stripped.startswith(">"):
            if lag_meta_next:
                # This > line is the lag warning — allowed
                lag_meta_next = False
                continue
            return False, f"quote block at line {i} is not allowed in PR body (prevents raw prompt leak)"

        # Any non-empty, non-comment line resets the lag_meta sentinel
        if stripped and not stripped.startswith("<!--"):
            lag_meta_next = False

    return True, ""
