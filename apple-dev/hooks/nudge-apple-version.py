#!/usr/bin/env python3
"""
PostToolUse hook for WebSearch / WebFetch.

Problem it addresses: when researching an Apple-platform behavior/API on the
web, it is easy to cite a source written for an OLDER OS version than the
project actually targets (e.g. an iOS-17-era forum thread on an iOS-18+ app),
and to reach for web search at all when the question is reproducible on the
booted simulator. This is a reasoning slip, not a tool-input error — the hook
cannot detect the version mismatch inside the fetched page. What it CAN do is
inject, right as the results land (before any conclusion is written), the one
machine-checkable fact (the project's deployment target) plus a push toward
on-device reproduction.

Why PostToolUse, not PreToolUse: a non-blocking nudge must reach the model via
`additionalContext`, which PreToolUse does not support (its outputs are
allow/deny/ask/defer + updatedInput — delivering text there would mean BLOCKING
the search). PostToolUse fires one step later (results already returned) but is
the earliest event that injects context without blocking. tool_input still
carries the original query/url at PostToolUse, so all gates below still apply.
(tool_response — the fetched content — is also available here, leaving room for
a future enhancement that scans it for version-stale tokens.)

Mechanics: SOFT nudge only. Emits hookSpecificOutput.additionalContext and
exits 0 — the tool always runs, nothing is blocked. Value is salience + timing.

Gates (cheap-first; all must pass, else silent exit 0 — listed in execution order):
  1. not a sub-agent (sidechain guard)
  2. tool is WebSearch / WebFetch
  3. the query/URL looks Apple-platform (keyword match)
  4. not within the cooldown window (per-project; avoid burst spam)
  5. cwd resolves to an Apple project (.xcodeproj / .xcworkspace / Package.swift w/ .iOS)

Fail-open: any exception -> exit 0, no nudge.
"""
import hashlib
import json
import os
import re
import sys
import time

COOLDOWN_SECONDS = 600  # one nudge per 10 min is plenty when researching iOS
# Cooldown is keyed per project root (see _cooldown_path) so a nudge in project
# A does not suppress a differently-targeted project B within the window.
COOLDOWN_DIR = os.path.expanduser("~/.claude")
SIM_CACHE_FILE = os.path.expanduser("~/.claude/.booted-sim-cache")
MAX_PARENT_LEVELS = 6  # how far up from cwd to look for the project root

# Dirs not worth walking when sniffing for an Xcode project.
PRUNE_DIRS = {
    ".git", "node_modules", "build", "DerivedData", ".build", "Pods",
    ".swiftpm", "Carthage", ".idea", "vendor", "dist", "out",
}
MAX_DIRS_VISITED = 400  # bound worst-case walk on large monorepos

# Apple-platform signal in the search query / fetched URL. Broad on purpose:
# the project gate already restricts to Apple projects, so a false fire costs
# one ignorable context line — under-firing (missing the catch) is worse.
APPLE_KEYWORDS = re.compile(
    r"(swiftui|swiftdata|swift\s*charts|uikit|appkit|watchkit|widgetkit|"
    r"swift\s*concurrency|combine|\bios\b|ipados|\bmacos\b|watchos|tvos|"
    r"visionos|iphoneos|xcode|simulator|sf\s*symbol|navigationstack|"
    r"presentationdetent|@observable|@available|deprecated|"
    r"developer\.apple\.com|apple\s*developer|wwdc)",
    re.IGNORECASE,
)


def emit(context: str) -> None:
    """Print the non-blocking additionalContext payload and exit 0.

    Shape verified against readback/hooks/post-tool-use.sh, whose identical
    payload reaches the model in practice. PostToolUse is the only event that
    can inject free-form context to the model WITHOUT blocking the tool:
    PreToolUse's documented outputs are allow/deny/ask/defer + updatedInput
    only (no additionalContext), so a non-blocking PreToolUse nudge would be
    silently dropped. See knowledge/workflow/2026-04-02-claude-code-hooks-reference.md.
    """
    out = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }
    print(json.dumps(out))
    sys.exit(0)


def find_apple_project(root: str):
    """Bounded walk. Returns (is_apple, pbxproj_paths, package_swift_paths)."""
    pbxprojs = []
    pkgs = []
    is_apple = False
    visited = 0
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        visited += 1
        if visited > MAX_DIRS_VISITED:
            break
        # Detect .xcodeproj / .xcworkspace (they are directories, so they show
        # up in dirnames). Read project.pbxproj for the deployment target.
        for d in dirnames:
            if d.endswith(".xcodeproj"):
                is_apple = True
                p = os.path.join(dirpath, d, "project.pbxproj")
                if os.path.isfile(p):
                    pbxprojs.append(p)
            elif d.endswith(".xcworkspace"):
                is_apple = True
        # Detect a Package.swift that declares an iOS platform.
        for f in filenames:
            if f == "Package.swift":
                fp = os.path.join(dirpath, f)
                try:
                    with open(fp, errors="ignore") as fh:
                        if ".iOS" in fh.read():
                            is_apple = True
                            pkgs.append(fp)
                except Exception:
                    pass
        if is_apple and (pbxprojs or pkgs):
            break  # enough signal to nudge with a concrete target
        # Prune traversal: skip heavy dirs and never descend INTO the project
        # bundles; stop entirely past depth 3.
        depth = dirpath[len(root):].count(os.sep)
        if depth >= 3:
            dirnames[:] = []
        else:
            dirnames[:] = [d for d in dirnames if d not in PRUNE_DIRS
                           and not d.endswith(".xcodeproj")
                           and not d.endswith(".xcworkspace")]
    return is_apple, pbxprojs, pkgs


def _parse_float(s: str):
    try:
        return float(s)
    except Exception:
        return None


def detect_deployment_target(pbxprojs, pkgs):
    """Return the minimum iOS deployment target found, as a string, or None."""
    versions = []
    for p in pbxprojs[:3]:
        try:
            with open(p, errors="ignore") as fh:
                text = fh.read()
        except Exception:
            continue
        for m in re.finditer(r"IPHONEOS_DEPLOYMENT_TARGET = ([0-9.]+)", text):
            v = _parse_float(m.group(1))
            if v:
                versions.append(v)
    for p in pkgs[:3]:
        try:
            with open(p, errors="ignore") as fh:
                text = fh.read()
        except Exception:
            continue
        # .iOS(.v18) / .iOS(.v18_0) / .iOS( .v18 )  and  .iOS("18.0")
        for m in re.finditer(r"\.iOS\(\s*\.v([0-9_]+)\s*\)", text):
            v = _parse_float(m.group(1).replace("_", "."))
            if v:
                versions.append(v)
        for m in re.finditer(r"\.iOS\(\s*\"([0-9.]+)\"\s*\)", text):
            v = _parse_float(m.group(1))
            if v:
                versions.append(v)
    if not versions:
        return None
    lo = min(versions)
    # 18.0 -> "18", 18.2 -> "18.2"
    return str(int(lo)) if lo == int(lo) else str(lo)


def resolve_project_root(start: str) -> str:
    """Walk UP from `start` looking for an Xcode/SwiftPM project root.

    Claude's cwd is often a subdirectory below the project (e.g. cd'd into a
    module), so the `.xcodeproj` lives above it. We check each ancestor (bounded
    by MAX_PARENT_LEVELS) for a project marker and return the first that has one.
    If none is found, return `start` unchanged — the caller's downward walk then
    covers the inverse case (project sits in a subdir below cwd).
    """
    cur = os.path.abspath(start)
    for _ in range(MAX_PARENT_LEVELS + 1):
        try:
            entries = os.listdir(cur)
        except Exception:
            break
        for e in entries:
            if e.endswith(".xcodeproj") or e.endswith(".xcworkspace"):
                return cur
            if e == "Package.swift":
                try:
                    with open(os.path.join(cur, e), errors="ignore") as fh:
                        if ".iOS" in fh.read():
                            return cur
                except Exception:
                    pass
        parent = os.path.dirname(cur)
        if parent == cur:  # reached filesystem root
            break
        cur = parent
    return os.path.abspath(start)


def _cooldown_path(root: str) -> str:
    """Per-project cooldown marker, keyed by a hash of the project root."""
    h = hashlib.md5(os.path.abspath(root).encode("utf-8", "replace")).hexdigest()[:12]
    return os.path.join(COOLDOWN_DIR, f".apple-version-nudge-{h}")


def cooldown_active(root: str) -> bool:
    try:
        last = os.path.getmtime(_cooldown_path(root))
        return (time.time() - last) < COOLDOWN_SECONDS
    except Exception:
        return False


def touch_cooldown(root: str) -> None:
    try:
        os.makedirs(COOLDOWN_DIR, exist_ok=True)
        with open(_cooldown_path(root), "w") as fh:
            fh.write(str(int(time.time())))
    except Exception:
        pass


def read_sim_version():
    try:
        with open(SIM_CACHE_FILE, errors="ignore") as fh:
            v = fh.read().strip()
        return v or None
    except Exception:
        return None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    # Gate 1: sub-agent activity does not nudge.
    if data.get("isSidechain"):
        sys.exit(0)

    # Gate 2: only WebSearch / WebFetch.
    tool_name = data.get("tool_name", "")
    if tool_name not in ("WebSearch", "WebFetch"):
        sys.exit(0)

    ti = data.get("tool_input", {}) or {}
    if tool_name == "WebSearch":
        haystack = ti.get("query", "") or ""
    else:  # WebFetch
        haystack = f"{ti.get('url', '')} {ti.get('prompt', '')}"

    # Gate 3: must look Apple-platform.
    if not APPLE_KEYWORDS.search(haystack):
        sys.exit(0)

    # Resolve the project root (walk up from cwd; cheap) BEFORE the cooldown
    # check so the cooldown can be keyed per-project and so the downward walk
    # starts from the real root even when cwd is nested below it.
    cwd = data.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        root = resolve_project_root(cwd)
    except Exception:
        root = cwd

    # Gate 4: per-project cooldown.
    if cooldown_active(root):
        sys.exit(0)

    # Gate 5: must be an Apple project (downward walk from the resolved root).
    try:
        is_apple, pbxprojs, pkgs = find_apple_project(root)
    except Exception:
        sys.exit(0)
    if not is_apple:
        sys.exit(0)

    target = detect_deployment_target(pbxprojs, pkgs)
    sim = read_sim_version()

    # Build the nudge. The deployment target is the load-bearing fact; the sim
    # version is a bonus ("you can reproduce right here").
    if target:
        head = f"本项目部署目标 iOS {target}+"
    else:
        head = "本项目是 Apple 平台工程"
    sim_clause = f"（booted sim: iOS {sim}，可直接复现）" if sim else ""

    context = (
        f"[apple-version] {head}{sim_clause}。你正在对 Apple 平台做 web 检索。"
        f"若这是可复现的行为/API 问题，先在模拟器或编译验证再下结论"
        f"（CLAUDE.md: 平台 API 可用性 → Bash 先于 Search），不要直接采信 web 结论。"
        f"若必须引用网页源，核对它是否适配"
        + (f" iOS {target}+" if target else "本项目的部署目标")
        + "，丢弃针对更旧 OS 版本的描述。本提醒不阻断本次检索。"
    )

    touch_cooldown(root)
    emit(context)


if __name__ == "__main__":
    main()
