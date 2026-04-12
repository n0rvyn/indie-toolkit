#!/usr/bin/env python3
"""Publish product-lens results as PKOS exchange artifacts."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

import yaml


INTENT_TO_SUBDIR = {
    "portfolio_scan": "portfolio-scan",
    "project_progress_pulse": "progress-pulse",
    "repo_reprioritize": "reprioritize",
    "recent_feature_review": "recent-feature-review",
    "verdict_refresh": "verdict-refresh",
}

ALLOWED_DECISIONS = {
    "portfolio_scan": {"focus", "maintain", "freeze", "stop", "watch"},
    "project_progress_pulse": {"accelerating", "steady", "stalled", "drifting"},
    "repo_reprioritize": {"focus", "maintain", "freeze", "stop"},
    "recent_feature_review": {"double_down", "polish", "simplify", "rethink", "drop"},
    "verdict_refresh": {"unchanged", "upgraded", "downgraded", "reversed"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Publish product-lens exchange artifact")
    parser.add_argument("--intent", required=True, choices=sorted(INTENT_TO_SUBDIR))
    parser.add_argument("--decision", required=True)
    parser.add_argument("--confidence", default="medium", choices=["high", "medium", "low"])
    parser.add_argument("--project-root", default="~/Code")
    parser.add_argument("--target", action="append", default=[])
    parser.add_argument("--project", default=None)
    parser.add_argument("--feature", default=None)
    parser.add_argument("--window-days", type=int, default=None)
    parser.add_argument("--risk", required=True)
    parser.add_argument("--reason", action="append", default=[])
    parser.add_argument("--action", action="append", default=[])
    parser.add_argument("--evidence", action="append", default=[])
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--created", default=date.today().isoformat())
    parser.add_argument("--exchange-root", default="~/Obsidian/PKOS/.exchange/product-lens")
    parser.add_argument("--slug", default=None)
    parser.add_argument("--sync-notion", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def slugify(value: str) -> str:
    return "-".join(part for part in "".join(c.lower() if c.isalnum() else "-" for c in value).split("-") if part) or "item"


def expand_path(raw: str) -> Path:
    return Path(os.path.expanduser(raw)).resolve()


def infer_project(args: argparse.Namespace) -> str:
    if args.project:
        return args.project
    if args.target:
        return Path(args.target[0].rstrip("/")).name or "portfolio"
    return "portfolio"


def infer_slug(args: argparse.Namespace, project: str) -> str:
    if args.slug:
        return slugify(args.slug)
    if args.feature:
        return slugify(args.feature)
    return slugify(project)


def validate_inputs(args: argparse.Namespace) -> None:
    allowed = ALLOWED_DECISIONS[args.intent]
    if args.decision not in allowed:
        raise SystemExit(
            f"Decision '{args.decision}' is invalid for intent '{args.intent}'. Allowed: {', '.join(sorted(allowed))}"
        )
    if not args.reason:
        raise SystemExit("At least one --reason is required.")
    if not args.action:
        raise SystemExit("At least one --action is required.")
    if not args.evidence:
        raise SystemExit("At least one --evidence is required.")


CONFIDENCE_TO_SIGNIFICANCE = {"high": 5, "medium": 3, "low": 2}


def artifact_path(args: argparse.Namespace, project: str, slug: str, seq: int) -> Path:
    """IEF-compliant filename: {YYYY-MM-DD}-{source}-{NNN}.md, grouped under intent subdir."""
    root = expand_path(args.exchange_root)
    subdir = INTENT_TO_SUBDIR[args.intent]
    filename = f"{args.created}-product-lens-{seq:03d}.md"
    return root / subdir / filename


def next_sequence(target_dir: Path, created_date: str) -> int:
    """Scan target_dir for existing artifacts created on the same date; return next NNN."""
    if not target_dir.exists():
        return 1
    prefix = f"{created_date}-product-lens-"
    used = []
    for path in target_dir.glob(f"{prefix}*.md"):
        stem = path.stem
        try:
            nnn = int(stem[len(prefix):len(prefix) + 3])
            used.append(nnn)
        except (ValueError, IndexError):
            continue
    return (max(used) + 1) if used else 1


def derive_title(args: argparse.Namespace, project: str) -> str:
    """Build a human-readable title for the directive."""
    intent_label = INTENT_TO_SUBDIR[args.intent].replace("-", " ")
    target = args.feature or project
    return f"{intent_label}: {args.decision} — {target}"


def derive_url(args: argparse.Namespace, project: str) -> str:
    """Use the first target as canonical URL-like reference when Notion page is not yet known."""
    if args.target:
        return f"file://{expand_path(args.target[0])}"
    return f"project://{project}"


def frontmatter(args: argparse.Namespace, project: str, seq: int) -> dict:
    tags = [f"product-lens", INTENT_TO_SUBDIR[args.intent], slugify(project)]
    tags.extend(args.tag)
    deduped = []
    seen = set()
    for tag in tags:
        if tag not in seen:
            seen.add(tag)
            deduped.append(tag)
    # IEF-required fields (stable cross-plugin envelope)
    data = {
        "id": f"{args.created}-product-lens-{seq:03d}",
        "source": "product-lens",
        "url": derive_url(args, project),
        "title": derive_title(args, project),
        "significance": CONFIDENCE_TO_SIGNIFICANCE.get(args.confidence, 3),
        "tags": deduped,
        "category": "directive",
        "domain": "product-strategy",
        "date": args.created,
        "read": False,
        # Extended fields (producer-specific; consumers ignore unknowns)
        "producer": "product-lens",
        "intent": args.intent,
        "project_root": args.project_root,
        "targets": args.target,
        "decision": args.decision,
        "confidence": args.confidence,
        "notion_sync_requested": args.sync_notion,
        "source_refs": args.evidence,
    }
    if args.feature:
        data["feature"] = args.feature
    if args.project:
        data["project"] = args.project
    if args.window_days is not None:
        data["window_days"] = args.window_days
    return data


def body(args: argparse.Namespace, project: str, title: str) -> str:
    """IEF directive body: title + Intent / Decision / Confidence / Context / Targets."""
    lines = [
        f"# {title}",
        "",
        f"**Intent:** {args.intent.replace('_', ' ')}",
        "",
        f"**Decision:** `{args.decision}`",
        "",
        f"**Confidence:** {args.confidence}",
        "",
        f"**Biggest risk:** {args.risk}",
        "",
        "**Context:**",
    ]
    for index, reason in enumerate(args.reason, start=1):
        lines.append(f"{index}. {reason}")
    lines.extend(["", "**Next actions:**"])
    for index, action in enumerate(args.action, start=1):
        lines.append(f"{index}. {action}")
    lines.extend(["", "**Evidence:**"])
    for evidence in args.evidence:
        lines.append(f"- {evidence}")
    lines.extend(["", "**Targets:**"])
    if args.target:
        for target in args.target:
            lines.append(f"- {target}")
    else:
        lines.append(f"- {project}")
    return "\n".join(lines) + "\n"


def render_markdown(frontmatter_data: dict, body_text: str) -> str:
    yaml_text = yaml.safe_dump(frontmatter_data, sort_keys=False, allow_unicode=True).strip()
    return f"---\n{yaml_text}\n---\n\n{body_text}"


def main() -> int:
    args = parse_args()
    validate_inputs(args)
    project = infer_project(args)
    slug = infer_slug(args, project)  # retained for callers that read it; id uses sequence
    # Compute target dir + sequence before path (path depends on sequence)
    subdir = INTENT_TO_SUBDIR[args.intent]
    target_dir = expand_path(args.exchange_root) / subdir
    seq = next_sequence(target_dir, args.created)
    target_path = artifact_path(args, project, slug, seq)
    fm = frontmatter(args, project, seq)
    content = render_markdown(fm, body(args, project, fm["title"]))

    if args.dry_run:
        print("Product Lens Exchange Dry Run")
        print(f"  IEF id: {fm['id']}")
        print(f"  Intent: {args.intent}")
        print(f"  Decision: {args.decision}")
        print(f"  Target: {target_path}")
        print(f"  Sync Notion: {'true' if args.sync_notion else 'false'}")
        return 0

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(content, encoding="utf-8")
    print(target_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
