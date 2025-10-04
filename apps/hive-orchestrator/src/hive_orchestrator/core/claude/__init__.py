from hive_logging import get_logger

logger = get_logger(__name__)

"""
Unified Claude CLI Bridge Package
Provides a single, robust interface for all Claude API interactions
"""

from .bridge import BaseClaludeBridge, ClaudeBridgeConfig
from .claude_service import ClaudeMetrics, ClaudeService, RateLimitConfig, get_claude_service, reset_claude_service
from .exceptions import (
    ClaudeBridgeError,
    ClaudeError,
    ClaudeNotFoundError,
    ClaudeRateLimitError,
    ClaudeResponseError,
    ClaudeServiceError,
    ClaudeTimeoutError,
    ClaudeValidationError,
)
from .json_parser import JsonExtractionStrategy, JsonExtractor
from .planner_bridge import ClaudePlannerBridge, ClaudePlanningResponse
from .reviewer_bridge import ClaudeReviewerBridge, ClaudeReviewResponse
from .validators import BaseResponseValidator

__version__ = ("1.1.0",)

__all__ = [
    # Bridge classes
    "BaseClaludeBridge",
    "BaseResponseValidator",
    "ClaudeBridgeConfig",
    "ClaudeBridgeError",
    # Exceptions
    "ClaudeError",
    "ClaudeMetrics",
    "ClaudeNotFoundError",
    "ClaudePlannerBridge",
    "ClaudePlanningResponse",
    "ClaudeRateLimitError",
    "ClaudeResponseError",
    "ClaudeReviewResponse",
    "ClaudeReviewerBridge",
    # Service
    "ClaudeService",
    "ClaudeServiceError",
    "ClaudeTimeoutError",
    "ClaudeValidationError",
    "JsonExtractionStrategy",
    "JsonExtractor",
    "RateLimitConfig",
    "get_claude_service",
    "reset_claude_service",
]
