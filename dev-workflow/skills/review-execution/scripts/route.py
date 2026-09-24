#!/usr/bin/env python3
"""Compute review-execution's routing flags from what the working tree actually changed.

Replaces the shell checks that SKILL.md Step 1 used to ask the model to run one by one.
Deterministic parts only; SPANS_LAYERS (does the diff span View / logic / data layers)
is judgment and stays with the model.

Usage:
    python3 route.py [--root DIR] [--scope-file PATH ...]

Prints one JSON object on stdout. Exit code is always 0 unless the root is not a git repo.
"""

import argparse
import glob
import json
import os
import subprocess
import sys

APPLE_NONSWIFT_SUFFIXES = (".plist", ".entitlements", ".xcconfig", ".pbxproj")
APPLE_NONSWIFT_NAMES = ("Package.swift",)


def git(root, *args):
    out = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(out.stderr.strip() or f"git {' '.join(args)} failed")
    return [l for l in out.stdout.splitlines() if l.strip()]


def changed_files(root):
    """Return (all_changed, added). Untracked files count as added: a new View that was
    never `git add`ed is still new work to review, and `git diff HEAD` alone misses it."""
    has_head = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=root,
                              capture_output=True).returncode == 0
    if has_head:
        modified = git(root, "diff", "--name-only", "HEAD")
        added = git(root, "diff", "--name-only", "--diff-filter=A", "HEAD")
    else:  # repo with no commits yet: everything staged is new
        modified = git(root, "diff", "--name-only", "--cached")
        added = list(modified)
    untracked = git(root, "ls-files", "--others", "--exclude-standard")
    all_changed = sorted(set(modified) | set(untracked))
    return all_changed, sorted(set(added) | set(untracked))


def is_apple_project(root):
    """Same test SKILL.md used: an Xcode project, workspace or Package.swift within depth 3."""
    base_depth = root.rstrip(os.sep).count(os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        depth = dirpath.count(os.sep) - base_depth
        for d in dirnames:
            if d.endswith((".xcodeproj", ".xcworkspace")):
                return True
        if "Package.swift" in filenames:
            return True
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and not d.endswith((".xcodeproj", ".xcworkspace"))]
        if depth >= 2:
            dirnames[:] = []
    return False


def apple_dev_installed():
    plugins = os.environ.get("ROUTE_PLUGINS_CACHE", os.path.expanduser("~/.claude/plugins/cache"))
    return bool(glob.glob(os.path.join(plugins, "*", "apple-dev")))


def is_view(path):
    return path.endswith("View.swift")


def is_apple_nonswift(path):
    name = os.path.basename(path)
    return (path.endswith(APPLE_NONSWIFT_SUFFIXES) or name in APPLE_NONSWIFT_NAMES
            or ".xcassets/" in path or path.endswith(".xcassets"))


def route(root, scope_files=None):
    root = os.path.abspath(root)
    all_changed, added = changed_files(root)
    result = {"root": root, "scope_applied": scope_files is not None}
    if scope_files is not None:
        scope = {os.path.normpath(s) for s in scope_files}
        all_changed = [f for f in all_changed if os.path.normpath(f) in scope]
        added = [f for f in added if os.path.normpath(f) in scope]
    result["changed_files"] = all_changed
    if not all_changed:
        result["stop"] = ("scope_files intersect no changed file" if scope_files is not None
                          else "no uncommitted changes")
        return result

    apple = is_apple_project(root)
    installed = apple_dev_installed() if apple else False
    views = [f for f in all_changed if is_view(f)]
    new_views = [f for f in added if is_view(f)]
    nonswift = [f for f in all_changed if is_apple_nonswift(f)]
    specs = sorted(glob.glob(os.path.join(root, "docs", "05-features", "**", "*.md"), recursive=True))
    specs = [os.path.relpath(s, root) for s in specs]

    result.update({
        "apple_project": apple,
        "apple_dev_installed": installed,
        "flags": {
            "HAS_VIEW_MODIFIED": bool(views),
            "HAS_NEW_VIEW": bool(new_views),
            "HAS_APPLE_NONSWIFT": bool(nonswift),
            "HAS_FEATURE_SPEC": bool(specs),
        },
        "apple_reviewers": [],
    })
    if apple and installed:
        r = result["apple_reviewers"]
        if views:
            r.append({"agent": "apple-dev:ui-reviewer", "files": views})
        if new_views:
            r.append({"agent": "apple-dev:design-reviewer", "files": new_views})
        if nonswift:
            r.append({"agent": "apple-dev:apple-reviewer", "files": nonswift})
        # feature-reviewer also fires on SPANS_LAYERS, which the model judges; say so explicitly.
        r.append({"agent": "apple-dev:feature-reviewer",
                  "when": "always" if specs else "only if SPANS_LAYERS",
                  "specs": specs})
    return result


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--scope-file", action="append", dest="scope_files")
    args = ap.parse_args(argv)
    try:
        out = route(args.root, args.scope_files)
    except RuntimeError as e:
        print(json.dumps({"error": str(e)}))
        return 2
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
