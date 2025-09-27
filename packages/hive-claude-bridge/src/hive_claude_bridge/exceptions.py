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