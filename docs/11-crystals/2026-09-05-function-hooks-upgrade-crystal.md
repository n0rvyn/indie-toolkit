---
type: crystal
status: deferred
tags: [function-hooks, claude-code, hooks, plugin-architecture, deferred-decision]
refs:
  - ~/.claude/knowledge/platform-constraints/2026-09-05-function-hooks-verified-contract.md
  - ~/.claude/knowledge/workflow/2026-09-05-binary-strings-prove-existence-not-contract.md
  - commit f3dfe57
  - commit d4dab4c
---

# Decision Crystal: hook → function hook 升级评估（暂缓，待 audit）

Date: 2026-09-05

**当前结论**：**不升级**。零转换。
**这份文档的用途**：过一段时间回来 audit，判断那些缺陷是偶然还是确实需要升级。
**`status: deferred` 什么时候改**：audit 得出结论时 —— 转成 `active`（决定升某几个）
或 `retired`（撤销提案）。第 5 节列了合法结论。

---

## 0. 重新评估之前，先确认三件事

function hooks 在 2026-09-05 是 **early access**，二进制自述 `it may change between releases`。
所以 audit 的第一步不是看下面的候选表，是先确认这三件事还成不成立：

| 要确认的 | 2026-09-05 的状态 | 怎么查 |
|---|---|---|
| 功能还在吗 | 引擎自 2.1.258 起随包发货 | `strings <CC 二进制> \| grep 'hooks worker'` |
| 灰度开了吗 | GrowthBook flag `tengu_plugin_hooks_modules` 默认 **false**；env `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` 可开 | 内置 skill `plugin-authoring` 出现在 skill 列表里 = 开了 |
| 契约还是那样吗 | 见 `~/.claude/knowledge/platform-constraints/2026-09-05-function-hooks-verified-contract.md` | 跑 `/plugin-types` 生成声明，与那份笔记比对 |

**第三条尤其重要**：那份笔记里的字段名（`next(e) → {ref, result, text}`、hook 返回 `{result}|{deny}`）
是 2.1.261 实测的。⛔ 如果 API 变了，下面所有"升级后应该变成什么"都要重写，
而不是照着做。**别拿旧字段名去写新代码**（这个坑本身已经踩过，见全局调试规则 10）。

---

## 1. 当前为什么不升级

四条理由，按权重排：

1. **灰度默认关闭。** 现在转，对任何没有手动 export 环境变量的人就是静默失效——
   hook 加载不了，不报错，什么都不发生。
2. **API 是 early access。** 现在写的代码要对着一个会变的契约。
3. **真正值得转的只有 3–5 个，不是全部。** 早期一版方案打算搬 12 个进新 plugin，
   算漏了一个数：剩下 7–9 个搬进去也永远不会转，纯白搬。
4. **失败域扩大。** shell hook 每次调用起独立进程，崩一次只影响那一次；
   function hook 每个 plugin 一个常驻 worker，一个死循环或未 await 的 rejection
   会让**整场会话所有 plugin 的 function hook 全部失效**（`function hooks are off for this session`）。

由第 4 条得出的路由规则，audit 时仍然适用：

> **一个 gate 越关键、越不能失效，越应该留在 shell —— 直到它需要 shell 表达不了的东西。**
> 转的理由必须是「shell 表达不了」，不能是「function hook 更优雅」。

---

## 2. 候选表

⚠️ **「只有 fh 能修」这一列是这张表的重点。** 不区分的话，audit 会把本来就能修的缺陷
算进升级理由，得出反的结论。

⚠️ **表里的文件有 4 个不在本仓**。2026-09-05 的归属重构（commit `f3dfe57`）把规则源在全局
CLAUDE.md 的 hook 迁到了 `~/.claude/hooks/`：

- `~/.claude/hooks/` — `big-read-gate.py`、`verify-agent-output.py`、`nudge-named-source.py`、`attribution-gate.py`
- `dev-workflow/hooks/`（本仓）— `bug-fix-gate.py`

| hook | 缺陷 | 2026-09-05 基线 | 只有 fh 能修？ | 已验证？ |
|---|---|---|---|---|
| `big-read-gate.py` | 想做「截断 + 明确告知」，`updatedOutput` 不存在，退化成「拦一次然后永久放行」。它自己的 docstring L18-20 就是这份妥协的签名 | 设计妥协，每次大文件整读都在生效 | **是** | **是** — fhdemo 端到端证明 `tool.call` 能改写已跑完的结果，模型只看到改写后的版本 |
| `verify-agent-output.py` | `extract_response_text()` 是手写多态解包器（str / list / dict，dict 里还嵌 output/content/text/result，只能挨个猜）；且只能事后发 `additionalContext`，改不了 agent 的返回本身 | 每次 Agent 返回都走这条 | **是**（改返回值） | 部分 — 改结果机制已验证，但没在 Agent 事件上试过 |
| `nudge-named-source.py` | 195 行里约 100 行在重建引擎已有的东西：手写 transcript jsonl 解析器 + 手写工具输入分派表（Read/Edit 看 file_path、WebFetch 看 url、Bash 正则搜 command、Grep 看 path） | 结构性，每次调用都在跑那 100 行 | 是（`$.session.messages()` + 类型化 `e`） | **否** — `$.session.messages()` 我没实跑过 |
| `bug-fix-gate.py` | 核心是纯语义判断（「这条消息是不是在报 bug」），用 10 条正则逼近。L29-31 注释自认：正则调得很紧是因为 hard 模式会阻断，「false positives are costly」（原文跨行） | 未计数 | 是（`$.model.classify`） | **否** — `$.model.classify` 我没实跑过 |
| `attribution-gate.py` | 同上，4 条正则做语义判断。`RELEASE_IDIOM` 那条补丁是因为它拦住了引入它自己的那次编辑（L44-45 自述） | 未计数 | 是（同上） | **否** |

### 已知的假候选（不要算进升级理由）

| 现象 | 真因 | 处置 |
|---|---|---|
| `check-repeated-edit` 报「同一处 old_string 第 2 次编辑」而实际 old_string 完全不同 | **双实例**：cache 里的旧注册 + settings.json 的新注册同时在跑，两个实例读写同一个 `.claude/edit-history.json`，第二个读到第一个刚写的同 fp 记录 | cache 更新后应自行消失。**可证伪**：没消失才是真缺陷 |
| `lint-claude-md` 的 p8 用例转红 | 它读**真实 skill 的 frontmatter**，而 `/handoff` 在 dev-workflow 2.42→2.43 之间把 `disable-model-invocation` 从 true 改成 false | 2026-09-05 已修（换成 `/afk`，并加了警告注释）。与 function hook 无关 |

---

## 3. 升级后应该变成什么（可证伪的预测）

只对「已验证」那一档给具体形状，其余标明是推测。

**`big-read-gate`（已验证机制）** —— 现在做不到的行为，届时应该是这个形状：

```ts
on("tool.call", { tool: "Read" }, async ($, e, next) => {
  const r = await next(e);
  // 字段名以 /plugin-types 生成的声明为准，不要照抄这里
  if (够小 || 已提示过) return r;
  return { ...r, result: { ...r.result, /* 截断 */ }, text: "…余 N 字，带 offset 再读" };
});
```

判据：**「截断 + 明确告知」能不能真的写出来**。写不出来（被 Read 的 output schema 拒），
这个候选就不成立——注意 Read 的 output schema 我**没有查过**，Bash 那次的成功不能直接推过去。

**其余四个** —— 推测，audit 时要先各写一个最小原型验证机制，再谈值不值。

---

## 4. 观察期看什么

三个月后回来，逐条对照：

1. **假候选消失了吗**
   - `check-repeated-edit` 的误报：cache 更新后还在 → 是真缺陷，升格为候选；消失了 → 从表里划掉
2. **真候选犯过几次**
   - `big-read-gate` 因 deny-once 造成过实际损失吗（该整读却因为「已经拦过一次」而放过）
   - `verify-agent-output` 漏报过吗（agent 声称写了文件、实际没有、而它没报）
   - `attribution-gate` / `bug-fix-gate` 的正则误报/漏报计数
3. **有没有新出现的、shell 表达不了的需求**
   —— 这条比前两条重要。升级的理由应该来自新需求，不是来自把旧缺陷擦亮

---

## 5. audit 的合法结论（不预设「要升」）

| 结论 | 触发条件 |
|---|---|
| **撤销这个提案** | 三个月里那些缺陷一次都没造成实际损失；或 function hooks 被砍/API 大改 |
| **继续观察** | 有零星发生但不足以支撑；或灰度仍未普放 |
| **转其中 1–2 个** | 某个候选的缺陷反复造成实际损失，且原型验证机制可行 |
| **全转** | ⛔ 这个结论需要格外强的证据。失败域扩大那条（第 1 节第 4 点）没有因为时间过去而消失 |

---

## 6. 相关材料

- 契约与调试坑：`~/.claude/knowledge/platform-constraints/2026-09-05-function-hooks-verified-contract.md`
- 方法教训（别拿二进制 strings 当 API）：`~/.claude/knowledge/workflow/2026-09-05-binary-strings-prove-existence-not-contract.md`
- 心智模型（event vs plugin、变轨比喻）：同上第一条的「心智模型」节
- 本次 hook 归属重构：commit `f3dfe57`（9 个 hook 迁出）、`d4dab4c`（auto-version scope 修复）
