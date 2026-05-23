#!/usr/bin/env python3
"""
scan.py — distill-project-skills scanner

Scans session jsonl files and optional cost-hint.log to surface candidate
patterns worth crystallizing as skills.

Usage:
  python3 scan.py <project-path> [output-file]
  python3 scan.py --jsonl-dir <dir> [--include-hint-log <log>] [--output <file>]

Output: JSON with structure {"candidates": [...]}
Each candidate: {pattern, frequency, est_cost_usd, suggested_name, suggested_frontmatter}
"""

import argparse
import json
import os
import re
import sys
import glob
from collections import defaultdict
from pathlib import Path


# Cost delta: Opus main-line vs sub-agent sonnet fork, per turn estimate
COST_DELTA_PER_TURN = 0.73

# Minimum frequency to report as candidate
MIN_FREQUENCY = 3


def encode_path(path: str) -> str:
    """Encode a filesystem path to Claude's projects directory naming convention.
    /Users/foo/Code/Bar -> -Users-foo-Code-Bar
    Claude preserves the leading hyphen from the leading slash; do NOT strip it.
    """
    return path.replace('/', '-')


def find_jsonl_files(jsonl_dir: str) -> list:
    """Find all .jsonl files in the given directory."""
    return glob.glob(os.path.join(jsonl_dir, '*.jsonl'))


def find_jsonl_files_for_project(project_path: str) -> list:
    """Find session jsonl files for a project path via Claude's projects dir."""
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
    """Return pattern name if command matches a mechanical pattern, else None."""
    cmd = cmd.strip()
    for name, pattern in MECHANICAL_PATTERNS:
        if pattern.match(cmd):
            return name
    return None


def extract_patterns_from_jsonl(filepath: str) -> list:
    """Extract mechanical Bash command patterns from a session jsonl file.
    Returns list of pattern names found in no-skill assistant turns."""
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

                # Claude jsonl record shape: top-level has `type`, `message`,
                # `attributionSkill`. Role/content live nested inside `message`.
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
    """Extract pattern names from cost-hint.log as secondary signal.
    Returns list of (pattern_name, count) tuples."""
    results = []
    if not log_path or not os.path.exists(log_path):
        return results
    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                # Format: <iso8601> <event-type> pattern=<name> count=<N> ...
                # or:     <iso8601> same-file-read-3x file=<path> count=<N>
                parts = line.split()
                if len(parts) < 2:
                    continue
                event_type = parts[1] if len(parts) > 1 else ''

                if event_type == 'mechanical-bash-cluster':
                    # extract pattern= field
                    for part in parts:
                        if part.startswith('pattern='):
                            pat = part[len('pattern='):]
                            # Map to our internal names
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


def build_candidates(pattern_counts: dict) -> list:
    """Build candidate list from pattern frequency counts."""
    candidates = []
    for pattern, frequency in sorted(pattern_counts.items(), key=lambda x: -x[1]):
        if frequency < MIN_FREQUENCY:
            continue
        est_cost = round(frequency * COST_DELTA_PER_TURN, 2)
        candidates.append({
            'pattern': pattern,
            'frequency': frequency,
            'est_cost_usd': est_cost,
            'suggested_name': SUGGESTED_NAMES.get(pattern, pattern.replace('-', '_') + '_skill'),
            'suggested_frontmatter': SUGGESTED_FRONTMATTER.get(pattern, {'model': 'sonnet', 'context': 'fork'}),
        })
    return candidates


def main():
    parser = argparse.ArgumentParser(description='Scan session jsonl for skill candidates')
    parser.add_argument('project_path', nargs='?', default=None,
                        help='Project path (used to locate session jsonl via ~/.claude/projects/)')
    parser.add_argument('output_file', nargs='?', default=None,
                        help='Output JSON file path (default: stdout)')
    parser.add_argument('--jsonl-dir', default=None,
                        help='Override: read jsonl files from this directory instead of ~/.claude/projects/')
    parser.add_argument('--include-hint-log', default=None,
                        help='Path to cost-hint.log for secondary signal')
    parser.add_argument('--output', default=None,
                        help='Output file path (alternative to positional arg)')
    parser.add_argument('--no-archive', action='store_true',
                        help='Skip archiving .claude/cost-hint.log even when project_path is given. '
                             'Use this when running against a project path you do not own '
                             '(debugging, exploration) so the existing log file is not rotated.')
    args = parser.parse_args()

    # Determine jsonl source
    if args.jsonl_dir:
        jsonl_files = find_jsonl_files(args.jsonl_dir)
    elif args.project_path:
        jsonl_files = find_jsonl_files_for_project(args.project_path)
    else:
        jsonl_files = []

    # Aggregate pattern counts across all session files
    pattern_counts: dict = defaultdict(int)

    for filepath in jsonl_files:
        patterns = extract_patterns_from_jsonl(filepath)
        for pat in patterns:
            pattern_counts[pat] += 1

    # Secondary signal from hint log
    hint_log_path = args.include_hint_log
    if not hint_log_path and args.project_path:
        # Default hint log location (DP-002: project-scoped)
        hint_log_path = os.path.join(args.project_path, '.claude', 'cost-hint.log')

    if hint_log_path:
        hint_patterns = extract_patterns_from_hint_log(hint_log_path)
        for pat in hint_patterns:
            # Hint log entries get higher confidence weight (plan spec).
            # Each hint event adds 2 to the count (weighted signal).
            pattern_counts[pat] += 2

    candidates = build_candidates(pattern_counts)
    result = {'candidates': candidates}

    # Archive cost-hint.log if using real project path (not test override + not opted out).
    # Guards (all must hold to archive):
    #   - project_path was provided (not --jsonl-dir override)
    #   - --no-archive flag NOT set
    #   - log file exists AND is non-empty (don't rotate empty/missing files)
    if args.project_path and not args.jsonl_dir and not args.no_archive:
        real_log = os.path.join(args.project_path, '.claude', 'cost-hint.log')
        try:
            log_nonempty = os.path.exists(real_log) and os.path.getsize(real_log) > 0
        except OSError:
            log_nonempty = False
        if log_nonempty:
            from datetime import datetime
            month_tag = datetime.now().strftime('%Y-%m')
            archive_path = os.path.join(args.project_path, '.claude', f'cost-hint-archive-{month_tag}.log')
            try:
                with open(real_log, 'r') as src, open(archive_path, 'a') as dst:
                    dst.write(src.read())
                # Truncate primary log
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
