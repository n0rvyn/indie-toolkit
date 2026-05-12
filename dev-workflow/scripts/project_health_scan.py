#!/usr/bin/env python3
"""Fast project health scanner for dev-workflow skills and hooks."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import subprocess
import sys
import time
from typing import Any


SIGNAL_NAMES = ["doc_drift", "module_size", "feedback_loop", "test_pressure", "active_churn"]


class Budget:
    def __init__(self, max_ms: int | None) -> None:
        self.max_ms = max_ms
        self.started = time.monotonic()

    def exceeded(self) -> bool:
        if self.max_ms is None:
            return False
        return (time.monotonic() - self.started) * 1000 >= self.max_ms


def run_git(root: pathlib.Path, args: list[str]) -> str:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=1,
        )
    except Exception:
        return ""
    if proc.returncode != 0:
        return ""
    return proc.stdout.strip()


def signal(status: str = "green", evidence: list[str] | None = None) -> dict[str, Any]:
    return {"status": status, "evidence": evidence or []}


def empty_report(root: pathlib.Path, mode: str, reason: str, warning: str | None = None) -> dict[str, Any]:
    signals = {name: signal() for name in SIGNAL_NAMES}
    report = {
        "project_root": str(root),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "mode": mode,
        "reason": reason,
        "signals": signals,
        "suggested_gates": [],
        "warnings": [],
    }
    if warning:
        report["warnings"].append(warning)
    return report


def read_state(root: pathlib.Path) -> tuple[dict[str, Any], str | None]:
    path = root / ".claude" / "dev-workflow-health.json"
    if not path.exists():
        return {}, None
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except Exception as exc:
        return {}, f"state-parse warning: {exc.__class__.__name__}"


def is_stale(state: dict[str, Any], days: int) -> bool:
    """Return True if state's updated_at is older than `days` or state is missing/malformed."""
    if not state:
        return True
    updated_at = state.get("updated_at")
    if not updated_at or not isinstance(updated_at, str):
        return True
    try:
        ts = dt.datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return True
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    age = dt.datetime.now(dt.timezone.utc) - ts
    return age.total_seconds() > days * 86400


def update_light(report: dict[str, Any], root: pathlib.Path) -> None:
    dirty = run_git(root, ["status", "--porcelain"])
    dirty_count = len([line for line in dirty.splitlines() if line.strip()])
    if dirty_count >= 20:
        report["signals"]["active_churn"] = signal("red", [f"{dirty_count} dirty files"])
        report["suggested_gates"].append("review-before-commit")
    elif dirty_count:
        report["signals"]["active_churn"] = signal("yellow", [f"{dirty_count} dirty files"])

    docs = ["docs/00-AI-CONTEXT.md", "CLAUDE.md", "AGENTS.md"]
    found = [name for name in docs if (root / name).exists()]
    if not found:
        report["signals"]["doc_drift"] = signal("yellow", ["no project context/rule file found"])
    else:
        report["signals"]["doc_drift"]["evidence"].append("context files: " + ", ".join(found))

    if (root / ".claude" / "dev-workflow-state.yml").exists():
        report["signals"]["feedback_loop"]["evidence"].append("dev-workflow state present")

    state, warning = read_state(root)
    if warning:
        report["warnings"].append(warning)
    if isinstance(state.get("last_runs"), dict):
        report["signals"]["feedback_loop"]["evidence"].append("last_runs present")


def process_headings(path: pathlib.Path) -> set[str]:
    if not path.exists():
        return set()
    headings: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            headings.add(stripped.lstrip("#").strip().lower())
    return headings


def update_full(report: dict[str, Any], root: pathlib.Path, budget: Budget) -> None:
    update_light(report, root)
    if budget.exceeded():
        report["warnings"].append("timeout warning: project health scan exceeded budget")
        return

    claude_heads = process_headings(root / "CLAUDE.md")
    agents_heads = process_headings(root / "AGENTS.md")
    if claude_heads and agents_heads:
        overlap = claude_heads & agents_heads
        if not overlap:
            report["signals"]["doc_drift"] = signal("yellow", ["CLAUDE.md and AGENTS.md share no headings"])
    if (root / "CONTEXT.md").exists() and (root / "docs" / "00-AI-CONTEXT.md").exists():
        report["signals"]["doc_drift"] = signal("red", ["two canonical context candidates: CONTEXT.md and docs/00-AI-CONTEXT.md"])
        report["suggested_gates"].append("design-drift")

    source_exts = {".swift", ".ts", ".tsx", ".js", ".jsx", ".py"}
    source_files = []
    test_files = []
    large_files = []
    for path in root.rglob("*"):
        if budget.exceeded():
            report["warnings"].append("timeout warning: project health scan exceeded budget")
            break
        if not path.is_file():
            continue
        if any(part in {".git", "node_modules", ".build", "DerivedData"} for part in path.parts):
            continue
        if path.suffix in source_exts:
            source_files.append(path)
            text = path.read_text(encoding="utf-8", errors="replace")
            line_count = text.count("\n") + 1
            if (path.suffix == ".swift" and line_count > 450) or line_count > 700:
                large_files.append(f"{path.relative_to(root)}:{line_count} lines")
            if "test" in str(path).lower():
                test_files.append(path)

    if large_files:
        report["signals"]["module_size"] = signal("yellow", large_files[:5])
        report["suggested_gates"].append("code-audit")

    if source_files and not test_files:
        report["signals"]["feedback_loop"] = signal("red", ["source files found but no test files"])
    elif source_files:
        ratio = round(len(source_files) / max(1, len(test_files)), 1)
        if ratio > 12:
            report["signals"]["test_pressure"] = signal("yellow", [f"source/test ratio {ratio}:1"])
        report["signals"]["feedback_loop"]["evidence"].append(f"{len(test_files)} test-like files")

    changed = run_git(root, ["diff", "--name-only"])
    recent = [line for line in changed.splitlines() if line.strip()]
    if recent:
        report["signals"]["active_churn"]["evidence"].append("changed: " + ", ".join(recent[:5]))


def write_state(root: pathlib.Path, report: dict[str, Any]) -> None:
    state_path = root / ".claude" / "dev-workflow-health.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "project_root": str(root),
        "updated_at": report["generated_at"],
        "last_reason": report.get("reason"),
        "last_health": report,
    }
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Project Health",
        "",
        f"- Root: `{report['project_root']}`",
        f"- Mode: `{report['mode']}`",
        f"- Reason: `{report['reason']}`",
        "",
        "| Signal | Status | Evidence |",
        "|---|---|---|",
    ]
    for name, data in report["signals"].items():
        evidence = "; ".join(data.get("evidence") or [])
        lines.append(f"| `{name}` | {data['status']} | {evidence} |")
    if report.get("warnings"):
        lines += ["", "## Warnings"]
        lines += [f"- {w}" for w in report["warnings"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--mode", choices=["light", "full"], default="light")
    parser.add_argument("--write-state", action="store_true")
    parser.add_argument("--reason", choices=["plan", "fix", "commit", "dev-guide"], default="plan")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    parser.add_argument("--max-ms", type=int)
    parser.add_argument("--check-staleness", type=int, metavar="DAYS",
                        help="If state's updated_at is older than DAYS, append a stale warning")
    args = parser.parse_args(argv)

    root = pathlib.Path(args.project_root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"error: --project-root is not a directory: {root}", file=sys.stderr)
        return 2

    budget = Budget(args.max_ms)
    if budget.exceeded():
        report = empty_report(root, args.mode, args.reason, "timeout warning: project health scan exceeded budget")
    else:
        report = empty_report(root, args.mode, args.reason)
        if args.check_staleness is not None:
            existing_state, _ = read_state(root)
            if is_stale(existing_state, args.check_staleness):
                report["warnings"].append(
                    f"stale: state older than {args.check_staleness} days or missing"
                )
        if args.mode == "light":
            update_light(report, root)
        else:
            update_full(report, root, budget)

    if args.write_state:
        write_state(root, report)

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
