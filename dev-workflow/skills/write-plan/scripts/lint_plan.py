#!/usr/bin/env python3
"""Check a plan file for the formats downstream tools depend on.

Only load-bearing formats are checked, using execute-plan's own parser
(`execute-plan/scripts/compute_checkpoints.py`), so "passes lint" means "execute-plan
sees every task". Prose quality is not checked here — that is verify-plan's job.

Usage:
    python3 lint_plan.py <plan.md>

Prints one JSON object {ok, tasks, errors, warnings}; exit 1 when errors exist.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "execute-plan", "scripts"))
from compute_checkpoints import DEPENDS_ON_RE, TASK_HEADING_RE, parse_tasks  # noqa: E402

# A heading shaped like a task (id, then a colon or dash separator) that the parser rejects,
# e.g. `### Task 2b-tests:` or `### Task 5.5:`. Notes headings such as `### Task 5 改动后` are not flagged.
LOOKS_LIKE_TASK_RE = re.compile(r"^#{1,6}\s*Tasks?\s*\d+\S*\s*([:：]|[-–—]\s)", re.IGNORECASE)
DEPENDS_MENTION_RE = re.compile(r"\*\*Depends on:?\*\*", re.IGNORECASE)
CODE_FENCE_RE = re.compile(r"^\s*(```|~~~)")
KNOWN_SUFFIXES = {"tests", "impl"}
NO_DEPENDENCY_RE = re.compile(r"^(none|n/?a|无|—|–|-)?(\s|[.(（]|$)", re.IGNORECASE)


def strip_fences(text):
    """Blank out fenced code blocks so format examples inside them are not linted."""
    out, fenced = [], False
    for line in text.splitlines(keepends=True):
        if CODE_FENCE_RE.match(line):
            fenced = not fenced
            out.append("\n")
            continue
        out.append("\n" if fenced else line)
    return "".join(out)


def lint(text):
    text = strip_fences(text)
    errors, warnings = [], []
    lines = text.splitlines()

    for i, line in enumerate(lines, 1):
        if LOOKS_LIKE_TASK_RE.match(line) and not TASK_HEADING_RE.match(line):
            errors.append({"line": i, "msg": f"looks like a task heading but execute-plan will not see it: {line.strip()!r} "
                                             "(expected `### Task N: name`, `### Task N-tests: name` or `### Task N-impl: name`)"})

    tasks = parse_tasks(text)
    if not tasks:
        errors.append({"line": None, "msg": "no `### Task N:` headings found — execute-plan would run nothing"})
        return {"ok": False, "tasks": 0, "errors": errors, "warnings": warnings}

    ids = [t["id"] for t in tasks]
    seen = set()
    for tid in ids:
        if tid in seen:
            errors.append({"task": tid, "msg": "duplicate task id"})
        seen.add(tid)

    for t in tasks:
        tid, body = t["id"], t["body"]
        if t["suffix"] and t["suffix"] not in KNOWN_SUFFIXES:
            warnings.append({"task": tid, "msg": f"suffix `-{t['suffix']}` is not one downstream tools recognize (`-tests` / `-impl`)"})
        if "**Files:**" not in body:
            errors.append({"task": tid, "msg": "missing `**Files:**`"})
        if "**Verify:**" not in body:
            errors.append({"task": tid, "msg": "missing `**Verify:**` — the execute-plan agent runs this to decide pass/fail"})
        dep_value = None
        mm = DEPENDS_MENTION_RE.search(body)
        if mm:
            dep_value = body[mm.end():body.find("\n", mm.end()) if "\n" in body[mm.end():] else len(body)].strip()
        if mm and not DEPENDS_ON_RE.search(body) and not NO_DEPENDENCY_RE.match(dep_value):
            errors.append({"task": tid, "msg": "`**Depends on:**` present but not in the form `**Depends on:** Task N` — the dependency is ignored"})
        dm = DEPENDS_ON_RE.search(body)
        if dm:
            ref = dm.group(1) + (f"-{dm.group(2)}" if dm.group(2) else "")
            if ref not in seen and ref not in ids:
                errors.append({"task": tid, "msg": f"depends on Task {ref}, which does not exist"})
            dep_line = body[dm.start():body.find("\n", dm.start())]
            if len(re.findall(r"Task\s+\d+", dep_line)) > 1:
                warnings.append({"task": tid, "msg": "several tasks on one `**Depends on:**` line — checkpoint computation only reads the first"})

    nums_with = {s: {t["num"] for t in tasks if t["suffix"] == s} for s in KNOWN_SUFFIXES}
    for n in sorted(nums_with["tests"] - nums_with["impl"]):
        errors.append({"task": f"{n}-tests", "msg": f"no matching `Task {n}-impl`"})
    for n in sorted(nums_with["impl"] - nums_with["tests"]):
        errors.append({"task": f"{n}-impl", "msg": f"no matching `Task {n}-tests`"})

    return {"ok": not errors, "tasks": len(tasks), "errors": errors, "warnings": warnings}


def main(argv):
    if len(argv) != 2:
        print("usage: lint_plan.py <plan.md>", file=sys.stderr)
        return 2
    with open(argv[1], encoding="utf-8") as f:
        result = lint(f.read())
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
