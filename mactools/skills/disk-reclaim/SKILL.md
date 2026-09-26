---
name: disk-reclaim
description: "排查 macOS 磁盘被什么占满并安全回收空间。先判定占用是不是目录问题（swap / 内存泄漏进程 / 本地快照常常才是大头），再按零风险-低风险-需确认三档逐项处理，删除前逐条征得确认。当用户说磁盘满了、空间不够、清理硬盘、startup disk full、看看什么占地方、为什么只剩几个 G 时使用。Use when the user reports a full or nearly full disk on macOS, asks what is eating space, or asks to clean up storage. Keywords: 磁盘满, 空间不足, 清理磁盘, 硬盘满了, 存储空间, disk full, startup disk, free up space, what is using my disk, reclaim storage."
compatibility: Requires macOS
effort: high
---

# Disk Reclaim

排查 macOS 磁盘占用并回收空间。**只读探查由脚本承担，删除决策留在主线逐项确认。**

## 为什么这个 skill 不用 `context: fork` / `model: haiku`

mactools 里另外十个 skill 都是 fork + haiku 的薄脚本封装。这个刻意不是，三条理由，别在"统一架构"时改回去：

1. **fork 出去就没人交叉核对了。** 磁盘数字有一整类系统性假象（见下），隔离上下文的子代理会把假象当事实报上来。实测：一次隔离扫描报上来的三个数字（挂载点 21G、clone 13G、稀疏文件 60G）全是错的，是主线核对才推翻的。
2. **`allowed-tools` 锁死脚本会挡住诊断命令。** 找根因用的是 `footprint -p` / `lsof +D` / `mount` / `F_LOG2PHYS_EXT`，"这次该用哪个"是判断，不是脚本分支。
3. **`rm -rf` 没有回收站。** mactools 里最重的写操作（`notes delete` / `mail trash`）都可撤销，这个不行。

Cost posture：Judgment 类 → inherit `model`，`effort` 按任务需要 pin（`skill-master/skills/plugin-master/cost-posture.md`）。

## 第一件事：占用不一定在目录里

⛔ **不要一上来就 `du`。** 最大的一项经常根本不是目录，`du` 怎么扫都扫不到它：

| 形态 | 怎么发现 | 实测 |
|---|---|---|
| 进程内存泄漏把 swap 撑成磁盘文件 | `top -l 1 -o mem` + `footprint -p <pid>` | 一个 `idevicesyslog` 孤儿进程 phys_footprint **56 GB**，16 GB 内存的机器被撑出 **60 GB** swapfile，占掉半块盘 |
| Time Machine 本地快照 | `tmutil listlocalsnapshots` | 算作已用，不属于任何目录 |
| 休眠镜像 | `/System/Volumes/VM/sleepimage` | 等于物理内存大小 |

`probe.sh` 的第 2 段就是干这个的，在惯犯清单之前跑。

## 工作流程

### Step 1 — 探查（只读，秒级）

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/probe.sh
```

清单驱动，不盲扫。输出四段：容器总账 / 非目录占用 / 惯犯清单（带档位、实测大小、三态、重建代价）/ 测量注记。

清单外还有大头时再加 `--deep`：**定向下钻嫌疑区**（Application Support / Containers / Caches / Developer / `.cache` / `var/folders`），本机实测 41 秒。

⛔ **它刻意不做全盘遍历。** 同一台机器上实测过两种做法：

| 做法 | 耗时 | 找到的清单外可清理项 |
|---|---|---|
| 全盘 `find $HOME -type f -size +1G` | **2257 秒**（37 分 37 秒） | **0 个**（11 个大文件全是用户数据或已在清单里） |
| 嫌疑区定向下钻 | **41 秒** | Claude/Claude-3p 的 VM 镜像 18G、`.cache/puppeteer` 1.4G |

55 倍差距，而且慢的那个一无所获。**穷举不是更彻底，只是更慢** —— 可清理的东西按定义就藏在应用自己写的目录里，不会均匀散落在文件系统各处。

`--deep` 会明确列出它**跳过了哪些目录**（`~/Code`、`~/Pictures`、`~/Movies` 等用户数据）。怀疑大头在那些目录里，对具体某个跑 `du -hx -d1 <目录> | sort -hr | head`，⛔ 但不要把它们加进清理清单。

首次使用或改过脚本后，先证明检查器是好的：

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/selftest.sh
```

### Step 2 — 读三态，别把三态读成两态

| STATE | 含义 | ⛔ 不许读成 |
|---|---|---|
| `FOUND` | 测到了 | — |
| `ABSENT` | 路径不存在，本机没这项 | "0 字节" |
| `DENIED` | 权限拒绝（TCC），**未测量** | "0 字节" / "没有" |
| `PARTIAL` | 有子路径被拒，数字是**下限** | 精确值 |

`~/Library/Messages`、`~/Library/Mail` 恒为 `DENIED`，`sudo` 也进不去 —— 要测得在「系统设置 → 隐私与安全性 → 完全磁盘访问权限」里授权终端。汇报时写"未测量"，不写"没有"。

### Step 3 — 删之前，先证明它没在用

对每个要删的目标：

```bash
lsof +D <目标路径> 2>/dev/null | tail -n +2 | wc -l
lsof +D /tmp 2>/dev/null | tail -n +2 | wc -l     # 正控：这个必须非零
```

⛔ **没有正控的 `0` 不算数** —— `lsof` 在某些路径上静默返回空，与"没人用"长得一模一样。

还要看有没有正在跑的相关活动：`pgrep -lf 'xcodebuild|XCTest'`、`xcrun simctl list devices booted`、其他 Claude/VM 会话在动哪些路径（`lsof -p <vm_pid>`）。

### Step 4 — 逐项确认

按档呈现，**一项一确认，不打包**：

- **档 0（零风险）** — 自动重建、无下载、无数据丢失。可以一次性列出让用户勾选。
- **档 1（低风险）** — 要重新下载或重新编译。必须说清重建代价（多久、要不要联网、会不会卡住下次操作）。
- **档 2（需确认）** — 有前提或有数据风险。逐条说明前提，用户不点头不动。

⛔ **不要自作主张扩大范围**。用户跳过的项就是跳过了，不要在下一轮"顺手也清了"。

### Step 5 — 删除，然后复测到稳定

```bash
BASE=$(bash ${CLAUDE_SKILL_DIR}/scripts/verify-free.sh --baseline)
rm -rf <目标>
bash ${CLAUDE_SKILL_DIR}/scripts/verify-free.sh "$BASE"
```

⛔ **删完立刻读 `df` 会低报。** CoreSimulator 和大目录树是异步回收的，实测 `df` 当场说回收 5 GiB，采样到稳定后真实是 **22 GiB**。`verify-free.sh` 采样到连续两次相等才返回。

回收为 0 时不要马上重删，先查两种解释：删的是 APFS clone（块共享）／同时有别的进程在写盘。

## 四类系统性假象 —— 下任何结论前对一遍

这四条是这个 skill 存在的主要理由。脚本里已经修正了测量方式，但**你在脚本之外自己跑命令时它们照样成立**。

### 1. 挂载点不是磁盘占用

`/Library/Developer/CoreSimulator/Volumes/iOS_*` 用 `du` 看是 21G，实际是一个 dmg 的挂载视图，真实占用 9.7G 在 `/System/Library/AssetsV2/...iOSSimulatorRuntime_Cryptex.dmg`。

```bash
mount | grep -E 'CoreSimulator|DVTDownloads'    # 先看哪些是挂载点
du -skx <path>                                  # -x 不跨设备，这是唯一正确的扫法
xcrun simctl runtime list                       # Last Used 近期的 runtime 不要删
```

### 2. `ls -lh` 对稀疏文件虚报

`~/Library/Containers/com.docker.docker/.../Docker.raw` 用 `ls -lh` 看是 **60G**，实占 **1.04G**。

```bash
python3 -c "import os,sys;s=os.stat(sys.argv[1]);print(f'logical={s.st_size/2**30:.1f}G 实占={s.st_blocks*512/2**30:.2f}G')" <file>
```

`du` 本身是按已分配块算的，**目录汇总不受影响**；只有 `find -exec ls -lh` 这种大文件清单会被骗。

### 3. `du` 把 APFS clone 全额计入，但块是共享的

Chrome 的 `code_sign_clone` 目录 `du` 看是 13G（9 份 ×1.4G），实际与 `/Applications/Google Chrome.app` 共享物理块，删了几乎不回收。

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/clonecheck.py <原件> <疑似克隆> ...
# SHARED = 同一物理块，删了不回收；DISTINCT = 独立块，删了真回收
```

### 4. 工具返回成功 ≠ 空间回来了

见 Step 5。`rm` 返回、`simctl delete` 返回，都不代表 `df` 已经反映。

## 需要人来做的两件事

| 情况 | 为什么模型做不了 | 给用户的确切指令 |
|---|---|---|
| 需要 `sudo` 的删除 | `sudo -n true` 报 `a password is required`；skill 跑的命令没有交互 TTY 接密码提示。**这不是 SIP** —— 用 `find <path> -flags +restricted`（正控：`/System/Library/CoreServices` 必须返回非空）确认没有 SIP 标志后再这么说 | "在 Terminal.app 里跑：`sudo rm -rf <path>`" |
| 读 `~/Library/Mail`、`~/Library/Messages` | TCC，`sudo` 无效 | "系统设置 → 隐私与安全性 → 完全磁盘访问权限 → 加上终端" |

⛔ 除这两类外，不要把可以自己查的事推给用户（全局 CLAUDE.md「用户能查吗？」自检）。

## 注意事项

- 探查全程只读；删除只在 Step 4 逐项确认之后发生
- 不碰 `~/Code`、`~/Documents`、`~/Desktop`、`~/Pictures`、`~/Movies` 这类用户数据目录 —— `--deep` **不扫它们**，只把跳过清单打出来。要看得手动对单个目录跑 `du`，且结果不进清理清单
- `~/Library/pnpm/store` ⛔ 禁止 `rm`：现有项目的 `node_modules` 全靠硬链接指向它，只能 `pnpm store prune`
- `~/Library/Developer/Xcode/Archives` 里有已上架版本的 dSYM，删了就无法符号化线上崩溃
- 清单里的路径会随 macOS / Xcode 版本漂移。`ABSENT` 的正确读法是"本机没这项"，不是"清单错了"；真的漂移了改 `probe.sh` 的 `CANDIDATES` 数组
