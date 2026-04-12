"""
vibehack/memory/db.py — Hardened SQLite-based Long-Term Memory (LTM).
"""
import sqlite3
import contextlib
from datetime import datetime
from vibehack.config import cfg

MEMORY_DB = cfg.MEMORY_DB

@contextlib.contextmanager
def get_db_conn():
    """Context manager for SQLite connections to ensure safe closure."""
    conn = sqlite3.connect(MEMORY_DB)
    try:
        yield conn
    finally:
        conn.close()

def init_memory():
    """Initialize the SQLite schema."""
    cfg.HOME.mkdir(parents=True, exist_ok=True)
    with get_db_conn() as conn:
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

def record_experience(target: str, tech: str, payload: str, score: int, summary: str) -> int:
    """Persist one experience fragment."""
    with get_db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO experience
               (target, technology, payload, result_score, summary, timestamp)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (target, tech, payload, score, summary, datetime.now().isoformat()),
        )
        row_id = cur.lastrowid
        conn.commit()
    return row_id

def search_experience(tech: str, limit: int = 5) -> list[tuple]:
    """Retrieve the most recent relevant experiences."""
    with get_db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """SELECT target, technology, payload, result_score, summary
               FROM experience
               WHERE technology LIKE ?
               ORDER BY timestamp DESC
               LIMIT ?""",
            (f"%{tech}%", limit),
        )
        return cur.fetchall()

def get_memory_context(tech: str) -> str:
    """Build a human-readable memory context block."""
    experiences = search_experience(tech)
    if not experiences:
        return ""

    lines = [f"\n### [Long-Term Memory] Past experiences with '{tech}':"]
    for target, tech, payload, score, summary in experiences:
        label = "✅ Worked" if score > 0 else ("❌ Failed" if score < 0 else "ℹ Neutral")
        lines.append(f"- {label}: `{payload[:100]}` → {summary}")
    lines.append("Use this to avoid repeating failed approaches.\n")
    return "\n".join(lines)

def get_memory_stats() -> dict:
    """Return summary statistics."""
    with get_db_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*), SUM(CASE WHEN result_score > 0 THEN 1 ELSE 0 END) FROM experience")
        total, successes = cur.fetchone()
    
    total = total or 0
    successes = successes or 0
    return {
        "total": total,
        "successes": successes,
        "failures": total - successes,
    }
