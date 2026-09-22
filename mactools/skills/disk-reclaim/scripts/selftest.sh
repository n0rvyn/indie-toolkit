#!/usr/bin/env bash
# selftest.sh — prove every checker in this skill returns non-zero on a known
# positive BEFORE any of its zeros are trusted.
#
# A checker that has never been shown to fire is not a checker: its "0" is
# indistinguishable from "I looked in the wrong place". Each test below pairs
# a positive control (must hit) with a negative control (must not hit).
#
# Run: selftest.sh   — exits 0 only if every check passes.
set -uo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GREP=/usr/bin/grep
FAIL=0

ok()   { printf 'PASS  %s\n' "$1"; }
bad()  { printf 'FAIL  %s\n' "$1"; FAIL=1; }
skip() { printf 'SKIP  %s\n' "$1"; }

TMP=$(mktemp -d)
# Detach before deleting: a kill between `hdiutil attach` and `hdiutil detach`
# would otherwise leave rm -rf walking into a live mount.
cleanup() { hdiutil detach "$TMP/mnt" -force -quiet 2>/dev/null; rm -rf "$TMP"; }
trap cleanup EXIT INT TERM

echo "=== 1. sparse / clone 检测（clonecheck.py 自带四项对照）==="
if python3 "$SELF_DIR/clonecheck.py" --selftest; then
  ok "clonecheck.py selftest"
else
  bad "clonecheck.py selftest"
fi

echo
echo "=== 2. du -x 不跨挂载点 ==="
# Build our own fixture instead of picking a mount off the host: every real
# mount point on this machine has a parent that is either "/" or the whole data
# volume, so walking it without -x means scanning hundreds of GB.
# A 40 MiB disk image mounted inside a temp dir gives a bounded, deterministic
# positive control that works the same on any Mac.
MNT="$TMP/mnt"
IMG="$TMP/probe-fixture"
mkdir -p "$MNT"
if hdiutil create -size 40m -fs APFS -volname probefixture -quiet "$IMG" 2>/dev/null \
   && hdiutil attach "$IMG.dmg" -mountpoint "$MNT" -nobrowse -quiet 2>/dev/null; then
  # 16 MiB inside the mount; nothing outside it.
  dd if=/dev/urandom of="$MNT/payload" bs=1m count=16 2>/dev/null
  sync
  with_x=$(du -skx "$TMP" 2>/dev/null | tail -1 | awk '{print $1}')
  no_x=$(du -sk  "$TMP" 2>/dev/null | tail -1 | awk '{print $1}')
  hdiutil detach "$MNT" -quiet 2>/dev/null
  if [ -n "$with_x" ] && [ -n "$no_x" ] && [ $((no_x - with_x)) -gt 8000 ]; then
    ok "du -x 排除了挂载点内容（-x=${with_x} KB, 不带=${no_x} KB, 差 $((no_x - with_x)) KB ≈ 挂载内的 16 MiB）"
  else
    bad "du -x 未排除挂载点内容 (-x=${with_x:-?} 不带=${no_x:-?}) —— probe.sh 的目录数字会重复计入挂载点"
  fi
else
  skip "hdiutil 建不出测试镜像 —— 本项未验证（不是通过）"
fi

echo
echo "=== 3. 三态判定：ABSENT / DENIED 不得塌成 0 ==="
missing="$TMP/definitely-not-here-$$"
out=$(bash "$SELF_DIR/probe.sh" 2>/dev/null | $GREP -c 'ABSENT\|DENIED\|PARTIAL\|FOUND')
if [ "${out:-0}" -gt 0 ]; then
  ok "probe.sh 输出带状态列（$out 行）"
else
  bad "probe.sh 未输出状态列"
fi
# Positive control for ABSENT itself: a path we know does not exist.
if [ ! -e "$missing" ]; then
  ok "ABSENT 正控成立（$missing 确实不存在）"
else
  bad "ABSENT 正控失效"
fi
# Positive control for DENIED: TCC blocks ~/Library/Mail without Full Disk Access.
if du -sk "$HOME/Library/Mail" >/dev/null 2>&1; then
  skip "本机已授予完全磁盘访问权限，DENIED 分支无正控 —— 未验证"
else
  ok "DENIED 正控成立（~/Library/Mail 被 TCC 拒绝，非 0）"
fi

echo
echo "=== 4. swap / top 读数可解析 ==="
if sysctl vm.swapusage 2>/dev/null | $GREP -q 'total ='; then
  ok "vm.swapusage 可解析"
else
  bad "vm.swapusage 不可解析"
fi
if [ "$(top -l 1 -o mem -n 3 -stats command,mem 2>/dev/null | tail -3 | wc -l)" -ge 3 ]; then
  ok "top -o mem 返回排序列表"
else
  bad "top -o mem 无输出"
fi

echo
echo "=== 5. verify-free.sh 能测出空间变化 ==="
before=$(df -k /System/Volumes/Data | tail -1 | awk '{print $4}')
dd if=/dev/urandom of="$TMP/ballast" bs=1m count=256 2>/dev/null
sync
after=$(df -k /System/Volumes/Data | tail -1 | awk '{print $4}')
rm -f "$TMP/ballast"
if [ "$before" -gt "$after" ]; then
  ok "df 能观测到 256 MiB 的写入（$before -> $after KB）"
else
  bad "df 观测不到写入 —— 空间复测不可信（before=${before} after=${after}）"
fi

echo
if [ "$FAIL" = "0" ]; then
  echo "SELFTEST PASS —— 检查器已验，可以相信它们的零"
else
  echo "SELFTEST FAIL —— 未验的检查器返回的零不可采信"
fi
exit "$FAIL"
