"""
vibehack/memory/db.py — SQLite-based Long-Term Memory (LTM).

Stores and retrieves "experience fragments" from past security sessions.
This is the Alpha implementation. Vector/RAG search is planned for v1.0 (Q1 2027).
"""
import sqlite3
from datetime import datetime
from vibehack.config import cfg

MEMORY_DB = cfg.MEMORY_DB


def init_memory():
    """Initialize the SQLite schema. Idempotent — safe to call every startup."""
    cfg.HOME.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(MEMORY_DB)
    cur = conn.cursor()
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS experience (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            target       TEXT    NOT NULL,
            technology   TEXT    NOT NULL DEFAULT 'unknown',
            payload      TEXT    NOT NULL,
            result_score INTEGER NOT NULL DEFAULT 0,
            summary      TEXT,
            timestamp    TEXT    NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_tech ON experience(technology);
        CREATE INDEX IF NOT EXISTS idx_score ON experience(result_score);
    """)
    conn.commit()
    conn.close()


def record_experience(
    target: str,
    tech: str,
    payload: str,
    score: int,
    summary: str,
) -> int:
    """
    Persist one experience fragment.
    score: +1 = success/finding, -1 = failure/blocked, 0 = neutral
    Returns the row id.
    """
    conn = sqlite3.connect(MEMORY_DB)
    cur = conn.cursor()
    cur.execute(
        """INSERT INTO experience
           (target, technology, payload, result_score, summary, timestamp)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (target, tech, payload, score, summary, datetime.now().isoformat()),
    )
    row_id = cur.lastrowid
    conn.commit()
    conn.close()
    return row_id


def search_experience(tech: str, limit: int = 5) -> list[tuple]:
    """
    Retrieve the most recent relevant experiences for a technology keyword.
    Returns list of (payload, result_score, summary) tuples.
    Alpha: keyword LIKE search. v1.0: vector similarity search.
    """
    conn = sqlite3.connect(MEMORY_DB)
    cur = conn.cursor()
    cur.execute(
        """SELECT payload, result_score, summary
           FROM experience
           WHERE technology LIKE ?
           ORDER BY timestamp DESC
           LIMIT ?""",
        (f"%{tech}%", limit),
    )
    results = cur.fetchall()
    conn.close()
    return results


def get_memory_context(tech: str) -> str:
    """
    Build a human-readable memory context block for LLM injection.
    Returns an empty string if no relevant experiences exist.
    """
    experiences = search_experience(tech)
    if not experiences:
        return ""

    lines = [f"\n### [Long-Term Memory] Past experiences with '{tech}':"]
    for payload, score, summary in experiences:
        label = "✅ Worked" if score > 0 else ("❌ Failed" if score < 0 else "ℹ Neutral")
        lines.append(f"- {label}: `{payload[:100]}` → {summary}")
    lines.append("Use this to avoid repeating failed approaches and build on successes.\n")
    return "\n".join(lines)


def get_memory_stats() -> dict:
    """Return summary statistics for the LTM database."""
    conn = sqlite3.connect(MEMORY_DB)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*), SUM(CASE WHEN result_score > 0 THEN 1 ELSE 0 END) FROM experience")
    total, successes = cur.fetchone()
    conn.close()
    return {
        "total": total or 0,
        "successes": successes or 0,
        "failures": (total or 0) - (successes or 0),
    }
