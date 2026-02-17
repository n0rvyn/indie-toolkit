# Installing Cookit for Codex

Enable Cookit skills in Codex via native skill discovery.

## Prerequisites

- Codex CLI
- Git

## Installation (macOS/Linux)

1. Clone or update the repository:

```bash
if [ -d ~/.codex/cookit/.git ]; then
  git -C ~/.codex/cookit pull --ff-only
else
  git clone https://github.com/n0rvyn/cookit.git ~/.codex/cookit
fi
```

2. Create skill source links:

```bash
mkdir -p ~/.codex/skills
ln -sfn ~/.codex/cookit/ios-development/skills ~/.codex/skills/cookit-ios-development
ln -sfn ~/.codex/cookit/mactools/skills ~/.codex/skills/cookit-mactools
```

3. (Optional) Expose iOS command docs as Codex skills.

Codex skill discovery expects `~/.codex/skills/<skill-name>/SKILL.md`.
The markdown files in `ios-development/commands/` are not discoverable as-is, so wrap each command doc as a skill:

```bash
mkdir -p ~/.codex/skills/cookit-ios-commands
for f in ~/.codex/cookit/ios-development/commands/*.md; do
  name="$(basename "$f" .md)"
  mkdir -p "~/.codex/skills/cookit-ios-commands/$name"
  cp -f "$f" "~/.codex/skills/cookit-ios-commands/$name/SKILL.md"
done
```

4. Restart Codex.

## Verify

```bash
ls -la ~/.codex/skills/cookit-ios-development
ls -la ~/.codex/skills/cookit-mactools
find ~/.codex/skills/cookit-ios-commands -maxdepth 2 -name SKILL.md -print
```

## Updating

```bash
git -C ~/.codex/cookit pull --ff-only
```

If new skills were added in the repo, re-run the symlink commands once.
If new command docs were added/changed, re-run the wrapping loop once.

## Uninstall

```bash
rm ~/.codex/skills/cookit-ios-development
rm ~/.codex/skills/cookit-mactools
rm -rf ~/.codex/skills/cookit-ios-commands
```
