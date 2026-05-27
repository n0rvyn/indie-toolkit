#!/usr/bin/env python3
"""
verify_frontmatter.py — Phase B helper for distill-project-skills.

After skill-master:plugin-master creates a new skill via distill's follow-up
flow, this script verifies the created SKILL.md frontmatter matches the
expected cost-posture (model + context).

Exit codes:
  0 — frontmatter matches expected
  1 — frontmatter missing or mismatched (diff printed to stdout)
  2 — usage error

Usage:
  python3 verify_frontmatter.py <skill-md-path> --expect-model haiku --expect-context fork
  python3 verify_frontmatter.py <skill-md-path> --expect-json '{"model":"sonnet","context":"fork"}'
"""

import argparse
import json
import re
import sys


def parse_frontmatter(path: str) -> dict | None:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
    except (OSError, IOError) as e:
        print(f'ERROR: cannot read {path}: {e}', file=sys.stderr)
        return None
    m = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
    if not m:
        print(f'ERROR: no frontmatter block found in {path}', file=sys.stderr)
        return None
    block = m.group(1)
    result = {}
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


def main() -> int:
    parser = argparse.ArgumentParser(description='Verify SKILL.md frontmatter matches expected cost-posture')
    parser.add_argument('skill_path', help='Path to the SKILL.md to verify')
    parser.add_argument('--expect-model', default=None,
                        help='Expected `model:` value (e.g. haiku, sonnet)')
    parser.add_argument('--expect-context', default=None,
                        help='Expected `context:` value (e.g. fork)')
    parser.add_argument('--expect-effort', default=None,
                        help='Expected `effort:` value (e.g. low, medium, high)')
    parser.add_argument('--expect-json', default=None,
                        help='JSON object of expected frontmatter keys (overrides --expect-* flags)')
    args = parser.parse_args()

    fm = parse_frontmatter(args.skill_path)
    if fm is None:
        return 1

    # Build expected dict
    if args.expect_json:
        try:
            expected = json.loads(args.expect_json)
        except json.JSONDecodeError as e:
            print(f'ERROR: --expect-json not valid JSON: {e}', file=sys.stderr)
            return 2
    else:
        expected = {}
        if args.expect_model is not None:
            expected['model'] = args.expect_model
        if args.expect_context is not None:
            expected['context'] = args.expect_context
        if args.expect_effort is not None:
            expected['effort'] = args.expect_effort

    if not expected:
        print('ERROR: no expectations provided (use --expect-model / --expect-context / --expect-effort / --expect-json)', file=sys.stderr)
        return 2

    mismatches = []
    for key, expected_val in expected.items():
        actual_val = fm.get(key)
        if actual_val != expected_val:
            mismatches.append({
                'key': key,
                'expected': expected_val,
                'actual': actual_val,
            })

    if mismatches:
        print('FRONTMATTER MISMATCH:')
        for m in mismatches:
            print(f'  {m["key"]}: expected={m["expected"]!r} actual={m["actual"]!r}')
        print(f'\nFile: {args.skill_path}')
        return 1

    print(f'OK: frontmatter matches expected ({", ".join(f"{k}={v}" for k,v in expected.items())})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
