---
type: regex
target: {source: file, path: app/client.py}
match: not_contains
weight: 0.5
---
\.get\(\s*[\"']timeout[\"']\s*,
