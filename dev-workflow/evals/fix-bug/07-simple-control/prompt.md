---
tags: [fix-bug]
max_turns: 80
timeout_seconds: 2400
allowed_tools: [Read, Write, Edit, Glob, Grep, Skill, Agent, "Bash(python3:*)", "Bash(node:*)", "Bash(mkdir:*)", "Bash(ls:*)", "Bash(cat:*)", "Bash(jq:*)", "Bash(date:*)"]
runs: 3
---
用 fix-bug 技能排查这个问题。

订单详情页的金额不对：一件 ¥59 的 T 恤，页面上显示「合计：¥5900.00」。跑 `python3 demo.py` 能看到问题。

项目代码在下面，先把这些文件原样建到当前目录，再排查。

我不在电脑前，不用等我确认，查清原因后直接改好，并说明你是怎么验证的。

`shop/__init__.py`（空文件）

`shop/models.py`

```python
from dataclasses import dataclass, field


@dataclass
class LineItem:
    name: str
    qty: int
    price_cents: int


@dataclass
class Order:
    id: str
    items: list = field(default_factory=list)

    @property
    def total_cents(self) -> int:
        return sum(item.qty * item.price_cents for item in self.items)
```

`shop/pages.py`

```python
from shop.models import Order


def render_order_detail(order: Order) -> str:
    lines = [f"订单 {order.id}"]
    for item in order.items:
        lines.append(f"{item.name} × {item.qty}")
    lines.append(f"合计：¥{order.total_cents:.2f}")
    return "\n".join(lines)
```

`shop/admin.py`

```python
from shop.models import Order


def admin_order_row(order: Order) -> str:
    return f"{order.id}\t¥{order.total_cents / 100:.2f}"
```

`demo.py`

```python
from shop.models import LineItem, Order
from shop.pages import render_order_detail

order = Order(id="A1024", items=[LineItem("纯棉 T 恤", 1, 5900)])
print(render_order_detail(order))
```

`shop/receipt.py`

```python
from shop.models import Order


def build_receipt_email(order: Order) -> str:
    lines = [f"感谢购买！订单号 {order.id}", ""]
    for item in order.items:
        lines.append(f"{item.name} × {item.qty}    ¥{item.price_cents * item.qty}")
    lines.append(f"实付：¥{order.total_cents}")
    return "\n".join(lines)
```
