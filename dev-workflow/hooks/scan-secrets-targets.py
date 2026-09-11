#!/usr/bin/env python3
"""Print the staged diff of every repository a Bash command commits into.

Called by scan-secrets.sh with the PreToolUse JSON on stdin. The hook's `if`
filter only narrows to git invocations; this script decides whether the command
commits, and where. It resolves the target repository the way git would:

  - global options before the subcommand (-C, --git-dir, --work-tree, -c ...)
    are replayed verbatim on `git diff --cached`
  - leading VAR=value assignments (GIT_DIR=..., GIT_WORK_TREE=...) become its env
  - `cd <dir>` earlier in the same command moves the working directory

Output is empty when the command does not commit or nothing is staged. Anything
it cannot resolve falls back to the session cwd, with a note on stderr so a miss
can be traced to the branch that ran.
"""
import json
import os
import re
import shlex
import subprocess
import sys

PUNCTUATION = "();<>|&\n"
GLOBAL_OPTS_WITH_ARG = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--config-env", "--super-prefix"}
PAGER_OPTS = {"-p", "--paginate", "-P", "--no-pager"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
DYNAMIC = re.compile(r"[$`]")


def note(msg):
    print(f"scan-secrets: {msg}", file=sys.stderr)


def split_commands(command):
    """Split a shell command line into simple commands (token lists)."""
    lex = shlex.shlex(command, posix=True, punctuation_chars=PUNCTUATION)
    lex.whitespace = " \t\r"  # newline separates commands, keep it as punctuation
    lex.whitespace_split = True
    lex.commenters = ""  # a comment would swallow the newline that separates commands
    commands, current, skip_redirect_target = [], [], False
    for tok in lex:
        if skip_redirect_target:
            skip_redirect_target = False
            continue
        if tok and all(c in PUNCTUATION for c in tok):
            if "<" in tok or ">" in tok:
                skip_redirect_target = True  # `> file`, `2>&1`, `<<EOF`
                continue
            if current:
                commands.append(current)
            current = []
            continue
        current.append(tok)
    if current:
        commands.append(current)
    return commands


def commit_targets(command, session_cwd):
    """Return (cwd, git global opts, env) for each `git ... commit` in the command.

    cwd is None when an earlier `cd` could not be resolved statically.
    """
    targets, cwd = [], session_cwd
    for cmd in split_commands(command):
        env = {}
        while cmd and ASSIGNMENT.match(cmd[0]):
            key, value = cmd.pop(0).split("=", 1)
            env[key] = value
        if not cmd:
            continue
        head = cmd[0]
        if head in ("cd", "pushd"):
            args = [a for a in cmd[1:] if a not in ("-P", "-L", "--")]
            dest = args[0] if args else "~"
            if dest == "-" or DYNAMIC.search(dest) or cwd is None:
                cwd = None
            else:
                cwd = os.path.normpath(os.path.join(cwd, os.path.expanduser(dest)))
            continue
        if os.path.basename(head) != "git":
            continue
        opts, i = [], 1
        while i < len(cmd) and cmd[i].startswith("-"):
            if cmd[i] in GLOBAL_OPTS_WITH_ARG and i + 1 < len(cmd):
                opts += cmd[i:i + 2]
                i += 2
            else:
                if cmd[i] not in PAGER_OPTS:
                    opts.append(cmd[i])
                i += 1
        if i < len(cmd) and cmd[i] == "commit":
            targets.append((cwd, opts, env))
    return targets


def staged_diff(cwd, opts, env):
    try:
        result = subprocess.run(
            ["git", "--no-pager", *opts, "diff", "--cached"],
            cwd=cwd, env={**os.environ, **env},
            capture_output=True, text=True, errors="replace",
        )
    except OSError:
        return None
    return result.stdout if result.returncode == 0 else None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    command = (data.get("tool_input") or {}).get("command") or ""
    session_cwd = data.get("cwd") or os.getcwd()

    try:
        targets = commit_targets(command, session_cwd)
    except ValueError as e:  # shlex: unbalanced quotes
        if not re.search(r"\bgit\b[^\n]*\bcommit\b", command):
            return
        note(f"could not parse the command ({e}); scanning {session_cwd} only")
        targets = [(session_cwd, [], {})]

    seen = set()
    for cwd, opts, env in targets:
        if cwd is None:
            note(f"could not resolve a `cd` before the commit; scanning {session_cwd} instead")
            cwd = session_cwd
        diff = staged_diff(cwd, opts, env)
        if diff is None and (cwd, opts, env) != (session_cwd, [], {}):
            shown = " ".join(["git", *opts]) + f" (in {cwd})"
            note(f"could not read staged changes via `{shown}`; scanning {session_cwd} instead")
            diff = staged_diff(session_cwd, [], {})
        if diff and diff not in seen:
            seen.add(diff)
            sys.stdout.write(diff)


if __name__ == "__main__":
    main()
