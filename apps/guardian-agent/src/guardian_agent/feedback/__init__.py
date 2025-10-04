"""Guardian feedback tracking system.

This module provides feedback tracking for Guardian AI code reviews, allowing
measurement of review quality through GitHub reaction data.
"""

from guardian_agent.feedback.tracker import FeedbackRecord, FeedbackTracker

__all__ = ["FeedbackRecord", "FeedbackTracker"]
