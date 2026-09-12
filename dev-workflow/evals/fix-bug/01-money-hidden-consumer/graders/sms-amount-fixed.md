---
type: llm
focus: {source: file, path: shop/notify.py}
weight: 1
---
This is the final shop/notify.py. `order.to_dict()["total"]` is an integer amount in CENTS (5900 means ¥59) and to_dict() is also what the mobile API returns, so it keeps that unit.
PASS if, for total 5900, the SMS text this file builds shows the amount as 59 or 59.00 元.
FAIL if it inserts the raw total (5900) as 元. If it calls a helper defined in another file, assume the helper does what its name says.
