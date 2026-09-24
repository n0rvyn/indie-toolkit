#!/usr/bin/env python3
"""
PreToolUse hook for Edit | Write | MultiEdit | NotebookEdit | Bash.

Denies any hand write of the run-phase state file
(`.claude/dev-workflow-state.json` or the legacy `.claude/dev-workflow-state.yml`).
`phase.py` (dev-workflow/skills/run-phase/scripts/phase.py) is the only writer;
this hook makes that rule mechanical instead of prose-only.

- Edit / Write / MultiEdit / NotebookEdit: denied when `file_path` (or
  `notebook_path`) ends with one of the two state-file suffixes.
- Bash: denied when a command segment writes onto the state file — as the target
  of `>` / `>>` / `>|` / `&>`, an argument of `tee`, a file under `sed -i` /
  `perl -i`, the destination (last argument) of `cp` / `mv`, or a python / perl /
  ruby / node one-liner or heredoc that opens it for writing. Segments that invoke
  `phase.py` are exempt. Reading (`cat`, `grep`, `jq` without a redirect onto the
  file, `cp state.json /tmp/bak`) passes.

The Bash check is a lexical heuristic, not a sandbox: a command built at run time
(`eval`, a variable holding the path, an encoded script) gets past it. It exists to
stop the ordinary shell rewrite, not a determined one.

JSON-deny style, following apple-dev/hooks/xcodebuild-guard.py: exit 0 always,
JSON is only honoured by the harness on exit 0, so a crashed or missing script
fails open instead of blocking every Edit/Write/Bash call. Not bug-fix-gate.py's
style (that one uses sys.exit(2) to hard-block).

Any other path or command, and any malformed or non-object hook input, exits 0
with no output.
"""
import json
import re
import shlex
import sys

STATE_SUFFIXES = (
    ".claude/dev-workflow-state.json",
    ".claude/dev-workflow-state.yml",
)

FILE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")

# The state path as it can appear inside a shell word (quotes already stripped by
# the caller, or not — the lookarounds tolerate both).
STATE_RE = re.compile(r"\.claude/dev-workflow-state\.(?:json|yml)(?![\w.-])")

PHASE_PY_RE = re.compile(r"(?:^|[\s/'\"])phase\.py(?:$|[\s'\"])")

# `>`, `>>`, `>|`, `&>`, `2>` … followed by the target word.
REDIRECT_RE = re.compile(r"(?:&>>?|\d*>>?\|?)\s*(\"[^\"]*\"|'[^']*'|[^\s;&|<>]+)")

# Segment separators. Newlines split heredoc bodies into their own segments; the
# interpreter check below looks at the whole command for exactly that reason.
SEGMENT_SPLIT_RE = re.compile(r"\|\||&&|;|\||\n")

INTERPRETER_RE = re.compile(r"(?:^|[\s/;|&(])(?:python\d*(?:\.\d+)?|perl|ruby|node)(?:$|[\s'\"])")
WRITE_INTENT_RE = re.compile(
    r"""open\s*\([^)]*['"](?:w|a|x|r\+|w\+|a\+|wb|ab|xb|wt|at)['"]"""  # python open(p, "w")
    r"""|open\s*\([^)]*(?:mode\s*=\s*['"][wax])"""                      # python open(p, mode="w")
    r"""|\.write_text\s*\(|\.write_bytes\s*\("""                         # pathlib
    r"""|json\.dump\s*\(|yaml\.(?:safe_)?dump\s*\("""
    r"""|os\.replace\s*\(|os\.rename\s*\(|shutil\.(?:copy\w*|move)\s*\("""
    r"""|open\s*\(?\s*[\w$]*\s*,\s*['"]\+?>"""                          # perl open(FH, ">file")
    r"""|writeFileSync|writeFile\s*\(|File\.write""",                    # node / ruby
)


def decide(decision, reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason}}, ensure_ascii=False))
    sys.exit(0)


def block(what):
    decide(
        "deny",
        f"[dev-workflow] {what} — the run-phase state file is written only by `phase.py` "
        "(dev-workflow/skills/run-phase/scripts/phase.py). Use its "
        "`init` / `step` / `set` / `note` / `migrate` / `quarantine` subcommands "
        "instead of writing the file by hand.",
    )


def _is_state(word):
    return bool(STATE_RE.search(word))


def _words(segment):
    try:
        return shlex.split(segment, posix=True)
    except ValueError:  # unbalanced quotes: fall back to whitespace
        return segment.split()


def _segment_writes_state(segment):
    """Reason string when this one shell segment writes onto the state file."""
    for target in REDIRECT_RE.findall(segment):
        if _is_state(target.strip("'\"")):
            return "redirect onto the state file"
    words = _words(segment)
    if not words:
        return None
    # Skip leading env assignments / sudo / command wrappers.
    i = 0
    while i < len(words) and (re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", words[i]) or words[i] in ("sudo", "command", "env", "exec")):
        i += 1
    if i >= len(words):
        return None
    cmd = words[i].rsplit("/", 1)[-1]
    args = words[i + 1:]
    operands = [a for a in args if not a.startswith("-")]
    if cmd == "tee":
        if any(_is_state(a) for a in operands):
            return "`tee` onto the state file"
    elif cmd in ("sed", "gsed", "perl"):
        in_place = any(a == "-i" or a.startswith("-i") or a.startswith("--in-place")
                       or (cmd == "perl" and re.match(r"^-\w*i", a)) for a in args)
        if in_place and any(_is_state(a) for a in args):
            return f"`{cmd} -i` on the state file"
    elif cmd in ("cp", "mv", "install", "rsync", "ln"):
        target_dir = None
        for j, a in enumerate(args):
            if a in ("-t", "--target-directory") and j + 1 < len(args):
                target_dir = args[j + 1]
            elif a.startswith("--target-directory="):
                target_dir = a.split("=", 1)[1]
        if target_dir is None and operands and _is_state(operands[-1]):
            return f"`{cmd}` onto the state file"
    return None


def bash_writes_state(command):
    """Reason string when the command writes the state file, else None."""
    if not _is_state(command):
        return None
    # Drop the segments that invoke phase.py — that is the sanctioned writer.
    kept = [seg for seg in SEGMENT_SPLIT_RE.split(command) if not PHASE_PY_RE.search(seg)]
    for seg in kept:
        why = _segment_writes_state(seg)
        if why:
            return why
    rest = "\n".join(kept)
    # Interpreter one-liners and heredocs: `python3 -c "open(p,'w')…"`, `python3 - <<EOF`.
    if INTERPRETER_RE.search(rest) and _is_state(rest) and WRITE_INTENT_RE.search(rest):
        return "script opening the state file for writing"
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(data, dict):
        return

    tool_name = data.get("tool_name")
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return

    if tool_name in FILE_TOOLS:
        path = tool_input.get("file_path") or tool_input.get("notebook_path") or ""
        if isinstance(path, str) and path.endswith(STATE_SUFFIXES):
            block(f"{path} may not be edited by hand")
        return

    if tool_name == "Bash":
        command = tool_input.get("command")
        if not isinstance(command, str):
            return
        why = bash_writes_state(command)
        if why:
            block(f"Bash command denied ({why})")


if __name__ == "__main__":
    main()
