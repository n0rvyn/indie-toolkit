# Cookit Marketplace for Claude Code

Curated Claude Code plugin marketplace with two plugins:

- `ios-development`: iOS/macOS/iPadOS development workflow
- `mactools`: macOS productivity and automation tools

## Installation

Add this marketplace in Claude Code:

```bash
/plugin marketplace add n0rvyn/cookit
```

Then install a plugin from this marketplace:

```bash
/plugin install ios-development@cookit-marketplace
/plugin install mactools@cookit-marketplace
```

## Available Plugins

### ios-development

Complete iOS/macOS/iPadOS workflow plugin for Claude Code.

What you get:

- Project kickoff and implementation review commands
- Design system generation workflow
- SwiftData, testing, localization guidance
- App Store Connect and CI/CD support

Install:

```bash
/plugin install ios-development@cookit-marketplace
```

### mactools

macOS automation toolkit plugin for Apple apps and local workflows.

What you get:

- Calendar, Reminders, Notes, Contacts, Mail, Safari operations
- Spotlight-based local file search and extraction
- OCR for images and scanned PDFs
- OmniFocus task workflows

Install:

```bash
/plugin install mactools@cookit-marketplace
```

## Repository Structure

```text
cookit/
├── .claude-plugin/
│   └── marketplace.json
├── ios-development/
│   ├── .claude-plugin/plugin.json
│   ├── commands/
│   ├── skills/
│   ├── references/
│   └── templates/
├── mactools/
│   ├── .claude-plugin/plugin.json
│   └── skills/
└── README.md
```

## Metadata

- Marketplace name: `cookit-marketplace`
- Version: `1.0.0`
- Owner: `Norvyn`
