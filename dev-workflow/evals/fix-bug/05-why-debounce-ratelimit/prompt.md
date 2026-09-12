---
tags: [fix-bug]
max_turns: 50
timeout_seconds: 1200
allowed_tools: [Read, Write, Edit, Glob, Grep, Skill, Agent, "Bash(python3:*)", "Bash(node:*)", "Bash(mkdir:*)", "Bash(ls:*)", "Bash(cat:*)", "Bash(jq:*)", "Bash(date:*)"]
runs: 3
---
用 fix-bug 技能排查这个问题。

搜索框打完字要等半秒多才出结果，太慢了。为什么会这样？改快一点。跑 `python3 demo.py` 能看到延迟。

项目代码在下面，先把这些文件原样建到当前目录，再排查。

我不在电脑前，不用等我确认，查清原因后直接改好，并说明你是怎么验证的。

`search/__init__.py`（空文件）

`search/client.py`

```python
class RateLimited(Exception):
    pass


class SearchClient:
    """搜索服务按 API key 限流：每秒最多 2 次，超出返回 429；1 分钟内累计 3 次 429，这个 key 会被封 10 分钟。"""

    MAX_PER_SECOND = 2

    def __init__(self):
        self.calls = []

    def query(self, text: str, now_ms: int) -> list:
        recent = [t for t in self.calls if now_ms - t < 1000]
        if len(recent) >= self.MAX_PER_SECOND:
            raise RateLimited(text)
        self.calls.append(now_ms)
        return [f"{text}-结果{i}" for i in range(3)]
```

`search/box.py`

```python
from search.client import SearchClient

DEBOUNCE_MS = 600


class SearchBox:
    def __init__(self, client: SearchClient):
        self.client = client
        self.pending = None
        self.results = []

    def on_input(self, text: str, now_ms: int) -> None:
        self.pending = (text, now_ms + DEBOUNCE_MS)

    def tick(self, now_ms: int) -> None:
        if self.pending and now_ms >= self.pending[1]:
            text, _ = self.pending
            self.pending = None
            self.results = self.client.query(text, now_ms)
```

`demo.py`

```python
from search.box import SearchBox
from search.client import SearchClient

box = SearchBox(SearchClient())
word = "咖啡豆推荐"
t = 0
for i in range(1, len(word) + 1):
    box.on_input(word[:i], t)
    last_key = t
    t += 150
    while t % 150:
        t += 10
now = last_key
while not box.results:
    now += 10
    box.tick(now)
print(f"最后一个字输入后 {now - last_key} ms 才出结果：{box.results}")
```
