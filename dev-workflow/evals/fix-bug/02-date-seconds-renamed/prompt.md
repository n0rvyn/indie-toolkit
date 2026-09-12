---
tags: [fix-bug]
max_turns: 50
timeout_seconds: 1200
allowed_tools: [Read, Write, Edit, Glob, Grep, Skill, Agent, "Bash(python3:*)", "Bash(node:*)", "Bash(mkdir:*)", "Bash(ls:*)", "Bash(cat:*)", "Bash(jq:*)", "Bash(date:*)"]
runs: 3
---
用 fix-bug 技能排查这个问题。

帖子列表里的日期全显示成 1970-01-21，帖子明明是这周发的。跑 `node demo.js` 能看到问题。

项目代码在下面，先把这些文件原样建到当前目录，再排查。

我不在电脑前，不用等我确认，查清原因后直接改好，并说明你是怎么验证的。

`src/api.js`

```js
// 后端接口返回的帖子列表（服务端代码不在这个仓库里，这里是它返回的数据）
function fetchPosts() {
  return [
    { id: 1, title: "周末去爬山", createdAt: 1789084800 },
    { id: 2, title: "新买的咖啡豆", createdAt: 1789171200 },
  ];
}

module.exports = { fetchPosts };
```

`src/format.js`

```js
function formatDate(date) {
  return date.toISOString().slice(0, 10);
}

module.exports = { formatDate };
```

`src/list.js`

```js
const { formatDate } = require("./format");

function renderList(posts) {
  return posts.map((p) => `${p.title}  ${formatDate(new Date(p.createdAt))}`).join("\n");
}

module.exports = { renderList };
```

`src/export.js`

```js
const { formatDate } = require("./format");

const toRow = ({ id, title, createdAt }) => ({ id, title, ts: createdAt });

function exportCsv(posts) {
  const rows = posts.map(toRow);
  return ["id,title,date", ...rows.map((r) => `${r.id},${r.title},${formatDate(new Date(r.ts))}`)].join("\n");
}

module.exports = { exportCsv };
```

`src/relative.js`

```js
function daysAgo(post, now = Date.now()) {
  return Math.floor((now - post.createdAt * 1000) / 86400000);
}

module.exports = { daysAgo };
```

`demo.js`

```js
const { fetchPosts } = require("./src/api");
const { renderList } = require("./src/list");

console.log(renderList(fetchPosts()));
```
