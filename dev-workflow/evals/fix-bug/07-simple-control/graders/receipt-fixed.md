---
type: regex
target: {source: file, path: shop/receipt.py}
match: not_contains
---
¥\{order\.total_cents\}
