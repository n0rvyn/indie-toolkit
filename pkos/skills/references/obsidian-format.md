# Obsidian Format Reference for PKOS

## Wikilinks

Use `[[wikilinks]]` for all internal vault references. This enables Obsidian's graph view, backlinks, and automatic rename tracking.

### Rules
- Note-to-note: `[[note-title]]` (no path prefix, no `.md` extension)
- Display text: `[[note-title|display text]]`
- Section link: `[[note-title#Section Heading]]`
- Link to MOC: `[[MOC-{topic}]]`
- External URLs: standard markdown `[text](url)` — never wikilink

### When to Add Wikilinks
- `related:` frontmatter entries → also add inline `[[wikilink]]` in body where contextually relevant
- Person mentions → `[[person-name]]` if a page exists in `40-People/`
- Topic references that have a MOC → `[[MOC-{topic}]]`
- Source notes referencing other source notes → `[[source-note-title]]`

## Callouts

Use Obsidian callouts for structured highlights within note body:

```
> [!insight] Key Takeaway
> The main insight from this source.

> [!question] Open Question
> Something that needs further exploration.

> [!warning] Contradiction
> Conflicts with [[other-note]] on point X.

> [!example] Example
> Concrete example illustrating the point.
```

Type usage:
- `insight` — primary takeaway from a source (intel-sync, inbox)
- `question` — open questions for serendipity/review to pick up
- `warning` — contradictions or caveats
- `example` — concrete examples
- `tip` — actionable advice
- `abstract` — summary/abstract of a longer piece

## Properties (Frontmatter)

Standard PKOS frontmatter fields (unchanged):
```yaml
---
type: knowledge | idea | reference | moc | digest | review
source: reminder | note | voice_memo | domain-intel | web | manual
created: YYYY-MM-DD
tags: [tag1, tag2]
quality: 0-5
citations: 0+
related: [path1, path2]
status: seed | growing | mature | needs-reconciliation
aliases: [alternative-title, 别名]
---
```

## Bases Compatibility

For notes to be queryable by Obsidian Bases (.base files):
- All filterable fields must be in YAML frontmatter (not inline)
- `tags` array enables: `file.hasTag("tag")` filter
- `created` date enables: temporal filters
- `quality` number enables: threshold filters
- `type` string enables: type-based views

## Body Structure

```markdown
# {Title}

> [!insight] Key Takeaway
> {One-sentence core insight, if applicable}

{Main content — preserve original voice, minimal editing}

## Connections

- Related: [[note-1]], [[note-2]]
- See also: [[MOC-topic]]
```

The `## Connections` section is optional. Only add when the note has meaningful cross-references beyond what `related:` frontmatter captures.

## Migration: Existing Vault Notes

Existing notes use `topics:` in frontmatter. Run this one-time migration:
```bash
find ~/Obsidian/PKOS -name "*.md" -exec grep -l "^topics:" {} \; | while read f; do
  sed -i '' 's/^topics:/tags:/' "$f"
done
```
