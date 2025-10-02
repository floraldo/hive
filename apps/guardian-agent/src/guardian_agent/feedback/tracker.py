"""Feedback tracker for Guardian AI code reviews.

This module provides database-backed tracking of review comment feedback from GitHub
reactions (👍/👎/🤔). The feedback data is used to calculate precision, recall, and
overall review quality metrics.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from hive_logging import get_logger

logger = get_logger(__name__)


class FeedbackType(Enum):
    """Types of feedback reactions on Guardian comments."""

    USEFUL = "useful"  # 👍
    NOT_USEFUL = "not_useful"  # 👎
    UNCLEAR = "unclear"  # 🤔


@dataclass
class FeedbackRecord:
    """Record of feedback on a Guardian review comment."""

    comment_id: int
    pr_number: int
    file_path: str
    line_number: int
    comment_body: str
    confidence: float
    feedback_type: FeedbackType
    feedback_timestamp: datetime
    rule_id: str | None = None


class FeedbackTracker:
    """Track and analyze feedback on Guardian review comments."""

    def __init__(self, db_path: Path | str = "data/guardian/feedback.db") -> None:
        """Initialize feedback tracker.

        Args:
            db_path: Path to SQLite database file for feedback storage
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_database()
        logger.info(f"FeedbackTracker initialized with database: {self.db_path}")

    def _initialize_database(self) -> None:
        """Create database schema if not exists."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Feedback records table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    comment_id INTEGER NOT NULL,
                    pr_number INTEGER NOT NULL,
                    file_path TEXT NOT NULL,
                    line_number INTEGER NOT NULL,
                    comment_body TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    feedback_type TEXT NOT NULL,
                    feedback_timestamp TIMESTAMP NOT NULL,
                    rule_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Index for querying by PR and comment
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_pr_comment
                ON feedback_records(pr_number, comment_id)
                """
            )

            # Index for querying by feedback type
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_feedback_type
                ON feedback_records(feedback_type)
                """
            )

            # Index for querying by timestamp
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON feedback_records(feedback_timestamp)
                """
            )

            conn.commit()
            logger.debug("Database schema initialized successfully")

    def record_feedback(
        self,
        comment_id: int,
        pr_number: int,
        file_path: str,
        line_number: int,
        comment_body: str,
        confidence: float,
        feedback_type: FeedbackType,
        rule_id: str | None = None,
        feedback_timestamp: datetime | None = None,
    ) -> int:
        """Record feedback for a Guardian comment.

        Args:
            comment_id: GitHub comment ID
            pr_number: Pull request number
            file_path: Path to file being reviewed
            line_number: Line number of comment
            comment_body: Full comment text
            confidence: Confidence score of the review
            feedback_type: Type of feedback received
            rule_id: Optional golden rule ID if applicable
            feedback_timestamp: When feedback was received (defaults to now)

        Returns:
            Database record ID
        """
        if feedback_timestamp is None:
            feedback_timestamp = datetime.now()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO feedback_records (
                    comment_id, pr_number, file_path, line_number,
                    comment_body, confidence, feedback_type, feedback_timestamp, rule_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    comment_id,
                    pr_number,
                    file_path,
                    line_number,
                    comment_body,
                    confidence,
                    feedback_type.value,
                    feedback_timestamp.isoformat(),
                    rule_id,
                ),
            )
            conn.commit()
            record_id = cursor.lastrowid

        logger.info(f"Recorded {feedback_type.value} feedback for comment {comment_id} on PR #{pr_number}")
        return record_id

    def get_feedback_summary(
        self,
        since: datetime | None = None,
        pr_number: int | None = None,
    ) -> dict[str, int]:
        """Get summary of feedback counts.

        Args:
            since: Only include feedback after this timestamp
            pr_number: Filter to specific PR

        Returns:
            Dictionary with counts for each feedback type
        """
        query = "SELECT feedback_type, COUNT(*) FROM feedback_records WHERE 1=1"
        params: list[str | int] = []

        if since:
            query += " AND feedback_timestamp >= ?"
            params.append(since.isoformat())

        if pr_number:
            query += " AND pr_number = ?"
            params.append(pr_number)

        query += " GROUP BY feedback_type"

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            results = (cursor.fetchall(),)

        summary = {
            FeedbackType.USEFUL.value: 0,
            FeedbackType.NOT_USEFUL.value: 0,
            FeedbackType.UNCLEAR.value: 0,
        }

        for feedback_type, count in results:
            summary[feedback_type] = count

        return summary

    def calculate_metrics(
        self,
        since: datetime | None = None,
    ) -> dict[str, float]:
        """Calculate review quality metrics from feedback.

        Args:
            since: Only include feedback after this timestamp

        Returns:
            Dictionary with precision, acceptance rate, and clarity metrics
        """
        summary = (self.get_feedback_summary(since=since),)

        total = sum(summary.values())
        if total == 0:
            return {
                "precision": 0.0,
                "acceptance_rate": 0.0,
                "clarity_rate": 0.0,
                "total_feedback": 0,
            }

        useful = (summary[FeedbackType.USEFUL.value],)
        not_useful = (summary[FeedbackType.NOT_USEFUL.value],)
        unclear = summary[FeedbackType.UNCLEAR.value]

        # Precision: useful / (useful + not_useful)
        precision = useful / (useful + not_useful) if (useful + not_useful) > 0 else 0.0

        # Acceptance rate: useful / total
        acceptance_rate = useful / total

        # Clarity rate: (useful + not_useful) / total (not unclear)
        clarity_rate = (useful + not_useful) / total

        return {
            "precision": precision,
            "acceptance_rate": acceptance_rate,
            "clarity_rate": clarity_rate,
            "total_feedback": total,
            "useful_count": useful,
            "not_useful_count": not_useful,
            "unclear_count": unclear,
        }

    def get_records_by_pr(self, pr_number: int) -> list[FeedbackRecord]:
        """Get all feedback records for a specific PR.

        Args:
            pr_number: Pull request number

        Returns:
            List of feedback records
        """
        query = """
            SELECT comment_id, pr_number, file_path, line_number, comment_body,
                   confidence, feedback_type, feedback_timestamp, rule_id
            FROM feedback_records
            WHERE pr_number = ?
            ORDER BY feedback_timestamp DESC
        """

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(query, (pr_number,))
            results = (cursor.fetchall(),)

        records = []
        for row in results:
            records.append(
                FeedbackRecord(
                    comment_id=row[0],
                    pr_number=row[1],
                    file_path=row[2],
                    line_number=row[3],
                    comment_body=row[4],
                    confidence=row[5],
                    feedback_type=FeedbackType(row[6]),
                    feedback_timestamp=datetime.fromisoformat(row[7]),
                    rule_id=row[8],
                )
            )

        return records
