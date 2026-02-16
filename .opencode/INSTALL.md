# Installing Cookit for OpenCode

Enable Cookit skills in OpenCode via native skill discovery.

## Prerequisites

- OpenCode
- Git

## Installation (macOS/Linux)

1. Clone or update the repository:

```bash
if [ -d ~/.config/opencode/cookit/.git ]; then
  git -C ~/.config/opencode/cookit pull --ff-only
else
  git clone https://github.com/n0rvyn/cookit.git ~/.config/opencode/cookit
fi
```

2. Create skill and command source links:

```bash
mkdir -p ~/.config/opencode/skills
mkdir -p ~/.config/opencode/commands
ln -sfn ~/.config/opencode/cookit/ios-development/skills ~/.config/opencode/skills/cookit-ios-development
ln -sfn ~/.config/opencode/cookit/mactools/skills ~/.config/opencode/skills/cookit-mactools
ln -sfn ~/.config/opencode/cookit/ios-development/commands ~/.config/opencode/commands/cookit-ios-development
```

3. Restart OpenCode.

## Verify

```bash
ls -la ~/.config/opencode/skills/cookit-ios-development
ls -la ~/.config/opencode/skills/cookit-mactools
ls -la ~/.config/opencode/commands/cookit-ios-development
```

## Updating

```bash
git -C ~/.config/opencode/cookit pull --ff-only
```

If new skills or commands were added in the repo, re-run the symlink commands once.

## Uninstall

```bash
rm ~/.config/opencode/skills/cookit-ios-development
rm ~/.config/opencode/skills/cookit-mactools
rm ~/.config/opencode/commands/cookit-ios-development
```
