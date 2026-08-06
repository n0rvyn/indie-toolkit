# aso-research Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "为这个 App 做 ASO 优化"
- "ASO"
- "关键词优化"
- "我的 app 在 App Store 搜不到"
- "why doesn't my app rank for X"
- "帮我看看商店关键词怎么写"
- "keyword research for the App Store"
- "Garmin 这个商标我能用到什么程度"
- "副标题能不能写 Strava"
- "竞品在商店里排第几"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "隐私标签应该怎么填" → asc-listing
- "帮我填 ASC 的字段" → asc-listing
- "上架前代码合规检查" → asc-submit-preview
- "这个需求有人要吗" → product-lens:demand-check
- "Review my code quality"
- "截图一下这个页面"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] 线上现状来自 Apple 接口实拉，不是照抄项目文档
- [ ] 项目文档与线上不一致时，差异被明确列出
- [ ] 报告中**没有**搜索量、难度分、机会分之类无数据源的数字
- [ ] 排名矩阵每行有：词 / 结果总数 / 本 App 名次
- [ ] 未命中标为「不在前 ~250」而非「未被索引」
- [ ] 自动补全按 Apple 返回的原始顺序列出，未附加评分
- [ ] 涉及第三方商标时给出**逐字段**结论，且引用了官方条款原文
- [ ] 问过用户有没有被拒历史（有则其权重高于在架推断）
- [ ] 每个建议字段带字符数且未超限
- [ ] 关键词建议写作「设为 X」，并说明为何无法与线上 diff
- [ ] 复检方法写入了交付文档
- [ ] 品牌名 / 改名作为用户决策呈现，未替用户拍板

## Failure Modes To Check
- 采集器返回空却被解读为「该词没有竞争」→ 必须先跑正例自测
- 用 `itunes.apple.com/search` 的排序当作 App Store 排名 → 必须用 MZSearch
- 名称里塞第三方商标 → 4.1(c)，且改名要走完整审核
- 关键词与副标题重复放同一个词（大小写不敏感）→ 白白浪费字符
