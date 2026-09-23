# shared-utils（html-report + mongo 脚本）—— 退役于 2026-09-23

**当初要解决什么**
一个放跨插件公用东西的插件。先后放过 Notion API 助手（09-23 已退役）、MongoDB 查询/写入脚本，以及 `html-report` 技能（把一次会话的工作写成一份深色主题、自包含的 HTML 验收报告）。

**为什么退役**
- **html-report**：30 天只被调用过 1 次。写一份自包含的 HTML 已经不需要专门的技能了：模型自己就能写，Claude Code 也有 Artifact 这类原生出口。它唯一的内部调用方是 self-pacing 的最终报告，现在改成在 self-pacing 里直接写明约束（一个文件、内联 CSS、不带 JS、没验证过的项标 pending）。
- **mongo_query.py / mongo_insert.py**：本仓库没有任何调用方。唯一的使用者 personal-os 的 health-insights 早就自带了一份（`health-insights/scripts/`，两边内容已经分叉）。
- 这两样拿掉之后插件就空了，所以整个插件一起退役。

**当时怎么做的**
`git show d73fb97:shared-utils/`。html-report 的深色模板在 `skills/html-report/SKILL.md` 的「House template」一节。

**再做的话要不同在哪**
「公用」插件要先有第二个真实调用方再建。只有一个调用方的时候，把东西放在调用方自己那里（health-insights 就是这么做的）。

**如果要重做，形态应该是**
不做。报告的格式约束写在需要报告的技能里；脚本跟着用它的插件走。

来源：session_013jH44W8QaXm2UExGPkHABs 用户原话「html-report 不如可退了，写个html应该不需要这个skill了吧？」
