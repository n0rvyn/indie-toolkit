#!/usr/bin/env python3
"""PreToolUse(Bash) guard for the xcodebuild / simctl hard rules.

Why a hook and not prose: the rules already exist in ~/.claude/rules/xcodebuild-ios.md,
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
import tempfile
from functools import lru_cache

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
        # ⚠️ 剥掉 shell 关键字前缀：`;` 切完之后循环体那段长这样 ——
        #   `do xcodebuild test …`。首 token 是 `do`，`_is_invocation` 认不出，于是
        #   `for …; do xcodebuild test …; done` 这一整类**绕过全部规则**
        #   （2026-08-26 端到端探针实测：kill 守卫对循环形态放行）。
        while True:
            head = seg.split(None, 1)
            if len(head) == 2 and head[0] in ("do", "then", "else", "!", "exec"):
                seg = head[1].strip()
                continue
            break
        if seg:
            yield seg


def _apply_cd(cwd, args):
    """把一段 `cd …` 作用到当前跟踪的 cwd 上。认不出目标就原样返回。

    `cd -` 回上一个目录，这里跟不了 —— 保持不变，比猜一个错的强。
    """
    if not args:
        return os.path.expanduser("~")
    target = args[0].strip("'\"")
    if target == "-":
        return cwd
    target = os.path.expanduser(target)
    if not os.path.isabs(target):
        if not cwd:
            return cwd
        target = os.path.join(cwd, target)
    return os.path.realpath(target)


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


@lru_cache(maxsize=1)
def _booted_count():
    # ⚠️ 三个外部调用都要缓存 + 收紧超时：hooks.json 注册的是 `timeout: 10`，
    #    而它们都在按段循环里。原来 4s×3 最坏 12s 就穿了预算 —— 超时 = 没有 JSON
    #    = 静默放行，守卫等于不存在。
    try:
        out = subprocess.run(["xcrun", "simctl", "list", "devices", "booted"],
                             capture_output=True, text=True, timeout=3).stdout
    except Exception:
        return None
    return len([ln for ln in out.splitlines() if "(Booted)" in ln])


@lru_cache(maxsize=1)
def _other_tests_running():
    """**所有**在跑的 `xcodebuild test`，回 [(pid, 完整命令行), …]。Uses `ps`, NOT `pgrep -af`.

    macOS ships BSD pgrep, which has no `-a`: `pgrep -af xcodebuild` prints bare
    PIDs, so the arg parsing below found nothing and this check silently returned
    "nothing running" forever. Same shape as the GNU-vs-BSD `find -newermt` trap
    in knowledge/workflow/2026-07-11. Caught by running a decoy positive control.

    Only command lines whose FIRST token is xcodebuild (or `xcrun xcodebuild`)
    count, so a grep/echo that merely mentions the string is not a match.

    ⚠️ 回**全部**而不是第一条：放宽并发之后这条从无害变成承重 —— 只跟第一条比时，
    第二条真的会互相踩的会被直接放过去。
    """
    try:
        out = subprocess.run(["ps", "-Ao", "pid=,command="],
                             capture_output=True, text=True, timeout=2).stdout
    except Exception:
        return ()
    found = []
    for ln in out.splitlines():
        parts = ln.strip().split(None, 1)
        if len(parts) < 2:
            continue
        cmd = parts[1]
        if not _is_test_run(cmd) or "build-for-testing" in cmd:
            continue
        # ⚠️ 返回**完整**命令行，不截断：下面要从里面读 -project / -destination
        # 来判断到底抢不抢同一样东西。原来这里 `cmd[:120]` 会把 destination 切掉，
        # 于是「同一台设备」永远判不出来。
        # ⭐ 连 PID 一起回：对方没写 `-project` 时，还能从它的 cwd 把项目认出来。
        found.append((parts[0], cmd))
    return tuple(found)


@lru_cache(maxsize=64)
def _pid_cwd(pid):
    """活进程的工作目录。对方没写 `-project` 时唯一还剩的线索。

    ⚠️ 2026-08-26 实测撞上：另一个会话在 **iPhone** 上跑 `-scheme Cashie`
    （没写 `-project`），本会话在 **iPad** 上跑 ArtLens —— 三条冲突理由一条都不成立，
    却被「认不出项目」那个兜底**连拦 5 次**。而那个进程的 cwd 里就躺着 `Cashie.xcodeproj`。

    `lsof -a -d cwd -p <pid> -Fn` 打出 `n<路径>`（macOS 自带，2026-08-26 实测可用）。
    """
    if not pid:
        return None
    try:
        out = subprocess.run(["lsof", "-a", "-d", "cwd", "-p", str(pid), "-Fn"],
                             capture_output=True, text=True, timeout=2).stdout
    except Exception:
        return None
    cwd = next((ln[1:] for ln in out.splitlines() if ln.startswith("n")), None)
    return os.path.realpath(cwd) if cwd and os.path.isdir(cwd) else None


# 往上找工程根的层数上限。⚠️ 必须封顶：不封顶时深层子目录会一路走到
# `~/Code/Projects` 甚至 `~`，于是两个毫不相干的工程共用一个标识 —— 那正是
# 这次要消掉的误拦。
_WALK_UP_MAX = 4
_HOME = os.path.realpath(os.path.expanduser("~"))
_MARKER_SUFFIXES = (".xcworkspace", ".xcodeproj")


def _has_project_marker(d):
    try:
        names = os.listdir(d)
    except OSError:
        return False
    return "Package.swift" in names or any(n.endswith(_MARKER_SUFFIXES) for n in names)


def _project_root(cwd, cmd=""):
    """标识 = **工程根目录的 realpath**，不是工程文件名。

    为什么按目录不按文件名 —— 文件名那版有两个洞，2026-08-26 各实测到一例：
      · 同一目录里 `X.xcworkspace` 与 `X.xcodeproj` 并存时按文件名判成两个项目
        → 放行，而它们共享同一份 DerivedData/build.db（**漏拦**）
      · SPM 工程（只有 `Package.swift`，盘上没有 `.xcodeproj`）按文件名根本认不出
        → 落回保守兜底一律拦死（**误拦**）。本机就有两个：`swift-llm-gateway`、
        `swift-mail-core`

    取值顺序：命令里写死的路径 → 从 cwd 往上找工程标记 → cwd 本身。
    最后那步让「认不出」几乎不再发生；真的拿不到 cwd 时才返回 None 落回兜底。
    """
    # ⛔ 这里**不收 `-xctestrun`**：它的路径落在 DerivedData
    #   （`…/DerivedData/Cashie-abc/Build/Products/Debug-iphoneos/X.xctestrun`），
    #   dirname 出来是产物目录，与同一工程普通 `test` 算出的工程根**不相等**（实测 False）
    #   —— 同一份 build.db 拿到两个标识 = 漏拦。让它走下面的 cwd 那条。
    m = re.search(r"-(?:project|workspace)\s+(?:'([^']*)'|\"([^\"]*)\"|(\S+))", cmd)
    if m:
        p = next((g for g in m.groups() if g), "")
        if p:
            p = os.path.expanduser(p)
            if not os.path.isabs(p):
                if not cwd:
                    return None   # 相对路径 + 不知道 cwd = 认不出，走保守兜底
                p = os.path.join(cwd, p)
            return os.path.realpath(os.path.dirname(p))

    if not cwd or not os.path.isdir(cwd):
        return None
    # `xcodebuild` 的自动发现就是从 cwd 开始的，所以这里也从 cwd 往上走。
    d = os.path.realpath(cwd)
    for _ in range(_WALK_UP_MAX):
        if _has_project_marker(d):
            return d
        parent = os.path.dirname(d)
        if parent == d or d == _HOME:
            break
        d = parent
    # 找不到标记就拿 cwd 本身当标识：宁可把两个无关目录判成「同一个」（多拦一次），
    # 也好过退回「认不出」那条一律拦死的兜底。
    return os.path.realpath(cwd)


def _contention_key(cmd, cwd=None):
    """这次调用会跟别人抢什么：(工程根, destination 的 id, 是不是模拟器)。"""
    proj = _project_root(cwd, cmd)
    # ⚠️ 带引号和不带引号两种都要吃：`ps` 打出来的命令行**没有引号**
    #    （`-destination platform=iOS,id=...`），只按引号匹配会一路吃到行尾，
    #    把后面的 `-only-testing:` 也吞进去 —— 路径里碰巧有 "Simulator" 就误判。
    m = re.search(r"-destination\s+(?:'([^']*)'|\"([^\"]*)\"|(\S+))", cmd)
    dstr = next((g for g in (m.groups() if m else ()) if g), "") if m else ""
    m2 = re.search(r"\bid=([0-9A-Fa-f-]+)", dstr)
    return proj, (m2.group(1) if m2 else None), ("Simulator" in dstr)


def _conflict_reason(new, old):
    """两次 `xcodebuild test` 到底抢不抢同一样东西。不抢就返回 None。

    SOP 规则 1 原文是「永远只跑一个」，但它的三条理由都是**有范围的**：
      · DerivedData / build.db 锁  → 按项目
      · 同一台设备装不下两个 test session → 按 destination
      · CoreSimulator daemon + FRONTBOARD watchdog → 只要两边都在模拟器上就成立
    两个不同项目、两台不同真机，三条一条都不成立 —— 那种情况下拦是白拦
    （2026-08-14 实测撞上：另一个会话在 iPad 上跑 Lucent，把本机 iPhone 上的
    ArtLens 测试也挡住了）。

    ⚠️ 认不出项目时**判冲突**：宁可多拦一次，也不放过真的会互相踩的那种。
    ⭐ 但「认不出」2026-08-26 基本被消掉了（见 `_project_root`）：标识改成**工程根目录**，
       命令里没写 `-project` 就从 cwd 往上找，找不到标记就用 cwd 本身。
       所以现在只剩「连 cwd 都拿不到」才会落到这个兜底。
       起因：`-project` 是少数写法（那天在跑的那条 `-scheme Cashie` 自己就没写），
       于是这个兜底不是偶发的保守分支而是**常态路径**，把「Cashie 在 iPhone /
       ArtLens 在 iPad」连拦 5 次，而三条真判据一条都不成立。
    """
    pn, dn, sn = new
    po, do, so = old
    if pn is None or po is None:
        return "拿不到其中一方的工程根（既没写 -project/-workspace，也取不到 cwd），保守判为冲突"
    if pn == po:
        return f"同一个工程根（{pn}）—— DerivedData 的 build.db 锁是共享的"
    if dn and do and dn == do:
        return f"同一台设备（{dn}）—— 一台设备装不下两个 test session"
    if sn and so:
        return ("两边都在模拟器上 —— CoreSimulator daemon 和 FRONTBOARD "
                "watchdog 是全局的，并发是崩批的常见诱因")
    return None


# 在跑的 `xcodebuild test` 靠这些服务才连得上设备 / 模拟器。杀掉它们 ≠ 杀掉测试进程：
# 测试进程还在，但它脚下的设备通道没了，于是失败长得像**产品缺陷或设备故障**。
# 2026-08-26 实测：`launchctl kickstart -k` 重启 `CoreDevice.CoreDeviceService` 与
# `remotepairingd` 之后真机连接当场断，而第一反应是去怀疑用户的手机。
_FRAGILE_SERVICES = re.compile(
    r"(CoreDevice|remotepairingd|\bremoted\b|usbmuxd|AMPDevice|CoreSimulator"
    r"|simdiskimaged|testmanagerd|\bsimd\b)", re.I)


def _kill_tool(seg):
    """段首真正的命令名，剥掉 `sudo` / `xcrun` / `env` 这些前缀 —— 与 `_is_invocation`
    同一套剥法。⚠️ 不剥的话 `sudo killall xcodebuild` 会被读成 `sudo`。"""
    tokens = seg.split()
    for tok in tokens:
        head = os.path.basename(tok)
        if head not in ("xcrun", "sudo", "time", "nice", "env"):
            return head
    return ""


def _kill_targets(seg):
    """这一段要杀什么。不是杀进程的段返回 None（注意区分「没在杀」和「杀的是别的」）。"""
    hit = _is_invocation(seg, "kill", "killall", "pkill", "launchctl")
    if not hit:
        return None
    tool = _kill_tool(seg)
    args = hit[1]
    if tool == "launchctl":
        # 只有这几个子命令会真的把服务打断；`list` / `print` 是只读的。
        if not args or args[0] not in ("kickstart", "kill", "bootout", "stop", "remove"):
            return None
        if args[0] == "kickstart" and "-k" not in args:
            return None   # 不带 -k 就不杀已在跑的那份
    # ⚠️ 回**整段**，不回切好的 token：2026-08-26 那条真命令是
    #   `launchctl kickstart -k user/$(id -u)/com.apple.CoreDevice.CoreDeviceService`，
    #   `$(id -u)` 里的空格把 token 切开，服务名那半变成 `-u)/com.apple.CoreDevice…`
    #   开头是 `-`，被「过滤 flag」那步当成选项丢掉 —— 端到端探针实测放行了。
    #   服务名匹配交给调用方对整段做，不依赖分词。
    return seg


def _kill_verdict(seg, command):
    """这一段杀的东西会不会踩到在跑的 test。会 → 回一句人话；不会 → None。

    ⚠️ 抽出来是为了能测：判断留在 `main()` 里的话，套件只能靠「本机真有一个
    `xcodebuild test` 在跑」才验得了，换台机器跑就静默失效。这里不查在跑的进程，
    只回答「杀的是不是危险的东西」，查进程留给 `main()`。

    「在不在杀」按**段**判，「杀的是不是脆弱服务」对**整条命令**判：
      `for s in com.apple.CoreDevice.X …; do launchctl kickstart -k …/$s; done`
    里服务名在 `for` 那段、杀的动作在 `do` 那段，按段匹配永远对不上
    （2026-08-26 端到端探针实测放行 —— 而那正是当天敲下去的形态）。
    整条命令先剥 heredoc：不剥的话「一边 killall node、一边用 heredoc 写一段讲
    CoreDevice 的文档」会被判成在杀设备服务 —— 正是 2026-08-10 挨过两次的那一类。
    """
    killing = _kill_targets(seg)
    if not killing:
        return None
    fragile = (_FRAGILE_SERVICES.search(killing)
               or _FRAGILE_SERVICES.search(_strip_heredocs(command)))
    if fragile:
        return f"{fragile.group(0)}（设备/模拟器服务）"
    if _kill_tool(seg) in ("killall", "pkill") and "xcodebuild" in killing:
        return "xcodebuild（killall/pkill 不分会话）"
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

    # 这次调用在哪个目录下跑 —— 工程标识就靠它（见 `_project_root`）。
    # ⚠️ 不是「解析命令找 cd」：`_segments` 本来就按 `&&`/`;` 把 `cd X` 切成独立一段，
    #    顺着已有的循环把 cwd 带下去就行。不带的话 `cd X && xcodebuild …` 会拿到
    #    会话 cwd（比如 indie-toolkit）当工程标识 —— 那是**垃圾值不是「未知」**，
    #    垃圾值跟谁都不相等，于是兜底从「多拦」静默翻成「漏拦」。
    cwd = data.get("cwd") or os.getcwd()

    for seg in _segments(command):
        cd_hit = _is_invocation(seg, "cd")
        if cd_hit:
            cwd = _apply_cd(cwd, cd_hit[1])
            continue

        # --- 6. 杀掉在跑的 test 脚下的服务 ----------------------------------
        what = _kill_verdict(seg, command)
        if what:
            live = _other_tests_running()
            if live:
                decide("ask",
                       f"⚠️ 现在有 {len(live)} 个 `xcodebuild test` 在跑，而你要杀的是 {what}。"
                       "杀**测试进程本身**没问题；杀的是它脚下的设备/模拟器服务时，"
                       "测试进程还活着、设备通道却断了，失败会长得像产品缺陷或设备故障"
                       "（2026-08-26 实测：kickstart CoreDeviceService 后真机连接当场断，"
                       "第一反应是去怀疑用户的手机）。"
                       f"在跑的是：{live[0][1][:100]}。"
                       "确认要杀就批准；否则等它结束，或改成只杀那个卡住的 PID。")

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
        # ⚠️ 跟**每一条**在跑的比，不是只跟第一条（见 `_other_tests_running`）。
        mine = _contention_key(seg, cwd)
        for running_pid, running in _other_tests_running():
            why = _conflict_reason(mine,
                                   _contention_key(running, _pid_cwd(running_pid)))
            if why:
                block("⛔ 已有一个 `xcodebuild test` 在跑，而且**和你这次抢同一样东西**"
                      f"（xcodebuild SOP 规则 1）：{why}。"
                      f"在跑的是：{running[:120]}。等它结束，或先确认那个是不是僵进程。")
            print("[xcodebuild-guard] 另有一个 `xcodebuild test` 在跑，但两边不抢同一样东西"
                  "（不同项目、不同设备、不都在模拟器上），放行。"
                  f"在跑的是：{running[:100]}", file=sys.stderr)

        # --- 4. >1 booted sim (nudge only) ---------------------------------
        n = _booted_count()
        if n is not None and n > 1:
            print(f"[xcodebuild-guard] {n} 台 sim 已 booted（SOP 规则 5 建议 ≤1）。"
                  "并发 sim 是 FRONTBOARD watchdog 崩批的常见诱因："
                  "`xcrun simctl shutdown all` 后只留要用的那台。", file=sys.stderr)

        # --- 5. SOP location, once per session (nudge only) -----------------
        _sop_pointer(data.get("session_id"))


def _sop_pointer(session_id):
    """Point at the SOP once per session, for the one path `paths:` cannot reach.

    2026-08-16 the SOP moved from ~/.claude/CLAUDE.md into
    ~/.claude/rules/xcodebuild-ios.md with a `paths:` scope. Measured: a
    paths-scoped rule loads only when Claude READS a matching file, so a session
    that greps logs and runs `xcodebuild test` without ever opening a .swift file
    never gets it — and that is exactly the "真机 test 起不来" diagnostic path
    where the error-signature table matters most. This hook is PreToolUse(Bash)
    and does not depend on file reads, so it can close that gap.

    Once per session: repeated `-only-testing:` runs are normal, and a nudge that
    repeats every run is a nudge that gets ignored (see check-repeated-edit.py's
    2026-07-11 noise fix).
    """
    rules = os.path.expanduser("~/.claude/rules/xcodebuild-ios.md")
    if not os.path.isfile(rules):
        return
    if session_id:
        sentinel = os.path.join(
            tempfile.gettempdir(), f".xcodebuild-sop-{session_id}"
        )
        if os.path.exists(sentinel):
            return
        try:
            open(sentinel, "w").close()
        except OSError:
            pass
    print("[xcodebuild-guard] xcodebuild SOP 全文在 `~/.claude/rules/xcodebuild-ios.md`"
          "（destination 决策 / 9 条并发与假绿硬约束 / 真机 test 起不来的错误签名分诊表）。"
          "它按 `paths:` 触发，只在 Read 过 Swift·Xcode 文件时才在上下文里；"
          "本轮若没读过、而你要判断 destination 或分诊测试失败，直接 Read 它。",
          file=sys.stderr)


if __name__ == "__main__":
    main()
