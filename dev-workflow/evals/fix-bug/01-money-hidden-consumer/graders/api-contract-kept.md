---
type: regex
target: {source: file, path: shop/models.py}
match: contains
weight: 0.5
---
[\"']total[\"']\s*:\s*self\.total_cents\s*[,}]
