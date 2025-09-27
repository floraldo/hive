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
    ClaudeValidationError
)

__version__ = "1.0.0"

__all__ = [
    "BaseClaludeBridge",
    "ClaudeBridgeConfig",
    "JsonExtractor",
    "JsonExtractionStrategy",
    "BaseResponseValidator",
    "ClaudePlannerBridge",
    "ClaudePlanningResponse",
    "ClaudeReviewerBridge",
    "ClaudeReviewResponse",
    "ClaudeError",
    "ClaudeNotFoundError",
    "ClaudeTimeoutError",
    "ClaudeResponseError",
    "ClaudeValidationError"
]