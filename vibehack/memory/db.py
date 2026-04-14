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
                embedding    BLOB,
                timestamp    TEXT    NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_tech ON experience(technology);
            CREATE INDEX IF NOT EXISTS idx_score ON experience(result_score);
        """)
        
        # Migration: Add embedding column if it doesn't exist
        cur.execute("PRAGMA table_info(experience)")
        columns = [c[1] for c in cur.fetchall()]
        if "embedding" not in columns:
            cur.execute("ALTER TABLE experience ADD COLUMN embedding BLOB")
            
        conn.commit()


def record_experience(
    target: str, tech: str, payload: str, score: int, summary: str
) -> int:
    """Persist one experience fragment with embedding."""
    embedding = get_embedding(f"{tech} {summary} {payload}")
    
    with get_db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO experience
               (target, technology, payload, result_score, summary, embedding, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (target, tech, payload, score, summary, embedding, datetime.now().isoformat()),
        )
        row_id = cur.lastrowid
        conn.commit()
    return row_id


def record_experiences(experiences: list[tuple[str, str, str, int, str]]) -> int:
    """Persist multiple experience fragments with embeddings in a single transaction."""
    if not experiences:
        return 0

    timestamp = datetime.now().isoformat()
    rows = []
    for target, tech, payload, score, summary in experiences:
        embedding = get_embedding(f"{tech} {summary} {payload}")
        rows.append((target, tech, payload, score, summary, embedding, timestamp))

    with get_db_conn() as conn:
        cur = conn.cursor()
        cur.executemany(
            """INSERT INTO experience
               (target, technology, payload, result_score, summary, embedding, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        conn.commit()
    return len(experiences)


def search_experience(query: str, limit: int = 5) -> list[tuple]:
    """Retrieve relevant experiences using semantic vector search."""
    query_vec = get_embedding(query)
    if not query_vec:
        return []

    import numpy as np
    import struct

    def cos_sim(a, b):
        if not a or not b: return 0.0
        # Convert blob back to float array
        arr_a = np.frombuffer(a, dtype=np.float32)
        arr_b = np.frombuffer(b, dtype=np.float32)
        return np.dot(arr_a, arr_b) / (np.linalg.norm(arr_a) * np.linalg.norm(arr_b))

    with get_db_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT target, technology, payload, result_score, summary, embedding FROM experience")
        rows = cur.fetchall()

    # Rank rows by similarity
    scored_rows = []
    for row in rows:
        sim = cos_sim(query_vec, row[5])
        scored_rows.append((sim,) + row[:-1])

    scored_rows.sort(key=lambda x: x[0], reverse=True)
    return [r[1:] for r in scored_rows[:limit]]


def get_embedding(text: str) -> bytes:
    """Get embedding vector from Gemini API and return as binary BLOB."""
    import google.generativeai as genai
    import numpy as np
    
    api_key = cfg.API_KEY # Ensure this matches your config location
    if not api_key: return None
    
    try:
        genai.configure(api_key=api_key)
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="retrieval_document"
        )
        # Convert to float32 for storage efficiency
        vec = np.array(result['embedding'], dtype=np.float32)
        return vec.tobytes()
    except Exception as e:
        print(f"DEBUG: Embedding failed: {e}")
        return None


def get_memory_context(tech: str) -> str:
    """Build a human-readable memory context block."""
    experiences = search_experience(tech)
    if not experiences:
        return ""

    lines = [f"\n### [Long-Term Memory] Past experiences with '{tech}':"]
    for target, tech, payload, score, summary in experiences:
        label = (
            "✅ Worked" if score > 0 else ("❌ Failed" if score < 0 else "ℹ Neutral")
        )
        lines.append(f"- {label}: `{payload[:100]}` → {summary}")
    lines.append("Use this to avoid repeating failed approaches.\n")
    return "\n".join(lines)


def get_memory_stats() -> dict:
    """Return summary statistics."""
    with get_db_conn() as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*), SUM(CASE WHEN result_score > 0 THEN 1 ELSE 0 END) FROM experience"
        )
        total, successes = cur.fetchone()

    total = total or 0
    successes = successes or 0
    return {
        "total": total,
        "successes": successes,
        "failures": total - successes,
    }
