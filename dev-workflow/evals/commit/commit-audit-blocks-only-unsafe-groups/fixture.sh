#!/bin/bash
set -eu
git init -q
git config user.email eval@example.com
git config user.name 'Commit eval'
mkdir -p dev-workflow/{export,import,runner,assets}
printf '# Existing project
' > README.md
printf 'def export_total(rows):\n    return list(rows)\n' > dev-workflow/export/total.py
git add -- README.md dev-workflow/export/total.py
git commit -qm 'chore: initialize fixture'
printf 'def export_total(rows):
    # TODO: Support custom delimiters
    return len(rows)
' > dev-workflow/export/total.py
printf 'api_key = "%s-%032d"
' sk 0 > dev-workflow/import/client.py
printf 'def run():
    breakpoint()
' > dev-workflow/runner/task.py
dd if=/dev/zero of=dev-workflow/assets/archive.bin bs=1024 count=512 2>/dev/null
