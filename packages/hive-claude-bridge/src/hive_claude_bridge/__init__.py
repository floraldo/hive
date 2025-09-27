"""
Unified Claude CLI Bridge Package
Provides a single, robust interface for all Claude API interactions
"""

from .bridge import BaseClaludeBridge, ClaudeBridgeConfig
from .json_parser import JsonExtractor, JsonExtractionStrategy
from .validators import BaseResponseValidator
from .planner_bridge import ClaudePlannerBridge, ClaudePlanningResponse
from .reviewer_bridge import ClaudeReviewerBridge, ClaudeReviewResponse
from .exceptions import (
    ClaudeError,
    ClaudeNotFoundError,
    ClaudeTimeoutError,
    ClaudeResponseError,
    ClaudeValidationError,
    ClaudeRateLimitError,
    ClaudeServiceError,
    ClaudeBridgeError
)
from .claude_service import (
    ClaudeService,
    ClaudeMetrics,
    RateLimitConfig,
    get_claude_service,
    reset_claude_service
)

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
    "ClaudeBridgeError"
]