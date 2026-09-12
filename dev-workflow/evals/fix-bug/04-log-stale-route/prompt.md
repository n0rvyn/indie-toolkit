---
tags: [fix-bug]
max_turns: 50
timeout_seconds: 1200
allowed_tools: [Read, Write, Edit, Glob, Grep, Skill, Agent, "Bash(python3:*)", "Bash(node:*)", "Bash(mkdir:*)", "Bash(ls:*)", "Bash(cat:*)", "Bash(jq:*)", "Bash(date:*)"]
runs: 3
---
用 fix-bug 技能排查这个问题。

手机竖着拍的照片，上传以后变成横的了。上传接口上个月已经换成了新版，新版会自动把照片转正。今天的服务日志贴在下面，你看一下。

日志：

```
INFO router dispatch path=/upload handler=legacy_upload
INFO storage saved image id=8812 orientation=raw
```

项目代码在下面，先把这些文件原样建到当前目录，再排查。

我不在电脑前，不用等我确认，查清原因后直接改好，并说明你是怎么验证的。

`app/__init__.py`（空文件）

`app/router.py`

```python
import logging

log = logging.getLogger("router")
ROUTES = {}


def register(path, handler):
    ROUTES[path] = handler


def dispatch(path, req):
    handler = ROUTES[path]
    log.info("dispatch path=%s handler=%s", path, handler.__name__)
    return handler(req)
```

`app/storage.py`

```python
import logging

log = logging.getLogger("storage")


def save_image(image: dict) -> dict:
    log.info("saved image id=%s orientation=%s", image["id"], image["orientation"])
    return image
```

`app/upload.py`

```python
from app.storage import save_image


def fix_orientation(image: dict) -> dict:
    # 按 EXIF 把竖拍的照片转正
    return {**image, "orientation": "upright"}


def upload_v2(req: dict) -> dict:
    return save_image(fix_orientation(req["image"]))
```

`app/legacy/__init__.py`（空文件）

`app/legacy/upload_old.py`

```python
from app.storage import save_image


def legacy_upload(req: dict) -> dict:
    return save_image(req["image"])
```

`server.py`

```python
import logging

from app.legacy.upload_old import legacy_upload
from app.router import dispatch, register
from app.upload import upload_v2

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

register("/upload", upload_v2)
register("/upload", legacy_upload)  # 旧版上传接口

if __name__ == "__main__":
    dispatch("/upload", {"image": {"id": 8812, "orientation": "raw"}})
```
