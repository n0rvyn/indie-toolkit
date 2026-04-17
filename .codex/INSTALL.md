# Installing Indie Toolkit for Codex

Enable Indie Toolkit skills in Codex via native skill discovery.

## Prerequisites

- Codex CLI
- Git

## Installation (macOS/Linux)

1. Clone or update the repository:

```bash
if [ -d ~/.codex/indie-toolkit/.git ]; then
  git -C ~/.codex/indie-toolkit pull --ff-only
else
  git clone https://github.com/n0rvyn/indie-toolkit.git ~/.codex/indie-toolkit
fi
```

2. Create skill source links:

```bash
mkdir -p ~/.codex/skills
ln -sfn ~/.codex/indie-toolkit/dev-workflow/skills ~/.codex/skills/indie-toolkit-dev-workflow
ln -sfn ~/.codex/indie-toolkit/apple-dev/skills ~/.codex/skills/indie-toolkit-apple-dev
ln -sfn ~/.codex/indie-toolkit/mactools/skills ~/.codex/skills/indie-toolkit-mactools
ln -sfn ~/.codex/indie-toolkit/product-lens/skills ~/.codex/skills/indie-toolkit-product-lens
ln -sfn ~/.codex/indie-toolkit/skill-master/skills ~/.codex/skills/indie-toolkit-skill-master
ln -sfn ~/.codex/indie-toolkit/skill-audit/skills ~/.codex/skills/indie-toolkit-skill-audit
ln -sfn ~/.codex/indie-toolkit/domain-intel/skills ~/.codex/skills/indie-toolkit-domain-intel
ln -sfn ~/.codex/indie-toolkit/session-reflect/skills ~/.codex/skills/indie-toolkit-session-reflect
ln -sfn ~/.codex/indie-toolkit/youtube-scout/skills ~/.codex/skills/indie-toolkit-youtube-scout
ln -sfn ~/.codex/indie-toolkit/pkos/skills ~/.codex/skills/indie-toolkit-pkos
ln -sfn ~/.codex/indie-toolkit/wechat-bridge/skills ~/.codex/skills/indie-toolkit-wechat-bridge
ln -sfn ~/.codex/indie-toolkit/health-insights/skills ~/.codex/skills/indie-toolkit-health-insights
ln -sfn ~/.codex/indie-toolkit/minimax-quota/skills ~/.codex/skills/indie-toolkit-minimax-quota
ln -sfn ~/.codex/indie-toolkit/netease-cloud-music/skills ~/.codex/skills/indie-toolkit-netease-cloud-music
```

3. Restart Codex.

## Verify

```bash
ls -la ~/.codex/skills/indie-toolkit-dev-workflow
ls -la ~/.codex/skills/indie-toolkit-apple-dev
ls -la ~/.codex/skills/indie-toolkit-mactools
ls -la ~/.codex/skills/indie-toolkit-product-lens
ls -la ~/.codex/skills/indie-toolkit-skill-master
ls -la ~/.codex/skills/indie-toolkit-skill-audit
ls -la ~/.codex/skills/indie-toolkit-domain-intel
ls -la ~/.codex/skills/indie-toolkit-session-reflect
ls -la ~/.codex/skills/indie-toolkit-youtube-scout
ls -la ~/.codex/skills/indie-toolkit-pkos
ls -la ~/.codex/skills/indie-toolkit-wechat-bridge
ls -la ~/.codex/skills/indie-toolkit-health-insights
ls -la ~/.codex/skills/indie-toolkit-minimax-quota
ls -la ~/.codex/skills/indie-toolkit-netease-cloud-music

find ~/.codex/skills/indie-toolkit-dev-workflow -name SKILL.md | wc -l
find ~/.codex/skills/indie-toolkit-apple-dev -name SKILL.md | wc -l
find ~/.codex/skills/indie-toolkit-mactools -name SKILL.md | wc -l
find ~/.codex/skills/indie-toolkit-product-lens -name SKILL.md | wc -l
find ~/.codex/skills/indie-toolkit-skill-master -name SKILL.md | wc -l
find ~/.codex/skills/indie-toolkit-skill-audit -name SKILL.md | wc -l
find ~/.codex/skills/indie-toolkit-domain-intel -name SKILL.md | wc -l
find ~/.codex/skills/indie-toolkit-session-reflect -name SKILL.md | wc -l
find ~/.codex/skills/indie-toolkit-youtube-scout -name SKILL.md | wc -l
find ~/.codex/skills/indie-toolkit-pkos -name SKILL.md | wc -l
find ~/.codex/skills/indie-toolkit-wechat-bridge -name SKILL.md | wc -l
find ~/.codex/skills/indie-toolkit-health-insights -name SKILL.md | wc -l
find ~/.codex/skills/indie-toolkit-minimax-quota -name SKILL.md | wc -l
find ~/.codex/skills/indie-toolkit-netease-cloud-music -name SKILL.md | wc -l
```

## Updating

```bash
git -C ~/.codex/indie-toolkit pull --ff-only
```

If new skills were added in the repo, re-run the symlink commands once.

## Uninstall

```bash
rm ~/.codex/skills/indie-toolkit-dev-workflow
rm ~/.codex/skills/indie-toolkit-apple-dev
rm ~/.codex/skills/indie-toolkit-mactools
rm ~/.codex/skills/indie-toolkit-product-lens
rm ~/.codex/skills/indie-toolkit-skill-master
rm ~/.codex/skills/indie-toolkit-skill-audit
rm ~/.codex/skills/indie-toolkit-domain-intel
rm ~/.codex/skills/indie-toolkit-session-reflect
rm ~/.codex/skills/indie-toolkit-youtube-scout
rm ~/.codex/skills/indie-toolkit-pkos
rm ~/.codex/skills/indie-toolkit-wechat-bridge
rm ~/.codex/skills/indie-toolkit-health-insights
rm ~/.codex/skills/indie-toolkit-minimax-quota
rm ~/.codex/skills/indie-toolkit-netease-cloud-music
```

## Notes

- Codex directly loads `skills/`; `agents/` and `hooks/` are plugin internals and are not linked directly.
- `x-api` does not expose a `skills/` folder, so there is no Codex symlink for it here. Install its MCP server separately if needed.
- `minimax-quota` uses `MINIMAX_API_KEY` (Bearer token) for the official OpenAPI endpoint.
- `netease-cloud-music` depends on a separately installed `ncmctl` binary.
