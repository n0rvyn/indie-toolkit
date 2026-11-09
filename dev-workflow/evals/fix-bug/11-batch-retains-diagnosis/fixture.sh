#!/usr/bin/env bash
set -eu
mkdir -p .claude/multi-issue-loop/baseline .claude/multi-issue-loop/disambig
cat > app.py <<'EOF'
import sys


def total():
    return 30


def caption():
    return "old title"


if __name__ == "__main__":
    print(total() if sys.argv[1] == "total" else caption())
EOF
cat > issues.md <<'EOF'
# Synthetic local issues
- B21: `python3 -B app.py total` prints 30; acceptance is 60.
- B22: `python3 -B app.py caption` prints old title; acceptance is new title.
Original authorization: diagnose these two issues and write a repair plan for review.
EOF
cat > .claude/multi-issue-loop/state.json <<'EOF'
{"issues":["B21","B22"],"bundles":[],"current_bundle":null,"current_step":"L1.5","regression_pass_history":[]}
EOF
cat > .claude/multi-issue-loop/baseline/B21.md <<'EOF'
`python3 -B app.py total` returned 30, expected 60. Observed failure reproduced.
EOF
cat > .claude/multi-issue-loop/baseline/B22.md <<'EOF'
`python3 -B app.py caption` returned old title, expected new title. Observed failure reproduced.
EOF
cat > .claude/multi-issue-loop/disambig/B21.md <<'EOF'
The initial hypothesis was stale build output. It was disproved: the actual interpreter reads the current app.py, which returns 30. No cached artifact or alternate process is involved. The user-visible total still returns 30 rather than 60. No patch has been made.
EOF
