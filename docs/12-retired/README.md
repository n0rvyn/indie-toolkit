# 退役记录

这里放的是**从 marketplace 里拿掉的 skill / agent 的理由**，不是备份 —— 代码在 git 里，`git show <sha>:<path>` 一条命令就能取回。

git 能重建的：文件长什么样、什么时候删的、谁删的。
git 重建不出来的：**为什么当初做它、为什么后来不要了、再做一次要哪里不一样**。这个目录只存后者。

## 什么时候读这里

想做一个新 skill 之前，先 `grep` 一遍这个目录。**十有八九以前做过**，而且当时是怎么死的、死在哪个前提上，都写在这儿。

## 记录格式

```markdown
# <name> — 退役于 YYYY-MM-DD

**当初要解决什么**：
**为什么退役**：能力被谁覆盖了 / 接线断了 / 需求消失 / 形态选错了
**当时怎么做的**：思路 + `git show <sha>:<path>`
**再做的话要不同在哪**：← 只有这条是 git log 重建不出来的
**如果要重做，形态应该是**：skill / reference / hook / 内联提示 —— 附理由
```

## 形态判据（2026-09-04 定，从这批退役里归纳出来的）

删这批东西的时候发现，**大部分「死掉的 skill」不是内容不好，是形态选错了**。判据：

| 形态 | 判据 | 归宿 |
|---|---|---|
| **只读检查** | 看代码 → 报发现 → 不改文件 | `review-execution` 下的一个 lens |
| **生成 / 写入** | 产出或修改文件 | 保留 skill（reviewer 按设计只读） |
| **知识** | 读一份参考再复述 | reference，挂进 `apple-swift-context` 的 Topic Router |

第三类是这批里最大的一档：五个 `context: fork` 的「参考加载器」，每个都是派一个子代理去读一个 markdown 文件，而 Topic Router 一行就能到同一个文件、还不用起子代理。

## 本目录索引

| 记录 | 退役日 | 一句话 |
|---|---|---|
| [swiftdata-patterns](swiftdata-patterns.md) | 2026-09-04 | 参考加载器壳，Topic Router 已指向同一文件 |
| [testing-guide](testing-guide.md) | 2026-09-04 | 同上；且唯一的调用方没有调用能力 |
| [profiling](profiling.md) | 2026-09-04 | 同上 |
| [xc-ui-test](xc-ui-test.md) | 2026-09-04 | 同上 |
| [localization-setup](localization-setup.md) | 2026-09-04 | 同上；且从来没有调用方 |
| [sync-design-md](sync-design-md.md) | 2026-09-04 | 前提不成立：要同步的两个文件在真实项目里共存过一次 |
| [validate-design-tokens](validate-design-tokens.md) | 2026-09-04 | 除去与 ui-reviewer 重复的部分，剩下的死在同一个前提上 |
| [code-audit](code-audit.md) | 2026-09-04 | 五类里四类重复、唯一独有的 security 搬成 review-execution Lens F |
| [audit-finishing-touches](audit-finishing-touches.md) | 2026-09-04 | 只读检查，4 项搬进 design-reviewer A13–A16 |
| [fetch-swift-api-updates](fetch-swift-api-updates.md) | 2026-09-04 | **迁出，非退役** —— 它维护本仓文件，却被发给不拥有这些文件的下游 |
