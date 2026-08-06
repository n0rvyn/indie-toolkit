# App Store 数据接口 — 实测可用清单

2026-08-06 实测通过。这些端点 Apple 均无公开文档，参数错一个就返回空或 5xx，而空结果极易被误读成「没数据」。

## Storefront 码

| 商店 | `X-Apple-Store-Front` |
|------|----------------------|
| 中国 | `143465-19,29` |
| 美国 | `143441-1,29` |

格式是 `<storefrontId>-<语言码>,<平台/版本码>`。storefront id 是 Apple 的国家码（美 143441、中 143465、日 143462、英 143444、德 143443）。

## 四个通用前提

1. **必须伪装 App Store 客户端 UA**：`AppStore/2.0 iOS/17.0 model/iPhone14,2 hwp/t8110 build/21A329 (6; dt:200)`。浏览器 UA 会拿到 302 或 503。
2. **必须 `curl -L`**。多个端点先返 301，不跟随就得到空 body，看起来像「接口挂了」。
3. **返回体没有稳定 schema**，Apple 随时改。解析前先把原始 JSON 存盘，解析失败时读原始文件定位，不要猜。
4. **不要并发打太狠**。8 路并发实测稳定，更高会零星 503。脚本要带磁盘缓存与重试。

---

## 1. 商品元数据 — iTunes Lookup

```
https://itunes.apple.com/lookup?bundleId=<bundleId>&country=<cc>
https://itunes.apple.com/lookup?id=<trackId>&country=<cc>
```

公开接口，无需 UA 伪装。给出：`trackName` · `sellerName` · `genres` · `version` · `releaseDate` · `currentVersionReleaseDate` · `averageUserRating` · `userRatingCount` · `description` · `releaseNotes` · `screenshotUrls` · `languageCodesISO2A` · `minimumOsVersion`。

**不给 subtitle。** 副标题必须走下面的 viewSoftware。

`entity=software`（iOS）/ `entity=macSoftware`（Mac）。搜 Mac App 时用错 entity 会查无。

## 2. 名称 + 副标题（权威）— MZStore viewSoftware

```
curl -sL -H "X-Apple-Store-Front: 143465-19,29" -A "$UA" \
  "https://itunes.apple.com/WebObjects/MZStore.woa/wa/viewSoftware?id=<trackId>"
```

解析路径：`storePlatformData.product-dv.results.<id>` → `name` · `subtitle` · `artistName` · `genreNames`。

这是唯一能拿到**每个 storefront 各自的**名称与副标题的接口。同一个 App 在 CN 与 US 返回不同值时，说明各本地化都填了；返回相同值时，说明其中一个本地化的这两个框是空的，Apple 在回落显示基础语言。

## 3. 真实搜索排名 — MZSearch

```
curl -sL -H "X-Apple-Store-Front: 143465-19,29" -A "$UA" \
  "https://search.itunes.apple.com/WebObjects/MZSearch.woa/wa/search?clientApplication=Software&term=<urlencoded>"
```

⚠️ 主机是 `search.itunes.apple.com`，**不是** `itunes.apple.com`。后者的同名路径返 503。

⚠️ **有序结果不在 lockup 里。** `storePlatformData['native-search-lockup']` 只有 `results` 字典且只水化前 8 条，**没有 `resultIds`**。完整排序在：

```
pageData.bubbles[0].results   # [{type, id, entity}, ...] 按名次排列
```

要拿到第 9 名往后的名称，用这些 id 逐个调 viewSoftware，或批量走 lookup（lookup 不给 subtitle）。

单次返回上限实测落在 246–250（Apple 未公开该数字）。因此「不在结果里」的正确表述是「不在前 ~250 名」，不是「未被索引」。

## 4. 搜索自动补全 — MZSearchHints

```
curl -sL -H "X-Apple-Store-Front: 143465-19,29" -A "$UA" \
  "https://search.itunes.apple.com/WebObjects/MZSearchHints.woa/wa/hints?clientApplication=Software&term=<urlencoded>"
```

返回 XML plist，取 `<key>term</key><string>…</string>`。这是 Apple 自己的搜索联想，按其自身顺序返回。

**它不是搜索量。** 能说的只有「Apple 会不会把这个词提示给用户」。返回空是有用信号：该词没有联想入口，用户必须完整手打。

---

## 走不通的路（省时间）

| 尝试 | 结果 |
|------|------|
| `apps.apple.com/<cc>/app/id<N>` 网页抓取 | 可用，但 Apple 按**请求 IP** 决定 storefront，从中国大陆抓 `/us/` 会被重定向到 `/cn/iphone/today`。跨区必须用 viewSoftware |
| `apps.apple.com/<cc>/search?term=X` | 404，网页端没有可抓的搜索页 |
| `amp-api.apps.apple.com/v1/catalog/...` | 401。需要 MEDIA_API bearer token，token 已不在页面 meta 里，需从 JS bundle 提取 |
| `uclient-api.itunes.apple.com/.../MZStorePlatform.woa/wa/search` | 404，端点已下线 |
| `itunes.apple.com/WebObjects/MZStore.woa/wa/search` | 503，路径在这台主机上无效（要用 search.itunes.apple.com） |

## 拿不到的数据

- **关键词字段**：Apple 无任何公开读接口。线上实际提交了什么无法核实。因此建议要写成「设为 X」，不能写「从 Y 改为 X」。唯一的反推手段是排名：App 为某词排名但名称与副标题都不含该词 → 该词在关键词字段里。
- **搜索量 / 转化率 / 下载量**：需要 App Store Connect API（要开发者账号私钥）或第三方付费面板。
- **历史排名**：接口只给当下。要趋势就自己定期跑、自己存。
