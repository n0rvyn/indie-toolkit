#!/usr/bin/env python3
"""Append/check one stable Apple Dev reference after kickoff instruction generation.
Only explicit project files are changed; no global configuration/cache edits.
"""
import argparse
import json
from pathlib import Path

START='<!-- apple-dev:app-support-entries:start -->'
END='<!-- apple-dev:app-support-entries:end -->'
REFERENCE='apple-dev/references/app-support-entries.md'
ENTRY='apple-dev:app-support-entries'
BLOCK=f'''{START}
## Apple App support-entry lifecycle

For Apple app creation, feature development, issue fixes and release preparation,
load `{ENTRY}` at task intake and closeout. It reads the shared canonical
checklist `{REFERENCE}` through the resolved Apple Dev plugin package;
this is a plugin resource, not a project-relative file or installed-cache path.
Maintain the existing project implementation/evidence record automatically;
report unresolved entries at closeout. Reading this checklist does not authorize
unrequested UI changes, outbound messages or release actions.
{END}
'''

def targets(root, selected=None):
    root=Path(root).resolve()
    if not root.is_dir():raise ValueError('Project directory does not exist')
    names=[selected] if selected else [n for n in ['AGENTS.md','CLAUDE.md'] if (root/n).exists()]
    if not names:names=['CLAUDE.md']
    if any(n not in ['AGENTS.md','CLAUDE.md'] for n in names):raise ValueError('Use the project AGENTS.md or CLAUDE.md convention')
    files=[root/n for n in names]
    if any(p.is_symlink() for p in files):raise ValueError('Instruction symlink requires explicit convention review; not overwritten')
    return files

def valid(text):
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    if text.count(START)!=1 or text.count(END)!=1:return False
    first=text.index(START);last=text.index(END)+len(END)
    return text[first:last]==BLOCK.rstrip('\n')

def run(root, platform, mode, selected=None):
    if platform!='apple':return {'skipped':True,'reason':'non-Apple project','files':[]}
    files=targets(root,selected)
    # Validate all existing blocks before any write, preserving hand edits.
    for p in files:
        if p.exists():
            text=p.read_bytes().decode('utf-8')
            if (START in text or END in text) and not valid(text):
                raise ValueError(f'{p.name}: existing support-reference block is incomplete or edited; preserve and review it')
    if mode=='install':
        for p in files:
            text=p.read_bytes().decode('utf-8') if p.exists() else ''
            if not valid(text):
                newline = '\r\n' if '\r\n' in text else '\n'
                separator = '' if not text or text.endswith(newline * 2) else newline if text.endswith(newline) else newline * 2
                p.write_bytes((text + separator + BLOCK.replace('\n', newline)).encode('utf-8'))
    missing=[p.name for p in files if not p.exists() or not valid(p.read_bytes().decode('utf-8'))]
    if missing:raise ValueError('Post-generation shared-reference check failed: '+', '.join(missing))
    return {'skipped':False,'files':[p.name for p in files],'reference':REFERENCE,'verified':True}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode',choices=['install','check']);p.add_argument('--project',required=True)
    p.add_argument('--platform',choices=['apple','other'],required=True)
    p.add_argument('--instruction-file',choices=['AGENTS.md','CLAUDE.md'])
    a=p.parse_args()
    reference=Path(__file__).resolve().parents[3]/'references/app-support-entries.md'
    if a.platform=='apple' and not reference.is_file():
        raise ValueError('Bundled canonical checklist missing; instruction generation incomplete')
    result=run(a.project,a.platform,a.mode,a.instruction_file)
    if a.platform=='apple':result['bundle_reference_verified']=True
    print(json.dumps(result))

if __name__=='__main__':
    try:main()
    except (ValueError,OSError) as e:raise SystemExit(str(e))
