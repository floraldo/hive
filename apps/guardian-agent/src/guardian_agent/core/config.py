"""Configuration management for Guardian Agent."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from hive_config import BaseConfig, ConfigField


@dataclass
class ReviewConfig:
    """Configuration for the review process."""

    model: str = "gpt-4"
    temperature: float = 0.3
    max_tokens: int = 2000
    enable_golden_rules: bool = True
    enable_security_scan: bool = True
    enable_performance_check: bool = True
    enable_style_check: bool = True
    parallel_analysis: bool = True
    max_file_size_kb: int = 500


@dataclass
class VectorSearchConfig:
    """Configuration for vector search capabilities."""

    enabled: bool = True
    index_path: Path = Path("./vectors")
    model_name: str = "text-embedding-ada-002"
    similarity_threshold: float = 0.85
    max_results: int = 10
    cache_embeddings: bool = True


@dataclass
class LearningConfig:
    """Configuration for the learning system."""

    enabled: bool = True
    min_confidence: float = 0.7
    feedback_loop: bool = True
    history_path: Path = Path("./review_history")
    max_history_items: int = 1000
    learn_from_fixes: bool = True


@dataclass
class CacheConfig:
    """Configuration for caching."""

    enabled: bool = True
    ttl_seconds: int = 3600
    max_cache_size_mb: int = 100
    cache_embeddings: bool = True
    cache_analysis: bool = True


class GuardianConfig(BaseConfig):
    """Main configuration for the Guardian Agent."""

    _config_file = "guardian.yaml"
    _env_prefix = "GUARDIAN"

    # Review settings
    review: ReviewConfig = ConfigField(default_factory=ReviewConfig, description="Review process configuration")

    # Vector search settings
    vector_search: VectorSearchConfig = ConfigField(
        default_factory=VectorSearchConfig, description="Vector search configuration"
    )

    # Learning system settings
    learning: LearningConfig = ConfigField(default_factory=LearningConfig, description="Learning system configuration")

    # Cache settings
    cache: CacheConfig = ConfigField(default_factory=CacheConfig, description="Cache configuration")

    # API keys (loaded from environment)
    openai_api_key: Optional[str] = ConfigField(default=None, env_var="OPENAI_API_KEY", secret=True)

    # File patterns
    include_patterns: List[str] = ConfigField(default_factory=lambda: ["*.py", "*.js", "*.ts"], description="File patterns to include")

    exclude_patterns: List[str] = ConfigField(
        default_factory=lambda: ["*_test.py", "*.test.js", "__pycache__", ".git", "node_modules"],
        description="File patterns to exclude",
    )

    # Logging
    log_level: str = ConfigField(default="INFO", env_var="LOG_LEVEL")
    log_file: Optional[Path] = ConfigField(default=None, description="Log file path")

    def validate(self) -> None:
        """Validate configuration."""
        super().validate()

        # Ensure API key is set if using OpenAI models
        if self.review.model.startswith("gpt") and not self.openai_api_key:
            raise ValueError("OpenAI API key is required for GPT models")

        # Ensure paths exist
        if self.vector_search.enabled:
            self.vector_search.index_path.mkdir(parents=True, exist_ok=True)

        if self.learning.enabled:
            self.learning.history_path.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load_from_file(cls, config_path: Path) -> "GuardianConfig":
        """Load configuration from file."""
        config = cls()
        config.load(config_path)
        config.validate()
        return config

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GuardianConfig":
        """Create configuration from dictionary."""
        config = cls()

        # Load review config
        if "review" in data:
            config.review = ReviewConfig(**data["review"])

        # Load vector search config
        if "vector_search" in data:
            config.vector_search = VectorSearchConfig(**data["vector_search"])

        # Load learning config
        if "learning" in data:
            config.learning = LearningConfig(**data["learning"])

        # Load cache config
        if "cache" in data:
            config.cache = CacheConfig(**data["cache"])

        # Load other fields
        for key, value in data.items():
            if key not in ["review", "vector_search", "learning", "cache"] and hasattr(config, key):
                setattr(config, key, value)

        config.validate()
        return config