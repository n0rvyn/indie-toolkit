#!/usr/bin/env python3
"""
diagnose.py — root-cause attribution for top expensive audit-tokens sessions.

Usage:
  python3 diagnose.py <tsv_path>               # output HTML fragment to stdout
  python3 diagnose.py <tsv_path> <html_out>    # write HTML fragment to file

TSV columns (14): sessionId, requestId, attributionSkill, attributionPlugin,
  model, input_tokens, cache_creation, cache_read, output_tokens,
  ephemeral_1h, ephemeral_5m, isSidechain, cwd, timestamp

Computes 4 root-cause categories per top-N session:
  - Skill gap        (TSV-derived: >50% of cost outside any skill)
  - Cache bloat      (TSV-derived: avg cache_read >250K AND max >500K)
  - Sub-agent miss   (jsonl-derived: ≥2 consecutive main-session mechanical Bash with no Agent dispatch within 5 events after)
  - Read pollution   (jsonl-derived: same file Read ≥3 times by main session)

The latter two require the source session jsonl files; if the jsonl for a session
cannot be located under ~/.claude/projects/<encoded-cwd>/<sessionId>.jsonl, those
attributions are skipped for that session (fail-open, never crashes).
"""

import sys
import csv
import os
import re
import json
from pathlib import Path
from collections import defaultdict
from html import escape


# Pricing constants (Anthropic public list 2026-05, per million tokens).
# Keyed by model FAMILY (substring match), not full model id — model strings
# in the wild have suffixes (`claude-opus-4-7[1m]`) and version variants
# (`claude-sonnet-4-5`) that exact-match would miss.
PRICE_PER_M = {
    "opus":    {"input": 15.0, "cw5": 18.75, "cw1": 30.0, "cache_read": 1.5,  "output": 75.0},
    "sonnet":  {"input": 3.0,  "cw5": 3.75,  "cw1": 6.0,  "cache_read": 0.3,  "output": 15.0},
    "haiku":   {"input": 0.8,  "cw5": 1.0,   "cw1": 1.6,  "cache_read": 0.08, "output": 4.0},
    "unknown": {"input": 15.0, "cw5": 18.75, "cw1": 30.0, "cache_read": 1.5,  "output": 75.0},
}


def classify_model(m: str) -> str:
    """Substring family match — mirrors audit-tokens generate_report.py."""
    if not m:
        return "unknown"
    m_lower = m.lower()
    if "opus" in m_lower:
        return "opus"
    if "sonnet" in m_lower:
        return "sonnet"
    if "haiku" in m_lower:
        return "haiku"
    return "unknown"


def safe_int(v):
    try:
        return int(v)
    except (ValueError, TypeError):
        return 0


def row_cost(row):
    """Compute per-row cost using family-matched pricing and 1h/5m cache split."""
    fam = classify_model(row.get("model", ""))
    prices = PRICE_PER_M[fam]
    m = 1_000_000
    # Split cache_creation into 1h and 5m components when available
    cw1 = safe_int(row.get("ephemeral_1h"))
    cw5_explicit = safe_int(row.get("ephemeral_5m"))
    cw_total = safe_int(row.get("cache_creation"))
    if cw1 == 0 and cw5_explicit == 0:
        # No split data — treat whole cache_creation as 5m (conservative for cost)
        cw5 = cw_total
    else:
        cw5 = cw5_explicit
    return (
        safe_int(row.get("input_tokens")) * prices["input"] / m
        + cw5 * prices["cw5"] / m
        + cw1 * prices["cw1"] / m
        + safe_int(row.get("cache_read")) * prices["cache_read"] / m
        + safe_int(row.get("output_tokens")) * prices["output"] / m
    )


def load_tsv(path):
    COLS = [
        "sessionId", "requestId", "attributionSkill", "attributionPlugin",
        "model", "input_tokens", "cache_creation", "cache_read", "output_tokens",
        "ephemeral_1h", "ephemeral_5m", "isSidechain", "cwd", "timestamp",
    ]
    rows = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t")
            for line in reader:
                if not line or all(c == "" for c in line):
                    continue
                row = {}
                for i, col in enumerate(COLS):
                    row[col] = line[i] if i < len(line) else ""
                rows.append(row)
    except FileNotFoundError:
        pass
    return rows


def aggregate_sessions(rows):
    """Group rows by sessionId, compute per-session stats."""
    sessions = defaultdict(lambda: {
        "cost": 0.0,
        "rows": [],
        "no_skill_cost": 0.0,
        "total_cache_read": 0,
        "max_cache_read": 0,
        "row_count": 0,
        "cwd": "",
    })
    for row in rows:
        sid = row.get("sessionId", "")
        c = row_cost(row)
        sessions[sid]["cost"] += c
        sessions[sid]["rows"].append(row)
        sessions[sid]["row_count"] += 1
        cr = safe_int(row.get("cache_read"))
        sessions[sid]["total_cache_read"] += cr
        if cr > sessions[sid]["max_cache_read"]:
            sessions[sid]["max_cache_read"] = cr
        skill = row.get("attributionSkill", "")
        if skill in ("", "_none_", "none"):
            sessions[sid]["no_skill_cost"] += c
        # Record cwd from any row (they should be consistent within a session)
        if not sessions[sid]["cwd"] and row.get("cwd"):
            sessions[sid]["cwd"] = row.get("cwd", "")
    return sessions


# ----- ARCH-1: jsonl-derived attribution helpers -----

MECHANICAL_PATTERNS_RE = [
    re.compile(r'^sqlite3\s+\S+\s+["\']?SELECT', re.IGNORECASE),
    re.compile(r'^curl\s+-s\s+https?://'),
    re.compile(r'^grep\s+-r'),
    re.compile(r'^find\s+'),
]


def is_mechanical_bash(cmd: str) -> bool:
    cmd = cmd.strip()
    for r in MECHANICAL_PATTERNS_RE:
        if r.match(cmd):
            return True
    return False


def encode_cwd_to_project_dir(cwd: str) -> str:
    """Mirror Claude's projects-dir naming: /Users/foo/Bar -> -Users-foo-Bar."""
    return cwd.replace('/', '-')


def find_session_jsonl(cwd: str, sid: str):
    """Locate the session jsonl under ~/.claude/projects/. Returns path or None."""
    if not cwd or not sid:
        return None
    enc = encode_cwd_to_project_dir(cwd)
    p = Path.home() / '.claude' / 'projects' / enc / f'{sid}.jsonl'
    return str(p) if p.exists() else None


def scan_jsonl_for_events(jsonl_path: str) -> dict:
    """Walk the session jsonl and return:
       - subagent_miss_count: # runs of ≥2 consecutive main-session mechanical Bash
         WITHOUT an Agent dispatch in the next 5 tool_use events after the run.
       - read_pollution_files: {file_path: count} for files Read ≥3× by main session.

    On any I/O or parse error: returns zeroed dict (fail-open).
    """
    result = {"subagent_miss_count": 0, "read_pollution_files": {}}
    if not jsonl_path:
        return result

    events = []  # (is_sidechain: bool, tool_name: str, payload: str)
    try:
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("type") != "assistant":
                    continue
                is_side = bool(rec.get("isSidechain", False))
                content = rec.get("message", {}).get("content", [])
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    name = block.get("name", "")
                    inp = block.get("input", {}) or {}
                    if name == "Bash":
                        events.append((is_side, "Bash", inp.get("command", "")))
                    elif name == "Read":
                        events.append((is_side, "Read", inp.get("file_path", "")))
                    elif name == "Agent":
                        events.append((is_side, "Agent", inp.get("subagent_type", "")))
    except (OSError, IOError):
        return result

    # Sub-agent miss: runs of ≥2 consecutive main mechanical Bash w/o Agent within next 5 events
    i = 0
    misses = 0
    while i < len(events):
        is_side, name, payload = events[i]
        if name == "Bash" and (not is_side) and is_mechanical_bash(payload):
            j = i + 1
            run = 1
            while j < len(events):
                jis, jname, jpayload = events[j]
                if jname == "Bash" and (not jis) and is_mechanical_bash(jpayload):
                    run += 1
                    j += 1
                else:
                    break
            if run >= 2:
                lookahead = events[j:j + 5]
                if not any(ev[1] == "Agent" for ev in lookahead):
                    misses += 1
            i = max(j, i + 1)
        else:
            i += 1
    result["subagent_miss_count"] = misses

    # Read pollution: files Read ≥3× by main session
    read_counts = defaultdict(int)
    for is_side, name, payload in events:
        if name == "Read" and (not is_side) and payload:
            read_counts[payload] += 1
    result["read_pollution_files"] = {fp: cnt for fp, cnt in read_counts.items() if cnt >= 3}

    return result


# ----- attribution + HTML emission -----


def classify_session(sid, info):
    """Return list of (category_name, detail_str) tuples for a session.
    Combines TSV-derived categories (Skill gap, Cache bloat) with jsonl-derived
    ones (Sub-agent miss, Read pollution) when the source jsonl is locatable.
    """
    attributions = []
    rows = info["rows"]
    n = len(rows)
    if n == 0:
        return attributions

    # --- TSV-derived ---
    if info["cost"] > 0 and (info["no_skill_cost"] / info["cost"]) > 0.50:
        pct = int(100 * info["no_skill_cost"] / info["cost"])
        attributions.append(("Skill gap", f"{pct}% of session cost ran outside any skill"))

    avg_cr = info["total_cache_read"] / n if n > 0 else 0
    if avg_cr > 250_000 and info["max_cache_read"] > 500_000:
        attributions.append((
            "Cache bloat",
            f"avg cache_read {avg_cr/1000:.0f}K, max {info['max_cache_read']/1000:.0f}K tokens — session context grew large without /clear"
        ))

    # --- jsonl-derived (ARCH-1) ---
    jsonl_path = find_session_jsonl(info["cwd"], sid)
    if jsonl_path:
        events = scan_jsonl_for_events(jsonl_path)
        miss = events["subagent_miss_count"]
        if miss >= 1:
            attributions.append((
                "Sub-agent miss",
                f"{miss} run(s) of ≥2 consecutive main-line mechanical探查 Bash with no Agent dispatch — should have been batched via Agent(subagent_type=general-purpose)"
            ))
        polluted = events["read_pollution_files"]
        if polluted:
            top = max(polluted.items(), key=lambda kv: kv[1])
            extra = f" (and {len(polluted) - 1} more file(s))" if len(polluted) > 1 else ""
            attributions.append((
                "Read pollution",
                f"{os.path.basename(top[0])} Read {top[1]}× by main session{extra} — repeated Read inflates cache_read of every subsequent turn"
            ))
    # If jsonl can't be located, silently skip these two categories (fail-open).

    return attributions


def build_html(sessions_sorted, rows_empty):
    parts = []
    parts.append('<section id="diagnosis">')
    parts.append('<h2>Diagnosis &amp; Suggestions</h2>')

    if rows_empty:
        parts.append('<p class="dim">No diagnosis data — TSV is empty or contains no rows.</p>')
        parts.append('</section>')
        return "\n".join(parts)

    top5 = sessions_sorted[:5]

    all_categories = defaultdict(int)
    session_attributions = []
    for sid, info in top5:
        attrs = classify_session(sid, info)
        session_attributions.append((sid, info, attrs))
        for cat, _ in attrs:
            all_categories[cat] += 1

    parts.append('<p>Top sessions by cost, with root-cause attribution. Sub-agent miss and Read pollution require the source session jsonl (under <code>~/.claude/projects/</code>); when the file is unavailable those rows show only TSV-derived attributions.</p>')
    parts.append('<table>')
    parts.append('<thead><tr><th>Session</th><th>Cost</th><th>Root causes</th></tr></thead>')
    parts.append('<tbody>')
    for sid, info, attrs in session_attributions:
        short_sid = escape(sid[:24] + ("..." if len(sid) > 24 else ""))
        cost_str = f"${info['cost']:.4f}"
        if attrs:
            cat_html = "; ".join(
                f"<strong>{escape(cat)}</strong>: {escape(detail)}"
                for cat, detail in attrs
            )
        else:
            cat_html = "<em>No detectable pattern from TSV or session jsonl</em>"
        parts.append(f'<tr><td><code title="{escape(sid)}">{short_sid}</code></td>'
                     f'<td class="num">{cost_str}</td>'
                     f'<td>{cat_html}</td></tr>')
    parts.append('</tbody>')
    parts.append('</table>')

    parts.append('<h3>Top Actions</h3>')
    parts.append('<ol>')
    action_map = {
        "Skill gap": "Route (no skill) mechanical work through existing skills or sub-agents. Use <code>/distill-project-skills</code> to identify candidates.",
        "Cache bloat": "Add <code>/clear</code> between topic switches to reset context window. Review big-file Reads — replace with Grep/Agent dispatch where intent is Verify or Extract.",
        "Sub-agent miss": "Batch ≥2 consecutive mechanical探查 Bash into a single <code>Agent(subagent_type=general-purpose)</code> dispatch (see CLAUDE.md 成本路由规则). The PreToolUse hook <code>suggest-agent-dispatch.sh</code> nudges via stderr.",
        "Read pollution": "Stop re-reading the same file. Use Grep when intent is Verify, sub-agent Extract when intent is single-region. Reserve main-line Read for Understand-context (per Read 路由 rule in CLAUDE.md).",
    }
    shown = 0
    for cat in ["Skill gap", "Cache bloat", "Sub-agent miss", "Read pollution"]:
        if all_categories.get(cat, 0) > 0 and shown < 3:
            parts.append(f'<li>{action_map[cat]}</li>')
            shown += 1
    if shown == 0:
        parts.append('<li>No high-confidence patterns detected. Run again after more sessions accumulate.</li>')
    parts.append('</ol>')

    parts.append('</section>')
    return "\n".join(parts)


def main():
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print("usage: diagnose.py <tsv_path> [html_out]", file=sys.stderr)
        sys.exit(2)

    tsv_path = sys.argv[1]
    html_out = sys.argv[2] if len(sys.argv) == 3 else None

    rows = load_tsv(tsv_path)
    rows_empty = len(rows) == 0

    sessions = aggregate_sessions(rows)
    sessions_sorted = sorted(sessions.items(), key=lambda kv: kv[1]["cost"], reverse=True)

    html = build_html(sessions_sorted, rows_empty)

    if html_out:
        with open(html_out, "w", encoding="utf-8") as f:
            f.write(html)
    else:
        print(html)


if __name__ == "__main__":
    main()
