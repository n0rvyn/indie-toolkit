#!/usr/bin/env python3
"""PreToolUse(Bash) guard for the xcodebuild / simctl hard rules.

Why a hook and not prose: the rules already exist in CLAUDE.md's xcodebuild SOP,
and prose lost twice — the July audit hand-fixed test-changes and finalize, then
characterization-test shipped `-destination '...,name=iPhone 16'` anyway (a
concrete bash template in context beats an abstract global rule). The same
conclusion is written into knowledge/bug-postmortem/2026-07-27:
「这次补的不是文字，是执行者。写进知识库没有拦住它，因为没有东西执行它。」

Decisions are emitted as PreToolUse JSON on exit 0 (docs: "JSON output is only
processed on exit 0"), never as exit 2. That choice is deliberate: a missing or
crashed script then produces no JSON and the call proceeds, so a broken guard
cannot wedge every Bash call.

  1. deny — `xcodebuild test` with a `name=` destination: clones a new sim, and
     under concurrency the clone storm takes the whole batch down (SOP rule 2).
  2. deny — `xcodebuild test` while another one is already running (SOP rule 1).
  3. ask  — `xcrun simctl boot`: escalates to a real permission prompt, which is
     what 禁止行为「未经批准启动模拟器」 asks for (approval, not a self-declared marker).
  4. stderr nudge, never blocks — more than one booted simulator (SOP rule 5).

False-positive control, two layers:
  a. heredoc BODIES are removed before segmentation (`_strip_heredocs`), so a doc
     or plan file written via `python3 - <<'EOF'` can quote the command freely;
  b. within a real segment only the FIRST token is inspected, so
     `grep -rn 'destination.*name=' …` and `echo "xcodebuild test"` never trip it.
Layer (b) alone was not enough: inside a heredoc body the first token really is
`xcodebuild` (2026-08-10, two denials on prose). Both layers are exercised by
`tests/test_xcodebuild_guard.sh`.
"""
import json
import os
import re
import subprocess
import sys

SEGMENT_SPLIT = re.compile(r"(?:\|\||&&|[;|&\n])")

# `<<EOF` / `<<'EOF'` / `<<"EOF"` / `<<-EOF`, capturing the delimiter word.
HEREDOC_START = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")


def _strip_heredocs(command):
    """Drop heredoc BODIES before segmentation.

    Why this exists: `SEGMENT_SPLIT` splits on `\\n`, so every line of a heredoc
    body became its own "shell segment". A body line that happens to start with
    `xcodebuild test …` — e.g. writing documentation, a knowledge-base entry, or
    a plan file that quotes the command — then looked exactly like a real
    invocation and got denied.

    Observed twice on 2026-08-10 (CleanLabel): both denials were `python3 - <<'PY'`
    heredocs whose payload was *prose about* the command, not a call. The existing
    first-token control could not help — inside the body, the first token really
    is `xcodebuild`.

    The `_is_invocation` control answers "is this token in command position?";
    this one answers the prior question "is this line shell at all?".

    Limitation: only heredocs are stripped. A multi-line double-quoted argument
    (`python3 -c "…\\nxcodebuild test …"`) still splits on the newline. Heredoc is
    the form that actually bit us; widening this to full shell lexing is not worth
    the risk of the guard failing open on syntax it mis-parses.
    """
    lines = command.split("\n")
    out, i = [], 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        m = HEREDOC_START.search(line)
        i += 1
        if not m:
            continue
        delim = m.group(2)
        # Skip body lines up to and including the terminator (`<<-` allows indent).
        while i < len(lines) and lines[i].strip() != delim:
            i += 1
        i += 1  # consume the terminator itself (no-op when unterminated)
    return "\n".join(out)


def _segments(command):
    """Shell segments, each stripped of leading env assignments and `cd x &&`."""
    for raw in SEGMENT_SPLIT.split(_strip_heredocs(command)):
        seg = raw.strip()
        while seg.startswith("(") or seg.startswith("$("):
            seg = seg.lstrip("($").strip()
        if seg:
            yield seg


def _is_invocation(segment, *tools):
    """True when the segment actually RUNS one of `tools`.

    Matches:   xcodebuild test …            xcrun simctl boot …
    Rejects:   grep -n 'xcodebuild test' …  echo "xcrun simctl boot"
    """
    tokens = segment.split()
    if not tokens:
        return False
    head = os.path.basename(tokens[0])
    rest = tokens[1:]
    if head in ("xcrun", "sudo", "time", "nice", "env"):
        if not rest:
            return False
        head = os.path.basename(rest[0])
        rest = rest[1:]
    if head not in tools:
        return False
    return True, rest


def _is_test_run(segment):
    """xcodebuild `test` action, excluding build-for-testing / test-without-building."""
    hit = _is_invocation(segment, "xcodebuild")
    if not hit:
        return False
    _, args = hit
    actions = [a for a in args if not a.startswith("-")]
    return any(a in ("test", "test-without-building") for a in actions)


def _booted_count():
    try:
        out = subprocess.run(["xcrun", "simctl", "list", "devices", "booted"],
                             capture_output=True, text=True, timeout=4).stdout
    except Exception:
        return None
    return len([ln for ln in out.splitlines() if "(Booted)" in ln])


def _other_test_running():
    """Any live `xcodebuild test`? Uses `ps`, NOT `pgrep -af`.

    macOS ships BSD pgrep, which has no `-a`: `pgrep -af xcodebuild` prints bare
    PIDs, so the arg parsing below found nothing and this check silently returned
    "nothing running" forever. Same shape as the GNU-vs-BSD `find -newermt` trap
    in knowledge/workflow/2026-07-11. Caught by running a decoy positive control.

    Only command lines whose FIRST token is xcodebuild (or `xcrun xcodebuild`)
    count, so a grep/echo that merely mentions the string is not a match.
    """
    try:
        out = subprocess.run(["ps", "-Ao", "pid=,command="],
                             capture_output=True, text=True, timeout=4).stdout
    except Exception:
        return None
    for ln in out.splitlines():
        parts = ln.strip().split(None, 1)
        if len(parts) < 2:
            continue
        cmd = parts[1]
        if not _is_test_run(cmd):
            continue
        if "build-for-testing" in cmd:
            continue
        return cmd[:120]
    return None


def decide(decision, reason):
    """Emit a PreToolUse decision. JSON is only honoured on exit 0 (official docs),
    so a crashed or missing script produces no JSON and the call proceeds — the
    guard fails open instead of blocking every Bash call."""
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason}}, ensure_ascii=False))
    sys.exit(0)


def block(msg):
    decide("deny", msg)


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    if data.get("tool_name") != "Bash":
        return
    command = (data.get("tool_input") or {}).get("command") or ""
    if not command:
        return

    for seg in _segments(command):
        # --- 3. unapproved simctl boot -------------------------------------
        hit = _is_invocation(seg, "simctl")
        if hit and "boot" in hit[1][:1]:
            decide("ask", "CLAUDE.md 禁止行为「未经批准启动模拟器」：boot 需要你本轮明确批准。"
                          "批准即放行；不批准的话，只验证能编用 `build-for-testing`，"
                          "或改用真机 `-destination \"platform=iOS,id=<UDID>\"`。")

        if not _is_test_run(seg):
            continue

        # --- 1. name= destination ------------------------------------------
        if re.search(r"-destination\s+['\"]?[^'\"]*\bname=", seg):
            block("⛔ `xcodebuild test` 用了 `name=` destination（xcodebuild SOP 规则 2）。"
                  "未 booted 的同名 sim 会被 clone 成新 sim，并发下 clone 风暴必崩。"
                  "改用 UDID：真机 `xcrun xctrace list devices` 取硬件 UDID → "
                  "`-destination \"platform=iOS,id=<UDID>\"`；真机不在位则用已 booted sim 的 UDID；"
                  "都没有 → 降级 `build-for-testing` 并报告「⚠️ 测试未运行」。")

        # --- 2. concurrent test run ----------------------------------------
        running = _other_test_running()
        if running:
            block("⛔ 已有一个 `xcodebuild test` 在跑（xcodebuild SOP 规则 1，永远只跑一个）。"
                  f"在跑的是：{running}。等它结束，或先确认那个是不是僵进程。")

        # --- 4. >1 booted sim (nudge only) ---------------------------------
        n = _booted_count()
        if n is not None and n > 1:
            print(f"[xcodebuild-guard] {n} 台 sim 已 booted（SOP 规则 5 建议 ≤1）。"
                  "并发 sim 是 FRONTBOARD watchdog 崩批的常见诱因："
                  "`xcrun simctl shutdown all` 后只留要用的那台。", file=sys.stderr)


if __name__ == "__main__":
    main()
