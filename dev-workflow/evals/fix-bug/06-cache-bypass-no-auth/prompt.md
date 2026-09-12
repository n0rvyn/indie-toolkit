---
tags: [fix-bug]
max_turns: 50
timeout_seconds: 1200
allowed_tools: [Read, Write, Edit, Glob, Grep, Skill, Agent, "Bash(python3:*)", "Bash(node:*)", "Bash(mkdir:*)", "Bash(ls:*)", "Bash(cat:*)", "Bash(jq:*)", "Bash(date:*)"]
runs: 3
---
用 fix-bug 技能排查这个问题。

在设置里改了昵称，个人主页还是显示旧昵称，要重启 App 才会变过来。跑 `python3 demo.py` 能看到。

项目代码在下面，先把这些文件原样建到当前目录，再排查。

`userprofile/__init__.py`（空文件）

`userprofile/store.py`

```python
DB = {1: {"nickname": "小林", "avatar": "a1.png"}}
_cache = {}


def get_profile(uid: int) -> dict:
    if uid not in _cache:
        _cache[uid] = dict(DB[uid])
    return _cache[uid]


def invalidate(uid: int) -> None:
    _cache.pop(uid, None)
```

`userprofile/api.py`

```python
from userprofile.store import DB, invalidate


def update_profile(uid: int, **fields) -> None:
    DB[uid].update(fields)
    invalidate(uid)
```

`settings/__init__.py`（空文件）

`settings/nickname.py`

```python
from userprofile.store import DB


def change_nickname(uid: int, name: str) -> None:
    DB[uid]["nickname"] = name
```

`settings/avatar.py`

```python
from userprofile.store import DB


def change_avatar(uid: int, url: str) -> None:
    DB[uid]["avatar"] = url
```

`demo.py`

```python
from settings.nickname import change_nickname
from userprofile.store import get_profile

print("主页昵称:", get_profile(1)["nickname"])
change_nickname(1, "林小满")
print("改名后主页昵称:", get_profile(1)["nickname"])
```
