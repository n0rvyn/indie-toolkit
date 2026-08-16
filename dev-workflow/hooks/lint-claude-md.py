#!/usr/bin/env python3
"""PostToolUse(Edit|Write) hook: lint a CLAUDE.md that was just written.

Fires only when the edited file's basename is CLAUDE.md / CLAUDE.local.md.
Silent when the file is clean.

Three checks, all defect-class (something is provably wrong), never style:

1. Phantom slash reference — a `/foo` written as a command, where no skill or
   builtin command named `foo` exists anywhere on this machine.
      Real catches: `/knowledge-search` (should be `/kb`), `/verify-dev-guide`
      (never existed; dev-guide-verifier is an agent auto-dispatched by
      write-dev-guide).

2. Dead doc path — a backticked `docs/...` path that does not exist on disk,
   resolved relative to the CLAUDE.md's own directory.
      Real catch: Glink pointed "遇到困惑时" at docs/00-AI-CONTEXT.md while the
      same file's table already marked that path "⚠️ 尚未创建".

3. Model-uninvocable skill given as an instruction to Claude — the skill exists
   but its frontmatter says `disable-model-invocation: true`, so Claude cannot
   route to it. Written as "用 /handoff" it is an instruction Claude structurally
   cannot follow; it has to be phrased as a prompt to the user instead.
      Real catch: `/handoff` in 12 project CLAUDE.md files.

Deliberately NOT checked: file length. The official guidance is "under 200
lines", but a length warning has no silent state — it would fire on every edit
to the files that are already long (ArtLens 331, GaitAnalysis 375), which is
exactly the noise failure recorded in check-repeated-edit.py's docstring (a
single approved batch fired ~50 times). Defect checks stay quiet when the file
is correct; style checks do not.

⛔ Matching is done with Python `re`, never by shelling out to grep. In this
environment `grep` is a shell function wrapping ugrep 7.5.0, and under ERE it
truncates `[a-z0-9:_-]{2,}\\b` at the hyphen: `/fix-bug` comes back as `/fix`,
`/verify-dev-guide` as `/verify`. A hyphenated phantom would be silently
downgraded to a non-phantom-looking prefix and dropped. Do not "simplify" this
into a shell one-liner. (Same root cause as
~/.claude/knowledge/workflow/2026-08-13-grep-is-shadowed-by-ugrep-in-cc-shell.md)
"""

import glob
import json
import os
import re
import sys

MAX_BYTES = 512 * 1024  # skip absurdly large files rather than stall the hook
MAX_REPORTED = 8  # cap each finding list so the nudge stays readable

# Builtin slash commands: not skills, must not be reported as phantoms.
BUILTINS = {
    "add-dir", "agents", "bug", "clear", "compact", "config", "context", "cost",
    "doctor", "export", "help", "hooks", "ide", "import", "init", "login",
    "logout", "mcp", "memory", "model", "permissions", "plugin", "release-notes",
    "resume", "review", "status", "terminal-setup", "vim",
}

# `/foo` inside backticks, or at the start of a line / after an opening bracket.
# Hyphens and colons are part of the name (plugin:skill, write-dev-guide).
# A trailing `/` means it is a path segment, not a command: `/api/apps` is a
# route, `/tmp/crashes` is a directory. Both are excluded by the (?!/) guard.
SLASH_RE = re.compile(
    r"`/([a-z][a-z0-9:_-]*)`(?!/)"                        # `/name`
    r"|(?:^|(?<=[ （(【「]))/([a-z][a-z0-9:_-]*)\b(?!/)",  # bare /name
    re.MULTILINE,
)

# Phantom detection (check 1) requires a hyphen or a plugin namespace colon.
# Measured against all 46 project CLAUDE.md files: both real phantoms are
# compound names (`knowledge-search`, `verify-dev-guide`) while every false
# positive is a bare single word that happens to be a filesystem root or an
# HTTP route standing alone in backticks — `/v1`, `/docs`, `/tmp`, `/api`,
# `/healthz`. Those are shape-identical to a single-word slash command, so no
# regex separates them. Known cost: a misspelled single-word command (`/kbb`
# for `/kb`) is not reported. Checks 2 and 3 are unaffected by this filter.
COMPOUND_RE = re.compile(r"[-:]")

DOCPATH_RE = re.compile(r"`((?:docs|doc)/[A-Za-z0-9_./一-鿿-]+)`")

# A path is a template placeholder, not a reference: the boilerplate writes
# "留档位置：`docs/05-features/功能名.md`" to say where a file *should go*.
# Nothing is broken when it does not exist.
PLACEHOLDER_MARKERS = (
    "YYYY", "MM-DD", "xxx", "XXX", "功能名", "feature-name", "<", ">", "{", "*",
    ":id", "文件名", "名称",
)
FM_DISABLE_RE = re.compile(r"^disable-model-invocation:\s*true\s*$", re.MULTILINE)

# Lines that already flag a path as missing are the file doing its job, not a
# defect. Skip doc-path findings whose line carries one of these markers.
ACKNOWLEDGED = ("⚠️", "尚未创建", "不存在", "not created", "does not exist")


def skill_dirs():
    """Every directory that can define a slash-invocable skill or command."""
    home = os.path.expanduser("~")
    patterns = [
        os.path.join(home, ".claude/plugins/cache/*/*/*/skills/*"),
        os.path.join(home, ".claude/skills/*"),
        os.path.join(home, ".claude/commands/*"),
    ]
    return [p for pat in patterns for p in glob.glob(pat)]


def local_names(claude_md_dir):
    """Project-local skills/commands live next to the CLAUDE.md being linted."""
    names = set()
    for sub in ("skills", "commands"):
        for p in glob.glob(os.path.join(claude_md_dir, ".claude", sub, "*")):
            names.add(os.path.splitext(os.path.basename(p))[0])
    return names


def build_index(claude_md_dir):
    """name -> True if model-invocable, False if disable-model-invocation."""
    index = {}
    for d in skill_dirs():
        name = os.path.splitext(os.path.basename(d))[0]
        invocable = True
        skill_md = os.path.join(d, "SKILL.md")
        if os.path.isfile(skill_md):
            try:
                with open(skill_md, encoding="utf-8") as fh:
                    if FM_DISABLE_RE.search(fh.read(4096)):
                        invocable = False
            except OSError:
                pass
        # A name defined in several plugin versions stays invocable if any is.
        index[name] = index.get(name, False) or invocable
    for name in local_names(claude_md_dir):
        index.setdefault(name, True)
    for name in BUILTINS:
        index[name] = True
    return index


def find_slash_refs(text):
    """(name, line_number) for every slash-command-looking token."""
    out = []
    for m in SLASH_RE.finditer(text):
        name = m.group(1) or m.group(2)
        if not name:
            continue
        out.append((name, text.count("\n", 0, m.start()) + 1))
    return out


def lint(path):
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    base_dir = os.path.dirname(os.path.abspath(path))
    index = build_index(base_dir)

    phantom, uninvocable, dead_paths = [], [], []
    lines = text.split("\n")

    for name, lineno in find_slash_refs(text):
        bare = name.split(":")[-1]
        if bare not in index:
            # Single-word tokens are indistinguishable from paths/routes; see
            # COMPOUND_RE. Only compound names are reported as phantoms.
            if COMPOUND_RE.search(name):
                phantom.append(f"/{name} (L{lineno})")
        elif index[bare] is False:
            uninvocable.append(f"/{name} (L{lineno})")

    for m in DOCPATH_RE.finditer(text):
        rel = m.group(1)
        lineno = text.count("\n", 0, m.start()) + 1
        if os.path.exists(os.path.join(base_dir, rel)):
            continue
        if any(mark in rel for mark in PLACEHOLDER_MARKERS):
            continue
        if any(mark in lines[lineno - 1] for mark in ACKNOWLEDGED):
            continue
        dead_paths.append(f"{rel} (L{lineno})")

    return phantom, uninvocable, dead_paths


def fmt(items):
    shown = ", ".join(items[:MAX_REPORTED])
    extra = len(items) - MAX_REPORTED
    return shown + (f" …(+{extra})" if extra > 0 else "")


def main():
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        sys.exit(0)

    path = (payload.get("tool_input") or {}).get("file_path") or ""
    if os.path.basename(path) not in ("CLAUDE.md", "CLAUDE.local.md"):
        sys.exit(0)
    try:
        if not os.path.isfile(path) or os.path.getsize(path) > MAX_BYTES:
            sys.exit(0)
        phantom, uninvocable, dead_paths = lint(path)
    except OSError:
        sys.exit(0)

    parts = []
    if phantom:
        parts.append(
            f"幽灵 slash 引用（无对应 skill/命令）：{fmt(phantom)}"
        )
    if uninvocable:
        parts.append(
            f"该 skill 是 disable-model-invocation，Claude 调不动，"
            f"写成给 Claude 的指令无效——改成提示用户运行：{fmt(uninvocable)}"
        )
    if dead_paths:
        parts.append(
            f"引用的路径在盘上不存在：{fmt(dead_paths)}"
            f"（若是有意保留的占位，在该行标 ⚠️ 或「尚未创建」即可静默）"
        )

    if parts:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": "[lint-claude-md] "
                        + os.path.basename(os.path.dirname(os.path.abspath(path)))
                        + "/CLAUDE.md — "
                        + "；".join(parts),
                    }
                }
            )
        )
    sys.exit(0)


if __name__ == "__main__":
    main()
