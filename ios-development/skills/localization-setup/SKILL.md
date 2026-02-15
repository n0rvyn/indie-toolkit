---
name: localization-setup
description: Provide localization workflow and setup guidance
---

# Localization Setup Skill

Provide interactive guidance on iOS localization based on `references/localization-guide.md`.

## When to Use

- Setting up localization for new project
- Adding new language support
- Questions about String Catalogs
- Pluralization or variable handling
- Localization validation

## Process

### 1. Identify Localization Need

Determine what the user needs:
- Initial localization setup
- Adding new languages
- String management best practices
- Pluralization handling
- Localization testing

### 2. Read Reference Guide

Read `references/localization-guide.md` section corresponding to the user's need.

### 3. Provide Contextual Guidance

Based on user's specific scenario:

**For Initial Setup**:
- Show .xcstrings creation from guide Section 1
- Explain String Catalog structure
- Demonstrate language addition

**For String Management**:
- Show String(localized:) usage from guide Section 2
- Explain table parameter for module organization
- Demonstrate comment usage for context

**For Pluralization**:
- Show pluralization patterns from guide Section 3
- Explain ^[count](inflect: true) syntax
- Handle language-specific plural rules

**For Organization**:
- Show recommended file structure from guide Section 4
- Explain naming conventions
- Demonstrate reuse strategies

**For Validation**:
- Show preview techniques from guide Section 5
- Explain pseudolocalization
- Demonstrate simulator testing

### 4. Provide Examples

Extract relevant localization patterns from the guide:
- String(localized:) examples
- .xcstrings structure
- Module organization
- Pluralization patterns

### 5. Common Localization Issues

- Hardcoded strings in code
- Not using table parameter
- Missing translations
- Text truncation in some languages
- Not handling RTL languages
- Hardcoded date/number formats

## Success Criteria

- All UI text is localizable
- Strings are organized by module
- Pluralization works correctly
- User can test in different languages
- Common pitfalls are avoided
