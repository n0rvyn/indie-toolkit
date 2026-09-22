#!/usr/bin/env bash
# probe.sh — read-only disk reclaim probe for macOS.
#
# Deletes nothing. Prints what is actually holding space, with the four
# measurement traps already corrected in how it measures:
#   1. mount points are not disk usage  -> du -x never crosses a device
#   2. ls -lh lies about sparse files   -> sizes come from du/st_blocks, never st_size
#   3. du counts APFS clones in full    -> candidates are clone-checked
#   4. the biggest item may not be a dir -> swap and per-process footprint come first
#
# Every path probe has THREE outcomes, never two: FOUND / ABSENT / DENIED.
# A missing path is not "nothing here" and a TCC refusal is not "0 bytes".
#
# Usage:
#   probe.sh              fast candidate-driven probe (seconds)
#   probe.sh --deep       + 嫌疑区定向下钻（本机实测 41 秒；刻意不做全盘遍历，理由见第 5 段）
#   probe.sh --selftest   prove the checkers work before trusting their zeros
set -uo pipefail   # deliberately not -e: individual probes are allowed to fail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GREP=/usr/bin/grep
DEEP=0

for arg in "$@"; do
  case "$arg" in
    --deep) DEEP=1 ;;
    --selftest) exec "$SELF_DIR/selftest.sh" ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

hr() { printf '\n== %s ==\n' "$1"; }
gib() { awk -v k="$1" 'BEGIN{printf "%.2f", k/1048576}'; }

# ---------------------------------------------------------------- section 1
hr "1. 容器与卷（先看总账，再看目录）"
df -h / /System/Volumes/Data /System/Volumes/VM 2>/dev/null | awk 'NR==1||/disk/'
echo
diskutil apfs list disk1 2>/dev/null \
  | $GREP -E 'Capacity In Use By Volumes|Capacity Not Allocated' \
  || echo "diskutil: 读不到 APFS 容器信息"

# ---------------------------------------------------------------- section 2
hr "2. 非目录占用 —— du 永远扫不到这些"
echo "[swap]"
sysctl vm.swapusage 2>/dev/null || echo "  读不到 vm.swapusage"
sw_n=$(ls /System/Volumes/VM 2>/dev/null | $GREP -c swapfile)
sw_kb=$(du -skx /System/Volumes/VM 2>/dev/null | awk '{print $1}')
echo "  swapfile 个数: ${sw_n:-?}    /System/Volumes/VM 实占: $(gib "${sw_kb:-0}") GiB"
echo "  判读: swap 只增不缩。释放它的唯一途径是让占用它的进程退出（然后系统回收），或重启。"

echo
echo "[单进程内存占用 top 8 —— 泄漏的进程会把 swap 撑成磁盘占用]"
top -l 1 -o mem -n 9 -stats command,mem 2>/dev/null | tail -n +2 | tail -9 \
  || echo "  top 读不到"
echo "  判读: 某进程 MEM 远大于物理内存 -> 差额在 swap 里。用 footprint -p <pid> 独立取证，"
echo "        不要只凭 top 一列下结论（ps RSS 不含换出页，两者差几百倍是正常的）。"

echo
echo "[Time Machine 本地快照]"
for v in / /System/Volumes/Data; do
  out=$(tmutil listlocalsnapshots "$v" 2>&1)
  n=$(printf '%s\n' "$out" | $GREP -c 'com.apple.TimeMachine')
  echo "  $v -> $n 个快照"
done
echo "  判读: 快照占的空间 df 算作已用但不属于任何目录。>0 时用 tmutil deletelocalsnapshots 处置。"

# ---------------------------------------------------------------- section 3
hr "3. 惯犯清单（按档；数字是本机实测，不是记忆）"
echo "TIER  SIZE_GiB  STATE     PATH"
echo "----  --------  --------  --------------------------------------------------"

# tier|label|path|rebuild-cost
CANDIDATES=(
  "0|XCTest 泄漏设备|$HOME/Library/Developer/XCTestDevices|Xcode 跑测试时自动重建，无下载"
  "0|失效模拟器设备|$HOME/Library/Developer/CoreSimulator/Devices|用 xcrun simctl delete unavailable，只删 runtime 已不存在的"
  "1|真机部署增量缓存|$HOME/Library/Containers/com.apple.CoreDevice.CoreDeviceService/Data/Library/Caches|Xcode 下次真机部署本地重建，无下载"
  "1|模拟器 dyld 缓存|/Library/Developer/CoreSimulator/Caches/dyld|首次启动模拟器重算，纯本地；需 sudo（真 Terminal，见 SKILL.md）"
  "1|iOS 真机符号|$HOME/Library/Developer/Xcode/iOS DeviceSupport|下次连真机重拉，每台数分钟"
  "1|Xcode DerivedData|$HOME/Library/Developer/Xcode/DerivedData|下次 build 重建，首次全量编译"
  "2|Xcode Archives|$HOME/Library/Developer/Xcode/Archives|⛔ 不可再生：已上架版本的 dSYM 在这里，删了就无法符号化线上崩溃"
  "1|Playwright 浏览器|$HOME/Library/Caches/ms-playwright|npx playwright install，数分钟"
  "1|SwiftPM 仓库缓存|$HOME/Library/Caches/org.swift.swiftpm/repositories|下次 resolve 重 clone"
  "1|SwiftPM manifests|$HOME/Library/Caches/org.swift.swiftpm/manifests|下次 resolve 重建"
  "1|CocoaPods 缓存|$HOME/Library/Caches/CocoaPods|pod install 重建 repo"
  "1|Homebrew 缓存|$HOME/Library/Caches/Homebrew|brew cleanup --prune=all"
  "1|go build 缓存|$HOME/Library/Caches/go-build|go clean -cache，下次 build 变慢一次"
  "1|npm 缓存|$HOME/.npm|npm cache clean --force"
  "2|pnpm 全局 store|$HOME/Library/pnpm/store|⛔ 禁止 rm。只能 pnpm store prune（现有项目靠硬链接指向它）"
  "2|HuggingFace 模型|$HOME/.cache/huggingface|重下很慢，先问用户"
  "2|Android AVD 镜像|$HOME/.android/avd|重建模拟器，先问用户"
  "2|Android SDK|$HOME/Library/Android/sdk|重下很慢，先问用户"
  "2|Xcode 下载组件|$HOME/Library/Developer/DVTDownloads|⚠️ 可能有正挂载的（查 mount），删了要重下"
  "2|Docker 虚拟磁盘|$HOME/Library/Containers/com.docker.docker/Data/vms|⚠️ ls -lh 会虚报几十 G；这里的数字是实占"
  "2|Cursor globalStorage|$HOME/Library/Application Support/Cursor/User/globalStorage|⚠️ state.vscdb 是聊天/工作区状态；只有 .backup 可删"
  "2|Chrome 缓存|$HOME/Library/Caches/Google|需先退出 Chrome"
  "2|Claude VM 镜像|$HOME/Library/Application Support/Claude/vm_bundles|⚠️ Claude Cowork 的虚拟机盘。删前确认没有会话在跑（pgrep -f Virtualization.VirtualMachine），删后首次用会重建"
  "2|Claude-3p VM 镜像|$HOME/Library/Application Support/Claude-3p/vm_bundles|同上，属另一个 Claude 安装"
)

# Paths du cannot reach because of TCC, regardless of sudo.
TCC_PATHS=("$HOME/Library/Messages" "$HOME/Library/Mail")

probe_one() {
  local tier="$1" label="$2" path="$3"
  if [ ! -e "$path" ]; then
    printf '%-4s  %8s  %-8s  %s\n' "$tier" "-" "ABSENT" "$path"
    return
  fi
  local errfile kb err state
  errfile=$(mktemp)
  kb=$(du -skx "$path" 2>"$errfile" | tail -1 | awk '{print $1}')
  err=$(cat "$errfile"); rm -f "$errfile"
  if [ -z "$kb" ]; then
    printf '%-4s  %8s  %-8s  %s\n' "$tier" "?" "DENIED" "$path"
    return
  fi
  state="FOUND"
  if printf '%s' "$err" | $GREP -qiE 'not permitted|permission denied'; then
    state="PARTIAL"   # the number is a LOWER BOUND, not the size
  fi
  printf '%-4s  %8s  %-8s  %s\n' "$tier" "$(gib "$kb")" "$state" "$path"
}

for entry in "${CANDIDATES[@]}"; do
  IFS='|' read -r tier label path _rebuild <<<"$entry"
  probe_one "$tier" "$label" "$path"
done

echo
echo "STATE 含义：FOUND=测到  ABSENT=路径不存在（不是 0，是本机没这项）"
echo "            DENIED=权限拒绝（不是 0，未测量）  PARTIAL=有子路径被拒，数字是下限"
echo
echo "重建代价（按上表顺序）："
for entry in "${CANDIDATES[@]}"; do
  IFS='|' read -r tier label path rebuild <<<"$entry"
  [ -e "$path" ] && printf '  [%s] %-18s %s\n' "$tier" "$label" "$rebuild"
done

echo
echo "[TCC 拒绝区 —— sudo 也进不去，需「隐私与安全性 -> 完全磁盘访问权限」授权终端]"
for p in "${TCC_PATHS[@]}"; do
  if du -skx "$p" >/dev/null 2>&1; then
    printf '  %8s GiB  %s（已授权，可测）\n' "$(gib "$(du -skx "$p" 2>/dev/null | awk '{print $1}')")" "$p"
  else
    printf '  %8s      %s（未测量，不是 0）\n' "DENIED" "$p"
  fi
done

# ---------------------------------------------------------------- section 4
hr "4. 测量注记 —— 下结论前必须读"
echo "[挂载点：出现在目录树里但不占 Data 卷]"
mount 2>/dev/null | $GREP -E 'CoreSimulator|DVTDownloads|\.dmg|disk[0-9]+s[0-9]+ on /Users|on /Library/Developer' \
  | sed 's/^/  /' || true
echo "  判读: du -x 已排除它们。若有人用不带 -x 的 du，这些会被重复计入（本清单不会）。"
echo
echo "[模拟器 runtime 的真实占用在 AssetsV2，不在挂载点]"
xcrun simctl runtime list 2>/dev/null | $GREP -E 'Total Disk Images|Last Used|^iOS|^watchOS' | sed 's/^/  /' \
  || echo "  simctl 读不到"
echo "  判读: Last Used 是近期的 runtime 不要删。"

if [ "$DEEP" = "1" ]; then
  hr "5. 下钻（--deep）—— 清单外的大头"
  # ⛔ 这里刻意 *不* 做全盘遍历。实测同一台机器：
  #    全盘 find "$HOME" -type f -size +1G  -> 2257 秒（37 分 37 秒），
  #      找到 11 个大文件，其中清单外的可清理项 0 个（其余全是用户数据或已在清单里）
  #    嫌疑区定向下钻（下面这段）    -> 41 秒，找到清单外的真东西
  #      （Application Support/Claude 12G + Claude-3p 5.8G 的 VM 镜像、.cache/puppeteer 1.4G）
  #    55 倍差距，而且慢的那个一无所获。穷举不是更彻底，只是更慢。
  #
  # 嫌疑区 = 应用自己往里写、用户不会去看、且删了不丢原始数据的地方。
  SUSPECTS=(
    "$HOME/Library/Application Support"
    "$HOME/Library/Containers"
    "$HOME/Library/Caches"
    "$HOME/Library/Developer"
    "$HOME/Library/Group Containers"
    "$HOME/.cache"
    "$HOME/.local"
    /private/var/folders
    /Library/Caches
  )
  for d in "${SUSPECTS[@]}"; do
    [ -d "$d" ] || { printf '  [ABSENT] %s\n' "$d"; continue; }
    du -hx -d1 "$d" 2>/dev/null | sort -hr | head -7 | sed 's/^/  /'
    echo
  done

  # 跳过了什么必须说出来 —— 默默缩小搜索范围和搜不到是两回事。
  echo "[⛔ 本次下钻**没有**扫描以下目录，它们是用户数据，不作为清理候选]"
  for d in "$HOME/Code" "$HOME/Documents" "$HOME/Desktop" "$HOME/Downloads" \
           "$HOME/Pictures" "$HOME/Movies" "$HOME/Music" "$HOME/Obsidian" "$HOME/VMs"; do
    [ -d "$d" ] && printf '  %s\n' "$d"
  done
  echo "  怀疑大头在这些目录里时，对具体某个跑： du -hx -d1 <目录> | sort -hr | head"
  echo "  ⛔ 不要把它们加进清理清单 —— 那是用户的东西，不是缓存。"
fi

hr "完成"
echo "这是只读探查，什么都没删。"
echo "下一步由 SKILL.md 的流程接管：分档 -> 逐项确认 -> 删 -> verify-free.sh 复测。"
