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
mkdir -p .claude/afk
cat > .claude/afk/demo.md <<'MD'
# afk run log — demo
[范围] src/sync.py only
[判据 1] pytest tests/test_sync.py
- 10:02 change A (retry backoff) -> 判据 1 red
- 10:20 change B (lock around flush) -> 判据 1 red again
- deferred nice-to-have: rename SyncQueue.flush to drain
## 终止：同一判据跨改动红两次
MD
cat > .claude/execute-plan-checkpoint.json <<'JSON'
{"completed": {"1": true, "2": true}}
JSON
printf '# demo\n' > CLAUDE.md
git add -A && git commit -qm "chore: init"
