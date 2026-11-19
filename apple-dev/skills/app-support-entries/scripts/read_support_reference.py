#!/usr/bin/env python3
"""Read the single bundled checklist, resolving symlinked skill discovery paths."""
from pathlib import Path

def resolve_reference(script_file=__file__):
    package=Path(script_file).resolve().parents[3]
    reference=package/'references/app-support-entries.md'
    if not reference.is_file():raise ValueError('Bundled canonical support reference is missing; do not guess an installed-cache path')
    return reference

if __name__=='__main__':
    try:
        reference=resolve_reference()
        print('Canonical source: '+str(reference))
        print(reference.read_text())
    except (ValueError,OSError) as e:raise SystemExit(str(e))
