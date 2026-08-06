---
name: aso-research
description: "Use when optimizing an App Store listing for search — the user says 'ASO', 'ASO 优化', '关键词优化', 'app store 关键词', '搜不到我的 app', 'why doesn't my app rank', '商店排名', 'keyword research', or asks whether a trademark can go in the app name/subtitle/keywords. Pulls REAL data from Apple's own endpoints (live metadata, ranked search results, autocomplete, competitor name+subtitle) and produces evidence-backed metadata copy. Not for filling ASC form fields (use /asc-listing) or code-level review compliance (use /asc-submit-preview)."
---

# ASO Research — 数据驱动的商店搜索优化

针对已上架或即将上架的 App，用 Apple 自己的接口拉真实数据，产出可直接提交的名称 / 副标题 / 关键词 / 描述。

## 硬约束

**禁止输出搜索量、难度分、机会分。** 那些数字来自 Sensor Tower / AppTweak 等付费面板。本 skill 没有该数据源，编出来的分值会让用户按假数据做决策。可以报告的只有实拉到的：排名名次、结果总数、自动补全词的原始顺序、竞品的名称与副标题。

需要难度代理指标时，只用自己测得的量并标注是自建指标，例如「某词前 10 名里有 N 个把该词写进了名称或副标题」。

**零结果先怀疑自己的采集器。** 排名查询返回空、补全词返回空时，先在一个已知会命中的词上跑同一条命令验证采集器可用，再解读这个空。

## Process

### Step 1: 确定目标 App 与商店

从用户消息或项目取 bundle id（`grep PRODUCT_BUNDLE_IDENTIFIER` 项目的 pbxproj，或直接问）。确定要分析哪些 storefront（常见：cn + us）。

```bash
python3 scripts/aso.py live <bundleId|trackId> <store>
```

**这一步必做**：项目里的文案文档经常与线上不符，不核实就写建议等于改一份幻觉。

记录并向用户报告任何不一致：文档写的与线上不同、What's New 里装着描述、同一 App 三个名字、某个 storefront 的本地化字段没填。

**App 尚未上架时**（`live()` 返回 `None`）：跳过第一节的现状核对，Step 3 的排名矩阵改成只测竞争面（结果总数 + 竞品名次，本 App 那一列为空）。Step 2 的商标判定、Step 4 的补全、Step 5 的竞品、Step 6 的文案全部照常做 —— 上架前定字段比上架后改代价低得多。

### Step 2: 商标可用范围判定（有第三方品牌时必做）

App 依赖或对接第三方服务时（Garmin、Strava、Notion、Claude…），先定这一条，它决定后面每个字段怎么写。

读 `references/trademark-by-field.md`。核心结论是**分字段**的，不是一个是非题。

除文档结论外，还要做两件事：
- 用 `details()` 拉该品牌词搜索结果前 50 名，找出开发者不是品牌方、却在名称或副标题里用了该品牌的在架 App
- **问用户有没有被拒历史**。同账号的实际驳回记录，权重高于任何在架推断 —— 别人架上有，可能是拿了授权或老提交沿用，不可依赖

### Step 3: 排名矩阵

```bash
python3 scripts/aso.py matrix <trackId> <store> <词1> <词2> ...   # 词 → 结果总数 → 本 App 名次
python3 scripts/aso.py search <词> <store> --id <trackId>          # 单个词的完整榜单（名称+副标题+开发者）
```

列 20–40 个候选词建表：词 → 结果总数 → 本 App 名次 → 主要竞品名次。竞品那一列用 `search()` 的返回自己筛 id。

`matrix` 会先在一个已知会命中的词上自测采集器，自测不过直接退出 —— 这道闸防的是把「采集器坏了」读成「这个词没竞争」。

候选词来源：现有描述里的功能词、品牌词及其中文译名、竞品名称里的词、Step 4 的补全词。

读表要点：
- 名次 > 25 约等于零曝光（搜索结果第三屏往后）
- `—`（不在返回范围内）不等于未被索引，只是不在前 ~250
- 只在自己 App 名上排第 1 = 关键词完全没打开
- 本 App 为某词排名但名称和副标题里都没有该词 → 该词一定在关键词字段里，且已过审。这是唯一能反推关键词字段内容的手段（Apple 无读接口）

### Step 4: 自动补全

```bash
python3 scripts/aso.py hints <词> <store>
```

**补全为空是重要信号**：Apple 不会主动把这个词提示给用户，纯靠手打，做主攻方向拿不到量。返回非空的词才是自然入口。

按原始顺序列出，不加任何评分。

### Step 5: 竞品

```bash
python3 scripts/aso.py details <trackId> <store>            # 权威 name + subtitle
curl -s "https://itunes.apple.com/lookup?id=<trackId>&country=<cc>"   # 上架日期 / 评分数 / 描述
```

对排名矩阵里反复压过本 App 的 App，拉完整档案：名称、副标题、开发者、上架日期、评分数与均分、描述。

重点看它赢在哪个**字段**：是名称里塞了关键词，还是本地化做全了，还是纯粹评分多。同期上架、功能重叠却排名领先的竞品，差别通常就在一两个字段上。

### Step 6: 产出文案

字段上限：名称 30 · 副标题 30 · 关键词 100 · 推广文本 170 · 描述 4000。**每一条都用脚本数字符数写进文档**，别靠目测 —— 中英混排目测必错。

```bash
python3 scripts/aso.py check name "佳同步 - 国区国际版活动记录互传"
python3 scripts/aso.py check subtitle "候选A" "候选B" "候选C"    # 可一次传多个
```

超限时退出码为 1，可直接串进脚本。

分配原则：

| 字段 | 放什么 |
|------|--------|
| 名称 | 最高权重。品类词 + 自有品牌。有第三方商标风险时一个商标字都不放 |
| 副标题 | 第二权重。第三方品牌词放这里，用「for X」/「适用于 X」的指代式 |
| 关键词 | 名称与副标题装不下的。不与前两者重复 |
| 描述 | iOS 端**不参与搜索索引**。只承担转化，不承担排名 |
| 推广文本 | 不索引、不过审、随时可改 |

去重规则：Apple 自动组合名称+副标题+关键词的词，**且大小写不敏感**。`connect` 与 `Connect` 算同一个词，放两遍纯浪费字符。

品牌名候选要实测命名空间（`python3 scripts/aso.py search <候选名> <store>`）：看该词有没有 App 正在用这个确切名字、前排是不是被大厂模糊匹配吃掉。注意「结果数少」只说明没人搜这个词，对品牌名而言是中性的，真正有用的判据是「这个确切名字无人占用」。

同时检查候选名与在架竞品是否同构（同前缀 + 同字数 + 同品类）—— 4.1(a)「minor changes to another app's name」管这个。

### Step 7: 落盘与复检

写两个文件：

- 分析文档 —— 全部实拉数据、采集方法、局限说明、复现方式
- 文案文档 —— 线上现状（已核实）与建议提交分两块，每项带字符数与依据

**必须写进文案文档的复检方法**：改动上线后重跑脚本，对同一批词取名次，与分析文档的排名矩阵逐行对比。没有复检方法的 ASO 报告无法证伪。

## 边界

- 评分数量与均分是排序输入项，改元数据动不了。一句话点出即可，不展开成章节
- 名称是唯一改动要走完整审核周期的字段，建议改名时必须明说这个代价
- 品牌名、App 改名属于 UX / 品牌决策，列候选与实测数据后由用户定，不替用户拍板

## Completion Criteria

- 线上现状已从 Apple 接口核实，与项目文档的差异已列出
- 涉及第三方商标时，逐字段结论已给出，且引用了官方条款原文 + 在架实证 + 用户的被拒历史
- 排名矩阵、补全词、竞品档案都有实拉数据支撑
- 每个建议字段都有字符数，且不超限
- 复检方法已写入文档
- 报告里没有任何搜索量 / 难度分之类的编造数字
