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
ln -sfn ~/.codex/indie-toolkit/ios-development/skills ~/.codex/skills/indie-toolkit-ios-development
ln -sfn ~/.codex/indie-toolkit/mactools/skills ~/.codex/skills/indie-toolkit-mactools
ln -sfn ~/.codex/indie-toolkit/product-lens/skills ~/.codex/skills/indie-toolkit-product-lens
ln -sfn ~/.codex/indie-toolkit/skill-audit/skills ~/.codex/skills/indie-toolkit-skill-audit
```

3. Restart Codex.

## Verify

```bash
ls -la ~/.codex/skills/indie-toolkit-dev-workflow
ls -la ~/.codex/skills/indie-toolkit-ios-development
ls -la ~/.codex/skills/indie-toolkit-mactools
ls -la ~/.codex/skills/indie-toolkit-product-lens
ls -la ~/.codex/skills/indie-toolkit-skill-audit

find ~/.codex/skills/indie-toolkit-dev-workflow -name SKILL.md | wc -l
find ~/.codex/skills/indie-toolkit-ios-development -name SKILL.md | wc -l
find ~/.codex/skills/indie-toolkit-mactools -name SKILL.md | wc -l
find ~/.codex/skills/indie-toolkit-product-lens -name SKILL.md | wc -l
find ~/.codex/skills/indie-toolkit-skill-audit -name SKILL.md | wc -l
```

## Updating

```bash
git -C ~/.codex/indie-toolkit pull --ff-only
```

If new skills were added in the repo, re-run the symlink commands once.

## Uninstall

```bash
rm ~/.codex/skills/indie-toolkit-dev-workflow
rm ~/.codex/skills/indie-toolkit-ios-development
rm ~/.codex/skills/indie-toolkit-mactools
rm ~/.codex/skills/indie-toolkit-product-lens
rm ~/.codex/skills/indie-toolkit-skill-audit
```

## Notes

- Codex directly loads `skills/`; `agents/` and `hooks/` are plugin internals and are not linked directly.
- `rag-server` is not a Codex skill folder. It is a separate MCP server component; see `rag-server/README.md`.
