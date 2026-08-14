#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""`git checkout -- <路径>` / `git restore <路径>` 之前，把要被丢弃的内容备份下来。

## 为什么是「备份后放行」而不是 deny / ask

这个动作**本身是正当的**：变异测试之后还原探针、丢掉临时改动，一天用六七次很正常。
拦它 → 假阳性太高，人会绕过去（换 `git stash`、换写法），规则形同虚设；
ask → 六七次打断，而且大概率一路确认 —— 它要防的恰恰是「我以为我知道在干什么」那一刻。

**真正的断点不是这个动作，是它不可逆。** 备份之后，误操作照样发生，
但代价从「工作没了」变成「从备份里拷回来」。

## 它防的是什么（实证 2026-08-14，同一天两次）

变异测试改坏代码 → 跑测试看红 → `git checkout -- <file>` 还原。
那一下把**同一文件里这轮还没提交的功能**一起还原掉了。

这类误删比一般误删阴：**代码没了，测试照样跑、照样绿** —— 它测的是一个不存在的功能。
症状还会伪装：第二次表现成「并发测试单跑通过、全套失败」，
花了六轮才定位到不是逻辑写错，是功能根本不在文件里了。

## 行为

- 只对**带路径**的还原形式动作（`git checkout -- x`、`git checkout .`、`git restore x`）。
  `git checkout <分支>` 不管 —— 那是切分支，git 自己会拒绝有冲突改动的切换。
- 逐个路径看有没有未提交改动，有就把当前内容拷进 `.git/undo-checkout/<时间戳>/`。
- 往 stderr 打一行备份位置，**exit 0 不做判断** = 放行。
- 任何异常都直接放行（守卫失效时本来就该 fail open）。
"""
import json
import os
import re
import shutil
import subprocess
import sys
import time

# `git checkout -- a b`、`git checkout .`、`git restore a`、`git restore --staged a`
FORM = re.compile(r"\bgit\s+(?:checkout|restore)\b([^\n;&|]*)")


def _git(args, cwd):
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True,
                          text=True, timeout=5)


def _paths_of(seg):
    """从 `git checkout/restore` 后面那截里抠出路径。抠不出返回空。"""
    toks = seg.split()
    if "--" in toks:
        return [t for t in toks[toks.index("--") + 1:] if not t.startswith("-")]
    # 没有 `--`：只认明显是路径的写法（`.` 或带 / 或带后缀），
    # 免得把 `git checkout main` 的分支名当成路径。
    out = []
    for t in toks:
        if t.startswith("-"):
            continue
        if t == "." or "/" in t or re.search(r"\.\w+$", t):
            out.append(t)
    return out


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if payload.get("tool_name") != "Bash":
        sys.exit(0)
    command = (payload.get("tool_input") or {}).get("command") or ""
    cwd = payload.get("cwd") or os.getcwd()

    targets = []
    for m in FORM.finditer(command):
        targets += _paths_of(m.group(1))
    if not targets:
        sys.exit(0)

    try:
        root = _git(["rev-parse", "--show-toplevel"], cwd)
        if root.returncode != 0:
            sys.exit(0)
        root = root.stdout.strip()

        # 哪些路径真的有未提交改动 —— 干净的没什么可丢，不用备份。
        dirty = _git(["diff", "--name-only", "HEAD", "--"] + targets, cwd)
        files = [f for f in dirty.stdout.splitlines() if f.strip()]
        if not files:
            sys.exit(0)

        stamp = time.strftime("%Y%m%d-%H%M%S")
        dest = os.path.join(root, ".git", "undo-checkout", stamp)
        for rel in files:
            src = os.path.join(root, rel)
            if not os.path.isfile(src):
                continue
            dst = os.path.join(dest, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)

        print(f"[backup-before-checkout] {len(files)} 个文件有未提交改动，"
              f"已备份到 .git/undo-checkout/{stamp}/ —— "
              f"如果这一下还原掉了不该还原的东西，从那儿拷回来。"
              f"（{'、'.join(files[:4])}{' …' if len(files) > 4 else ''}）",
              file=sys.stderr)
    except Exception:
        pass          # 备份失败也放行：守卫不该成为新的失败模式
    sys.exit(0)


if __name__ == "__main__":
    main()
