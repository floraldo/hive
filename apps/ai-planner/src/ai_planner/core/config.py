from hive_logging import get_logger

logger = get_logger(__name__)

"""
AI Planner Configuration Management.

Extends hive-config with planner-specific settings following the inherit→extend pattern.
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


from pydantic import BaseModel


class ClaudeIntegrationConfig(BaseModel):
    """Claude AI integration configuration"""

    mock_mode: bool = True
    rate_limit_requests_per_minute: int = 50
    timeout_seconds: int = 30
    retry_attempts: int = 3
    model_name: str = "claude-3-sonnet"


class PlanningConfig(BaseModel):
    """Planning-specific configuration"""

    max_subtasks_per_plan: int = 20
    max_planning_depth: int = 3
    enable_dependency_analysis: bool = True
    auto_create_subtasks: bool = True
    planning_timeout_minutes: int = 10
    complexity_threshold: int = 5

    # Plan quality settings
    min_plan_quality_score: float = 0.7
    require_time_estimates: bool = True
    validate_dependencies: bool = True


class MonitoringConfig(BaseModel):
    """Planning monitoring configuration"""

    polling_interval_seconds: int = 30
    max_concurrent_plans: int = 5
    health_check_interval_minutes: int = 5
    metrics_retention_days: int = 30


class AIPlannerConfig(HiveConfig):
    """Extended configuration for AI Planner"""

    planning: PlanningConfig = PlanningConfig()
    claude: ClaudeIntegrationConfig = ClaudeIntegrationConfig()
    monitoring: MonitoringConfig = MonitoringConfig()


def load_config() -> AIPlannerConfig:
    """
    Load AI Planner configuration extending hive config.

    Returns:
        AIPlannerConfig: Complete configuration with hive base + planner extensions
    """
    # Load base hive configuration
    hive_config = load_hive_config()

    # Merge with planner-specific config
    return AIPlannerConfig(
        **hive_config.dict(), planning=PlanningConfig(), claude=ClaudeIntegrationConfig(), monitoring=MonitoringConfig()
    )


# Convenience functions for getting specific configs
def get_planning_config() -> PlanningConfig:
    """Get planning-specific configuration"""

    return config.planning


def get_claude_config() -> ClaudeIntegrationConfig:
    """Get Claude integration configuration"""

    return config.claude
