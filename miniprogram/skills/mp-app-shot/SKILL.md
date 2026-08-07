---
name: mp-app-shot
model: sonnet
description: "Use when you need to VISUALLY verify a running WeChat mini program (微信小程序) from the CLI — headless, WITHOUT stealing focus or touching the devtools GUI: screenshot any route, read back the page's real `data`, measure element geometry, and drive unreachable branches by temporary code injection. Covers the edit → recompile-wait → screenshot → assert loop, plus the capsule-button (胶囊按钮) safe-area check that screenshots structurally cannot show. Triggers: '截图验证小程序', '看一下小程序界面', 'screenshot the mini program', '验证小程序渲染', '小程序 UI 对不对', '空态/骨架/降级分支长什么样', 'verify the mini program UI'. NOT for: macOS/iOS apps (use mac-app-shot / swiftui-visual-audit), web pages (use a browser tool), pre-submission config checks (use mp-submit-preview), or logic-only tests (they never show layout)."
---

## What this is

A **headless** loop for verifying a running mini program's actual rendered UI and its real `data`.
It needs the WeChat devtools **running**, but never needs it focused, foregrounded, or clicked —
so it doesn't interrupt whatever the user is doing.

Core moves: (1) enable the automation port, (2) `reLaunch` a route, (3) **screenshot AND read
`page.data()`** — the pixel and the view model together, (4) measure geometry via
`boundingClientRect` when a screenshot can't settle the question, (5) inject-and-revert to reach
branches real data can't produce.

Catches the bug class that green tests + `BUILD SUCCEEDED` structurally cannot: an element
anchored to the document instead of the viewport, content sitting under the capsule button,
a branch that renders its default because a `data` flag has no consumer, a chart bar that shows
missing data as the best result.

## Prerequisites

- WeChat devtools installed; the project opened at least once.
- `miniprogram-automator` in the project (`npm i -D miniprogram-automator`).
- Automation must be enabled in devtools settings (安全设置 → CLI/HTTP 调用).

## 0. The two helper scripts (and where they live)

Both ship with this plugin. Bind them once per session — every later block uses `$SHOOT` / `$MEASURE`:

```bash
SHOOT="${CLAUDE_PLUGIN_ROOT}/skills/mp-app-shot/scripts/shoot.js"
MEASURE="${CLAUDE_PLUGIN_ROOT}/skills/mp-app-shot/scripts/measure.js"

node "$SHOOT"   <projectDir> <route> <outName> [waitMs]   # screenshot + page.data() in one pass
node "$MEASURE" <projectDir> <route> <selector...>        # boundingClientRect, viewport-relative
```

Both require the **absolute project directory** as argv[1] — they resolve
`miniprogram-automator` out of that project's `node_modules`, not their own. Calling them with
fewer args exits 2 with a usage line rather than doing anything.

The inline JS in §2 and §3 is the same thing spelled out; use the scripts for the routine loop
and the inline form when you need to change what gets asserted.

## 1. Enable the automation port (does NOT need focus)

```bash
CLI=/Applications/wechatwebdevtools.app/Contents/MacOS/cli
"$CLI" auto --project "$PWD" --auto-port 9420
```

Run it in the background if it blocks:
`( "$CLI" auto --project "$PWD" --auto-port 9420 > /tmp/auto.log 2>&1 & ); sleep 35`

## 2. Shoot + read the view model in one pass

```js
const automator = require('<abs>/node_modules/miniprogram-automator');
const mp = await automator.connect({ wsEndpoint: 'ws://127.0.0.1:9420' });
mp.on('console',   m => console.log('[console]', m.type, (m.args||[]).map(a=>String(a&&a.value!==undefined?a.value:a)).join(' ')));
mp.on('exception', e => console.log('[EXCEPTION]', e.message));

await mp.reLaunch('/pages/index/index');
await new Promise(r => setTimeout(r, 8000));          // 等网络请求回来
const page = await mp.currentPage();
console.log(await page.data());                        // ← 断言视图模型，不只看图
await mp.screenshot({ path: '.claude/shots/root.png' });
await mp.disconnect();
```

**Always print `page.data()` next to the screenshot.** The pixel tells you it looks right; the
data tells you *why*. When they disagree, you've found something.

## 3. Measure geometry when a screenshot can't decide

`boundingClientRect` is **viewport-relative**, so it settles "is this pinned to the viewport or
to the document?" without any scrolling:

```js
const m = await mp.evaluate(() => new Promise(res => {
  wx.createSelectorQuery()
    .select('.masthead').boundingClientRect()
    .selectViewport().scrollOffset()
    .exec(r => res({ bottom: r[0].bottom, scrollHeight: r[1].scrollHeight }));
}));
```

Document 1248 tall, viewport 844: viewport-anchored reads `bottom≈820`, document-anchored reads
`bottom≈1224`. **A/B it** — flip the one CSS property, re-measure, compare the two numbers. That
is a real proof; two screenshots that "look the same" are not.

## 4. Reach branches real data can't produce

Empty states, degraded charts, error screens: patch the page `.ts` to force the state, shoot,
then restore from a pristine copy.

```bash
cp path/page.ts /tmp/page.pristine
python3 -c "...patch with a '// TEMP-PROBE' marker..."
sleep 12 && node "$SHOOT" "$PWD" /pages/index/index empty-state
cp /tmp/page.pristine path/page.ts
grep -rn 'TEMP-PROBE' miniprogram && echo LEAK || echo clean
diff -q /tmp/page.pristine path/page.ts && echo "byte-identical"
```

Marker + `diff -q` + `git diff --stat` is the whole discipline. Never leave a `?state=` debug
switch in production code just to make this easier.

## Hard rules — every one of these cost real time

- **Wait ~12s after editing before you screenshot.** Devtools self-compiles, but not instantly.
  Screenshot too early and you capture the **previous bundle** — which looks exactly like a bug
  in your new code. *(Do NOT `cli close` + `cli open` + `cli cache clean` to "fix" it: devtools
  compiles on its own, that sequence wastes minutes and changes nothing. If a stale bundle
  persists past ~15s, the real cause is usually a **compile error** — devtools keeps serving the
  last good bundle while showing red. Read `mp.on('console')` / `mp.on('exception')` first.)*
- **Screenshots do not include the capsule button (胶囊按钮).** Under
  `navigationStyle: "custom"` WeChat still draws 「···」+「⊙」 at top-right, and the devtools
  screenshot omits it — so content sitting *under* it looks perfectly fine in every image.
  Check it numerically, every time:
  ```js
  const cap = await mp.evaluate(() => wx.getMenuButtonBoundingClientRect());
  // content top must be >= cap.bottom; nothing may sit in x ∈ [cap.left, cap.right]
  ```
  Correct top inset = `cap.bottom + (cap.top - statusBarHeight)`, **not** `statusBarHeight + N`.
- **md5 your screenshots before citing them as evidence.**
  `md5 -q shots/*.png | sort | uniq -d` must be empty. Two "different states" that are the same
  file means one capture didn't happen — a false proof is worse than no proof.
- **`pageScrollTo` may silently no-op** (observed: `scrollTop` stays 0 through automator). Verify
  it moved (`selectViewport().scrollOffset()`) before believing a scroll-based conclusion; if it
  won't move, use the §3 A/B measurement instead.
- **A flex child with `height:` still shrinks.** Padding a page to make it scrollable needs
  `flex-shrink: 0`, or the filler collapses and the page never scrolls.
- **Session/openid differs from your `curl` session.** The devtools has its own `wx.login`
  openid. To flip a server-side preference *for the page you're looking at*, read the app's own
  token: `await mp.evaluate(() => wx.getStorageSync('<session-key>'))` and use **that**.
- **Racing the first frame rarely works.** To capture a skeleton/loading state, don't try to
  screenshot fast — inject an early `return` into the fetch and capture deterministically.

## Reporting

Cite each claim with the artifact that supports it: a filename **and** the `data` readout, or a
measured number. "It renders correctly" without one of those is not a verification.
