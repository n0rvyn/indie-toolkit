#!/usr/bin/env python3
"""Cross-session linking for session-reflect Phase 3."""

import math
import re
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import sessions_db  # noqa: E402

TOKEN_PATTERN = re.compile(r"[a-z0-9_]+")
SUMMARY_STOPWORDS = {
    "a", "an", "and", "the", "for", "to", "of", "on", "in", "with",
    "fix", "add", "update", "work", "continue", "finish", "tests",
    "test", "task", "session", "issue", "bug", "code", "tool",
}
GAP_SECONDS = 4 * 60 * 60
CONTINUATION_SCORE_MIN = 1.1
RELATED_SCORE_MIN = 0.95
RELATED_SCORE_RATIO = 0.88


def tokenize_summary(text):
    """Tokenize and normalize task_summary text."""
    tokens = []
    for token in TOKEN_PATTERN.findall((text or "").lower()):
        if token in SUMMARY_STOPWORDS:
            continue
        tokens.append(token)
    return tokens


def tool_terms(sequence):
    """Build lexical terms from ordered tool sequence."""
    terms = []
    lowered = [tool.lower() for tool in sequence]
    for tool in lowered:
        terms.append(f"tool_{tool}")
    for idx in range(len(lowered) - 1):
        terms.append(f"toolpair_{lowered[idx]}_{lowered[idx + 1]}")
    return terms


class BM25Index:
    """Minimal Okapi BM25 implementation for a small in-memory corpus."""

    def __init__(self, docs, k1=1.5, b=0.75):
        self.docs = docs
        self.k1 = k1
        self.b = b
        self.doc_freq = {}
        self.avgdl = 0.0
        lengths = []
        for tokens in docs:
            lengths.append(len(tokens))
            for token in set(tokens):
                self.doc_freq[token] = self.doc_freq.get(token, 0) + 1
        self.doc_lengths = lengths
        self.avgdl = sum(lengths) / len(lengths) if lengths else 0.0
        self.doc_count = len(docs)

    def score(self, query_tokens, doc_index):
        tokens = self.docs[doc_index]
        if not tokens or not query_tokens:
            return 0.0
        tf = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1
        score = 0.0
        doc_len = self.doc_lengths[doc_index]
        for token in query_tokens:
            if token not in tf:
                continue
            df = self.doc_freq.get(token, 0)
            idf = math.log(1 + (self.doc_count - df + 0.5) / (df + 0.5))
            numerator = tf[token] * (self.k1 + 1)
            denominator = tf[token] + self.k1 * (1 - self.b + self.b * (doc_len / self.avgdl if self.avgdl else 0))
            score += idf * (numerator / denominator)
        return score


def build_session_docs(session_rows, tool_sequences):
    """Build lexical docs for BM25 scoring."""
    docs = {}
    for row in session_rows:
        summary_tokens = tokenize_summary(row.get("task_summary"))
        docs[row["session_id"]] = {
            "summary_tokens": summary_tokens,
            "doc_tokens": summary_tokens + tool_terms(tool_sequences.get(row["session_id"], [])),
        }
    return docs


def _parse_time(timestamp):
    if not timestamp:
        return None
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def _score_to_confidence(score):
    if score <= 0:
        return 0.0
    return round(score / (score + 2.5), 3)


def build_links(session_rows, tool_sequences):
    """Build continuation/related edges for the provided sessions."""
    ordered = sorted(session_rows, key=lambda row: (row.get("time_start") or "", row.get("session_id")))
    docs = build_session_docs(ordered, tool_sequences)
    links = []

    for index, source in enumerate(ordered):
        source_id = source["session_id"]
        source_summary = docs[source_id]["summary_tokens"]
        if not source_summary:
            continue

        candidate_rows = []
        for target in ordered[index + 1:]:
            if source.get("project") != target.get("project"):
                continue
            if source.get("branch") != target.get("branch"):
                continue
            source_time = _parse_time(source.get("time_start"))
            target_time = _parse_time(target.get("time_start"))
            if not source_time or not target_time:
                continue
            if (target_time - source_time).total_seconds() >= GAP_SECONDS:
                break
            shared_summary = set(source_summary) & set(docs[target["session_id"]]["summary_tokens"])
            if not shared_summary:
                continue
            candidate_rows.append(target)

        if not candidate_rows:
            continue

        corpus = [docs[target["session_id"]]["doc_tokens"] for target in candidate_rows]
        indexer = BM25Index(corpus)
        scores = []
        query_tokens = docs[source_id]["doc_tokens"]
        for idx, target in enumerate(candidate_rows):
            score = indexer.score(query_tokens, idx)
            scores.append((score, target))
        scores.sort(key=lambda item: (-item[0], item[1]["session_id"]))
        best_score, best_target = scores[0]
        if best_score < CONTINUATION_SCORE_MIN:
            continue

        links.append({
            "source_session_id": source_id,
            "target_session_id": best_target["session_id"],
            "link_type": "continuation",
            "confidence": _score_to_confidence(best_score),
        })

        for score, target in scores[1:]:
            if score < RELATED_SCORE_MIN:
                continue
            if score < best_score * RELATED_SCORE_RATIO:
                continue
            links.append({
                "source_session_id": source_id,
                "target_session_id": target["session_id"],
                "link_type": "related",
                "confidence": _score_to_confidence(score),
            })

    return links


def recompute_session_links(target_session_ids=None, db_path=None):
    """Rebuild links for all sessions or for the project/branch neighborhoods around target_session_ids."""
    if db_path:
        sessions_db.set_db_path(db_path)

    all_sessions = sessions_db.get_sessions_for_linking()
    if not all_sessions:
        return {"source_sessions": 0, "links_written": 0}

    scoped_sessions = all_sessions
    if target_session_ids:
        target_pairs = {
            (row.get("project"), row.get("branch"))
            for row in all_sessions
            if row.get("session_id") in set(target_session_ids)
        }
        scoped_sessions = [
            row for row in all_sessions
            if (row.get("project"), row.get("branch")) in target_pairs
        ]

    if not scoped_sessions:
        return {"source_sessions": 0, "links_written": 0}

    source_ids = [row["session_id"] for row in scoped_sessions]
    tool_sequences = sessions_db.get_tool_sequences(source_ids)
    links = build_links(scoped_sessions, tool_sequences)
    sessions_db.replace_session_links(source_ids, links)
    return {
        "source_sessions": len(source_ids),
        "links_written": len(links),
    }
