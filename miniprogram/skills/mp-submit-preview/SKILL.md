---
name: mp-submit-preview
model: sonnet
description: 微信小程序上线前自检 + 修配置。当用户说「小程序上线前检查」「上传前自检」「mp submit preview」「小程序体验评分」「代码质量」「要发布小程序」时使用。逐项核对 project.config.json 压缩/兼容配置、合法域名白名单、包体积、SafeArea、需真机验证项，给出 pass/fail + 一键修可修项。非 iOS ASC（那是 apple-dev:asc-submit-preview）。
allowed-tools: Bash, Read, Grep, Glob, Edit
---

# 小程序上线前自检（mp-submit-preview）

微信小程序发布前的代码/配置侧自检，对标 devtools「代码质量 / 体验评分」+ 常踩的上线坑。**只查代码与配置**（真机、mp 后台材料靠人工，列出但不代查）。逐项跑，输出一张 `项目 → 现状 → 判定(✅/❌/⚠️需真机) → 修法` 表，可修的配置项当场问用户是否修。

> 根因备忘：小程序 `project.config.json` 由微信开发者工具「新建项目」生成，默认 `minified:false`（JS 不压缩）、`es6:false`——**不是 bug 是默认值**，所以每个新项目都要过这一遍。本 skill 就是替代那个"没人改的默认值"。

## 前置

定位项目根（含 `project.config.json`）。读它的 `setting` 块 + `miniprogramRoot`。以下命令把 `$ROOT` 换成项目根，`$SRC` = `$ROOT/<miniprogramRoot>`。

## 检查项（逐条跑）

### 1. 代码压缩（devtools「代码质量→代码压缩」直接读这三个开关）

```bash
python3 -c "import json;s=json.load(open('$ROOT/project.config.json'))['setting'];print('minified(JS):',s.get('minified'));print('minifyWXML:',s.get('minifyWXML'));print('minifyWXSS:',s.get('minifyWXSS'))"
```
- 三者都应 `true`。任一 `false` → devtools 对应文件「未通过」。
- **修法**：Edit `project.config.json` 把对应项改 `true`。
- 说明给用户：`minified:true` 会让 devtools 也编译压缩后的 JS，报错栈略难读；但只要 `uploadWithSourceMap:true`（下面查）配 source map 就能调，生产包本来上传时也会压缩。要保 dev 期栈可读可临时关，上线前再开。

- ⚠️ **改 `minified:true` 前必须先做「压缩语法兼容」检查，否则上传/预览会炸 `Unexpected token: punc (.)`**。微信内置压缩器（老 uglify）**解析不了 ES2020 语法**（可选链 `?.`、空值合并 `??`、逻辑赋值 `||=`/`&&=`/`??=`、数字分隔符 `1_000`）。TS 项目若 `tsconfig.json` 的 `target ≥ ES2020`，这些语法会原样进 `.js`，压缩即失败。
  ```bash
  # a) 源码/tsconfig 层面
  grep -REn '\?\.|(\?\?)|(\|\|=)|(&&=)|(\?\?=)' "$SRC" --include='*.ts' --include='*.js' | grep -v node_modules | head
  ```
  - ⛔ **不要靠改 `tsconfig.json` 的 `target`**：实测（2026-07-25 连栽两次）devtools 的 TS 编译插件**不按项目 tsconfig 的 target 降级**，改 `ES2020→ES2019` 对 devtools 产出**无效**；用 `npx tsc` 验证是**假证据**（那是你自己的编译器，不是 devtools 的）。
  - ✅ **修法（compiler-agnostic，唯一可靠）= 把现代语法从源码删掉**：`x?.()` → `const f=x; typeof f==='function' ? f.call(...) : null`；`a ?? b` → `a || b`（值域安全时）或三元。**连注释里的 `?.`/`??` 字面量也去掉**（tsc 默认保留注释，会进 .js）。源码里没有，任何压缩器都无从保留。
  - ✅ **第二层防御**：`project.config.json` `setting.es6:true`（devtools babel 全量转 ES5，兜住未来误写 + 兼老机型）。
  - ⚠️ **验证必须走真实压缩路径，不是 dev 渲染**：`minified:true` 在 dev 预览**不压缩**（app 照常渲染、状态栏 `⊗ 0` 都会骗你），压缩只在**上传/预览**发生。先 `cli close --project`（释放 automation 锁，否则报 `错误 undefined code 10`，那不是 minify 错），再 `cli preview --project <path>`——打印 `✔ preview` + 体积表 + 出二维码才算真通过。

### 2. ES6→ES5 / 增强编译（老机型兼容）

```bash
python3 -c "import json;s=json.load(open('$ROOT/project.config.json'))['setting'];print('es6:',s.get('es6'),' enhance:',s.get('enhance'),' postcss:',s.get('postcss'))"
```
- 面向国内安卓/老机型建议 `es6:true`（转 ES5）、`enhance:true`、`postcss:true`（自动补前缀）。非硬性，⚠️ 提示 + 问是否开。

### 3. 合法域名白名单（最容易线上炸的一项）

```bash
# 提取代码里真实网络请求域名（排除 SVG xmlns / 注释里的 w3.org、weixin.qq.com 文档链接）
grep -rhoE "https://[a-zA-Z0-9._-]+" "$SRC" | sort -u | grep -viE "w3\.org|weixin\.qq\.com|example\."
python3 -c "import json;print('urlCheck:',json.load(open('$ROOT/project.config.json'))['setting'].get('urlCheck'))"
```
- `urlCheck:false` = devtools「不校验合法域名」开着 → dev 能跑但**真机/上线必须把上面每个域名加进 mp 后台『开发→开发管理→服务器域名』的 request/socket/uploadFile/downloadFile 白名单**，否则真机所有请求失败。
- 输出：把提取到的域名列给用户，标「⚠️ 需在 mp 后台白名单确认」（后台是人工，不代填）。

### 4. 包体积（主包 ≤2MB，总 ≤20MB，超了传不上去）

```bash
du -sh "$SRC" 2>/dev/null
find "$SRC" -type f \( -name '*.png' -o -name '*.jpg' -o -name '*.jpeg' -o -name '*.gif' \) -size +100k -exec ls -lh {} \; 2>/dev/null | awk '{print $5, $9}'
```
- 源码目录体积仅参考（真实以 devtools「上传」弹窗显示为准，压缩后更小）。>100KB 的图片列出——大图优先转 WebP / 走 CDN / 分包。
- 无分包且主包逼近 2MB → 建议分包（`subpackages`）。

### 5. SafeArea / 自定义导航（本类项目老坑）

```bash
grep -rn "env(safe-area-inset" "$SRC" || echo "无 env(safe-area) 用法"
grep -rn "statusBarHeight\|getWindowInfo\|safeArea" "$SRC" | head
```
- **`env(safe-area-inset-*)` 在小程序多机型返 0，不可靠**。顶部安全区应用 `wx.getWindowInfo().statusBarHeight`，底部（home 指示条）用 `screenHeight - safeArea.bottom`。
- 命中 `env(safe-area` 且 `navigationStyle:custom` → ❌ 提示改 JS 方案。都用 statusBarHeight → ✅。

### 6. appid 非测试号

```bash
grep -n '"appid"' "$ROOT/project.config.json" "$ROOT/project.private.config.json" 2>/dev/null
```
- 不能是 `touristappid` 或测试 appid。⚠️ 让用户确认是正式 appid。

### 7. sourcemap 上传（线上报错可定位）

```bash
python3 -c "import json;print('uploadWithSourceMap:',json.load(open('$ROOT/project.config.json'))['setting'].get('uploadWithSourceMap'))"
```
- 建议 `true`（生产报错能还原栈）。

### 8. 调试残留（可选清理）

```bash
grep -rn "console\.\(log\|debug\)\|debugger" "$SRC" | grep -v "console.warn\|console.error" | wc -l
```
- 数量报给用户，问是否清理（warn/error 保留）。

### 9. 只能真机验的（列出，不代验）

devtools ≠ 真机，以下每个若项目里有，标「⚠️ 需真机」：
- 自定义 tabBar（`tabBar.custom:true`）：真机渲染 / 安全区 / 切换态。
- 相册：`saveImageToPhotosAlbum` 授权弹窗（scope.writePhotosAlbum）。
- 支付：`requestPayment` 调起（devtools 不走真机调起校验）。
- 转发/分享图：`showShareImageMenu` / 转发卡片。
- 定位 / 摄像头 / 录音等需授权能力。

## 输出

一张表：`# | 检查项 | 现状 | 判定 | 修法`。判定用 ✅通过 / ❌需修 / ⚠️需真机或人工确认。
- 所有 ❌ 的**可自动修配置项**（1/2/7）：批量列出「预期修改」，用户一次确认后 Edit `project.config.json`。
- ⚠️ 项（域名白名单、appid、真机验证）：列清单，说明为何模型不能代做 + 具体步骤。
- 结尾一句总结：`N 项通过 / M 项需修 / K 项需真机确认`。

## 不做

- 不改 mp 后台配置（域名白名单、类目、隐私协议）——那是人工。
- 不代替真机验证。
- 不动源码逻辑（只动 project.config.json 配置项，且经用户确认）。
