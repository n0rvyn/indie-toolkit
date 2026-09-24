# update-asc-docs — 退役于 2026-09-24

**当初要解决什么**：提交 App Store 前，扫代码（敏感框架、Info.plist 权限、本地存储、网络与第三方服务、同意流程），据此更新仓库里的 4 份文档（隐私政策、用户协议、支持页、商店文案，位于 `docs/10-app-store-connect/`），再列出要去 ASC 后台手动做的事。

**为什么退役**：与 `asc-listing` 重叠——后者已覆盖隐私标签和「隐私政策必须与代码一致」的核对清单。真正难手工做的只有「扫代码 → 对照文档」这一段，已并入 `asc-listing/references/asc-audit-checklist.md` 的「隐私政策一致性检查」。其余是复制粘贴量级的活，后续也可由 Chrome 插件 + CC 完成。60 天记录内调用 0 次。

- 来源：session_01WHz4QdvADFm4LqjfETYqn5 用户原话「leave asc-listing (增补它，如果需要） retire update-asc-docs」

**当时怎么做的**：按 4 种文档分别审计 → 输出差异报告 → 用户确认后改文档 → 同步公开副本 → 输出 ASC 操作清单。`git show 4583a9f:apple-dev/skills/update-asc-docs/SKILL.md`

**再做的话要不同在哪**：用户对它的记忆是「往 ASC 网页填字段」，实际做的是改仓库里的法律文档——名字和描述没让用户记住它真正的价值。重做时名字要说出「隐私政策对代码」这件事。

**如果要重做，形态应该是**：reference（现已在 `asc-listing` 的核对清单里），不是独立 skill。
