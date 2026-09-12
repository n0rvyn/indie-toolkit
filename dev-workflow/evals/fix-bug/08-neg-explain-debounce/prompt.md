---
tags: [fix-bug, negative-trigger]
max_turns: 8
timeout_seconds: 180
allowed_tools: [Read, Glob, Grep, Skill]
runs: 3
---
下面这段搜索框代码里，`DEBOUNCE_MS` 是干什么用的？为什么设成 600？讲清楚就行，不用改代码。

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
