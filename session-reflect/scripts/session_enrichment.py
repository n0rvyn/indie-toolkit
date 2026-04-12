#!/usr/bin/env python3
"""Enrichment helpers for session-reflect.

Architecture C (2026-04-12): plugin scripts do NOT invoke LLM APIs or the
Claude CLI. Heuristic (rule-based) audit runs locally; LLM-based dimension
enrichment is deferred to `/reflect --enrich`, which dispatches the
session-parser agent via the host Claude Code session.

Covered heuristic rules (subset of claude-md-rule-enumeration.md):
- style-zh-banwords          -- Chinese banned buzzwords in assistant prose
- style-en-banwords          -- English banned words / fluff phrases
- style-no-opening-agreement -- "你说得对" / "Great question" openings
- behavior-no-ask-what-code-can-answer -- Read-heavy session with no edits

All remaining rules (LLM-classification) stay unpopulated until the
session-parser agent runs via /reflect --enrich.
"""

from pathlib import Path

from analyzer_version import ANALYZER_VERSION

TOP_LEVEL_ENRICH_FIELDS = (
    "session_dna",
    "task_summary",
    "corrections",
    "emotion_signals",
    "prompt_assessments",
    "process_gaps",
    "ai_behavior_audit",
)

ZH_BANWORDS = (
    "可能", "也许", "或许", "应该",
    "赋能", "抓手",
    "打通", "闭环", "链路",
    "沉淀", "复盘",
    "对齐", "拉齐",
    "颗粒度",
    "底层逻辑", "方法论",
    "触达",
)

ZH_OPENING_AGREEMENT = (
    "你说得对", "确实", "没错", "好。", "好的。", "明白。", "理解。",
)
EN_OPENING_AGREEMENT = (
    "Great question", "Absolutely", "You're right",
)

EN_BANWORDS = (
    "utilize", "leverage",
    "robust", "seamless", "numerous", "facilitate",
    "best practices",
)

EN_FILLER = (
    "in conclusion", "hope this helps",
)


def build_system_prompt():
    """Assemble the session-parser agent prompt plus the Phase 2 rule reference.

    Used by `/reflect --enrich` when dispatching the session-parser agent via
    the Task tool. Never used by this module to invoke the CLI.
    """
    base_dir = Path(__file__).resolve().parent.parent
    agent_prompt = (base_dir / "agents" / "session-parser.md").read_text()
    rule_reference = (base_dir / "references" / "claude-md-rule-enumeration.md").read_text()
    return (
        f"{agent_prompt}\n\n"
        "## AI Behavior Audit Rule Reference\n\n"
        "Use the following rule contract for `ai_behavior_audit`. "
        "Return `rule_id` values exactly as listed here.\n\n"
        f"{rule_reference}\n"
    )


def _scan_style_zh(turn_idx, text):
    out = []
    for word in ZH_BANWORDS:
        if word in text:
            out.append({
                "turn": turn_idx,
                "rule_category": "style",
                "rule_id": "style-zh-banwords",
                "hit": 1,
                "evidence": f"Chinese banword: {word}",
            })
    return out


def _scan_style_en(turn_idx, text):
    out = []
    lowered = text.lower()
    for word in EN_BANWORDS:
        if word in lowered:
            out.append({
                "turn": turn_idx,
                "rule_category": "style",
                "rule_id": "style-en-banwords",
                "hit": 1,
                "evidence": f"English banword: {word}",
            })
    for phrase in EN_FILLER:
        if phrase in lowered:
            out.append({
                "turn": turn_idx,
                "rule_category": "style",
                "rule_id": "style-en-banwords",
                "hit": 1,
                "evidence": f"English filler: {phrase}",
            })
    return out


def _scan_opening_agreement(turn_idx, text):
    stripped = text.lstrip()
    for phrase in ZH_OPENING_AGREEMENT + EN_OPENING_AGREEMENT:
        if stripped.startswith(phrase):
            return [{
                "turn": turn_idx,
                "rule_category": "style",
                "rule_id": "style-no-opening-agreement",
                "hit": 1,
                "evidence": f"Opening with: {phrase}",
            }]
    return []


def _scan_read_only_session(result):
    """behavior-no-ask-what-code-can-answer: heuristic flag."""
    seq = result.get("tools", {}).get("sequence", []) or []
    if not seq:
        return []
    reads = sum(1 for t in seq if t == "Read")
    edits = sum(1 for t in seq if t in ("Edit", "Write", "NotebookEdit"))
    user_turns = result.get("turns", {}).get("user", 0) or 0
    if reads >= 5 and edits == 0 and user_turns >= 2:
        return [{
            "turn": None,
            "rule_category": "behavior",
            "rule_id": "behavior-no-ask-what-code-can-answer",
            "hit": 1,
            "evidence": f"Read-heavy ({reads} reads) with no edits across {user_turns} user turns; verify assistant did not defer answerable facts to user.",
        }]
    return []


def run_rule_based_audit(result):
    """Scan a parsed session for heuristic (non-LLM) rule violations.

    Returns a list of `ai_behavior_audit` row dicts. Safe to call on any
    parsed session; returns [] when no assistant-turn text is available.
    """
    audit = []
    for turn in result.get("assistant_turns", []) or []:
        turn_idx = turn.get("turn")
        text = turn.get("text") or ""
        if not text:
            continue
        audit.extend(_scan_style_zh(turn_idx, text))
        audit.extend(_scan_style_en(turn_idx, text))
        audit.extend(_scan_opening_agreement(turn_idx, text))
    audit.extend(_scan_read_only_session(result))
    return audit


def apply_enrichment(result, db_path=None):
    """Apply rule-based audit to a parsed session and mark LLM enrichment pending.

    This function never spawns subprocesses or calls external APIs. When a DB
    path is given, it writes the heuristic audit rows and sets
    `sessions.enrichment_pending = 1` so `/reflect --enrich` can finish the
    LLM portion later via the session-parser agent.

    Returns `(enriched_result, warning_message)`. warning_message is None on
    success (it can be non-None when a future implementation needs to surface
    partial failures; kept for signature back-compat).
    """
    enriched = dict(result)
    enriched["analyzer_version"] = ANALYZER_VERSION
    audit_rows = run_rule_based_audit(result)
    enriched["ai_behavior_audit"] = audit_rows
    enriched["enrichment_pending"] = 1

    if db_path:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import sessions_db

        original_db_path = sessions_db.DB_PATH
        sessions_db.DB_PATH = Path(db_path)
        try:
            sessions_db.init_db()
            sessions_db.upsert_ai_behavior_audit(enriched["session_id"], audit_rows)
            sessions_db.set_enrichment_pending(enriched["session_id"], pending=1)
        finally:
            sessions_db.DB_PATH = original_db_path

    return enriched, None
