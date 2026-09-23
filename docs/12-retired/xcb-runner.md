# xcb-runner + run-tests — 退役于 2026-09-23（从未发布，停在 Phase 1 之后）

**当初要解决什么**
模型在 Apple 项目里直接用 Bash 跑 `xcodebuild test`：14 天里 381 次，而 test-changes 被调用了 0 次。遇到的问题有三类：
- **过滤写法不统一**：每次都是临时手写，出现过拿 `Executed N tests` 判断结果的写法，而这个计数对 Swift Testing 恒为 0。
- **子代理并发**：子代理跑了 92 次，违反规则 3。
- **规则文件太大**：`rules/xcodebuild-ios.md` 有 25KB，读到任何 `.swift` 文件都会加载。

设想把规则写成可执行的代码，换来两样东西：规则真的被执行，同时 context 变小。

**为什么退役** —— 投入和目标严重不成比例
用户的目标是「一个跑测试的技能，替代模型直接调 xcodebuild，出问题时带上 reference 文档」。实际做出来的是约 1700 行 Python、218 条测试，外加 3 轮计划校验、7 路 review、2 轮修复。

复杂度是一层层加上去的：
- **排队**：从「冲突时拒绝」改成「冲突时排队等待」（DP-002），问题就变成了分布式锁：mkdir 锁的回收竞态出了三版，最后换成 `fcntl.flock`。
- **脱离 worker**：绕过 Bash 单次调用 600 秒的上限，引入了 `await` 协议。
- **function hook 改写**：用的是 early access API，而且默认关闭，别人装了插件也不会生效。
- **覆盖面**：SPM、macOS 自动识别、设备缓存交叉校验、模拟器卡死后自动恢复。

每一步单独看都说得通。但没有人在「实现代价 vs 用户目标」这一层卡过它。用户原话：「为了省那点token浪费这么多精力测试、开发、eval，我觉得不值。」

**当时怎么做的**
代码原先保存在本地分支 `archive/xcb-runner`（未 push），该分支已于 2026-09-23 按用户要求删除。之后只能在 reflog 过期前（默认 90 天）用 `git show 1d05dff:<path>` 取回，下面的路径也照此替换：
- `git show archive/xcb-runner:apple-dev/scripts/xcb/xcb.py`：runner，包含 resolve-destination、flock 锁、run/await/cancel、summarize、build-results 分类
- `git show archive/xcb-runner:apple-dev/skills/run-tests/SKILL.md`
- `git show archive/xcb-runner:apple-dev/scripts/xcb/tests/REAL_PATH.md`：两台真机、macOS、SPM 的实测记录

设计与 review 过程在 `docs/06-plans/2026-09-23-xcodebuild-runner-dev-guide.md`、`…-xcb-phase1-review-fixes.md`、`…-xcb-hook-phase2-plan.md`（这几份是 gitignore 的本地文件）。

**实测得到、已经补进 reference 的知识**
见 `~/.claude/rules/xcodebuild-ios.md` 与 `~/.claude/references/xcodebuild-simulator-testing.md` 本次新增的条目：code 74 的 Mac 侧处置、结果包路径冲突会以 exit 64 失败、真机测试必须有 host app、`swift test` 的过滤写法与 xunit 格式、`build-results` 的 status 语义、`TEST_RUNNER_` 前缀。

**留下的那一小部分**
test-changes 里 3 个旧缺陷、守卫里 1 个旧缺陷，改为在原来的内联形态上直接修。它们都是本项目之前就已经发布出去的 bug，与 runner 无关。

**再做的话要不同在哪**
1. **先问「0 条测试不能算通过」这类核心价值能不能用一行命令加一条规则拿到。** 这次的答案是能：`xcresulttool get test-results summary` 读 `totalTestCount`。先做这一行，确认不够用再往上加。
2. **「冲突时排队」和「拒绝后让模型重试」对用户的差别很小，前者的实现代价却高出一个数量级。** 以后遇到「把拒绝升级成等待」这类需求，先把两者的代价差讲出来。
3. **基础设施类改动不要套用重型 dev-workflow。** 每个零件都走一遍「计划 → 校验 → 执行 → 7 路 review → 修复」，零件越多，轮次按乘法增长。这和 issue #40（拆分判据）是同一类问题。
4. **用 early access 且默认关闭的 API（function hook）做发布功能，先确认目标用户能用上。**

**如果要重做，形态应该是**
reference 加规则里的一行命令，不做 skill，也不做脚本。能强制执行的部分交给已有的经典守卫（`xcodebuild-guard.py`），它拒绝错误写法，同时指向 reference。
