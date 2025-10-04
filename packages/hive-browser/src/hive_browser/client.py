"""High-level browser automation client using Playwright."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from hive_logging import get_logger
from playwright.sync_api import Browser, Page, Playwright, sync_playwright

from .errors import BrowserTimeoutError, ElementNotFoundError, NavigationError, ScreenshotError

logger = get_logger(__name__)

BrowserType = Literal["chromium", "firefox", "webkit"]


class BrowserClient:
    """
    High-level browser automation client.

    Provides simplified API for browser operations using Playwright.
    Handles resource management, error handling, and smart waiting.

    Example:
        browser = BrowserClient(headless=True)
        page = browser.goto_url("https://example.com")
        browser.click_element(page, "button#submit")
        browser.close()
    """

    def __init__(self, headless: bool = True, browser_type: BrowserType = "chromium") -> None:
        """
        Initialize browser instance.

        Args:
            headless: Run browser in headless mode (no UI)
            browser_type: Browser engine to use (chromium, firefox, webkit)
        """
        self.headless = headless
        self.browser_type = browser_type
        self.logger = logger

        # Initialize Playwright
        self._playwright: Playwright = sync_playwright().start()

        # Launch browser
        if browser_type == "chromium":
            self._browser: Browser = self._playwright.chromium.launch(headless=headless)
        elif browser_type == "firefox":
            self._browser: Browser = self._playwright.firefox.launch(headless=headless)
        elif browser_type == "webkit":
            self._browser: Browser = self._playwright.webkit.launch(headless=headless)
        else:
            msg = f"Unsupported browser type: {browser_type}"
            raise ValueError(msg)

        self.logger.info(f"Browser initialized: {browser_type} (headless={headless})")

    def goto_url(self, url: str, timeout: int = 30000) -> Page:
        """
        Navigate to URL with auto-waiting for DOM load.

        Args:
            url: Target URL to navigate to
            timeout: Navigation timeout in milliseconds (default: 30s)

        Returns:
            Page object for further interactions

        Raises:
            NavigationError: If navigation fails
        """
        try:
            page = self._browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=timeout)
            self.logger.info(f"Navigated to: {url}")
            return page

        except Exception as e:
            raise NavigationError(url, str(e)) from e

    def click_element(self, page: Page, selector: str, timeout: int = 30000) -> None:
        """
        Click element with smart waiting.

        Playwright automatically waits for:
        - Element to be visible
        - Element to be enabled
        - Element to be stable (not animating)

        Args:
            page: Page object from goto_url
            selector: CSS or XPath selector
            timeout: Wait timeout in milliseconds (default: 30s)

        Raises:
            ElementNotFoundError: If element not found within timeout
        """
        try:
            page.click(selector, timeout=timeout)
            self.logger.info(f"Clicked: {selector}")

        except Exception as e:
            raise ElementNotFoundError(selector, timeout // 1000) from e

    def fill_form(self, page: Page, selector: str, text: str, timeout: int = 30000) -> None:
        """
        Fill form field with text.

        Args:
            page: Page object from goto_url
            selector: CSS or XPath selector for input field
            text: Text to fill
            timeout: Wait timeout in milliseconds (default: 30s)

        Raises:
            ElementNotFoundError: If element not found within timeout
        """
        try:
            page.fill(selector, text, timeout=timeout)
            self.logger.info(f"Filled {selector} with: {text[:20]}...")

        except Exception as e:
            raise ElementNotFoundError(selector, timeout // 1000) from e

    def read_page_content(self, page: Page) -> str:
        """
        Extract text content from page body.

        Args:
            page: Page object from goto_url

        Returns:
            Text content of page body
        """
        content = page.inner_text("body")
        self.logger.info(f"Read page content: {len(content)} characters")
        return content

    def take_screenshot(self, page: Page, path: str | Path) -> None:
        """
        Capture screenshot for debugging.

        Args:
            page: Page object from goto_url
            path: File path to save screenshot (PNG format)

        Raises:
            ScreenshotError: If screenshot capture fails
        """
        try:
            screenshot_path = Path(path)
            screenshot_path.parent.mkdir(parents=True, exist_ok=True)

            page.screenshot(path=str(screenshot_path))
            self.logger.info(f"Screenshot saved: {screenshot_path}")

        except Exception as e:
            raise ScreenshotError(str(path), str(e)) from e

    def is_element_visible(self, page: Page, selector: str) -> bool:
        """
        Check if element is visible on page.

        Args:
            page: Page object from goto_url
            selector: CSS or XPath selector

        Returns:
            True if element is visible, False otherwise
        """
        visible = page.is_visible(selector)
        self.logger.info(f"Element {selector} visible: {visible}")
        return visible

    def wait_for_selector(self, page: Page, selector: str, timeout: int = 30000) -> None:
        """
        Wait for element to appear on page.

        Args:
            page: Page object from goto_url
            selector: CSS or XPath selector
            timeout: Wait timeout in milliseconds (default: 30s)

        Raises:
            BrowserTimeoutError: If element doesn't appear within timeout
        """
        try:
            page.wait_for_selector(selector, timeout=timeout)
            self.logger.info(f"Element appeared: {selector}")

        except Exception as e:
            raise BrowserTimeoutError(f"wait_for_selector({selector})", timeout // 1000) from e

    def close(self) -> None:
        """
        Cleanup browser resources.

        Always call this method when done to prevent resource leaks.
        """
        try:
            self._browser.close()
            self._playwright.stop()
            self.logger.info("Browser closed")

        except Exception as e:
            self.logger.warning(f"Error during browser cleanup: {e}")

    def __enter__(self) -> BrowserClient:
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:  # noqa: ANN001
        """Context manager exit with automatic cleanup."""
        self.close()
