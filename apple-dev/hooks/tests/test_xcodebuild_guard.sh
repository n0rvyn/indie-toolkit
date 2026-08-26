#!/bin/bash
set -u

# Tests for xcodebuild-guard.py's two false-positive control layers.
#
# The regression that motivated this file (2026-08-10, CleanLabel): the guard
# split the command on newlines, so every line of a `python3 - <<'EOF'` heredoc
# body became a "shell segment". Writing a doc/plan/knowledge entry that quoted
# `xcodebuild test …` was denied twice as if it were a real invocation.
#
# Deterministic cases only: the concurrent-run rule reads live `ps`, so it is
# deliberately NOT asserted here (it would pass or fail depending on what else
# is running on the machine).

HOOK_SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/xcodebuild-guard.py"

PASS=0
FAIL=0

# run_case <name> <command> <expect: deny|ask|none>
run_case() {
    local name="$1" command="$2" expect="$3"

    local input_json
    input_json=$(COMMAND="$command" python3 -c "
import json, os
print(json.dumps({
    'tool_name': 'Bash',
    'tool_input': {'command': os.environ['COMMAND']},
    'hook_event_name': 'PreToolUse',
}))
")

    local stdout_output actual
    stdout_output=$(printf '%s' "$input_json" | python3 "$HOOK_SCRIPT" 2>/dev/null)

    if [ -z "$stdout_output" ]; then
        actual="none"
    else
        actual=$(OUT="$stdout_output" python3 -c "
import json, os
try:
    d = json.loads(os.environ['OUT'])
    print(d['hookSpecificOutput']['permissionDecision'])
except Exception:
    print('unparseable')
")
    fi

    if [ "$actual" = "$expect" ]; then
        echo "  ✅ $name (expect=$expect)"
        PASS=$((PASS + 1))
    else
        echo "  ❌ $name — expected '$expect', got '$actual'"
        FAIL=$((FAIL + 1))
    fi
}

echo "== layer a: heredoc bodies are not shell =="

# The exact shape that was denied twice on 2026-08-10.
run_case "heredoc body quoting the command is not an invocation" \
"python3 - <<'PYEOF'
import pathlib
body = '''
xcodebuild test -scheme CleanLabel -destination \"platform=iOS,id=00008140\"
'''
pathlib.Path('doc.md').write_text(body)
PYEOF" \
"none"

run_case "unquoted heredoc delimiter also strips" \
"cat > notes.md <<EOF
xcodebuild test -destination 'platform=iOS Simulator,name=iPhone 16'
EOF" \
"none"

run_case "<<- (tab-indented) heredoc strips" \
"cat > notes.md <<-EOF
	xcodebuild test -scheme X
	EOF" \
"none"

run_case "real invocation AFTER a heredoc still evaluated" \
"cat > notes.md <<'EOF'
just prose
EOF
xcodebuild test -scheme X -destination 'platform=iOS Simulator,name=iPhone 16'" \
"deny"

echo "== layer b: first-token control (pre-existing) =="

run_case "echo mentioning the command" \
'echo "xcodebuild test -destination name=iPhone 16"' \
"none"

run_case "grep for a name= destination" \
"grep -rn 'destination.*name=' ." \
"none"

echo "== rules still fire on genuine invocations =="

run_case "name= destination is denied" \
"xcodebuild test -scheme CleanLabel -destination 'platform=iOS Simulator,name=iPhone 16'" \
"deny"

run_case "name= denied even behind cd &&" \
"cd /tmp && xcodebuild test -scheme X -destination \"platform=iOS Simulator,name=iPhone 16\"" \
"deny"

run_case "simctl boot asks for approval" \
"xcrun simctl boot ABC-123" \
"ask"

run_case "build-for-testing is not a test run" \
"xcodebuild build-for-testing -scheme X -destination 'platform=iOS Simulator,name=iPhone 16'" \
"none"

# 2026-08-26：`;` 切完循环体那段是 `do xcodebuild test …`，首 token 是 `do`，
# `_is_invocation` 认不出 → `for …; do …; done` 这一整类曾绕过全部规则。
run_case "for 循环体里的调用照样受管（do 前缀）" \
"for d in A B; do xcodebuild test -scheme X -destination 'platform=iOS Simulator,name=iPhone 16'; done" \
"deny"

run_case "then/else 分支里的调用照样受管" \
"if true; then xcodebuild test -scheme X -destination 'platform=iOS Simulator,name=iPhone 16'; fi" \
"deny"

echo
echo "Passed: $PASS   Failed: $FAIL"
[ "$FAIL" -eq 0 ] || exit 1

# ---------------------------------------------------------------------------
# 并发规则的判据（2026-08-14）：从「看见任何 test 就拦」改成「只拦真抢同一样东西的」
#
# 这几条测的是纯函数 `_conflict_reason` / `_contention_key`，不读 live `ps`，
# 所以是确定性的 —— 上面那条「并发规则不在这里断言」的说明只对读 ps 的那部分成立。
echo
echo "── 并发冲突判据"
python3 - "$HOOK_SCRIPT" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("guard", sys.argv[1])
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)

IPHONE = "00008140-0001546401FB001C"
IPAD   = "00008027-000165A00A39002E"

def cmd(proj, dev, sim=False):
    plat = "iOS Simulator" if sim else "iOS"
    # ⚠️ `-project` 给**绝对路径**：标识按工程根目录算，相对路径在没有 cwd 时
    #    解析不出来，会落到「认不出」兜底，让这几条断言变成空转。
    return (f'xcodebuild test -project /src/{proj}/{proj}.xcodeproj -scheme {proj} '
            f'-destination "platform={plat},id={dev}"')

cases = [
    # (说明, 新的, 在跑的, 期望拦不拦)
    ("同一个项目 → 拦（build.db 锁共享）",
     cmd("ArtLens", IPHONE), cmd("ArtLens", IPAD), True),
    ("同一台设备 → 拦（一台设备装不下两个 session）",
     cmd("ArtLens", IPHONE), cmd("Lucent", IPHONE), True),
    ("两边都在模拟器 → 拦（CoreSimulator daemon 是全局的）",
     cmd("ArtLens", "AAA", sim=True), cmd("Lucent", "BBB", sim=True), True),
    ("不同项目 + 不同真机 → 放行（三条理由一条都不成立）",
     cmd("ArtLens", IPHONE), cmd("Lucent", IPAD), False),
    ("认不出项目（没写 -project） → 保守拦",
     'xcodebuild test -scheme ArtLens -destination "platform=iOS,id=%s"' % IPHONE,
     cmd("Lucent", IPAD), True),
    ("一边真机一边模拟器、不同项目 → 放行",
     cmd("ArtLens", IPHONE), cmd("Lucent", "BBB", sim=True), False),
]

bad = 0
for name, new, old, want_block in cases:
    why = g._conflict_reason(g._contention_key(new), g._contention_key(old))
    got = why is not None
    ok = got == want_block
    bad += 0 if ok else 1
    print(f"  {'✅' if ok else '❌'} {name}" + (f"　→ {why}" if why else "　→ 放行"))
sys.exit(1 if bad else 0)
PY
if [ $? -eq 0 ]; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); fi

echo "── 认不出项目时用 cwd 补认（2026-08-26）"
python3 - "$HOOK_SCRIPT" <<'PY'
import importlib.util, os, subprocess, sys, tempfile, time
spec = importlib.util.spec_from_file_location("guard", sys.argv[1])
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)

IPHONE = "00008140-0001546401FB001C"
IPAD   = "00008027-000165A00A39002E"
TOOL   = "xcode" + "build"   # ⚠️ 拼起来写：整串出现在命令里会被守卫自己拦下

def run_cmd(dev, scheme="X", project=None, sim=False):
    plat = "iOS Simulator" if sim else "iOS"
    proj = f"-project {project} " if project else ""
    return f'{TOOL} test {proj}-scheme {scheme} -destination "platform={plat},id={dev}"'

bad = 0
def check(name, ok, extra=""):
    global bad
    bad += 0 if ok else 1
    print(f"  {'✅' if ok else '❌'} {name}{extra}")

def mkproj(parent, name):
    d = os.path.join(parent, name)
    os.makedirs(os.path.join(d, name + ".xcodeproj"))
    return d

def mkspm(parent, name):
    d = os.path.join(parent, name)
    os.makedirs(d)
    open(os.path.join(d, "Package.swift"), "w").close()
    return d

with tempfile.TemporaryDirectory() as tmp:
    artlens = mkproj(tmp, "ArtLens")
    cashie  = mkproj(tmp, "Cashie")
    gateway = mkspm(tmp, "swift-llm-gateway")

    # ⭐ 正控：先证明这个原语真能从一个目录认出工程根，否则下面每条「放行」都一文不值
    check("正控：从 cwd 认出工程根（.xcodeproj）",
          g._project_root(artlens) == os.path.realpath(artlens),
          f"　→ {g._project_root(artlens)}")
    check("正控：从 cwd 认出工程根（SPM，盘上没有 .xcodeproj）",
          g._project_root(gateway) == os.path.realpath(gateway),
          f"　→ {g._project_root(gateway)}")
    sub = os.path.join(artlens, "ArtLens", "Views")
    os.makedirs(sub)
    check("正控：子目录里也能往上找到工程根",
          g._project_root(sub) == os.path.realpath(artlens), f"　→ {g._project_root(sub)}")

    # ── 主症（F1）：**新命令这侧**没写 -project，不同项目 + 不同真机 → 必须放行
    why = g._conflict_reason(
        g._contention_key(run_cmd(IPAD, "ArtLens"), artlens),
        g._contention_key(run_cmd(IPHONE, "Cashie"), cashie))
    check("新命令侧无 -project + 不同项目 + 不同真机 → 放行", why is None,
          f"　→ {why or '放行'}")

    # SPM 工程：盘上没有 .xcodeproj，按文件名的老写法在这里必然认不出
    why = g._conflict_reason(
        g._contention_key(run_cmd(IPAD, "swift-llm-gateway"), gateway),
        g._contention_key(run_cmd(IPHONE, "Cashie"), cashie))
    check("SPM 工程（无 .xcodeproj）+ 不同真机 → 放行", why is None,
          f"　→ {why or '放行'}")

    # 同一目录 workspace / project 并存：按文件名会判成两个项目 → 漏拦
    open(os.path.join(artlens, "ArtLens.xcworkspace"), "w").close()
    why = g._conflict_reason(
        g._contention_key(f'{TOOL} test -workspace ArtLens.xcworkspace -scheme A '
                          f'-destination "platform=iOS,id={IPAD}"', artlens),
        g._contention_key(f'{TOOL} test -project ArtLens.xcodeproj -scheme A '
                          f'-destination "platform=iOS,id={IPHONE}"', artlens))
    check("同目录 workspace vs project → 拦（共享 build.db）", why is not None,
          f"　→ {why or '放行'}")

    # 两侧都在同一个工程根 → 照样拦
    why = g._conflict_reason(
        g._contention_key(run_cmd(IPAD, "ArtLens"), artlens),
        g._contention_key(run_cmd(IPHONE, "ArtLens"), artlens))
    check("同一个工程根 + 不同设备 → 拦（build.db 锁）", why is not None,
          f"　→ {why or '放行'}")

    # 负控：兜底还活着 —— 两边都拿不到 cwd 且命令里也没写工程
    why = g._conflict_reason(
        g._contention_key(run_cmd(IPAD, "ArtLens"), None),
        g._contention_key(run_cmd(IPHONE, "Cashie"), None))
    check("负控：两侧都认不出（无 cwd、无 -project）→ 保守拦", why is not None,
          f"　→ {why or '放行'}")

    # 负控：`-xctestrun` 的路径落在 DerivedData，dirname 是产物目录不是工程根。
    #   拿它当标识的话，同一份 build.db 会拿到两个标识 → 漏拦（实测过一次）。
    dd = os.path.join(tmp, "DerivedData", "ArtLens-abc", "Build", "Products", "Debug")
    os.makedirs(dd)
    xr = os.path.join(dd, "ArtLens_iphoneos.xctestrun")
    open(xr, "w").close()
    check("负控：test-without-building -xctestrun 与普通 test 标识一致（不漏拦）",
          g._project_root(artlens, f'{TOOL} test-without-building -xctestrun {xr}')
          == g._project_root(artlens, run_cmd(IPAD, "ArtLens")),
          f"　→ {g._project_root(artlens, f'{TOOL} test-without-building -xctestrun {xr}')}")

    # 负控：往上找封顶 —— 深到超过上限时不许把 /tmp 之类当成工程根
    deep = os.path.join(gateway, "a", "b", "c", "d", "e", "f")
    os.makedirs(deep)
    check("负控：往上找封顶，深层子目录不回退到无关上级",
          g._project_root(deep) != os.path.realpath(gateway),
          f"　→ {g._project_root(deep)}")

# 正控：lsof 那条路（给在跑的进程用）真能取到 cwd
with tempfile.TemporaryDirectory() as d:
    p = subprocess.Popen(["sleep", "30"], cwd=d)
    try:
        time.sleep(0.4)
        check("正控：lsof 从活进程取到 cwd",
              g._pid_cwd(p.pid) == os.path.realpath(d), f"　→ {g._pid_cwd(p.pid)}")
    finally:
        p.kill(); p.wait()
check("负控：pid 为 None → 不崩，返回 None", g._pid_cwd(None) is None)

sys.exit(1 if bad else 0)
PY
if [ $? -eq 0 ]; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); fi

echo "── 杀服务前先看有没有 test 在跑（2026-08-26）"
python3 - "$HOOK_SCRIPT" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("guard", sys.argv[1])
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)

bad = 0
def check(name, ok, extra=""):
    global bad
    bad += 0 if ok else 1
    print(f"  {'✅' if ok else '❌'} {name}{extra}")

def targets(seg):
    return g._kill_targets(seg)

def fragile(seg):
    t = targets(seg)
    return bool(t) and bool(g._FRAGILE_SERVICES.search(t))

# ⭐ 正控：先证明这个判据认得出那条真的把设备连接搞断的命令 ——
#    2026-08-26 实际敲下去的**逐字**就是它。⚠️ 必须带 `$(id -u)`：按 token 过滤 flag
#    的那版对字面量 `user/501/…` 是绿的，而对这条真命令端到端实测**放行**了 ——
#    `$(id -u)` 里的空格把服务名那半切成 `-u)/com.apple.CoreDevice…`，开头是 `-`。
REAL = "launchctl kickstart -k user/$(id -u)/com.apple.CoreDevice.CoreDeviceService"
check("正控：认出 2026-08-26 那条 kickstart -k CoreDeviceService（原样，带 $(id -u)）",
      fragile(REAL), f"　→ {targets(REAL)}")
check("正控：写死 uid 的同形命令也认得出",
      fragile("launchctl kickstart -k user/501/com.apple.CoreDevice.remotepairingd"))
check("正控：认出 killall CoreSimulatorService（SOP 规则 6 的恢复序列）",
      fragile("killall -9 com.apple.CoreSimulator.CoreSimulatorService"))
check("正控：认出 sudo pkill usbmuxd", fragile("sudo pkill usbmuxd"))

# 负控：只读的 launchctl 子命令不算「在杀」
check("负控：launchctl list 不算杀", targets("launchctl list") is None)
check("负控：launchctl print 不算杀", targets("launchctl print user/501") is None)
# 负控：kickstart 不带 -k 不会打断已在跑的那份
check("负控：kickstart 不带 -k → 不算杀",
      targets("launchctl kickstart user/501/com.apple.CoreDevice.CoreDeviceService") is None)
# 负控：first-token 控制仍在 —— 提到这些字样的 grep/echo 不算
check("负控：grep 提到 killall 不算杀", targets("grep -rn 'killall CoreDevice' .") is None)
check("负控：echo 提到 launchctl 不算杀",
      targets('echo "launchctl kickstart -k CoreDevice"') is None)
# 负控：杀的是无关进程 → 认得出在杀，但不属于脆弱服务
check("负控：kill 无关 PID → 在杀但不是脆弱服务",
      targets("kill -9 12345") is not None and not fragile("kill -9 12345"))
check("负控：killall node → 在杀但不是脆弱服务",
      targets("killall node") is not None and not fragile("killall node"))

# ── `_kill_verdict`：判断本身（不查在跑的进程，所以换台机器也确定）
V = g._kill_verdict
LOOP = ("for s in com.apple.CoreDevice.CoreDeviceService "
        "com.apple.CoreDevice.remotepairingd; do launchctl kickstart -k user/$(id -u)/$s; done")
loop_kill_seg = "launchctl kickstart -k user/$(id -u)/$s"
check("正控：循环形态 —— 服务名在 for 段、杀在 do 段，靠整条命令认出",
      V(loop_kill_seg, LOOP) is not None, f"　→ {V(loop_kill_seg, LOOP)}")
check("正控：killall xcodebuild 不分会话 → 也要问",
      V("sudo killall -9 xcodebuild", "sudo killall -9 xcodebuild") is not None,
      f"　→ {V('sudo killall -9 xcodebuild', 'sudo killall -9 xcodebuild')}")
check("负控：kill 单个 PID → 不问（正当恢复手段）",
      V("kill -9 12345", "kill -9 12345") is None)
check("负控：killall node → 不问", V("killall node", "killall node") is None)
check("负控：完全没在杀（普通命令）→ 不问", V("ls -la", "ls -la") is None)
# 负控：heredoc 里**讲** CoreDevice 的文档，不算在杀它
#   （不剥 heredoc 的话整条命令扫描会命中 —— 2026-08-10 挨过两次的那一类）
DOC = ("killall node\n"
       "cat > notes.md <<'EOF'\n"
       "kickstart -k com.apple.CoreDevice.CoreDeviceService 会断开真机\n"
       "EOF")
check("负控：heredoc 里讲 CoreDevice 的文档 + killall node → 不问",
      V("killall node", DOC) is None, f"　→ {V('killall node', DOC)}")

sys.exit(1 if bad else 0)
PY
if [ $? -eq 0 ]; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); fi
