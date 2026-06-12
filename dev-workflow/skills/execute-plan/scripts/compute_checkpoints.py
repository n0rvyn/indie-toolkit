#!/usr/bin/env python3
"""
compute_checkpoints.py — pure checkpoint computation for execute-plan.

Parses a plan file and emits JSON with:
  - batch_size: int
  - total: int (number of tasks)
  - batches: [[taskId...]] — canonical task ids only ("<N>" / "<N>-tests" / "<N>-impl")
  - dependents: {taskId: int} — direct downstream dependent count
  - hard_stops: [batchIndex...] — batch 0 always; any batch with a task whose
                dependents >= K; any batch with a task body containing
                `<!-- checkpoint -->`

Pair-keep rule: a <N>-tests / <N>-impl pair must stay in the same batch.
When a batch cut would fall between them, push the -tests task into the next
batch with its -impl (a batch may run one over batch_size to keep a pair
intact). This guarantees no pair straddles a batch boundary.

This is a pure function + CLI. No filesystem writes outside stdout.
"""

import argparse
import json
import re
import sys
from typing import Dict, List, Tuple


TASK_HEADING_RE = re.compile(r"^###\s+Task\s+(\d+)(?:-([a-zA-Z]+))?\s*:", re.MULTILINE)
DEPENDS_ON_RE = re.compile(r"\*\*Depends on:\*\*\s*Task\s+(\d+)(?:-([a-zA-Z]+))?")
CHECKPOINT_MARKER_RE = re.compile(r"<!--\s*checkpoint\s*-->")


def _canonical_id(num: int, suffix: str | None) -> str:
    """Build canonical task id: '<N>' / '<N>-<suffix>'."""
    if suffix is None:
        return str(num)
    return f"{num}-{suffix}"


def parse_tasks(plan_text: str) -> List[Dict]:
    """Parse `### Task N:` / `### Task N-tests:` / `### Task N-impl:` headings.

    Returns ordered list of {id, num, suffix, body, has_marker, depends_on}.
    """
    matches = list(TASK_HEADING_RE.finditer(plan_text))
    tasks: List[Dict] = []
    for i, m in enumerate(matches):
        num = int(m.group(1))
        suffix = m.group(2)  # None for plain "Task N"
        # Body runs from end of this heading to start of the next heading (or EOF)
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(plan_text)
        body = plan_text[body_start:body_end]

        # depends_on — single Task reference (the canonical plan form)
        depends_on = []
        dm = DEPENDS_ON_RE.search(body)
        if dm:
            depends_on.append(_canonical_id(int(dm.group(1)), dm.group(2)))

        tasks.append(
            {
                "id": _canonical_id(num, suffix),
                "num": num,
                "suffix": suffix,
                "body": body,
                "has_marker": bool(CHECKPOINT_MARKER_RE.search(body)),
                "depends_on": depends_on,
            }
        )
    return tasks


def compute_dependents(tasks: List[Dict]) -> Dict[str, int]:
    """Direct downstream dependent count (not transitive)."""
    dependents: Dict[str, int] = {t["id"]: 0 for t in tasks}
    for t in tasks:
        for dep in t["depends_on"]:
            if dep in dependents:
                dependents[dep] += 1
    return dependents


def build_batches(
    tasks: List[Dict], batch_size: int
) -> Tuple[List[List[str]], List[int]]:
    """Group tasks into batches of `batch_size`, applying pair-keep rule.

    A <N>-tests / <N>-impl pair must stay in the same batch. When a batch cut
    would land between them, push the -tests task into the next batch with
    its -impl (a batch may run one over batch_size to keep a pair intact).

    Returns (batches, pair_start_indices) where pair_start_indices are the
    indices in tasks where a "-tests" task begins a pair.
    """
    # Pre-compute pair boundaries: an index i is a pair start if tasks[i].suffix
    # is "tests" and tasks[i+1].suffix is "impl" with the same num.
    pair_starts = set()
    for i in range(len(tasks) - 1):
        a, b = tasks[i], tasks[i + 1]
        if (
            a["suffix"] == "tests"
            and b["suffix"] == "impl"
            and a["num"] == b["num"]
        ):
            pair_starts.add(i)

    batches: List[List[str]] = []
    i = 0
    n = len(tasks)
    while i < n:
        # If this task is the start of a pair and a batch cut would split it,
        # push the -tests into the next batch with its -impl.
        if i in pair_starts and (i % batch_size) == batch_size - 1:
            # The current -tests task would be the last in a batch but its
            # -impl is the next task. Start a new batch with both.
            batch = [tasks[i]["id"], tasks[i + 1]["id"]]
            batches.append(batch)
            i += 2
        else:
            batch = [tasks[i]["id"]]
            i += 1
            # Fill batch up to batch_size, unless the next task is a pair start
            # whose -impl would be the batch_size+1 item (splitting the pair).
            while len(batch) < batch_size and i < n:
                # If adding tasks[i] would make a pair start in this batch
                # such that the -impl spills to the next batch — push both out.
                if i in pair_starts and (len(batch) + 1) == batch_size and (i + 1) < n:
                    # Stop this batch now, next batch starts with the pair
                    break
                batch.append(tasks[i]["id"])
                i += 1
            batches.append(batch)
    return batches, sorted(pair_starts)


def compute_hard_stops(
    batches: List[List[str]],
    task_id_to_meta: Dict[str, Dict],
    dependents: Dict[str, int],
    k: int,
) -> List[int]:
    """Compute hard-stop batch indices.

    Rule: batch index 0 always; any batch containing a task with
    dependents[task] >= K; any batch containing a task whose body has
    <!-- checkpoint -->.
    """
    hard: List[int] = []
    if not batches:
        return hard
    hard.append(0)
    for i, batch in enumerate(batches):
        if i in hard:
            continue
        for tid in batch:
            meta = task_id_to_meta.get(tid)
            if meta is None:
                continue
            if meta["has_marker"]:
                hard.append(i)
                break
            if dependents.get(tid, 0) >= k:
                hard.append(i)
                break
    return sorted(set(hard))


def compute(plan_path: str, k: int, batch_size: int) -> Dict:
    """Top-level compute: parse, group, return contract dict."""
    with open(plan_path, "r", encoding="utf-8") as f:
        plan_text = f.read()

    tasks = parse_tasks(plan_text)
    if not tasks:
        return {
            "batch_size": batch_size,
            "total": 0,
            "batches": [],
            "dependents": {},
            "hard_stops": [],
            "tasks": [],
        }

    dependents = compute_dependents(tasks)
    batches, _ = build_batches(tasks, batch_size)
    task_id_to_meta = {t["id"]: t for t in tasks}
    hard_stops = compute_hard_stops(batches, task_id_to_meta, dependents, k)

    # Emit the per-task forward dependency edges so the main agent can forward
    # `tasks: [{id, depends_on}]` to the workflow for dependency-skip. NOTE:
    # `depends_on` captures a SINGLE `**Depends on:** Task M` ref per task (the
    # canonical plan form); a task with two deps registers only the first. This
    # is the documented plan scope — not full multi-dep skip support.
    task_edges = [{"id": t["id"], "depends_on": t["depends_on"]} for t in tasks]

    return {
        "batch_size": batch_size,
        "total": len(tasks),
        "batches": batches,
        "dependents": dependents,
        "hard_stops": hard_stops,
        "tasks": task_edges,
    }


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Compute checkpoint batches for a plan file")
    parser.add_argument("plan_file", help="Path to plan file")
    parser.add_argument("--k", type=int, default=3, help="Dependency-hub threshold (default 3)")
    parser.add_argument(
        "--batch-size", type=int, default=5, help="Batch size (default 5)"
    )
    args = parser.parse_args(argv)

    result = compute(args.plan_file, k=args.k, batch_size=args.batch_size)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
