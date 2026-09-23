# notion-with-api + notion-page-sync — 退役于 2026-09-23

**当初要解决什么**
App Store Connect 要求填写隐私政策、使用条款、支持页的公开 URL。当时的做法是把这几份本地 Markdown 同步到 Notion，用 Notion 的公开页面当这个 URL。
- `notion-with-api`：带鉴权的 Notion API 脚本（`notion_api.py`，约 1.5K 行）。
- `notion-page-sync`：读取 `.claude/notion-sync.local.md` 里的 token、父页面和文件到页面 ID 的映射，把本地 Markdown 推到 Notion。
- 调用方有三处：apple-dev 的 `update-asc-docs` Step 4、`project-kickoff` 9.9、`asc-listing` 审计清单。

**为什么退役** —— 需求消失了
- ASC 文档正在逐步迁到 norvyn.com，Notion 页面基本不再使用。
- 自 2026-08-05 以来两个技能都是 0 次调用（按 `local_command` 记录计数，并用 commit 做正控）。
- 以后要直接操作 Notion，用官方 Notion MCP 就行。

**当时怎么做的**
`git show d5e2e95:shared-utils/skills/notion-with-api/` 与 `git show d5e2e95:shared-utils/skills/notion-page-sync/SKILL.md`。

**迁移期注意**
Cashie 的 `CLAUDE.md:383-385` 里，ASC 的三个公开 URL 仍指向 notion.site。页面本身不受影响。在迁到 norvyn.com 之前，如果要改这几页的内容，就用官方 Notion MCP，或者手动在 Notion 里改。

**再做的话要不同在哪**
先问公开 URL 由谁托管。托管方自己的发布工具通常就够用，不需要在插件里另外维护一个 API 客户端。

**如果要重做，形态应该是**
不用做 skill。apple-dev 那几个调用方里写一句「更新公开副本并打开 URL 核对」，已经这样改了。

来源：session_013jH44W8QaXm2UExGPkHABs 用户原话「notion的，可以清理，因为现在ASC文档全部逐步迁到 https://norvyn.com 上面，notion的pages基本不在用了，如果单纯是用 Notion，可以用MCP（官方的）」
