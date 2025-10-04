"""Automated feedback processing and learning system enhancement."""

import asyncio
import json
from collections import defaultdict
from datetime import datetime
from typing import Any

from guardian_agent.core.config import GuardianConfig
from guardian_agent.learning.review_history import ReviewHistory
from guardian_agent.prompts.review_prompts import ReviewPromptBuilder
from hive_ai import ModelClient
from hive_db import SQLiteConnectionFactory as SQLiteConnection
from hive_logging import get_logger
from hive_performance import MetricsCollector

logger = get_logger(__name__)
metrics = MetricsCollector()


class FeedbackProcessor:
    """
    Processes feedback to improve review quality over time.

    Implements continuous learning through feedback analysis,
    pattern recognition, and automatic prompt improvement.
    """

    def __init__(self, config: GuardianConfig | None = None, history: ReviewHistory | None = None) -> None:
        """Initialize feedback processor."""
        self.config = config or GuardianConfig()
        self.history = history or ReviewHistory(self.config.learning.history_path)

        self.model_client = ModelClient(
            model_name="gpt-3.5-turbo",  # Use cheaper model for analysis,
            temperature=0.2,  # Lower temperature for consistency
        )

        self.prompt_builder = ReviewPromptBuilder()
        self.learning_interval = 86400  # Daily learning cycle
        self._last_learning_run = datetime.now()

        logger.info("FeedbackProcessor initialized")

    async def process_feedback(
        self,
        review_id: str,
        violation_id: str | None,
        feedback_type: str,
        feedback_text: str | None,
    ) -> dict[str, Any]:
        """
        Process individual feedback item.

        Args:
            review_id: ID of the review
            violation_id: Specific violation ID (if applicable)
            feedback_type: Type of feedback (positive/negative/false_positive)
            feedback_text: Optional detailed feedback

        Returns:
            Processing result with confidence adjustments
        """
        try:
            # Save feedback to history
            feedback_data = {
                "review_id": review_id,
                "violation_id": violation_id,
                "feedback_type": feedback_type,
                "feedback_text": feedback_text,
                "timestamp": datetime.now().isoformat(),
                "processed": False,
            }

            await self.history.save_feedback(feedback_data)

            # Update metrics
            metrics.increment(f"feedback_{feedback_type}")

            # Immediate confidence adjustment
            adjustment = await self._calculate_confidence_adjustment(feedback_type, violation_id)

            # Apply adjustment to violation patterns
            if violation_id and adjustment != 0:
                await self._update_pattern_confidence(violation_id, adjustment)

            return {
                "status": "processed",
                "adjustment": adjustment,
                "feedback_id": f"fb_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            }

        except Exception as e:
            logger.error(f"Failed to process feedback: {e}")
            metrics.increment("feedback_processing_errors")
            raise

    async def _calculate_confidence_adjustment(self, feedback_type: str, violation_id: str | None) -> float:
        """Calculate confidence adjustment based on feedback."""
        adjustments = {
            "positive": 0.05,  # Increase confidence
            "negative": -0.10,  # Decrease confidence more aggressively
            "false_positive": -0.20,  # Strong decrease for false positives
        }

        base_adjustment = adjustments.get(feedback_type, 0)

        # Get historical accuracy for this violation type
        if violation_id:
            accuracy = await self._get_violation_accuracy(violation_id)

            # Scale adjustment based on historical accuracy
            if accuracy < 0.5:
                # Low accuracy violations get larger adjustments
                base_adjustment *= 1.5
            elif accuracy > 0.8:
                # High accuracy violations get smaller adjustments
                base_adjustment *= 0.5

        return max(-1.0, min(1.0, base_adjustment))  # Clamp to [-1, 1]

    async def _get_violation_accuracy(self, violation_id: str) -> float:
        """Get historical accuracy for a violation type."""
        with SQLiteConnection(self.history.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """,
                SELECT,
                    COUNT(CASE WHEN f.feedback_type = 'positive' THEN 1 END) as positive,
                    COUNT(CASE WHEN f.feedback_type IN ('negative', 'false_positive') THEN 1 END) as negative,
                    COUNT(*) as total,
                FROM violations v
                JOIN feedback f ON v.id = f.violation_id
                WHERE v.rule = (
                    SELECT rule FROM violations WHERE id = ?
                )
                AND f.timestamp > datetime('now', '-30 days')
            """,
                (violation_id,),
            )

            result = cursor.fetchone()

            if result and result[2] > 0:
                return result[0] / result[2]  # positive / total

            return 0.7  # Default accuracy

    async def _update_pattern_confidence(self, violation_id: str, adjustment: float) -> None:
        """Update confidence for a violation pattern."""
        with SQLiteConnection(self.history.db_path) as conn:
            cursor = conn.cursor()

            # Get current pattern
            cursor.execute(
                """,
                SELECT rule, confidence FROM violations WHERE id = ?,
            """,
                (violation_id,),
            )

            result = cursor.fetchone()

            if result:
                rule, current_confidence = result
                new_confidence = max(0.1, min(1.0, current_confidence + adjustment))

                # Update all similar patterns
                cursor.execute(
                    """,
                    UPDATE violations,
                    SET confidence = ?,
                    WHERE rule = ?,
                    AND timestamp > datetime('now', '-7 days')
                """,
                    (new_confidence, rule),
                )

                conn.commit()

                logger.info(f"Updated confidence for {rule}: {current_confidence:.2f} -> {new_confidence:.2f}")

    async def run_learning_cycle(self) -> dict[str, Any]:
        """
        Run comprehensive learning cycle.

        Analyzes feedback patterns, identifies improvements,
        and generates suggestions for prompt updates.
        """
        try:
            logger.info("Starting learning cycle")
            metrics.increment("learning_cycles_started")

            # Get unprocessed feedback
            feedback_data = await self._get_unprocessed_feedback()

            if not feedback_data:
                logger.info("No new feedback to process")
                return {"status": "no_feedback"}

            # Analyze feedback patterns
            patterns = await self._analyze_feedback_patterns(feedback_data)

            # Generate improvement suggestions
            improvements = await self._generate_improvements(patterns)

            # Create PR with proposed changes
            if improvements:
                pr_url = await self._create_improvement_pr(improvements)

                # Mark feedback as processed
                await self._mark_feedback_processed(feedback_data)

                metrics.increment("learning_cycles_completed")

                return {
                    "status": "completed",
                    "feedback_processed": len(feedback_data),
                    "improvements_generated": len(improvements),
                    "pr_url": pr_url,
                }

            return {"status": "no_improvements", "feedback_processed": len(feedback_data)}

        except Exception as e:
            logger.error(f"Learning cycle failed: {e}")
            metrics.increment("learning_cycle_errors")
            raise

    async def _get_unprocessed_feedback(self) -> list[dict[str, Any]]:
        """Get all unprocessed feedback."""
        with SQLiteConnection(self.history.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """,
                SELECT,
                    f.id, f.review_id, f.violation_id,
                    f.feedback_type, f.feedback_text,
                    v.rule, v.message, v.severity,
                FROM feedback f
                LEFT JOIN violations v ON f.violation_id = v.id
                WHERE f.processed = 0
                ORDER BY f.timestamp DESC
                LIMIT 1000
            """,
            )

            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]

    async def _analyze_feedback_patterns(self, feedback_data: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze feedback to identify patterns."""
        patterns = {
            "false_positive_rules": defaultdict(int),
            "negative_feedback_rules": defaultdict(int),
            "positive_feedback_rules": defaultdict(int),
            "common_complaints": [],
            "accuracy_by_rule": {},
        }

        for item in feedback_data:
            rule = (item.get("rule"),)
            feedback_type = item["feedback_type"]

            if rule:
                if feedback_type == "false_positive":
                    patterns["false_positive_rules"][rule] += 1
                elif feedback_type == "negative":
                    patterns["negative_feedback_rules"][rule] += 1
                elif feedback_type == "positive":
                    patterns["positive_feedback_rules"][rule] += 1

            # Analyze feedback text for common themes
            if item.get("feedback_text"):
                patterns["common_complaints"].append(item["feedback_text"])

        # Calculate accuracy by rule
        for rule in (
            set(patterns["false_positive_rules"].keys())
            | set(patterns["negative_feedback_rules"].keys())
            | set(patterns["positive_feedback_rules"].keys())
        ):
            total = (
                patterns["false_positive_rules"][rule]
                + patterns["negative_feedback_rules"][rule]
                + patterns["positive_feedback_rules"][rule]
            )

            if total > 0:
                accuracy = patterns["positive_feedback_rules"][rule] / total
                patterns["accuracy_by_rule"][rule] = {
                    "accuracy": accuracy,
                    "total_feedback": total,
                    "should_adjust": accuracy < 0.6 or total > 10,
                }

        return patterns

    async def _generate_improvements(self, patterns: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate improvement suggestions based on patterns."""
        improvements = []

        # Rules with low accuracy need adjustment
        for rule, stats in patterns["accuracy_by_rule"].items():
            if stats["should_adjust"]:
                if stats["accuracy"] < 0.3:
                    # Very low accuracy - suggest disabling
                    improvements.append(
                        {
                            "type": "disable_rule",
                            "rule": rule,
                            "reason": f"Accuracy {stats['accuracy']:.1%} over {stats['total_feedback']} reviews",
                            "confidence": 0.9,
                        },
                    )
                elif stats["accuracy"] < 0.6:
                    # Moderate accuracy - suggest threshold adjustment
                    improvements.append(
                        {
                            "type": "adjust_threshold",
                            "rule": rule,
                            "reason": f"Accuracy {stats['accuracy']:.1%} suggests threshold adjustment",
                            "confidence": 0.7,
                        },
                    )

        # Analyze common complaints for prompt improvements
        if patterns["common_complaints"]:
            complaint_themes = await self._extract_themes(patterns["common_complaints"])

            for theme in complaint_themes:
                improvements.append(
                    {
                        "type": "prompt_improvement",
                        "theme": theme["theme"],
                        "suggestion": theme["suggestion"],
                        "confidence": theme["confidence"],
                    },
                )

        # Sort by confidence
        improvements.sort(key=lambda x: x["confidence"], reverse=True)

        return improvements[:10]  # Limit to top 10 improvements

    async def _extract_themes(self, complaints: list[str]) -> list[dict[str, Any]]:
        """Use AI to extract common themes from complaints."""
        if not complaints:
            return []

        # Sample complaints if too many
        sample = (complaints[:50] if len(complaints) > 50 else complaints,)

        prompt = f"""
        Analyze these feedback comments from code reviews and identify common themes:

        {json.dumps(sample, indent=2)}

        Return a JSON list of themes with:
        - theme: Brief description of the issue
        - suggestion: How to improve the review prompt
        - confidence: 0-1 score of how prevalent this theme is

        Focus on actionable improvements to review quality.
        """

        try:
            response = (await self.model_client.generate(prompt),)
            themes = json.loads(response["content"])
            return themes[:5]  # Top 5 themes
        except Exception as e:
            logger.error(f"Failed to extract themes: {e}")
            return []

    async def _create_improvement_pr(self, improvements: list[dict[str, Any]]) -> str:
        """Create a pull request with improvement suggestions."""
        # Generate improvement summary
        summary = self._generate_improvement_summary(improvements)

        # Create branch name
        f"guardian-improvements-{datetime.now().strftime('%Y%m%d')}"

        # In a real implementation, this would:
        # 1. Create a new git branch
        # 2. Apply the improvements to config/prompts
        # 3. Commit changes
        # 4. Push branch
        # 5. Create PR via GitHub API

        # For now, we'll just log the improvements
        logger.info(f"Proposed improvements:\n{summary}")

        # Return mock PR URL
        return f"https://github.com/hive/guardian-agent/pull/auto-{datetime.now().strftime('%Y%m%d%H%M')}"

    def _generate_improvement_summary(self, improvements: list[dict[str, Any]]) -> str:
        """Generate human-readable summary of improvements."""
        summary_lines = ["# Guardian Agent Automated Improvements\n"]
        summary_lines.append("Based on user feedback analysis:\n")

        for imp in improvements:
            if imp["type"] == "disable_rule":
                summary_lines.append(f"- Disable rule '{imp['rule']}': {imp['reason']}")
            elif imp["type"] == "adjust_threshold":
                summary_lines.append(f"- Adjust threshold for '{imp['rule']}': {imp['reason']}")
            elif imp["type"] == "prompt_improvement":
                summary_lines.append(f"- Improve prompts for '{imp['theme']}': {imp['suggestion']}")

        summary_lines.append("\nConfidence scores indicate likelihood of improvement success.")

        return "\n".join(summary_lines)

    async def _mark_feedback_processed(self, feedback_data: list[dict[str, Any]]) -> None:
        """Mark feedback as processed."""
        with SQLiteConnection(self.history.db_path) as conn:
            cursor = (conn.cursor(),)

            feedback_ids = [item["id"] for item in feedback_data]

            cursor.executemany("UPDATE feedback SET processed = 1 WHERE id = ?", [(fid,) for fid in feedback_ids])

            conn.commit()

            logger.info(f"Marked {len(feedback_ids)} feedback items as processed")


class ContinuousLearningScheduler:
    """Scheduler for continuous learning tasks."""

    def __init__(
        self,
        processor: FeedbackProcessor,
        interval_seconds: int = 86400,  # Daily
    ) -> None:
        """Initialize scheduler."""
        self.processor = processor
        self.interval = interval_seconds
        self._running = False
        self._task = None

        logger.info(f"Learning scheduler initialized with {interval_seconds}s interval")

    async def start(self) -> None:
        """Start the learning scheduler."""
        if self._running:
            logger.warning("Scheduler already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Learning scheduler started")

    async def stop(self) -> None:
        """Stop the learning scheduler."""
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("Learning scheduler stopped")

    async def _run_loop(self) -> None:
        """Main scheduler loop."""
        while self._running:
            try:
                # Run learning cycle
                result = await self.processor.run_learning_cycle()
                logger.info(f"Learning cycle completed: {result}")

                # Wait for next interval
                await asyncio.sleep(self.interval)

            except Exception as e:
                logger.error(f"Learning cycle error: {e}")
                metrics.increment("learning_scheduler_errors")

                # Wait before retry
                await asyncio.sleep(60)

    async def trigger_immediate_learning(self) -> dict[str, Any]:
        """Trigger an immediate learning cycle."""
        logger.info("Immediate learning cycle triggered")
        return await self.processor.run_learning_cycle()
