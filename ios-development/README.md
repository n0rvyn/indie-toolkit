# iOS Development Plugin

Complete iOS/macOS/iPadOS development workflow plugin for Claude Code.

For Codex/OpenCode, install individual skills from `ios-development/skills/*` using GitHub paths.

## Features

- **Design Token System**: Generate Apple HIG-compliant Design System code
- **Complete Workflow**: From project kickoff to App Store Connect submission
- **Code Review**: Design review, UI review, execution review
- **Best Practices**: SwiftData, Testing, Localization guides
- **CI/CD**: Fastlane + GitHub Actions for TestFlight uploads

## Commands

- `/project-kickoff` - Initialize new iOS project
- `/generate-design-system` - Generate DesignSystem.swift
- `/execution-review` - Verify implementation matches plan
- `/design-review` - Design quality review
- `/ui-review` - UI/UX compliance check
- `/appstoreconnect-review` - App Store Connect submission guide
- `/setup-ci-cd` - Configure Fastlane + GitHub Actions

## Installation

```bash
/plugin install ios-development@cookit-marketplace
```

Codex install examples:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo n0rvyn/cookit \
  --path ios-development/skills/testing-guide
```

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo n0rvyn/cookit \
  --path ios-development/skills/testing-guide \
  --path ios-development/skills/swiftdata-patterns \
  --path ios-development/skills/localization-setup \
  --path ios-development/skills/validate-design-tokens \
  --path ios-development/skills/generate-design-system
```

OpenCode install examples:

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo n0rvyn/cookit \
  --path ios-development/skills/testing-guide
```

```bash
python3 ~/.codex/skills/.system/skill-installer/scripts/install-skill-from-github.py \
  --repo n0rvyn/cookit \
  --path ios-development/skills/testing-guide \
  --path ios-development/skills/swiftdata-patterns \
  --path ios-development/skills/localization-setup \
  --path ios-development/skills/validate-design-tokens \
  --path ios-development/skills/generate-design-system
```

## Usage

See individual command help with `/<command> --help`
