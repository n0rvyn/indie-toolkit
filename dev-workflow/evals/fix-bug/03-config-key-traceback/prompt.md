---
tags: [fix-bug]
max_turns: 50
timeout_seconds: 1200
allowed_tools: [Read, Write, Edit, Glob, Grep, Skill, Agent, "Bash(python3:*)", "Bash(node:*)", "Bash(mkdir:*)", "Bash(ls:*)", "Bash(cat:*)", "Bash(jq:*)", "Bash(date:*)"]
runs: 3
---
用 fix-bug 技能排查这个问题。

设置页把网络超时改成 5 秒之后，一同步就报下面这个错。跑 `python3 main.py` 能复现。

报错：

```
Traceback (most recent call last):
  File "main.py", line 8, in <module>
    print(fetch_inbox(cfg))
          ~~~~~~~~~~~^^^^^
  File "app/client.py", line 5, in fetch_inbox
    return http_get("https://api.example.com/inbox", timeout=cfg["timeout"])
                                                             ~~~^^^^^^^^^^^
KeyError: 'timeout'
```

项目代码在下面，先把这些文件原样建到当前目录，再排查。

我不在电脑前，不用等我确认，查清原因后直接改好，并说明你是怎么验证的。

`app/__init__.py`（空文件）

`app/http.py`

```python
def http_get(url: str, timeout: float) -> str:
    """timeout 单位：秒"""
    return f"GET {url} (timeout={timeout}s)"
```

`app/settings.py`

```python
import json


def save_settings(path: str, timeout_seconds: float) -> None:
    with open(path, "w") as f:
        json.dump({"timeout_ms": int(timeout_seconds * 1000)}, f)


def load_settings(path: str) -> dict:
    with open(path) as f:
        return json.load(f)
```

`app/client.py`

```python
from app.http import http_get


def fetch_inbox(cfg: dict) -> str:
    return http_get("https://api.example.com/inbox", timeout=cfg["timeout"])
```

`app/sync.py`

```python
from app.http import http_get


def sync_contacts(cfg: dict) -> str:
    return http_get("https://api.example.com/contacts", timeout=cfg.get("timeout", 30))
```

`main.py`

```python
from app.client import fetch_inbox
from app.settings import load_settings, save_settings
from app.sync import sync_contacts

save_settings("settings.json", timeout_seconds=5)  # 用户在设置页把超时改成 5 秒
cfg = load_settings("settings.json")
print(sync_contacts(cfg))
print(fetch_inbox(cfg))
```
