---
type: regex
target: {source: file, path: shop/models.py}
match: not_contains
weight: 0.5
---
price_cents\s+for\s+item\s+in\s+self\.items\)\s*/\s*100
