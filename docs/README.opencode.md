# Cookit for OpenCode

This repo is a Claude marketplace repo, but OpenCode can use all skills here.

OpenCode installs skills by GitHub path (folders containing `SKILL.md`).

## Install One Skill

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo n0rvyn/cookit \
  --path ios-development/skills/testing-guide
```

## Install All iOS Skills

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo n0rvyn/cookit \
  --path ios-development/skills/testing-guide \
  --path ios-development/skills/swiftdata-patterns \
  --path ios-development/skills/localization-setup \
  --path ios-development/skills/validate-design-tokens \
  --path ios-development/skills/generate-design-system
```

## Install All mactools Skills

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo n0rvyn/cookit \
  --path mactools/skills/calendar \
  --path mactools/skills/contacts \
  --path mactools/skills/mail \
  --path mactools/skills/notes \
  --path mactools/skills/ocr \
  --path mactools/skills/omnifocus \
  --path mactools/skills/photos \
  --path mactools/skills/reminders \
  --path mactools/skills/safari \
  --path mactools/skills/spotlight
```

## Verify

1. Restart OpenCode after installation.
2. Ask a task that should trigger one installed skill.
3. If it does not trigger, verify the path and ensure the target folder has `SKILL.md`.
