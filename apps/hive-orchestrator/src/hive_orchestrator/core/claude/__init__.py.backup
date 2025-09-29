"""
Unified Claude CLI Bridge Package
Provides a single, robust interface for all Claude API interactions
"""

from .bridge import BaseClaludeBridge, ClaudeBridgeConfig
from .claude_service import (
    ClaudeMetrics,
    ClaudeService,
    RateLimitConfig,
    get_claude_service,
    reset_claude_service,
)
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

__version__ = "1.1.0"

__all__ = [
    # Bridge classes
    "BaseClaludeBridge",
    "ClaudeBridgeConfig",
    "JsonExtractor",
    "JsonExtractionStrategy",
    "BaseResponseValidator",
    "ClaudePlannerBridge",
    "ClaudePlanningResponse",
    "ClaudeReviewerBridge",
    "ClaudeReviewResponse",
    # Service
    "ClaudeService",
    "ClaudeMetrics",
    "RateLimitConfig",
    "get_claude_service",
    "reset_claude_service",
    # Exceptions
    "ClaudeError",
    "ClaudeNotFoundError",
    "ClaudeTimeoutError",
    "ClaudeResponseError",
    "ClaudeValidationError",
    "ClaudeRateLimitError",
    "ClaudeServiceError",
    "ClaudeBridgeError",
]
