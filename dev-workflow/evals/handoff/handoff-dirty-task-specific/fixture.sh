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
cat > docs/06-plans/HANDOFF-2026-09-20-1010.md <<'MD'
## 0. 你（新会话）现在要做的
Read this file.
## 7. 下一步
1. Import tasks 1-2 are done; do not re-verify them.
MD
cat > CLAUDE.md <<'MD'
# demo

## 必读顺序
1. **新会话第一件事：读 docs/06-plans/HANDOFF-2026-09-20-1010.md**
MD
git add -A && git commit -qm "chore: init"
printf 'def parse_row(r):\n    return r.split(",")  # WIP: task 3\n' > src/importer.py
