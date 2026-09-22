#!/usr/bin/env bash
# verify-free.sh — read free space until it stops moving, then report.
#
# Why this exists: `rm -rf` returns long before the space comes back.
# CoreSimulator and large trees are reclaimed asynchronously — reading `df`
# straight after the delete reports a fraction of what was actually freed
# (measured: df said 5 GiB, the real figure once settled was 22 GiB).
# Sampling until two consecutive reads agree is the only honest reading.
#
# Usage:
#   verify-free.sh                 sample until stable, print current free
#   verify-free.sh <baseline_kb>   also print the delta against a baseline
#   verify-free.sh --baseline      print just the current free KB (for capture)
set -uo pipefail

VOL=/System/Volumes/Data
free_kb() { df -k "$VOL" | tail -1 | awk '{print $4}'; }
gib() { awk -v k="$1" 'BEGIN{printf "%.1f", k/1048576}'; }

if [ "${1:-}" = "--baseline" ]; then
  free_kb
  exit 0
fi

BASELINE="${1:-}"
INTERVAL=10
MAX_ROUNDS=30   # 5 minutes; large simulator trees have taken ~2

prev=$(free_kb)
stable=0
for ((i = 1; i <= MAX_ROUNDS; i++)); do
  sleep "$INTERVAL"
  cur=$(free_kb)
  if [ "$cur" = "$prev" ]; then
    stable=$((stable + 1))
    [ "$stable" -ge 2 ] && break
  else
    stable=0
    printf '  ...仍在回收：%s GiB（第 %d 次采样）\n' "$(gib "$cur")" "$i"
  fi
  prev=$cur
done

cur=$(free_kb)
if [ "$stable" -lt 2 ]; then
  echo "⚠️ ${MAX_ROUNDS} 次采样后仍未稳定，下面的数字是当前值而非最终值"
fi

echo "可用: $(gib "$cur") GiB"
if [ -n "$BASELINE" ]; then
  delta=$((cur - BASELINE))
  printf '回收: %s GiB（基线 %s GiB）\n' "$(gib "$delta")" "$(gib "$BASELINE")"
  if [ "$delta" -le 0 ]; then
    echo "⚠️ 空间没有增加。别急着重删 —— 先查两种解释："
    echo "   ① 删掉的是 APFS clone，块与原件共享（用 clonecheck.py 验）"
    echo "   ② 同时有别的进程在写盘（Cowork VM / 构建 / 下载），回收被抵消了"
  fi
fi

diskutil apfs list disk1 2>/dev/null | /usr/bin/grep -E 'Capacity In Use|Not Allocated'
