from hive_logging import get_logger

logger = get_logger(__name__)

"""
AI Reviewer Configuration Management.

Extends hive-config with reviewer-specific settings following the inherit→extend pattern.
"""


try:
    from hive_config import HiveConfig
    from hive_config import load_config as load_hive_config
except ImportError:
    # Fallback for development - define minimal config structure
    from pydantic import BaseModel

    class HiveConfig(BaseModel):
        """Minimal hive config for fallback"""

        pass

    def load_hive_config() -> "HiveConfig":
        """Fallback config loader"""
        return HiveConfig()


from pydantic import BaseModel, Field


class ReviewCriteriaConfig(BaseModel):
    """Code review criteria configuration"""

    min_quality_score: float = 70.0
    check_code_style: bool = True
    check_security: bool = True
    check_performance: bool = True
    check_maintainability: bool = True
    check_test_coverage: bool = True
    require_documentation: bool = True


class ClaudeReviewConfig(BaseModel):
    """Claude AI review integration configuration"""

    mock_mode: bool = True
    model_name: str = "claude-3-sonnet"
    max_file_size_kb: int = 100
    timeout_seconds: int = 60
    retry_attempts: int = 2
    concurrent_reviews: int = 3


class ReviewConfig(BaseModel):
    """Review-specific configuration"""

    auto_approve_threshold: float = 90.0
    auto_reject_threshold: float = 40.0
    require_human_review: bool = False
    max_review_time_minutes: int = 15
    enable_suggestions: bool = True
    track_metrics: bool = True

    # Review criteria
    criteria: ReviewCriteriaConfig = ReviewCriteriaConfig()


class NotificationConfig(BaseModel):
    """Review notification configuration"""

    send_on_approval: bool = True
    send_on_rejection: bool = True
    send_on_error: bool = True
    webhook_urls: list[str] = Field(default_factory=list)


class AIReviewerConfig(HiveConfig):
    """Extended configuration for AI Reviewer"""

    review: ReviewConfig = ReviewConfig()
    claude: ClaudeReviewConfig = ClaudeReviewConfig()
    notifications: NotificationConfig = NotificationConfig()


def load_config(base_config: dict | None = None) -> AIReviewerConfig:
    """
    Load AI Reviewer configuration extending hive config.

    Args:
        base_config: Optional base configuration dict to use instead of global config

    Returns:
        AIReviewerConfig: Complete configuration with hive base + reviewer extensions
    """
    # Load base hive configuration or use provided config
    if base_config:
        hive_config = HiveConfig(**base_config)
    else:
        hive_config = load_hive_config()

    # Merge with reviewer-specific config
    return AIReviewerConfig(
        **hive_config.dict(), review=ReviewConfig(), claude=ClaudeReviewConfig(), notifications=NotificationConfig(),
    )


# Convenience functions for getting specific configs
def get_review_config() -> ReviewConfig:
    """Get review-specific configuration"""

    return config.review


def get_claude_config() -> ClaudeReviewConfig:
    """Get Claude integration configuration"""

    return config.claude
