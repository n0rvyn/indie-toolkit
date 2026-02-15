# Cookit for Codex

This repo is a Claude marketplace repo, but Codex can use all skills here.

Codex installs skills by GitHub path (folders containing `SKILL.md`).

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
  ios-development/skills/swiftdata-patterns \
  ios-development/skills/localization-setup \
  ios-development/skills/validate-design-tokens \
  ios-development/skills/generate-design-system
```

## Install All mactools Skills

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo n0rvyn/cookit \
  --path mactools/skills/calendar \
  mactools/skills/contacts \
  mactools/skills/mail \
  mactools/skills/notes \
  mactools/skills/ocr \
  mactools/skills/omnifocus \
  mactools/skills/photos \
  mactools/skills/reminders \
  mactools/skills/safari \
  mactools/skills/spotlight
```

## Verify

1. Restart Codex after installation.
2. Ask a task that should trigger one installed skill.
3. If it does not trigger, verify the path and ensure the target folder has `SKILL.md`.
