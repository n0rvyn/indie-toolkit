# miniprogram

WeChat mini program (微信小程序) development QA for Claude Code.

Two things that a green test suite and a successful compile structurally cannot tell you:
what the running app actually renders, and whether the thing you are about to upload will
survive review.

## Skills

| Skill | Use it when |
|---|---|
| `mp-app-shot` | You need to *see* a running mini program from the CLI — headless, without stealing focus or touching the devtools GUI. Screenshot any route, read the page's real `data` back, measure element geometry, and drive branches real data can't produce by temporary code injection. |
| `mp-submit-preview` | Before uploading. Checks `project.config.json` compression/compatibility settings, the request-domain allowlist, package size, SafeArea handling, and the items that only a real device can settle. |

## Why these two are one plugin

They are the two halves of "is this shippable": `mp-app-shot` answers *does it render right*,
`mp-submit-preview` answers *will it pass*. Both need the WeChat devtools toolchain and neither
is useful outside a mini program project, so they gate together.

## Requirements

- WeChat devtools installed, project opened at least once.
- `miniprogram-automator` in the project under test (`npm i -D miniprogram-automator`).
- Automation enabled in devtools (安全设置 → CLI/HTTP 调用) — `mp-app-shot` only.

## Helper scripts

`mp-app-shot` ships `scripts/shoot.js` and `scripts/measure.js`. Both take the **absolute project
directory** as their first argument: they resolve `miniprogram-automator` from the project under
test, not from the plugin. Paths are `${CLAUDE_PLUGIN_ROOT}/skills/mp-app-shot/scripts/…`.

## Not this plugin

- macOS / iOS apps → `apple-dev` (`mac-app-shot`, `swiftui-visual-audit`).
- Web pages → a browser tool.
- WeChat *messaging* / login bridge → `wechat-bridge` (an MCP server, unrelated to mini program dev).
