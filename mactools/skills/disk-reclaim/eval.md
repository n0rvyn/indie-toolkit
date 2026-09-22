# disk-reclaim Eval

Runnable cases live in `mactools/evals/disk-reclaim/`. This file holds the
trigger spec and the assertions that only a human on a real host can check.

**必须带 Bash 授权跑**，否则结果无意义：

```bash
claude plugin eval ./mactools --trust-plugin --allow-tools Bash --case '01-*'
```

不带 `--allow-tools Bash` 时 CLI 会把 Bash 从模型手里收走，于是 `nothing-deleted`
（`max: 0` 的 Bash 匹配）**必然通过 —— 因为一次 Bash 都没发生过**，那是假绿。
配套的 `selftest-ran`（`min: 1`）在同一情形下会失败，用例整体仍会红，
这对 grader 是刻意成对的：一个防假绿，一个才是真正的断言。

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "磁盘满了，看看什么占地方"
- "只剩 2 个 G 了，有什么能清的"
- "Your startup disk is almost full，帮我看看"
- "free up space on my mac"
- "what is eating my disk"
- "清理一下硬盘"
- "存储空间不足，能删点什么"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "搜一下我电脑上的合同文件" → spotlight
- "这个文件夹里有什么" → 直接 ls
- "帮我把 Downloads 里的 pdf 移到 Documents" → 普通文件操作，不是空间回收
- "这次会话用了多少 token" → dev-workflow:audit-tokens
- "删掉这个项目的 node_modules" → 目标已指定，直接删，不需要排查

## Assertions verifiable only on a real host
<!-- These need an actual Mac with actual disk state; the runnable cases in
     evals/disk-reclaim/ cover what a sandbox can reach. -->

- [ ] 非目录占用先于惯犯清单呈现（swap / 本地快照 / 单进程 footprint 在 `du` 结果之前）
- [ ] `DENIED` 与 `ABSENT` 在汇报给用户时不被写成 "0" 或 "没有"
- [ ] 删除前对每个目标跑过 `lsof +D` **且带正控**
- [ ] 删除按档分组，档 1 与档 2 逐项确认，用户跳过的项不在后续轮次被清理
- [ ] 删除后用 `verify-free.sh` 采样到稳定，不用删除瞬间的 `df` 读数
- [ ] 需要 sudo 或 TCC 授权的项，交回给用户并附确切指令；其余项不推给用户
- [ ] `~/Library/pnpm/store` 永不出现在 `rm` 命令里（只出现在 `pnpm store prune`）
