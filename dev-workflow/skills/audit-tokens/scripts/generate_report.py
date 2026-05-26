#!/usr/bin/env python3
"""audit-tokens HTML report generator.

Reads the TSV produced by analyze.sh, computes aggregates across multiple
dimensions, scans installed plugin SKILL.md files for cost-posture gaps,
and emits a self-contained HTML report.

Usage: generate_report.py <tsv_path> <html_out_path> <days>
"""

from __future__ import annotations

import csv
import datetime as _dt
import glob
import os
import re
import sys
from collections import Counter, defaultdict
from html import escape
from pathlib import Path

# Pricing (USD per 1M tokens) — Opus 4.7 / Sonnet 4.6 / Haiku 4.5 public list (2026-05)
PRICING = {
    "opus":   {"in": 15.00, "cw_1h": 30.00, "cw_5m": 18.75, "cr": 1.50, "out": 75.00},
    "sonnet": {"in":  3.00, "cw_1h":  6.00, "cw_5m":  3.75, "cr": 0.30, "out": 15.00},
    "haiku":  {"in":  1.00, "cw_1h":  2.00, "cw_5m":  1.25, "cr": 0.10, "out":  5.00},
}

# Cost-posture heuristic: keyword-based skill classification
MECHANICAL_KEYWORDS = (
    "execute", "executes", "apply", "applies", "run", "runs",
    "parse", "parses", "scan", "scans", "audit", "audits",
    "validate", "validates", "verify", "verifies",
    "sync", "syncs", "extract", "extracts", "generate", "generates",
    "lint", "format", "mechanical",
)
RETRIEVAL_KEYWORDS = (
    "search", "retrieve", "query", "find", "look up", "lookup",
    "fetch", "fetches",
)
TOOL_WRAPPER_KEYWORDS = (
    "wraps", "wrapper", "cli", "api call", "rest call",
    "send", "post", "trigger",
)
JUDGMENT_KEYWORDS = (
    "judge", "judges", "critique", "critiques", "review", "reviews",
    "diagnose", "diagnoses", "design", "designs", "synthesize", "synthesizes",
    "brainstorm", "decide", "decides", "orchestrate", "orchestrates",
    "evaluate", "evaluates", "assess", "assesses",
)


# ----------------------------------------------------------------------------
# Data layer
# ----------------------------------------------------------------------------


def classify_model(model_id: str) -> str:
    if not model_id or model_id == "<synthetic>" or model_id == "_":
        return "_skip_"
    m = model_id.lower()
    if "opus" in m:
        return "opus"
    if "sonnet" in m:
        return "sonnet"
    if "haiku" in m:
        return "haiku"
    return "other"


def turn_cost(model_class: str, row: dict) -> float:
    """Cost in USD for a single turn given its model class and usage."""
    p = PRICING.get(model_class)
    if p is None:
        # Unknown model — fall back to opus pricing (conservative upper bound)
        p = PRICING["opus"]
    return (
        row["input"] * p["in"]
        + row["cw_1h"] * p["cw_1h"]
        + row["cw_5m"] * p["cw_5m"]
        + row["cr"] * p["cr"]
        + row["out"] * p["out"]
    ) / 1_000_000


def load_tsv(path: str):
    rows = []
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 14:
                continue
            try:
                row = {
                    "session": parts[0],
                    "request": parts[1],
                    "skill": parts[2] or "_none_",
                    "plugin": parts[3] or "_none_",
                    "model": parts[4],
                    "model_class": classify_model(parts[4]),
                    "input": int(parts[5] or 0),
                    "cw": int(parts[6] or 0),  # total cache_creation (not split)
                    "cr": int(parts[7] or 0),
                    "out": int(parts[8] or 0),
                    "cw_1h": int(parts[9] or 0),
                    "cw_5m": int(parts[10] or 0),
                    "sidechain": parts[11] == "true",
                    "cwd": parts[12] or "_",
                    "ts": parts[13],
                }
            except (ValueError, IndexError):
                continue
            # Skip synthetic placeholders (all zeros, unknown model)
            if row["model_class"] == "_skip_":
                continue
            rows.append(row)
    return rows


# ----------------------------------------------------------------------------
# Aggregations
# ----------------------------------------------------------------------------


def agg_totals(rows):
    totals = {"input": 0, "cw": 0, "cw_1h": 0, "cw_5m": 0, "cr": 0, "out": 0, "n": 0, "cost": 0.0}
    for r in rows:
        totals["input"] += r["input"]
        totals["cw"] += r["cw"]
        totals["cw_1h"] += r["cw_1h"]
        totals["cw_5m"] += r["cw_5m"]
        totals["cr"] += r["cr"]
        totals["out"] += r["out"]
        totals["n"] += 1
        totals["cost"] += turn_cost(r["model_class"], r)
    billed_input = totals["input"] + totals["cw"] + totals["cr"]
    totals["hit_rate"] = (totals["cr"] / billed_input * 100) if billed_input else 0.0
    return totals


def agg_by(rows, key_fn):
    bucket = defaultdict(lambda: {"input": 0, "cw": 0, "cw_1h": 0, "cw_5m": 0, "cr": 0, "out": 0, "n": 0, "cost": 0.0})
    for r in rows:
        k = key_fn(r)
        b = bucket[k]
        b["input"] += r["input"]
        b["cw"] += r["cw"]
        b["cw_1h"] += r["cw_1h"]
        b["cw_5m"] += r["cw_5m"]
        b["cr"] += r["cr"]
        b["out"] += r["out"]
        b["n"] += 1
        b["cost"] += turn_cost(r["model_class"], r)
    for k, b in bucket.items():
        billed = b["input"] + b["cw"] + b["cr"]
        b["hit_rate"] = (b["cr"] / billed * 100) if billed else 0.0
        b["cost_per_turn"] = b["cost"] / b["n"] if b["n"] else 0.0
    return bucket


def agg_skill_model(rows):
    """Per-(skill, model_class) breakdown — used for cost-posture recommendations."""
    bucket = defaultdict(lambda: {"n": 0, "cost": 0.0})
    for r in rows:
        k = (r["skill"], r["model_class"])
        bucket[k]["n"] += 1
        bucket[k]["cost"] += turn_cost(r["model_class"], r)
    return bucket


# ----------------------------------------------------------------------------
# Cost-posture: scan installed SKILL.md for optimization gaps
# ----------------------------------------------------------------------------


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(skill_path: str) -> dict:
    try:
        text = Path(skill_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm = {}
    for line in m.group(1).splitlines():
        # very lax YAML parsing — only need top-level scalar fields
        if ":" not in line or line.lstrip().startswith("#"):
            continue
        if line.startswith(" ") or line.startswith("\t"):
            continue  # nested, skip
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip().strip('"').strip("'")
    return fm


def classify_skill_by_description(description: str) -> str:
    """Return one of: mechanical / retrieval / tool_wrapper / judgment / unknown."""
    if not description:
        return "unknown"
    d = description.lower()
    # Judgment / synthesis / orchestration takes precedence — these MUST stay on inherit
    for kw in JUDGMENT_KEYWORDS:
        if kw in d:
            return "judgment"
    # Tool wrapper second — "send/post/trigger to external API"
    for kw in TOOL_WRAPPER_KEYWORDS:
        if kw in d:
            return "tool_wrapper"
    # Retrieval
    for kw in RETRIEVAL_KEYWORDS:
        if kw in d:
            return "retrieval"
    # Mechanical last (most permissive bucket)
    for kw in MECHANICAL_KEYWORDS:
        if kw in d:
            return "mechanical"
    return "unknown"


def scan_skills_for_gaps(rows):
    """Find installed plugin skills that look like cost-posture candidates.

    Returns a list of dicts: {skill, plugin, class, current_model, opus_turns, opus_cost, recommended}
    Only includes skills with actual Opus usage in the window (cost > $5)
    AND a clear non-judgment classification.
    """
    # Per-skill Opus usage from the window
    skill_opus = defaultdict(lambda: {"n": 0, "cost": 0.0})
    for r in rows:
        if r["model_class"] == "opus" and r["skill"] != "_none_":
            skill_opus[r["skill"]]["n"] += 1
            skill_opus[r["skill"]]["cost"] += turn_cost("opus", r)

    # Scan installed SKILL.md
    home = os.path.expanduser("~/.claude/plugins")
    candidates = []
    seen_names = set()  # dedupe across marketplaces/symlinks
    for skill_md in glob.glob(os.path.join(home, "**", "SKILL.md"), recursive=True):
        fm = parse_frontmatter(skill_md)
        name = fm.get("name") or os.path.basename(os.path.dirname(skill_md))
        if name in seen_names:
            continue
        seen_names.add(name)
        cur_model = fm.get("model", "")  # empty = inherit
        if cur_model:  # already configured, skip
            continue
        description = fm.get("description", "")
        klass = classify_skill_by_description(description)
        if klass not in ("mechanical", "retrieval", "tool_wrapper"):
            continue  # judgment / unknown — don't recommend

        # Match against actual usage. Skills in the TSV are namespaced like "plugin:name".
        # Try several matching strategies.
        usage = None
        for skill_key, val in skill_opus.items():
            tail = skill_key.split(":")[-1]
            if tail == name:
                usage = val
                break
        if usage is None or usage["cost"] < 5.0:
            continue

        if klass == "mechanical":
            rec = "model: sonnet"
        elif klass == "retrieval":
            rec = "model: sonnet  (consider also context: fork, agent: Explore)"
        else:  # tool_wrapper
            rec = "model: haiku\\ncontext: fork"

        # Estimate post-downgrade cost as a fraction of the observed Opus cost. Tool wrappers
        # (recommended → haiku) drop ~95% of Opus per-turn cost; mechanical and retrieval
        # (recommended → sonnet) drop ~93%. Lower ratio = bigger savings.
        ratio = 0.05 if klass == "tool_wrapper" else 0.07
        est_save = usage["cost"] * (1 - ratio)

        candidates.append({
            "skill": name,
            "path": skill_md,
            "class": klass,
            "opus_turns": usage["n"],
            "opus_cost": usage["cost"],
            "est_save": est_save,
            "recommended": rec,
        })

    candidates.sort(key=lambda c: -c["est_save"])
    return candidates


# ----------------------------------------------------------------------------
# HTML rendering
# ----------------------------------------------------------------------------


def fmt_int(n):
    return f"{n:,}"


def fmt_money(x):
    if x >= 1000:
        return f"${x:,.0f}"
    if x >= 10:
        return f"${x:,.2f}"
    return f"${x:.3f}"


def fmt_tokens(n):
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.1f}K"
    return str(n)


CSS = """
* { box-sizing: border-box; }
body {
  margin: 0;
  font: 14px/1.55 -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif;
  color: #1a1a24;
  background: #f6f7f9;
}
header {
  padding: 28px 36px 64px;
  background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
  color: #fff;
}
header h1 { margin: 0 0 6px 0; font-size: 24px; font-weight: 600; letter-spacing: -0.01em; }
header .meta { font-size: 12px; opacity: 0.7; }
main { padding: 0 36px 60px; max-width: 1200px; margin: 0 auto; }
section { margin-top: 32px; }
section > h2 {
  margin: 0 0 14px 0;
  font-size: 14px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #6b7280;
}
.cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin-top: -36px; position: relative; z-index: 1; }
.card {
  background: #fff;
  border-radius: 10px;
  padding: 18px 18px 16px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.04), 0 1px 3px rgba(0,0,0,0.06);
}
.card .label { font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600; }
.card .value { font-size: 26px; font-weight: 700; margin: 6px 0 2px; letter-spacing: -0.02em; color: #0f172a; }
.card .sub { font-size: 12px; color: #94a3b8; }
table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
th {
  text-align: left;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: #6b7280;
  font-weight: 600;
  padding: 10px 14px;
  background: #f9fafb;
  border-bottom: 1px solid #e5e7eb;
}
td {
  padding: 10px 14px;
  border-bottom: 1px solid #f1f3f5;
  font-variant-numeric: tabular-nums;
}
tr:last-child td { border-bottom: none; }
tr:hover td { background: #fafbfc; }
td.num, th.num { text-align: right; }
td.dim { color: #94a3b8; }
.bar-row { display: flex; align-items: center; gap: 12px; margin: 6px 0; }
.bar-label { width: 140px; font-size: 12px; color: #4b5563; }
.bar-track { flex: 1; height: 14px; background: #f1f3f5; border-radius: 4px; overflow: hidden; position: relative; }
.bar-fill { height: 100%; border-radius: 4px; }
.bar-value { width: 100px; text-align: right; font-size: 12px; color: #6b7280; font-variant-numeric: tabular-nums; }
.bar-cr   { background: linear-gradient(90deg, #6366f1, #818cf8); }
.bar-cw1h { background: linear-gradient(90deg, #ef4444, #f87171); }
.bar-cw5m { background: linear-gradient(90deg, #f97316, #fb923c); }
.bar-out  { background: linear-gradient(90deg, #14b8a6, #5eead4); }
.bar-in   { background: linear-gradient(90deg, #94a3b8, #cbd5e1); }
.tag { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.tag-opus   { background: #fee2e2; color: #991b1b; }
.tag-sonnet { background: #dbeafe; color: #1e40af; }
.tag-haiku  { background: #dcfce7; color: #166534; }
.tag-other  { background: #f3f4f6; color: #4b5563; }
.tag-mechanical   { background: #ecfeff; color: #155e75; }
.tag-retrieval    { background: #fef3c7; color: #92400e; }
.tag-tool_wrapper { background: #f3e8ff; color: #6b21a8; }
.rec-card {
  background: #fff;
  border-left: 3px solid #6366f1;
  padding: 14px 18px;
  margin: 10px 0;
  border-radius: 0 6px 6px 0;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}
.rec-card .rec-skill { font-weight: 700; font-size: 14px; color: #0f172a; }
.rec-card .rec-meta { font-size: 12px; color: #6b7280; margin-top: 3px; }
.rec-card .rec-fix { margin-top: 8px; padding: 8px 10px; background: #f9fafb; border-radius: 4px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; white-space: pre-wrap; }
.rec-card.rec-empty { border-left-color: #d1d5db; color: #6b7280; }
footer { margin-top: 60px; padding-top: 20px; border-top: 1px solid #e5e7eb; font-size: 12px; color: #94a3b8; }
footer p { margin: 4px 0; }
.skill-name { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12.5px; }
.dim-cell { color: #94a3b8; font-size: 12px; }
"""


def render(rows, days: int, candidates):
    totals = agg_totals(rows)
    by_model = agg_by(rows, lambda r: r["model_class"])
    by_skill_full = agg_by(rows, lambda r: f"{r['plugin']}::{r['skill']}" if r["skill"] != "_none_" else "(no skill)")
    by_cwd = agg_by(rows, lambda r: r["cwd"])
    by_date = agg_by(rows, lambda r: r["ts"][:10] if r["ts"] else "_")
    by_chain = agg_by(rows, lambda r: "subagent" if r["sidechain"] else "main session")

    # Sort + slice
    skill_rows = sorted(by_skill_full.items(), key=lambda kv: -kv[1]["cost"])[:15]
    cwd_rows = sorted(by_cwd.items(), key=lambda kv: -kv[1]["cost"])[:10]
    date_rows = sorted(by_date.items(), key=lambda kv: kv[0])
    model_rows = sorted(by_model.items(), key=lambda kv: -kv[1]["cost"])

    # Cost composition — model-aware per-row sums (Opus/Sonnet/Haiku have distinct rates)
    cost_in = cost_cw1h = cost_cw5m = cost_cr = cost_out = 0.0
    for r in rows:
        p = PRICING.get(r["model_class"], PRICING["opus"])
        cost_in   += r["input"]  * p["in"]    / 1_000_000
        cost_cw1h += r["cw_1h"]  * p["cw_1h"] / 1_000_000
        cost_cw5m += r["cw_5m"]  * p["cw_5m"] / 1_000_000
        cost_cr   += r["cr"]     * p["cr"]    / 1_000_000
        cost_out  += r["out"]    * p["out"]   / 1_000_000
    cost_total = cost_in + cost_cw1h + cost_cw5m + cost_cr + cost_out

    def pct(x): return (x / cost_total * 100) if cost_total else 0.0

    # Top-3 recommendations summary (for SUMMARY block)
    top_recs = candidates[:3]

    # Date stamp
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    parts = []
    # Machine-readable summary in comment (consumed by SKILL.md Step 4)
    summary = {
        "window_days": days,
        "total_turns": totals["n"],
        "total_cost_usd": round(cost_total, 2),
        "cache_hit_rate_pct": round(totals["hit_rate"], 1),
        "top_recommendations": [
            f"{c['skill']} ({c['class']}): {c['recommended'].splitlines()[0]} (Opus ${c['opus_cost']:.0f} → est save ${c['est_save']:.0f})"
            for c in top_recs
        ],
    }
    parts.append("<!DOCTYPE html>")
    parts.append("<html lang='en'>")
    parts.append("<head>")
    parts.append("<meta charset='utf-8'>")
    parts.append(f"<title>Token Audit — last {days} days</title>")
    parts.append(f"<style>{CSS}</style>")
    parts.append("</head>")
    parts.append("<!-- SUMMARY")
    import json as _json
    parts.append(_json.dumps(summary, indent=2))
    parts.append("END SUMMARY -->")
    parts.append("<body>")

    # Header
    parts.append("<header>")
    parts.append(f"<h1>Token Audit</h1>")
    parts.append(f"<div class='meta'>Window: last {days} days &nbsp;·&nbsp; Generated: {escape(now)} &nbsp;·&nbsp; {fmt_int(totals['n'])} unique turns analysed</div>")
    parts.append("</header>")

    parts.append("<main>")

    # Summary cards
    parts.append("<div class='cards'>")
    cards = [
        ("Total spend", fmt_money(cost_total), f"{fmt_int(totals['n'])} turns"),
        ("Cache hit rate", f"{totals['hit_rate']:.1f}%", f"{fmt_tokens(totals['cr'])} cache reads"),
        ("Output tokens", fmt_tokens(totals['out']), fmt_money(cost_out)),
        ("Cost / turn", fmt_money(cost_total / totals["n"] if totals["n"] else 0), "average"),
    ]
    for label, value, sub in cards:
        parts.append(f"<div class='card'><div class='label'>{escape(label)}</div><div class='value'>{escape(value)}</div><div class='sub'>{escape(sub)}</div></div>")
    parts.append("</div>")

    # Recommendations
    parts.append("<section>")
    parts.append("<h2>Cost-Posture Recommendations</h2>")
    if not candidates:
        parts.append("<div class='rec-card rec-empty'>No optimization gaps detected. Either everything is already configured, or no skills have crossed the $5 Opus threshold in this window.</div>")
    else:
        parts.append(f"<div style='font-size:13px;color:#4b5563;margin-bottom:14px;'>Found {len(candidates)} skill(s) currently inheriting Opus that classify as mechanical/retrieval/tool-wrapper per the cost-posture heuristic. Estimated savings assume Sonnet ≈ 5-15% and Haiku ≈ 5% of the Opus per-turn cost based on observed usage patterns. Always validate with real usage before committing.</div>")
        for c in candidates:
            parts.append("<div class='rec-card'>")
            parts.append(f"<div class='rec-skill'>{escape(c['skill'])} <span class='tag tag-{c['class']}'>{c['class']}</span></div>")
            parts.append(f"<div class='rec-meta'>{fmt_int(c['opus_turns'])} Opus turns · {fmt_money(c['opus_cost'])} spent · est save <strong>{fmt_money(c['est_save'])}</strong></div>")
            parts.append(f"<div class='rec-fix'>{escape(c['recommended'])}</div>")
            parts.append(f"<div class='rec-meta' style='margin-top:6px;'>{escape(c['path'])}</div>")
            parts.append("</div>")
    parts.append("</section>")

    # Cost composition
    parts.append("<section>")
    parts.append("<h2>Cost Composition</h2>")
    comp_items = [
        ("Cache read",       cost_cr,   "bar-cr"),
        ("Cache write (1h)", cost_cw1h, "bar-cw1h"),
        ("Cache write (5m)", cost_cw5m, "bar-cw5m"),
        ("Output",           cost_out,  "bar-out"),
        ("Uncached input",   cost_in,   "bar-in"),
    ]
    for label, amount, cls in comp_items:
        p = pct(amount)
        parts.append("<div class='bar-row'>")
        parts.append(f"<div class='bar-label'>{escape(label)}</div>")
        parts.append(f"<div class='bar-track'><div class='bar-fill {cls}' style='width:{p:.1f}%'></div></div>")
        parts.append(f"<div class='bar-value'>{fmt_money(amount)} · {p:.1f}%</div>")
        parts.append("</div>")
    parts.append("</section>")

    # By model
    parts.append("<section>")
    parts.append("<h2>By Model</h2>")
    parts.append("<table>")
    parts.append("<thead><tr><th>Model</th><th class='num'>Turns</th><th class='num'>Avg cache_read</th><th class='num'>Avg output</th><th class='num'>$ / turn</th><th class='num'>Total</th><th class='num'>Hit rate</th></tr></thead>")
    parts.append("<tbody>")
    for model, b in model_rows:
        avg_cr = b["cr"] / b["n"] if b["n"] else 0
        avg_out = b["out"] / b["n"] if b["n"] else 0
        parts.append("<tr>")
        parts.append(f"<td><span class='tag tag-{model}'>{escape(model)}</span></td>")
        parts.append(f"<td class='num'>{fmt_int(b['n'])}</td>")
        parts.append(f"<td class='num dim-cell'>{fmt_tokens(int(avg_cr))}</td>")
        parts.append(f"<td class='num dim-cell'>{fmt_int(int(avg_out))}</td>")
        parts.append(f"<td class='num'>{fmt_money(b['cost_per_turn'])}</td>")
        parts.append(f"<td class='num'><strong>{fmt_money(b['cost'])}</strong></td>")
        parts.append(f"<td class='num dim-cell'>{b['hit_rate']:.1f}%</td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    parts.append("</section>")

    # By skill (top 15)
    parts.append("<section>")
    parts.append("<h2>Top Skills by Cost</h2>")
    parts.append("<table>")
    parts.append("<thead><tr><th>Skill</th><th class='num'>Turns</th><th class='num'>$ / turn</th><th class='num'>Hit %</th><th class='num'>Total</th></tr></thead>")
    parts.append("<tbody>")
    for key, b in skill_rows:
        plugin, _, name = key.partition("::")
        if plugin == "_none_":
            display = "(no plugin)"
        else:
            display = plugin
        display_skill = name if name else key
        parts.append("<tr>")
        parts.append(f"<td><span class='skill-name'>{escape(display_skill)}</span><div class='dim-cell'>{escape(display)}</div></td>")
        parts.append(f"<td class='num'>{fmt_int(b['n'])}</td>")
        parts.append(f"<td class='num'>{fmt_money(b['cost_per_turn'])}</td>")
        parts.append(f"<td class='num dim-cell'>{b['hit_rate']:.1f}%</td>")
        parts.append(f"<td class='num'><strong>{fmt_money(b['cost'])}</strong></td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    parts.append("</section>")

    # By project
    parts.append("<section>")
    parts.append("<h2>Top Projects (cwd)</h2>")
    parts.append("<table>")
    parts.append("<thead><tr><th>Project</th><th class='num'>Turns</th><th class='num'>Total</th></tr></thead>")
    parts.append("<tbody>")
    for cwd, b in cwd_rows:
        short = cwd if len(cwd) <= 60 else "…" + cwd[-58:]
        parts.append("<tr>")
        parts.append(f"<td><span class='skill-name'>{escape(short)}</span></td>")
        parts.append(f"<td class='num'>{fmt_int(b['n'])}</td>")
        parts.append(f"<td class='num'><strong>{fmt_money(b['cost'])}</strong></td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    parts.append("</section>")

    # Daily
    parts.append("<section>")
    parts.append("<h2>Daily Breakdown</h2>")
    parts.append("<table>")
    parts.append("<thead><tr><th>Date</th><th class='num'>Turns</th><th class='num'>Hit %</th><th class='num'>Cost</th></tr></thead>")
    parts.append("<tbody>")
    for date, b in date_rows:
        if date == "_":
            continue
        parts.append("<tr>")
        parts.append(f"<td>{escape(date)}</td>")
        parts.append(f"<td class='num'>{fmt_int(b['n'])}</td>")
        parts.append(f"<td class='num dim-cell'>{b['hit_rate']:.1f}%</td>")
        parts.append(f"<td class='num'><strong>{fmt_money(b['cost'])}</strong></td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    parts.append("</section>")

    # Sidechain
    parts.append("<section>")
    parts.append("<h2>Subagent vs Main Session</h2>")
    parts.append("<table>")
    parts.append("<thead><tr><th>Layer</th><th class='num'>Turns</th><th class='num'>Cache read</th><th class='num'>Total</th></tr></thead>")
    parts.append("<tbody>")
    for label, b in sorted(by_chain.items(), key=lambda kv: -kv[1]["cost"]):
        parts.append("<tr>")
        parts.append(f"<td>{escape(label)}</td>")
        parts.append(f"<td class='num'>{fmt_int(b['n'])}</td>")
        parts.append(f"<td class='num dim-cell'>{fmt_tokens(b['cr'])}</td>")
        parts.append(f"<td class='num'><strong>{fmt_money(b['cost'])}</strong></td>")
        parts.append("</tr>")
    parts.append("</tbody></table>")
    parts.append("</section>")

    # Cache TTL
    parts.append("<section>")
    parts.append("<h2>Cache TTL Split (informational)</h2>")
    total_cw = totals["cw_1h"] + totals["cw_5m"]
    pct_1h = (totals["cw_1h"] / total_cw * 100) if total_cw else 0
    pct_5m = (totals["cw_5m"] / total_cw * 100) if total_cw else 0
    parts.append("<table>")
    parts.append("<thead><tr><th>TTL</th><th class='num'>Tokens written</th><th class='num'>Share</th></tr></thead>")
    parts.append("<tbody>")
    parts.append(f"<tr><td>1 hour ephemeral</td><td class='num'>{fmt_tokens(totals['cw_1h'])}</td><td class='num dim-cell'>{pct_1h:.1f}%</td></tr>")
    parts.append(f"<tr><td>5 minute ephemeral</td><td class='num'>{fmt_tokens(totals['cw_5m'])}</td><td class='num dim-cell'>{pct_5m:.1f}%</td></tr>")
    parts.append("</tbody></table>")
    parts.append("<p style='font-size:12px;color:#94a3b8;margin-top:8px;'>1h is 1.6× the per-token write cost of 5m. The split is decided automatically by the Claude Code harness; there is currently no user-side configuration. Reported for awareness only.</p>")
    parts.append("</section>")

    # Diagnosis placeholder (injected by audit-tokens Step 3.5 via scripts/diagnose.py)
    parts.append("<!-- DIAGNOSIS -->")

    # Footer
    parts.append("<footer>")
    parts.append("<p>Pricing reflects Anthropic public list prices for Claude Opus 4.7 / Sonnet 4.6 / Haiku 4.5 as of 2026-05. On flat-rate plans the dollar figures are notional — use them as relative ranking, not actual billing.</p>")
    parts.append("<p>Cost-posture heuristic: see <code>skill-master/skills/plugin-master/cost-posture.md</code> in the indie-toolkit repo.</p>")
    parts.append("<p>Data source: <code>~/.claude/projects/*/*.jsonl</code> filtered by mtime within window. Deduped by requestId.</p>")
    parts.append("</footer>")

    parts.append("</main>")
    parts.append("</body></html>")
    return "\n".join(parts)


# ----------------------------------------------------------------------------
# Entry point
# ----------------------------------------------------------------------------


def main():
    if len(sys.argv) != 4:
        print("usage: generate_report.py <tsv_path> <html_out_path> <days>", file=sys.stderr)
        sys.exit(2)

    tsv_path, html_out, days_str = sys.argv[1], sys.argv[2], sys.argv[3]
    try:
        days = int(days_str)
    except ValueError:
        print(f"error: days must be integer, got: {days_str}", file=sys.stderr)
        sys.exit(2)

    rows = load_tsv(tsv_path)
    if len(rows) < 10:
        print(f"error: only {len(rows)} usable rows in TSV — window too narrow or no usage", file=sys.stderr)
        sys.exit(3)

    candidates = scan_skills_for_gaps(rows)

    html = render(rows, days, candidates)
    Path(html_out).write_text(html, encoding="utf-8")
    print(html_out)


if __name__ == "__main__":
    main()
