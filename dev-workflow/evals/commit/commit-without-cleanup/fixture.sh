#!/bin/bash
set -eu
git init -q
git config user.email eval@example.com
git config user.name 'Commit eval'
mkdir -p src logs
printf '# Existing project
' > README.md
git add -- README.md
git commit -qm 'chore: initialize fixture'
printf 'def report(rows):
    return len(rows)
' > src/report.py
printf 'One-shot debug output
' > logs/one-shot-debug.log
