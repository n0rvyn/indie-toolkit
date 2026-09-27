#!/bin/bash
# Builds a small git repo in the run's empty workspace. Runs only with --scaffold.
set -e
git init -q
git config user.email eval@example.com
git config user.name eval
mkdir -p docs/06-plans src
cat > src/dates.py <<'PY'
def format_date(d):
    return d.strftime("%Y-%m-%d")
PY
printf '# demo\n' > CLAUDE.md
git add -A && git commit -qm "fix: validate amounts before Decimal parsing"
