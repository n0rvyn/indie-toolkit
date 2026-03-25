# indie-toolkit

Multi-plugin monorepo for Claude Code plugins, published to the `indie-toolkit` marketplace.

## Plugin-specific Build Rules

### wechat-bridge

- Uses **esbuild bundle** (not plain tsc output). The MCP server runs in the plugin cache where `node_modules` doesn't exist; all dependencies must be inlined into the dist files.
- Build: `npm run build` = `tsc --noEmit` (type check only) + `esbuild` (bundle to `dist/`).
- Release artifacts in `dist/` must be self-contained single files. If a new dependency is added, verify it gets bundled — `--packages=external` is NOT used.
