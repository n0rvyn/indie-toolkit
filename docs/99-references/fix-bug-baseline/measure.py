#!/usr/bin/env python3
"""Measure fix-bug episodes in local Claude Code transcripts.

Rerun unchanged for the before/after audit:
    python3 measure.py --since 2026-08-05 --until 2026-09-23   # baseline
    python3 measure.py --since <change date>                    # after

Episode: starts at a fix-bug invocation (model Skill call, or user-typed
/fix-bug, or /dev-workflow:fix-bug), ends at the next fix-bug invocation in the
same session, a gap of more than 30 idle minutes, or the session end.

Per episode: wall minutes, main-session USD, subagent USD (sidechain transcripts
whose first record falls inside the episode), main tool calls, subagents
dispatched, human turns, frustration hits from ~/.claude/fuck-moments.jsonl.

USD uses the price table below (repo 2026-06 list: Opus 4.8 / Sonnet 4.6 /
Haiku 4.5). Keep it unchanged between runs so the numbers stay comparable.
"""
import argparse, glob, json, os, re, statistics
from datetime import datetime, timedelta

P = {"opus": (5, 6.25, 10, .5, 25), "sonnet": (3, 3.75, 6, .3, 15), "haiku": (1, 1.25, 2, .1, 5)}
IDLE = timedelta(minutes=30)
ROOT = os.path.expanduser("~/.claude/projects")


def fam(m):
    m = (m or "").lower()
    return next((k for k in P if k in m), "opus")


def cost(model, u):
    p = P[fam(model)]
    cc = u.get("cache_creation") or {}
    cw1 = cc.get("ephemeral_1h_input_tokens", 0)
    cw5 = cc.get("ephemeral_5m_input_tokens", 0) if cc else u.get("cache_creation_input_tokens", 0)
    return (u.get("input_tokens", 0) * p[0] + cw5 * p[1] + cw1 * p[2]
            + u.get("cache_read_input_tokens", 0) * p[3] + u.get("output_tokens", 0) * p[4]) / 1e6


def ts(d):
    t = d.get("timestamp")
    return datetime.fromisoformat(t.replace("Z", "+00:00")) if t else None


def is_invocation(d):
    m = d.get("message") or {}
    c = m.get("content")
    if d.get("type") == "assistant" and isinstance(c, list):
        return any(b.get("type") == "tool_use" and b.get("name") == "Skill"
                   and b.get("input", {}).get("skill", "").split(":")[-1] == "fix-bug" for b in c)
    if d.get("type") == "user" and not d.get("isSidechain"):
        s = c if isinstance(c, str) else json.dumps(c, ensure_ascii=False) if c else ""
        return bool(re.search(r"<command-name>/(dev-workflow:)?fix-bug</command-name>", s))
    return False


def human_turn(d):
    if d.get("type") != "user" or d.get("isMeta") or d.get("isSidechain"):
        return False
    c = (d.get("message") or {}).get("content")
    return isinstance(c, str) and not c.startswith("<")


def sub_costs(session_dir):
    out = []
    for f in glob.glob(os.path.join(session_dir, "subagents", "**", "*.jsonl"), recursive=True):
        seen, first = {}, None
        for line in open(f, errors="ignore"):
            try:
                d = json.loads(line)
            except ValueError:
                continue
            first = first or ts(d)
            m = d.get("message") or {}
            if d.get("type") == "assistant" and m.get("usage"):
                seen[m.get("id")] = (m.get("model"), m["usage"])
        if first:
            out.append((first, sum(cost(a, u) for a, u in seen.values())))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", default="2999-01-01")
    a = ap.parse_args()
    lo = datetime.fromisoformat(a.since + "T00:00:00+00:00")
    hi = datetime.fromisoformat(a.until + "T00:00:00+00:00")
    rage = []
    fm = os.path.expanduser("~/.claude/fuck-moments.jsonl")
    if os.path.exists(fm):
        for line in open(fm):
            try:
                r = json.loads(line)
                rage.append((r["session"], datetime.fromisoformat(r["ts"])))
            except (ValueError, KeyError):
                pass
    eps = []
    for f in glob.glob(os.path.join(ROOT, "*", "*.jsonl")):
        # scratchpad projects are probe/eval runs, not real bug work
        if "scratchpad" in f or "fix-bug" not in open(f, errors="ignore").read():
            continue
        L = []
        for line in open(f, errors="ignore"):
            try:
                L.append(json.loads(line))
            except ValueError:
                pass
        starts = [i for i, d in enumerate(L) if is_invocation(d) and ts(d) and lo <= ts(d) < hi]
        if not starts:
            continue
        subs = sub_costs(f[:-6])
        sid = os.path.basename(f)[:8]
        for n, i in enumerate(starts):
            stop = starts[n + 1] if n + 1 < len(starts) else len(L)
            t0 = last = ts(L[i])
            usd, tools, agents, humans, seen = 0.0, 0, 0, 0, set()
            for d in L[i:stop]:
                t = ts(d)
                if t and t - last > IDLE:
                    break
                if t:
                    last = t
                m = d.get("message") or {}
                if d.get("type") == "assistant" and not d.get("isSidechain"):
                    if m.get("usage") and m.get("id") not in seen:
                        seen.add(m.get("id"))
                        usd += cost(m.get("model"), m["usage"])
                    for b in m.get("content") or []:
                        if isinstance(b, dict) and b.get("type") == "tool_use":
                            tools += 1
                            agents += b.get("name") in ("Agent", "Task", "Workflow")
                humans += human_turn(d)
            sub = sum(c for t, c in subs if t0 <= t <= last)
            loc = lambda x: x.astimezone().replace(tzinfo=None)
            # the log stores either the 8-char prefix or the full session id
            hits = sum(1 for s, t in rage if s[:8] == sid and loc(t0) <= t <= loc(last))
            eps.append(dict(session=sid, project=f.split("/")[-2][-24:], start=t0.isoformat()[:16],
                            minutes=round((last - t0).total_seconds() / 60, 1), main_usd=round(usd, 2),
                            sub_usd=round(sub, 2), tools=tools, agents=agents, human_turns=humans, frustration=hits))
    eps.sort(key=lambda e: e["start"])
    for e in eps:
        print(json.dumps(e, ensure_ascii=False))
    if eps:
        tot = [e["main_usd"] + e["sub_usd"] for e in eps]
        med = lambda k: statistics.median(e[k] for e in eps)
        print(f"# episodes={len(eps)} median_usd={statistics.median(tot):.2f} mean_usd={statistics.mean(tot):.2f} "
              f"median_min={med('minutes')} median_tools={med('tools')} median_agents={med('agents')} "
              f"median_human_turns={med('human_turns')} "
              f"episodes_with_frustration={sum(e['frustration'] > 0 for e in eps)}")


if __name__ == "__main__":
    main()
