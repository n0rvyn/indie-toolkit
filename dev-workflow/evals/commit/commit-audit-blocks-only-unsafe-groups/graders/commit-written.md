---
type: regex
target: {source: file, path: .git/logs/HEAD}
pattern: 'commit: (?:feat|fix)\(dev-workflow\)!:'
flags: m
---
