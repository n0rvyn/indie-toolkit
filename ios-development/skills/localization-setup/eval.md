# localization-setup Eval

## Trigger Tests
<!-- Prompts that SHOULD trigger this skill -->
- "Set up localization for my iOS project"
- "How do I add Chinese localization?"
- "Configure String Catalogs for my app"
- "设置多语言支持"
- "How do I handle pluralization in localization?"

## Negative Trigger Tests
<!-- Prompts that should NOT trigger this skill -->
- "Review my code"
- "Write a plan"
- "Fix this bug"

## Output Assertions
<!-- What must be true in the skill's output -->
- [ ] Output identifies localization need (initial setup / new language / String Catalogs / pluralization / validation)
- [ ] Output reads relevant section from localization-guide.md based on need mapping
- [ ] Initial setup: shows .xcstrings creation and structure explanation
- [ ] String management: demonstrates String(localized:) best practices
- [ ] Pluralization: explains pluralization rules and variable handling
- [ ] Output provides interactive guidance rather than static documentation dump

## Redundancy Risk
Baseline comparison: Base model can explain localization concepts but lacks structured reference-based interactive guidance
Last tested model: Opus 4.6
Last tested date: 2026-03-08
Verdict: essential
