"""hive-browser - Browser automation toolkit using Playwright.

Provides high-level API for browser automation, enabling agents to interact
with web UIs, read documentation, and perform end-to-end testing.

Example:
    from hive_browser import BrowserClient

    browser = BrowserClient(headless=True)
    page = browser.goto_url("https://example.com")
    browser.click_element(page, "button#submit")
    browser.close()

"""

from .client import BrowserClient
from .errors import BrowserError, ElementNotFoundError, NavigationError

__all__ = [
    "BrowserClient",
    "BrowserError",
    "ElementNotFoundError",
    "NavigationError",
]

__version__ = "0.1.0"
