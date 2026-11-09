#!/usr/bin/env bash
set -eu
cat > calculator.py <<'EOF'
FACTOR = 2


def calculate(value):
    return value * FACTOR


def main():
    value = 3
    print(calculate(value) // 2)


if __name__ == "__main__":
    main()
EOF
cat > experiment.py <<'EOF'
import hashlib
import json
from pathlib import Path
import subprocess
from calculator import FACTOR, calculate

observation = {
    "source_sha256": hashlib.sha256(Path("calculator.py").read_bytes()).hexdigest(),
    "factor": FACTOR,
    "direct": calculate(3),
    "cli": subprocess.check_output(["python3", "-B", "calculator.py"], text=True).strip(),
}
with Path("observations.jsonl").open("a") as out:
    out.write(json.dumps(observation) + "\n")
print(json.dumps(observation))
EOF
cat > diagnosis.md <<'EOF'
# Synthetic prior agent return

## Diagnosis
Status: probable
Confidence: medium
### Cause
calculator.py:1 — FACTOR is suspected to be too small for the displayed result.
Evidence: the reported output is half the expected output; the CLI has not yet been exercised by this diagnosis.
Chain: main → calculate → displayed result
### Same-Cause Sites
none found
### Consumers
calculator.py:7 — main displays the result.
### Design Verdict
Verdict: bug
Evidence: acceptance requires CLI input 3 to display 6.
### Premise Check
n/a
### Unverified Premises
- Whether calculate itself is wrong or its caller transforms the correct value.
### Next Experiment
Run python3 -B experiment.py before changing calculator.py. It records the current source hash, calls calculate(3), then runs the actual CLI. Direct=3 and CLI=3 supports the suspected factor issue; direct=6 and CLI=3 rejects that explanation and places the failure after calculate.
EOF
