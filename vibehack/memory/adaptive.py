"""
vibehack/memory/adaptive.py — Dynamic Pattern Learning System.

Learns from:
  1. User feedback (rejected commands)
  2. Successful exploits
  3. Failed attempts
  4. Technology patterns

Adaptive features:
  - Pattern extraction from success/failure
  - Technology-specific tactics
  - Command optimization
  - Real-time learning
"""

import sqlite3
import json
import re
from typing import Dict, List, Optional, Set
from datetime import datetime
from pathlib import Path


class AdaptiveLearner:
    """
    Dynamic pattern learner that evolves with use.
    Unlike fixed skills, this learns from actual sessions.
    """

    def __init__(self, db_path: str = None):
        from vibehack.config import cfg

        self.db_path = db_path or str(cfg.HOME / "adaptive.db")
        self._init_db()

    def _init_db(self):
        """Initialize adaptive learning database."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        # Learned command patterns
        cur.execute("""
            CREATE TABLE IF NOT EXISTS command_patterns (
                id INTEGER PRIMARY KEY,
                pattern TEXT NOT NULL,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                technologies TEXT,
                last_used TEXT,
                confidence REAL DEFAULT 0.5
            )
        """)

        # Technology tactics learned
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tech_tactics (
                id INTEGER PRIMARY KEY,
                technology TEXT NOT NULL,
                tactic TEXT NOT NULL,
                success_count INTEGER DEFAULT 0,
                failure_count INTEGER DEFAULT 0,
                last_used TEXT,
                confidence REAL DEFAULT 0.5
            )
        """)

        # User feedback history
        cur.execute("""
            CREATE TABLE IF NOT EXISTS user_feedback (
                id INTEGER PRIMARY KEY,
                session_id TEXT,
                command TEXT,
                feedback_type TEXT,
                hint TEXT,
                timestamp TEXT
            )
        """)

        conn.commit()
        conn.close()

    def learn_from_feedback(
        self, command: str, feedback_type: str, hint: str = "", session_id: str = ""
    ):
        """Learn from user feedback (reject/accept/hint)."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        timestamp = datetime.now().isoformat()
        cur.execute(
            "INSERT INTO user_feedback VALUES (NULL, ?, ?, ?, ?, ?)",
            (session_id, command, feedback_type, hint, timestamp),
        )

        if feedback_type == "reject":
            # Decrease confidence for similar commands
            self._decrease_pattern_confidence(command)
        elif feedback_type == "accept":
            # Increase confidence
            self._increase_pattern_confidence(command)

        conn.commit()
        conn.close()

    def _decrease_pattern_confidence(self, command: str):
        """Reduce pattern confidence after rejection."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        pattern = self._normalize_command(command)
        cur.execute(
            "UPDATE command_patterns SET confidence = confidence - 0.2, failure_count = failure_count + 1 WHERE pattern LIKE ?",
            (f"%{pattern[:20]}%",),
        )
        conn.commit()
        conn.close()

    def _increase_pattern_confidence(self, command: str):
        """Increase pattern confidence after success."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        pattern = self._normalize_command(command)
        cur.execute(
            "UPDATE command_patterns SET confidence = MIN(1.0, confidence + 0.1), success_count = success_count + 1 WHERE pattern LIKE ?",
            (f"%{pattern[:20]}%",),
        )
        conn.commit()
        conn.close()

    def _normalize_command(self, cmd: str) -> str:
        """Normalize command for pattern matching."""
        # Remove specific values, keep structure
        normalized = re.sub(r"\d+\.\d+\.\d+\.\d+", "<IP>", cmd)
        normalized = re.sub(r"\d+", "<NUM>", normalized)
        normalized = re.sub(r"[a-zA-Z0-9_.-]+@[a-zA-Z0-9.-]+", "<EMAIL>", normalized)
        return normalized.strip()

    def register_success(self, command: str, technology: str = ""):
        """Register a successful command."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        pattern = self._normalize_command(command)
        timestamp = datetime.now().isoformat()

        # Check if pattern exists
        cur.execute(
            "SELECT id FROM command_patterns WHERE pattern LIKE ?",
            (f"%{pattern[:30]}%",),
        )
        existing = cur.fetchone()

        if existing:
            cur.execute(
                "UPDATE command_patterns SET success_count = success_count + 1, confidence = MIN(1.0, confidence + 0.1), last_used = ? WHERE pattern LIKE ?",
                (timestamp, f"%{pattern[:30]}%"),
            )
        else:
            cur.execute(
                "INSERT INTO command_patterns VALUES (NULL, ?, 1, 0, ?, ?, 0.6)",
                (pattern[:200], technology, timestamp),
            )

        # Also learn technology tactic
        if technology:
            cur.execute(
                "SELECT id FROM tech_tactics WHERE technology = ? AND tactic LIKE ?",
                (technology, f"%{command[:30]}%"),
            )
            if cur.fetchone():
                cur.execute(
                    "UPDATE tech_tactics SET success_count = success_count + 1, confidence = MIN(1.0, confidence + 0.15) WHERE technology = ?",
                    (technology,),
                )
            else:
                cur.execute(
                    "INSERT INTO tech_tactics VALUES (NULL, ?, ?, 1, 0, ?, 0.6)",
                    (technology, command[:200], timestamp),
                )

        conn.commit()
        conn.close()

    def register_failure(self, command: str, technology: str = ""):
        """Register a failed command."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        pattern = self._normalize_command(command)
        timestamp = datetime.now().isoformat()

        cur.execute(
            "SELECT id FROM command_patterns WHERE pattern LIKE ?",
            (f"%{pattern[:30]}%",),
        )
        existing = cur.fetchone()

        if existing:
            cur.execute(
                "UPDATE command_patterns SET failure_count = failure_count + 1, confidence = MAX(0.1, confidence - 0.15), last_used = ? WHERE pattern LIKE ?",
                (timestamp, f"%{pattern[:30]}%"),
            )
        else:
            cur.execute(
                "INSERT INTO command_patterns VALUES (NULL, ?, 0, 1, ?, ?, 0.3)",
                (pattern[:200], technology, timestamp),
            )

        conn.commit()
        conn.close()

    def get_optimized_commands(
        self, base_command: str, technology: str = ""
    ) -> List[str]:
        """Get optimized versions of a command based on learned patterns."""
        suggestions = [base_command]  # Always include original

        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        # Get high-confidence patterns for technology
        if technology:
            cur.execute(
                "SELECT tactic FROM tech_tactics WHERE technology = ? AND confidence > 0.6 ORDER BY confidence DESC LIMIT 5",
                (technology,),
            )
            for row in cur.fetchall():
                if row[0] not in suggestions:
                    suggestions.append(row[0])

        # Get high-confidence command patterns
        cur.execute(
            "SELECT pattern FROM command_patterns WHERE confidence > 0.7 ORDER BY confidence DESC LIMIT 5"
        )
        for row in cur.fetchall():
            if (
                row[0] not in suggestions
                and row[0][: len(base_command)] == base_command[: len(row[0])]
            ):
                suggestions.append(row[0])

        conn.close()
        return suggestions[:5]

    def get_tech_tactics(self, technology: str) -> List[Dict]:
        """Get learned tactics for a specific technology."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        cur.execute(
            "SELECT tactic, success_count, failure_count, confidence FROM tech_tactics WHERE technology = ? ORDER BY confidence DESC",
            (technology,),
        )

        tactics = []
        for row in cur.fetchall():
            tactics.append(
                {
                    "tactic": row[0],
                    "success": row[1],
                    "failure": row[2],
                    "confidence": row[3],
                }
            )

        conn.close()
        return tactics

    def get_stats(self) -> Dict:
        """Get learning statistics."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.cursor()

        stats = {}

        cur.execute("SELECT COUNT(*), AVG(confidence) FROM command_patterns")
        stats["patterns"] = cur.fetchone()

        cur.execute("SELECT COUNT(*), AVG(confidence) FROM tech_tactics")
        stats["tactics"] = cur.fetchone()

        cur.execute("SELECT COUNT(*) FROM user_feedback")
        stats["feedback"] = cur.fetchone()

        conn.close()
        return stats


# Global instance
_learner = None


def get_learner() -> AdaptiveLearner:
    """Get global adaptive learner instance."""
    global _learner
    if _learner is None:
        _learner = AdaptiveLearner()
    return _learner


def register_command_result(command: str, success: bool, technology: str = ""):
    """Quick function to register command result."""
    learner = get_learner()
    if success:
        learner.register_success(command, technology)
    else:
        learner.register_failure(command, technology)


def get_learned_tactics(technology: str) -> List[Dict]:
    """Get learned tactics for technology."""
    return get_learner().get_tech_tactics(technology)
