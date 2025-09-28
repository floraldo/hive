"""
Exception hierarchy for Claude Bridge operations
"""


class ClaudeError(Exception):
    """Base exception for all Claude-related errors"""

    pass


class ClaudeNotFoundError(ClaudeError):
    """Raised when Claude CLI is not found on the system"""

    pass


class ClaudeTimeoutError(ClaudeError):
    """Raised when Claude CLI execution times out"""

    pass


class ClaudeResponseError(ClaudeError):
    """Raised when Claude returns an unexpected response"""

    pass


class ClaudeValidationError(ClaudeError):
    """Raised when Claude response fails validation"""

    pass


class ClaudeRateLimitError(ClaudeError):
    """Raised when rate limit is exceeded"""

    pass


class ClaudeServiceError(ClaudeError):
    """General Claude service error"""

    def __init__(self, message: str, operation: str, original_error: Exception = None):
        super().__init__(message)
        self.operation = operation
        self.original_error = original_error


class ClaudeBridgeError(ClaudeError):
    """Base exception for bridge-specific errors"""

    def __init__(self, message: str, original_error: Exception = None):
        super().__init__(message)
        self.original_error = original_error
