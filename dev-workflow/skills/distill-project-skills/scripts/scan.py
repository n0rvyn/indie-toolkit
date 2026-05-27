#!/usr/bin/env python3
"""
scan.py — distill-project-skills scanner

Scans session jsonl files and optional cost-hint.log to surface candidate
patterns worth crystallizing as skills.

Usage:
  python3 scan.py <project-path> [output-file]
  python3 scan.py --jsonl-dir <dir> [--include-hint-log <log>] [--output <file>]

Output: JSON with structure {"candidates": [...]}
Each candidate: {pattern, frequency, est_cost_usd, suggested_name,
                 suggested_frontmatter, status, covered_by?}

Status values:
  new              — no existing skill matches; safe to create
  name-exists      — suggested_name already exists as a skill name
  possibly-covered — an existing skill's description overlaps with this pattern
  already-built    — distill previously generated this skill (history outcome=created)

Candidates with outcome=declined within DECLINED_TTL_DAYS (30) are omitted entirely.
"""

import argparse
import json
import os
import re
import sys
import glob
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


# Per-turn cost delta when a mechanical Bash cluster runs on main-line Opus
# instead of a sub-agent fork on Sonnet. Approximate; derived from audit-tokens
# pricing tables (Opus $15/$75 base vs Sonnet $3/$15 with 0.1x cache-read).
# Update when pricing changes or when posture heuristic shifts.
COST_DELTA_PER_TURN = 0.73

# Below this frequency, a pattern is statistical noise rather than a habit
# worth crystallizing as a new skill. Tuned by manual review of 7-day windows;
# raise if false positives, lower if real patterns are missed.
MIN_FREQUENCY = 3

# How long after a user declines a candidate before it can resurface.
# 30 days balances "user mind may change" vs "don't badger".
DECLINED_TTL_DAYS = 30

# Default glob patterns for enumerating existing SKILL.md files when checking
# candidate dedup. Order: project-local plugins → user-global skills → installed
# plugin cache. When scan.py is given a project_path argument, that path's
# {plugin}/skills/*/SKILL.md is also scanned dynamically (see main()).
DEFAULT_SKILL_ROOT_GLOBS = [
    os.path.expanduser('~/.claude/skills/*/SKILL.md'),
    os.path.expanduser('~/.claude/plugins/**/skills/*/SKILL.md'),
]


def encode_path(path: str) -> str:
    """Encode a filesystem path to Claude's projects directory naming convention."""
    return path.replace('/', '-')


def find_jsonl_files(jsonl_dir: str) -> list:
    return glob.glob(os.path.join(jsonl_dir, '*.jsonl'))


def find_jsonl_files_for_project(project_path: str) -> list:
    encoded = encode_path(os.path.abspath(project_path))
    projects_dir = os.path.expanduser('~/.claude/projects')
    pattern = os.path.join(projects_dir, encoded, '*.jsonl')
    return glob.glob(pattern)


MECHANICAL_PATTERNS = [
    ('sqlite3-select', re.compile(r'^sqlite3\s+\S+\s+["\']?SELECT', re.IGNORECASE)),
    ('curl-get',       re.compile(r'^curl\s+-s\s+https?://')),
    ('grep-recursive', re.compile(r'^grep\s+-r')),
    ('find-scan',      re.compile(r'^find\s+')),
]


def classify_bash_command(cmd: str) -> str | None:
    cmd = cmd.strip()
    for name, pattern in MECHANICAL_PATTERNS:
        if pattern.match(cmd):
            return name
    return None


def extract_patterns_from_jsonl(filepath: str) -> list:
    patterns = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if msg.get('type') != 'assistant':
                    continue
                if msg.get('attributionSkill', ''):
                    continue
                content = msg.get('message', {}).get('content', [])
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get('type') != 'tool_use':
                        continue
                    if block.get('name') != 'Bash':
                        continue
                    cmd = block.get('input', {}).get('command', '')
                    pat = classify_bash_command(cmd)
                    if pat:
                        patterns.append(pat)
    except (OSError, IOError):
        pass
    return patterns


def extract_patterns_from_hint_log(log_path: str) -> list:
    results = []
    if not log_path or not os.path.exists(log_path):
        return results
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue
                event_type = parts[1] if len(parts) > 1 else ''
                if event_type == 'mechanical-bash-cluster':
                    for part in parts:
                        if part.startswith('pattern='):
                            pat = part[len('pattern='):]
                            if 'sqlite3' in pat:
                                results.append('sqlite3-select')
                            elif 'curl' in pat:
                                results.append('curl-get')
                            elif 'grep' in pat:
                                results.append('grep-recursive')
                            elif 'find' in pat:
                                results.append('find-scan')
                            break
                elif event_type == 'same-file-read-3x':
                    results.append('same-file-read')
    except (OSError, IOError):
        pass
    return results


SUGGESTED_NAMES = {
    'sqlite3-select': 'query-adam-db',
    'curl-get':       'http-probe',
    'grep-recursive': 'codebase-search',
    'find-scan':      'file-finder',
    'same-file-read': 'cached-file-reader',
}

SUGGESTED_FRONTMATTER = {
    'sqlite3-select': {'model': 'haiku', 'context': 'fork'},
    'curl-get':       {'model': 'haiku', 'context': 'fork'},
    'grep-recursive': {'model': 'sonnet', 'context': 'fork'},
    'find-scan':      {'model': 'sonnet', 'context': 'fork'},
    'same-file-read': {'model': 'sonnet', 'context': 'fork'},
}

# Pattern → tokens for fuzzy "possibly-covered" detection.
# Token must be 2+ chars; matched against existing skill description as whole word.
PATTERN_TOKENS = {
    'sqlite3-select': ['sqlite', 'sql', 'database', 'db', 'query'],
    'curl-get':       ['http', 'curl', 'url', 'api', 'fetch'],
    'grep-recursive': ['grep', 'search', 'codebase'],
    'find-scan':      ['find', 'glob', 'locate'],
    'same-file-read': ['read', 'cache', 'reread'],
}


def parse_skill_frontmatter(path: str) -> dict | None:
    """Parse minimal YAML frontmatter (single-line key: value) from a SKILL.md.
    Returns dict with keys present, or None on parse failure."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
    except (OSError, IOError):
        return None
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
    if not m:
        return None
    block = m.group(1)
    result = {'_path': path}
    for line in block.split('\n'):
        if ':' not in line:
            continue
        key, _, val = line.partition(':')
        key = key.strip()
        val = val.strip()
        if val.startswith('"') and val.endswith('"'):
            val = val[1:-1]
        elif val.startswith("'") and val.endswith("'"):
            val = val[1:-1]
        result[key] = val
    return result


def enumerate_existing_skills(root_globs: list) -> list:
    """Find all SKILL.md across given glob patterns; return parsed frontmatter list.
    Each entry has at least: name, description, _path."""
    skills = []
    seen_paths = set()
    for pattern in root_globs:
        for path in glob.glob(pattern, recursive=True):
            if path in seen_paths:
                continue
            seen_paths.add(path)
            fm = parse_skill_frontmatter(path)
            if not fm:
                continue
            if not fm.get('name'):
                continue
            skills.append(fm)
    return skills


def load_history(history_path: str) -> list:
    """Load distill-history.jsonl entries. Returns list of dicts."""
    entries = []
    if not history_path or not os.path.exists(history_path):
        return entries
    try:
        with open(history_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except (OSError, IOError):
        pass
    return entries


def parse_iso8601(s: str) -> datetime | None:
    if not s:
        return None
    try:
        # Accept 'Z' suffix and offsets
        s2 = s.rstrip('Z')
        if s2 == s:
            # no Z; try as-is
            return datetime.fromisoformat(s)
        return datetime.fromisoformat(s2).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def is_declined_recently(pattern: str, history: list, now: datetime, ttl_days: int) -> bool:
    """Return True if pattern has outcome=declined in history within ttl_days of now."""
    cutoff = now - timedelta(days=ttl_days)
    for entry in history:
        if entry.get('pattern') != pattern:
            continue
        if entry.get('outcome') != 'declined':
            continue
        ts = parse_iso8601(entry.get('ts', ''))
        if ts is None:
            continue
        if ts >= cutoff:
            return True
    return False


def find_built_record(pattern: str, suggested_name: str, history: list) -> dict | None:
    """Find a 'created' history entry matching the pattern or suggested name.
    Returns most recent matching entry, or None."""
    matches = []
    for entry in history:
        if entry.get('outcome') != 'created':
            continue
        if entry.get('pattern') == pattern or entry.get('suggested_name') == suggested_name:
            matches.append(entry)
    if not matches:
        return None
    matches.sort(key=lambda e: e.get('ts', ''), reverse=True)
    return matches[0]


def _tokens(s: str) -> set:
    """Extract lowercase word tokens of length >=2 from a string."""
    return {tok.lower() for tok in re.findall(r'[A-Za-z][A-Za-z0-9]+', s) if len(tok) >= 2}


def find_covering_skill(pattern: str, suggested_name: str,
                       existing_skills: list) -> tuple[str | None, dict | None]:
    """Detect if an existing skill possibly covers this candidate.

    Returns (status, covering_skill_dict) where status is one of:
      'name-exists'      — exact name match
      'possibly-covered' — fuzzy: name token + description token both overlap pattern tokens
      None               — no coverage detected
    """
    if not existing_skills:
        return (None, None)

    # Exact name match
    for skill in existing_skills:
        if skill.get('name') == suggested_name:
            return ('name-exists', skill)

    # Fuzzy: candidate token set vs existing skill name+description token set.
    # Per DP-2: BOTH name and description must show overlap (reduce false positives).
    candidate_name_tokens = _tokens(suggested_name)
    pattern_kw = set(PATTERN_TOKENS.get(pattern, []))
    candidate_token_set = candidate_name_tokens | pattern_kw

    if not candidate_token_set:
        return (None, None)

    for skill in existing_skills:
        skill_name_tokens = _tokens(skill.get('name', ''))
        skill_desc_tokens = _tokens(skill.get('description', ''))
        name_hit = bool(candidate_token_set & skill_name_tokens)
        desc_hit = bool(candidate_token_set & skill_desc_tokens)
        if name_hit and desc_hit:
            return ('possibly-covered', skill)

    return (None, None)


def compute_status(pattern: str, suggested_name: str,
                  existing_skills: list, history: list) -> tuple[str, dict | None]:
    """Decide status + optional covered_by record.

    Priority:
      1. history says 'created' → already-built (point to history entry / created path)
      2. existing skill matches suggested_name exactly → name-exists
      3. existing skill description overlaps → possibly-covered
      4. otherwise → new
    """
    built = find_built_record(pattern, suggested_name, history)
    if built:
        covered_by = {
            'kind': 'history',
            'created_path': built.get('created_path'),
            'ts': built.get('ts'),
        }
        return ('already-built', covered_by)

    status, skill = find_covering_skill(pattern, suggested_name, existing_skills)
    if status:
        return (status, {
            'kind': 'existing-skill',
            'name': skill.get('name'),
            'description': skill.get('description', '')[:120],
            'path': skill.get('_path'),
        })

    return ('new', None)


def build_candidates(pattern_counts: dict, existing_skills: list,
                    history: list, now: datetime, declined_ttl_days: int) -> list:
    """Build candidate list from pattern frequency counts.
    Drops patterns declined within ttl. Annotates each with status + covered_by."""
    candidates = []
    for pattern, frequency in sorted(pattern_counts.items(), key=lambda x: -x[1]):
        if frequency < MIN_FREQUENCY:
            continue
        if is_declined_recently(pattern, history, now, declined_ttl_days):
            continue
        suggested_name = SUGGESTED_NAMES.get(pattern, pattern.replace('-', '_') + '_skill')
        suggested_frontmatter = SUGGESTED_FRONTMATTER.get(pattern, {'model': 'sonnet', 'context': 'fork'})
        status, covered_by = compute_status(pattern, suggested_name, existing_skills, history)
        candidate = {
            'pattern': pattern,
            'frequency': frequency,
            'est_cost_usd': round(frequency * COST_DELTA_PER_TURN, 2),
            'suggested_name': suggested_name,
            'suggested_frontmatter': suggested_frontmatter,
            'status': status,
        }
        if covered_by:
            candidate['covered_by'] = covered_by
        candidates.append(candidate)
    return candidates


def main():
    parser = argparse.ArgumentParser(description='Scan session jsonl for skill candidates')
    parser.add_argument('project_path', nargs='?', default=None,
                        help='Project path (used to locate session jsonl via ~/.claude/projects/)')
    parser.add_argument('output_file', nargs='?', default=None,
                        help='Output JSON file path (default: stdout)')
    parser.add_argument('--jsonl-dir', default=None,
                        help='Override: read jsonl files from this directory')
    parser.add_argument('--include-hint-log', default=None,
                        help='Path to cost-hint.log for secondary signal')
    parser.add_argument('--output', default=None,
                        help='Output file path (alternative to positional arg)')
    parser.add_argument('--no-archive', action='store_true',
                        help='Skip archiving .claude/cost-hint.log even when project_path is given.')
    parser.add_argument('--skill-roots', nargs='+', default=None,
                        help='Override glob patterns for enumerating existing SKILL.md files. '
                             'Default: indie-toolkit + ~/.claude/skills + ~/.claude/plugins.')
    parser.add_argument('--history-file', default=None,
                        help='Path to distill-history.jsonl. '
                             'Default: ${project}/.claude/distill-history.jsonl when project_path given.')
    parser.add_argument('--no-history', action='store_true',
                        help='Skip history check (do not load distill-history.jsonl).')
    parser.add_argument('--no-existing-skills', action='store_true',
                        help='Skip existing-skill enumeration (status will always be "new").')
    parser.add_argument('--declined-ttl-days', type=int, default=DECLINED_TTL_DAYS,
                        help=f'TTL for declined-recently filter (default {DECLINED_TTL_DAYS}).')
    args = parser.parse_args()

    # Determine jsonl source
    if args.jsonl_dir:
        jsonl_files = find_jsonl_files(args.jsonl_dir)
    elif args.project_path:
        jsonl_files = find_jsonl_files_for_project(args.project_path)
    else:
        jsonl_files = []

    # Aggregate pattern counts
    pattern_counts: dict = defaultdict(int)
    for filepath in jsonl_files:
        for pat in extract_patterns_from_jsonl(filepath):
            pattern_counts[pat] += 1

    # Secondary signal from hint log
    hint_log_path = args.include_hint_log
    if not hint_log_path and args.project_path:
        hint_log_path = os.path.join(args.project_path, '.claude', 'cost-hint.log')
    if hint_log_path:
        for pat in extract_patterns_from_hint_log(hint_log_path):
            pattern_counts[pat] += 2

    # Load existing-skill inventory (DP-2: name + description fuzzy match)
    if args.no_existing_skills:
        existing_skills = []
    else:
        if args.skill_roots:
            roots = list(args.skill_roots)
        else:
            roots = list(DEFAULT_SKILL_ROOT_GLOBS)
            # If invoked with a project_path, also scan the project's own
            # plugin-monorepo layout: {project}/{plugin}/skills/{name}/SKILL.md
            if args.project_path:
                proj = os.path.abspath(args.project_path)
                roots.append(os.path.join(proj, '*', 'skills', '*', 'SKILL.md'))
        existing_skills = enumerate_existing_skills(roots)

    # Load distill history (DP-1: project-scoped; DP-3: 30-day declined TTL)
    if args.no_history:
        history = []
        history_path = None
    else:
        history_path = args.history_file
        if not history_path and args.project_path:
            history_path = os.path.join(args.project_path, '.claude', 'distill-history.jsonl')
        history = load_history(history_path) if history_path else []

    now = datetime.now(timezone.utc)
    candidates = build_candidates(
        pattern_counts, existing_skills, history, now, args.declined_ttl_days
    )

    result = {
        'candidates': candidates,
        'meta': {
            'existing_skill_count': len(existing_skills),
            'history_entries': len(history),
            'history_path': history_path,
            'declined_ttl_days': args.declined_ttl_days,
        }
    }

    # Archive cost-hint.log (unchanged behavior)
    if args.project_path and not args.jsonl_dir and not args.no_archive:
        real_log = os.path.join(args.project_path, '.claude', 'cost-hint.log')
        try:
            log_nonempty = os.path.exists(real_log) and os.path.getsize(real_log) > 0
        except OSError:
            log_nonempty = False
        if log_nonempty:
            month_tag = datetime.now().strftime('%Y-%m')
            archive_path = os.path.join(args.project_path, '.claude', f'cost-hint-archive-{month_tag}.log')
            try:
                with open(real_log, 'r') as src, open(archive_path, 'a') as dst:
                    dst.write(src.read())
                open(real_log, 'w').close()
            except (OSError, IOError) as e:
                print(f'[scan.py] Warning: could not archive cost-hint.log: {e}', file=sys.stderr)

    # Output
    output_path = args.output or args.output_file
    output_json = json.dumps(result, indent=2)
    if output_path and output_path != '/dev/stdout':
        with open(output_path, 'w') as f:
            f.write(output_json)
    else:
        print(output_json)


if __name__ == '__main__':
    main()
