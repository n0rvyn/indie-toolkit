---
type: regex
target: {source: file, path: .git/logs/HEAD}
pattern: 'commit: (?:feat|fix)\([^)]+\):'
flags: m
---
