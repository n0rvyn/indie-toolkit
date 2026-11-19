#!/bin/bash
set -eu
git init -q
git config user.email eval@example.com
git config user.name 'Commit eval'
mkdir -p src tools build-output logs notes
cat > tools/build-demo.sh <<'SH'
#!/bin/bash
mkdir -p build-output
printf 'generated example binary
' > build-output/demo.bin
SH
printf 'def report(rows):
    return rows
' > src/report.py
git add -- src/report.py tools/build-demo.sh
git commit -qm 'chore: initialize fixture'
printf 'def report(rows):
    return {"row_count": len(rows)}
' > src/report.py
bash tools/build-demo.sh
printf 'previous output from tools/build-demo.sh
' > build-output/demo-old.bin
printf 'Private local experiment notes
' > notes/scratch.md
printf 'One-shot diagnostics; no dependencies
' > logs/one-shot-debug.log
printf 'Only baseline for unfinished comparison
' > logs/profiling-baseline.log
printf 'Unknown provenance
' > logs/unknown.log
