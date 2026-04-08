---
type: crystal
status: active
tags: [cross-project-knowledge, harvester, pkos, obsidian-bases]
refs: []
---

# Decision Crystal: Cross-Project Knowledge Harvester

Date: 2026-04-08

## Initial Idea

我在 ~/Code/Projects/ 下面有众���项目，每个项目下面都或许会有项目级别的 11-crystal 以及其它 docs（或���有用，或许没用），我们能否把这张大网编织起来，实现更大规模的知识库建立、联动呢？

## Discussion Points

1. **知识规模盘点**: 扫描发现 26 个项目共有 41 crystals、47 lessons、405 plans。知识散落在独立项目中，彼此完全隔离。例如 Adam 的 sandbox crystal 和 Shield 的安全设计不知道彼此存在。

2. **汇入架构**: 提出三层方案 — harvester 收割 + cross-project ripple 关联 + cross-project Bases 视图。用户接受此方向。

3. **与现有体系的关系**: kb-bridge（刚实现的双向）变成 harvester 的子集。harvester 覆盖所有项目，kb-bridge 只做 ~/.claude/knowledge/ 这一个方向。serendipity 的图谱计算基础扩大到包含 26 个项目的决策历史。

4. **增量策略**: state file 记录 {project}/{file_path} → hash + vault_path，每次 harvest 只处理新增/变更文件。可 Adam cron 定时跑或手动 /pkos harvest。

5. **vault 存储位置**: 跨项目���档写入 PKOS vault 的 30-Projects/{project}/ 目录，保持来源可追溯。

## Rejected Alternatives

- **每个项目单独配置 kb-bridge**: Rejected because — 需要在每个项目中分别配置和运行，不可扩展到 26 个项目；用户需要一个集中式的 harvester 而非分布式的 bridge。Rejection scope: 分布式 bridge 作为跨项目方案；does NOT reject kb-bridge 继续处理 ~/.claude/knowledge/ 方向。

- **直接 symlink 所有项目 docs 进 PKOS vault**: Rejected because — 会引入大量非知识文件（plans 中有很多过程性文件），且 Obsidian 索引负担过重；需要有选择性地收割高价值文档。Rejection scope: 全量 symlink；does NOT reject 选择性收割。

## Decisions (machine-readable)

- [D-001] 新建 `/pkos harvest` skill，扫描 ~/Code/Projects/*/docs/ 收割 crystals、lessons、designs 到 PKOS vault
- [D-002] 收割文档写入 ~/Obsidian/PKOS/30-Projects/{project-name}/ 目录，保持项目来源可追溯
- [D-003] 增量运行：state file 追踪已导入文件 + 文件 hash 检测变更，只处理新增/变更
- [D-004] 收割后对每个文档跑 ripple-compiler，让 MOC 层自动发现跨项目的 tag 重叠
- [D-005] 生成跨项目 Bases 视图：cross-project-decisions.base、cross-project-lessons.base、project-activity.base
- [D-006] harvester 覆盖所有项目后，kb-bridge 的双向功能变成 harvester 的子集；kb-bridge 保留但专注 ~/.claude/knowledge/ 方向
- [D-007] serendipity skill 的图谱计算基础扩大到包含所有已收割项目的文档

### AI-supplemented

- [D-S01] ⚠️ AI 补充：收割范围限定为 crystals（11-crystals/）、lessons（09-lessons-learned/）和 design docs（*-design.md），不包含 plans（06-plans/ 中 405 个文件大部分是过程性文件）。Reasoning: plans 是执行细节，价值密度低于 crystals/lessons/designs；全量导入会造成 vault 噪音过高。
- [D-S02] ⚠️ AI 补充：CLAUDE.md 不纳入收割范围（25 个项目各有一个），因为 CLAUDE.md 是 AI 行为指令而非知识文档。Reasoning: CLAUDE.md 的内容面向 AI 执行者，对知识图谱无贡献。

## Constraints

- ~/Code/Projects/ 下项目数量会持续增长，harvester 必须自动发现新项目
- 不同项目的 crystal/lesson 格式可能不完全一致（早期项目缺少 tags frontmatter），harvester 需要容错处理
- Obsidian vault 索引性能：30-Projects/ 下按项目子目录组织，避免单一扁平目录

## Scope Boundaries

- IN: 跨项目知识收割 — "把这张大网编织起来"
- IN: PKOS vault 中实现跨项目联动 — "更大规模的知识库建立、联动"
- OUT: 修改各项目自身的 docs 结构（harvester 只读不写源项目）

## Source Context

- Design doc: none
- Design analysis: none
- Key files discussed:
  - ~/Code/Projects/*/docs/11-crystals/*.md (41 files across 11 projects)
  - ~/Code/Projects/*/docs/09-lessons-learned/*.md (47 files across ~15 projects)
  - pkos/skills/kb-bridge/SKILL.md
  - pkos/skills/serendipity/SKILL.md
  - pkos/agents/ripple-compiler.md
