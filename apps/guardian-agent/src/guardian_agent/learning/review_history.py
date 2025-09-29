"""Review history management for learning system."""

import json
from pathlib import Path
from typing import Any

from hive_db import SQLiteConnection
from hive_logging import get_logger

logger = get_logger(__name__)


class ReviewHistory:
    """
    Manages historical review data for learning and improvement.

    Stores review results, feedback, and patterns to improve
    future review quality.
    """

    def __init__(self, history_path: Path) -> None:
        """Initialize the review history."""
        self.history_path = Path(history_path)
        self.history_path.mkdir(parents=True, exist_ok=True)

        self.db_path = self.history_path / "reviews.db"
        self._initialize_database()

        logger.info("ReviewHistory initialized at %s", self.history_path)

    def _initialize_database(self) -> None:
        """Initialize the database schema."""
        with SQLiteConnection(self.db_path) as conn:
            cursor = conn.cursor()

            # Reviews table
            cursor.execute(
                """,
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    score REAL,
                    violations_count INTEGER,
                    suggestions_count INTEGER,
                    ai_confidence REAL,
                    review_data TEXT,
                    metadata TEXT
                )
            """
            )

            # Violations table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS violations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    review_id INTEGER,
                    type TEXT,
                    severity TEXT,
                    rule TEXT,
                    message TEXT,
                    line_number INTEGER,
                    was_fixed BOOLEAN DEFAULT 0,
                    fix_confirmed BOOLEAN DEFAULT 0,
                    FOREIGN KEY (review_id) REFERENCES reviews(id)
                )
            """
            )

            # Feedback table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    review_id INTEGER,
                    violation_id INTEGER,
                    feedback_type TEXT,
                    feedback_text TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    processed BOOLEAN DEFAULT 0,
                    FOREIGN KEY (review_id) REFERENCES reviews(id),
                    FOREIGN KEY (violation_id) REFERENCES violations(id)
                )
            """
            )

            # Patterns table for learned patterns
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS learned_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    pattern_type TEXT,
                    pattern_content TEXT,
                    confidence REAL,
                    occurrences INTEGER DEFAULT 1,
                    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """
            )

            # Team preferences table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS team_preferences (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    preference_key TEXT UNIQUE,
                    preference_value TEXT,
                    confidence REAL,
                    examples TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """
            )

            conn.commit()

    async def store_review(
        self,
        file_path: Path,
        review_result: Any,  # ReviewResult type
    ) -> int:
        """
        Store a review result.

        Args:
            file_path: Path to the reviewed file
            review_result: The review result object

        Returns:
            Review ID
        """
        with SQLiteConnection(self.db_path) as conn:
            cursor = conn.cursor()

            # Store main review
            cursor.execute(
                """,
                INSERT INTO reviews (
                    file_path, score, violations_count,
                    suggestions_count, ai_confidence,
                    review_data, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    str(file_path),
                    review_result.overall_score,
                    sum(review_result.violations_count.values()),
                    review_result.suggestions_count,
                    review_result.ai_confidence,
                    json.dumps(
                        {
                            "summary": review_result.summary,
                            "violations_by_severity": {k.value: v for k, v in review_result.violations_count.items()},
                        }
                    ),
                    json.dumps(review_result.metadata),
                ),
            )

            review_id = cursor.lastrowid

            # Store violations
            for violation in review_result.all_violations:
                cursor.execute(
                    """,
                    INSERT INTO violations (
                        review_id, type, severity, rule,
                        message, line_number
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        review_id,
                        violation.type.value,
                        violation.severity.value,
                        violation.rule,
                        violation.message,
                        violation.line_number,
                    ),
                )

            conn.commit()

        logger.info("Stored review %d for %s", review_id, file_path)
        return review_id

    async def store_feedback(
        self,
        review_id: int,
        feedback_type: str,
        feedback_text: str,
        violation_id: int | None = None,
    ) -> None:
        """
        Store feedback on a review.

        Args:
            review_id: ID of the review
            feedback_type: Type of feedback (positive, negative, correction)
            feedback_text: The feedback text
            violation_id: Optional specific violation ID
        """
        with SQLiteConnection(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """,
                INSERT INTO feedback (
                    review_id, violation_id, feedback_type,
                    feedback_text
                ) VALUES (?, ?, ?, ?)
            """,
                (review_id, violation_id, feedback_type, feedback_text),
            )

            conn.commit()

        logger.info("Stored %s feedback for review %d", feedback_type, review_id)

    async def get_similar_reviews(
        self,
        file_path: Path,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """
        Get similar past reviews for learning.

        Args:
            file_path: Path to compare
            limit: Maximum number of results

        Returns:
            List of similar reviews
        """
        with SQLiteConnection(self.db_path) as conn:
            cursor = conn.cursor()

            # Get reviews for similar files
            cursor.execute(
                """,
                SELECT r.*,
                       COUNT(f.id) as feedback_count,
                       AVG(CASE WHEN f.feedback_type = 'positive' THEN 1 ELSE 0 END) as positive_ratio,
                FROM reviews r,
                LEFT JOIN feedback f ON r.id = f.review_id
                WHERE r.file_path LIKE ?
                GROUP BY r.id
                ORDER BY r.timestamp DESC
                LIMIT ?
            """,
                (f"%{file_path.name}", limit),
            )

            reviews = []
            for row in cursor.fetchall():
                reviews.append(
                    {
                        "id": row[0],
                        "file_path": row[1],
                        "timestamp": row[2],
                        "score": row[3],
                        "feedback_count": row[-2],
                        "positive_ratio": row[-1],
                    }
                )

            return reviews

    async def learn_team_preference(
        self,
        preference_key: str,
        preference_value: str,
        example: str,
    ) -> None:
        """
        Learn a team preference from feedback.

        Args:
            preference_key: Key identifying the preference
            preference_value: The preferred approach
            example: Example code showing the preference
        """
        with SQLiteConnection(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if preference exists
            cursor.execute(
                """,
                SELECT id, confidence, examples,
                FROM team_preferences,
                WHERE preference_key = ?,
            """,
                (preference_key,),
            )

            existing = cursor.fetchone()

            if existing:
                # Update existing preference
                pref_id, confidence, examples_json = existing
                examples = json.loads(examples_json) if examples_json else []
                examples.append(example)

                cursor.execute(
                    """,
                    UPDATE team_preferences,
                    SET preference_value = ?,
                        confidence = ?,
                        examples = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """,
                    (
                        preference_value,
                        min(confidence + 0.1, 1.0),  # Increase confidence,
                        json.dumps(examples[-10:]),  # Keep last 10 examples,
                        pref_id,
                    ),
                )
            else:
                # Create new preference
                cursor.execute(
                    """
                    INSERT INTO team_preferences (
                        preference_key, preference_value,
                        confidence, examples
                    ) VALUES (?, ?, ?, ?)
                """,
                    (
                        preference_key,
                        preference_value,
                        0.5,  # Initial confidence
                        json.dumps([example]),
                    ),
                )

            conn.commit()

        logger.info("Learned team preference: %s", preference_key)

    async def get_team_preferences(self) -> dict[str, dict[str, Any]]:
        """
        Get all learned team preferences.

        Returns:
            Dictionary of preferences
        """
        with SQLiteConnection(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """,
                SELECT preference_key, preference_value,
                       confidence, examples,
                FROM team_preferences,
                WHERE confidence > 0.6,
                ORDER BY confidence DESC
            """
            )

            preferences = {}
            for row in cursor.fetchall():
                preferences[row[0]] = {
                    "value": row[1],
                    "confidence": row[2],
                    "examples": json.loads(row[3]) if row[3] else [],
                }

            return preferences

    async def get_violation_accuracy(
        self,
        violation_type: str,
        time_window_days: int = 30,
    ) -> dict[str, float]:
        """
        Get accuracy metrics for a violation type.

        Args:
            violation_type: Type of violation to check
            time_window_days: Days to look back

        Returns:
            Accuracy metrics
        """
        with SQLiteConnection(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """,
                SELECT,
                    COUNT(*) as total,
                    SUM(CASE WHEN was_fixed THEN 1 ELSE 0 END) as fixed,
                    SUM(CASE WHEN fix_confirmed THEN 1 ELSE 0 END) as confirmed,
                FROM violations v
                JOIN reviews r ON v.review_id = r.id
                WHERE v.type = ?
                  AND r.timestamp > datetime('now', '-' || ? || ' days')
            """,
                (violation_type, time_window_days),
            )

            row = cursor.fetchone()
            total, fixed, confirmed = row

            return {
                "total_detected": total,
                "fix_rate": fixed / total if total > 0 else 0,
                "confirmation_rate": confirmed / total if total > 0 else 0,
            }

    async def update_violation_status(
        self,
        violation_id: int,
        was_fixed: bool,
        fix_confirmed: bool,
    ) -> None:
        """
        Update violation status based on feedback.

        Args:
            violation_id: ID of the violation
            was_fixed: Whether the violation was fixed
            fix_confirmed: Whether the fix was confirmed as correct
        """
        with SQLiteConnection(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """,
                UPDATE violations,
                SET was_fixed = ?, fix_confirmed = ?,
                WHERE id = ?,
            """,
                (was_fixed, fix_confirmed, violation_id),
            )

            conn.commit()

        logger.info("Updated violation %d status", violation_id)
