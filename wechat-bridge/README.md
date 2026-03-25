# wechat-bridge

Claude Code plugin that bridges WeChat messages to Claude Code sessions via the MCP `--channels` protocol (development preview).

## Features

- **Permission relay**: Approve or deny Claude Code tool requests from WeChat
- **Push messages**: Send messages from WeChat into your Claude Code session
- **Reply**: Claude can send messages back to your WeChat
- **QR scan login**: Authenticate with WeChat via QR code

## Quick Start

### 1. Install

Install from the indie-toolkit marketplace:

```bash
claude mcp add-from-marketplace indie-toolkit wechat-bridge
```

Or, for local development:

```bash
cd wechat-bridge
npm install
npm run build
```

### 2. Login

WeChat authentication is required before running the channel. Use the `/wechat-login` skill or run manually:

```bash
node dist/login-cli.js login
```

Scan the QR code with your WeChat app. Credentials are saved to `~/.adam/wechat/`.

### 3. Run with Claude Code

The `--channels` protocol is a development preview and requires the development flag:

```bash
claude --dangerously-load-development-channels plugin:wechat-bridge@indie-toolkit
```

## Permission Relay

When Claude Code needs tool approval, you receive a WeChat message:

```
🔐 Claude wants to: Bash
List files in directory
Preview: {"command": "ls -la"}

Reply 'yes abcde' or 'no abcde'
```

Reply with the request ID to approve or deny. Chinese replies also work: `是 abcde` / `否 abcde`.

If you don't respond within the timeout (default 120s), the request is auto-denied.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WECHAT_API_BASE_URL` | `https://ilinkai.weixin.qq.com` | iLink Bot API base URL |
| `WECHAT_CHANNEL_ID` | `default` | Channel ID for multi-account setups |
| `WECHAT_ROUTE_TAG` | (none) | SKRouteTag header for API routing |
| `WECHAT_PERMISSION_TIMEOUT_MS` | `120000` | Permission request timeout in ms |

### CLI Flags

```bash
node dist/login-cli.js login [--api-base-url URL] [--channel-id ID] [--route-tag TAG]
```

### Token Storage

Credentials and sync state are stored in `~/.adam/wechat/`:
- `<channel-id>.json` — bot token, account ID, user ID
- `<channel-id>.sync` — getUpdates long-poll state

Delete these files to force re-login.

## Architecture

```
Claude Code (--dangerously-load-development-channels plugin:wechat-bridge@indie-toolkit)
    ↕ MCP stdio (JSON-RPC)
wechat-bridge MCP Channel Server
    ↕ iLink Bot HTTP API (long-poll)
WeChat (your phone)
```

The MCP server declares `claude/channel` and `claude/channel/permission` experimental capabilities. A protocol adapter layer (`protocol.ts`) wraps the experimental notification names, so future API changes only require updating one module.

## Troubleshooting

**"No WeChat session found"**
Run `node dist/login-cli.js login` first.

**QR code expired**
The login flow auto-refreshes the QR code up to 3 times. If it still expires, restart the login command.

**Permission requests not arriving**
Check that Claude Code was started with `--dangerously-load-development-channels plugin:wechat-bridge@indie-toolkit` and that your WeChat session is active.

**Messages not being received**
The getUpdates long-poll has a ~35s cycle. Messages may take up to 35 seconds to arrive. Check stderr output for API errors.

## Note

The `--channels` protocol is a Claude Code **development preview** feature gated behind `--dangerously-load-development-channels`. The API may change in future versions. This plugin uses a protocol adapter layer (`protocol.ts`) to minimize the impact of breaking changes.
