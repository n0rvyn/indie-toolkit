---
name: html-report
description: "Render the work just done in this session (a bug fix, root-cause investigation, review, migration, analysis) into ONE self-contained, dark-themed HTML report that a human reads for acceptance. Trigger phrases — '/html-report', '出一份 HTML 报告', '把这次工作/这次排查写成 HTML 报告', '生成一份验收报告', 'make an HTML report of what we did', 'render this as an HTML report', 'ship report'. Manual, on-demand: the user runs it when they want the polished artifact. Not when: the user wants a markdown summary in chat (just write markdown), or a token-spend audit (use dev-workflow:audit-tokens), or to sync docs to Notion (use notion-page-sync)."
disable-model-invocation: false
allowed-tools: Read, Write, Bash(open *), Bash(mkdir -p *), Bash(git rev-parse *)
---

# HTML Report

Turn the work just completed (in THIS session) into one self-contained HTML file — the finished artifact a human reads to accept the work. Markdown is for the working loop; HTML is for the deliverable a person actually reviews (per Anthropic's own May-2026 shift to HTML for finished artifacts).

This skill runs in the **main session** — it reports on what was just done, which lives in the current conversation. Do not fork it.

## When the user invokes this

1. **Decide the subject.** Default: the work done in this session (the bug fixed, the root cause found, the review completed, the migration shipped). If the user names a specific topic or points at a file/diff, report on that instead.

2. **Pick the sections that fit the work.** This is a flexible template, NOT a fixed form — include only the sections that apply, in this order. A debugging session uses most of them; a small review uses a few.

   - **一句话结论 (lead card)** — the single most important takeaway, in a highlighted card at the top. Always include.
   - **现象 / 背景 (Situation)** — what was observed / the starting state. Tables for per-item data (e.g. per-step status, per-file change).
   - **根因 / 分析 (Root cause / Analysis)** — split into sub-sections (`<h3>`) when there are multiple distinct findings. Quote real `file:line`, commands, and outputs as evidence.
   - **决策 (Decision)** — when a choice was made between approaches, use a comparison table (option / what you get / cost) and state which won and why. Include rejected alternatives.
   - **实现 (What changed)** — the concrete edits, by file, in plain language.
   - **权衡 (Tradeoffs)** — a table: choice / gain / cost. Be honest about what was given up.
   - **遗留 / 建议 (Deferred / Recommendations)** — what was intentionally NOT done and why; follow-ups. (The skills-engineering equivalent of a "Gotchas" section — the most valuable part for the next reader.)
   - **结果 (Result)** — the outcome, with evidence. If a run/verification is still pending, say so explicitly with a "待填/pending" pill rather than implying success.
   - **验证门 (Verification)** — what was actually run (build/test/e2e) and its real status. Never claim green here unless a command was run and seen to pass; flaky/skipped/pending must be labelled.

3. **Write ONE self-contained HTML file** using the house template below. Fill real content from the session — do not invent results. Faithfully label anything unverified, skipped, or pending (mirror the honesty rules: evidence before claims).

4. **Save and offer to open.**
   - In a git repo: `docs/reports/{YYYY-MM-DD}-{kebab-slug}.html` (run `mkdir -p docs/reports` first).
   - Otherwise: `~/Desktop/{YYYY-MM-DD}-{kebab-slug}.html`.
   - Then offer: "`open <path>` 看一下？" — only run `open` if the user says yes.

## Hard rules (non-negotiable)

- **Single self-contained file.** All CSS inline in one `<style>` block. No external stylesheets, fonts, scripts, or image URLs. It must open correctly with no network.
- **No JavaScript.** Interactivity, if any, is CSS-only (`<details>` for collapsible sections). Include the meta tag `<meta http-equiv="Content-Security-Policy" content="script-src 'none'">` so the file can never execute script even if opened from an authenticated origin.
- **Print-friendly.** The layout already prints cleanly; do not add anything that breaks `Cmd-P`.
- **Content honesty.** The report inherits the session's verification discipline: a result is only "✅ 通过/done" if a command was run and its output seen. Pending → `待填/pending` pill; flaky → labelled; skipped → labelled.
- **Chinese by default** (match the user's working language) unless the user asks otherwise.

## House template (copy this `<style>` verbatim; fill the body)

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta http-equiv="Content-Security-Policy" content="script-src 'none'">
<title>{标题} · {日期}</title>
<style>
  :root{--bg:#0f1115;--card:#1a1d24;--ink:#e6e8ec;--dim:#9aa3b2;--line:#2a2f3a;--ok:#3fb950;--bad:#f85149;--warn:#d29922;--accent:#58a6ff;--code:#11141a;}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif;}
  .wrap{max-width:960px;margin:0 auto;padding:40px 24px 80px;}
  h1{font-size:28px;margin:0 0 4px;}
  .sub{color:var(--dim);margin-bottom:32px;}
  h2{font-size:21px;margin:38px 0 12px;padding-top:18px;border-top:1px solid var(--line);}
  h3{font-size:17px;margin:22px 0 8px;color:var(--accent);}
  .card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:18px 20px;margin:14px 0;}
  code{background:var(--code);padding:2px 6px;border-radius:4px;font:14px/1.5 "SF Mono",Menlo,monospace;color:#c9d1d9;}
  pre{background:var(--code);border:1px solid var(--line);border-radius:8px;padding:14px 16px;overflow-x:auto;font:13px/1.6 "SF Mono",Menlo,monospace;}
  table{border-collapse:collapse;width:100%;margin:12px 0;font-size:14.5px;}
  th,td{border:1px solid var(--line);padding:8px 11px;text-align:left;vertical-align:top;}
  th{background:#212631;color:var(--dim);font-weight:600;}
  .ok{color:var(--ok);} .bad{color:var(--bad);} .warn{color:var(--warn);} .dim{color:var(--dim);}
  .pill{display:inline-block;padding:1px 9px;border-radius:20px;font-size:12.5px;border:1px solid var(--line);}
  .pill.ok{border-color:var(--ok);} .pill.bad{border-color:var(--bad);} .pill.warn{border-color:var(--warn);}
  ul{margin:8px 0;padding-left:22px;} li{margin:5px 0;}
  blockquote{margin:10px 0;padding:8px 16px;border-left:3px solid var(--accent);color:var(--dim);background:#161a21;}
  details{margin:10px 0;} summary{cursor:pointer;color:var(--accent);}
  .tag{font-size:12px;color:var(--dim);}
  @media print{body{background:#fff;color:#000;} .card,pre,code{background:#f5f5f5;} .wrap{max-width:none;}}
</style>
</head>
<body>
<div class="wrap">

  <h1>{标题}</h1>
  <div class="sub">{日期} · {项目/范围} · {作者}</div>

  <div class="card"><b>一句话结论：</b>{最重要的那句话}</div>

  <!-- 按 step 2 选用的 section，每个用 <h2> 开头；
       per-item 数据用 <table>；多个根因用 <h3> 分章；
       决策/权衡用对比表；长 section 可用 <details><summary> 折叠。 -->

</div>
</body>
</html>
```

## Gotchas

- **Do not fork this skill.** A forked sub-agent cannot see the session that produced the work, so it would have nothing real to report. Run in the main session.
- **Do not auto-open without asking.** `open` launches the user's browser; offer first.
- **Do not pad.** Skip sections that don't apply. A 3-section report for a small fix is correct; forcing all 9 sections is noise.
- **Do not claim results you didn't see.** If the build/test/e2e hasn't finished, use a `待填/pending` pill — never imply green.
- **Keep it one file.** The moment you reach for an external CSS/JS/font/image URL, stop — inline it or drop it. The value of this artifact is that it opens anywhere, offline, forever.
- **Style is intentionally fixed** (dark theme above). If the user later wants variants or a light theme, that is a future iteration — do not invent alternate styles ad hoc.
