"""Browser-specific errors and exceptions."""

from __future__ import annotations

from hive_errors import BaseError


class BrowserError(BaseError):
    """Base class for browser-related errors."""



class NavigationError(BrowserError):
    """Raised when navigation to URL fails."""

    def __init__(self, url: str, reason: str):
        super().__init__(f"Failed to navigate to {url}: {reason}")
        self.url = url
        self.reason = reason


class ElementNotFoundError(BrowserError):
    """Raised when element selector doesn't match any elements."""

    def __init__(self, selector: str, timeout: int = 30):
        super().__init__(f"Element not found: {selector} (timeout: {timeout}s)")
        self.selector = selector
        self.timeout = timeout


class BrowserTimeoutError(BrowserError):
    """Raised when browser operation times out."""

    def __init__(self, operation: str, timeout: int):
        super().__init__(f"Operation '{operation}' timed out after {timeout}s")
        self.operation = operation
        self.timeout = timeout


class ScreenshotError(BrowserError):
    """Raised when screenshot capture fails."""

    def __init__(self, path: str, reason: str):
        super().__init__(f"Failed to capture screenshot to {path}: {reason}")
        self.path = path
        self.reason = reason
