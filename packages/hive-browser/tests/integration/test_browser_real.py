"""Integration tests for BrowserClient with real browser automation.

These tests require Playwright browsers to be installed:
    poetry run playwright install chromium
"""

from __future__ import annotations

import pytest

from hive_browser import BrowserClient
from hive_browser.errors import ElementNotFoundError, NavigationError


@pytest.fixture
def browser():
    """Fixture providing real browser instance."""
    client = BrowserClient(headless=True)
    yield client
    client.close()


class TestRealBrowserNavigation:
    """Test browser navigation with real browser."""

    def test_navigate_to_example_com(self, browser: BrowserClient) -> None:
        """Test navigation to example.com."""
        page = browser.goto_url("https://example.com")

        # Verify page loaded
        assert page is not None
        assert "example" in page.url.lower()

    def test_read_page_content(self, browser: BrowserClient) -> None:
        """Test reading content from real page."""
        page = browser.goto_url("https://example.com")
        content = browser.read_page_content(page)

        # Example.com should contain expected text
        assert len(content) > 0
        assert "Example Domain" in content

    def test_navigation_to_invalid_url(self, browser: BrowserClient) -> None:
        """Test navigation to invalid URL raises error."""
        with pytest.raises(NavigationError):
            browser.goto_url("https://this-domain-definitely-does-not-exist-12345.com", timeout=5000)


class TestRealBrowserInteractions:
    """Test browser interactions with real elements."""

    def test_element_visibility_check(self, browser: BrowserClient) -> None:
        """Test checking element visibility on real page."""
        page = browser.goto_url("https://example.com")

        # The h1 element should be visible
        visible = browser.is_element_visible(page, "h1")
        assert visible is True

        # Non-existent element should not be visible
        visible = browser.is_element_visible(page, "#non-existent-element")
        assert visible is False

    def test_wait_for_selector(self, browser: BrowserClient) -> None:
        """Test waiting for element to appear."""
        page = browser.goto_url("https://example.com")

        # h1 already exists, should return immediately
        browser.wait_for_selector(page, "h1", timeout=5000)

    def test_click_nonexistent_element(self, browser: BrowserClient) -> None:
        """Test clicking non-existent element raises error."""
        page = browser.goto_url("https://example.com")

        with pytest.raises(ElementNotFoundError):
            browser.click_element(page, "#does-not-exist", timeout=2000)


class TestRealBrowserScreenshots:
    """Test screenshot functionality with real browser."""

    def test_take_screenshot(self, browser: BrowserClient, tmp_path) -> None:
        """Test capturing screenshot of real page."""
        page = browser.goto_url("https://example.com")

        screenshot_path = tmp_path / "example_screenshot.png"
        browser.take_screenshot(page, str(screenshot_path))

        # Verify screenshot file was created
        assert screenshot_path.exists()
        assert screenshot_path.stat().st_size > 0  # Not empty


class TestBrowserContextManager:
    """Test context manager pattern with real browser."""

    def test_context_manager_auto_cleanup(self) -> None:
        """Test context manager automatically cleans up resources."""
        with BrowserClient(headless=True) as browser:
            page = browser.goto_url("https://example.com")
            content = browser.read_page_content(page)
            assert "Example Domain" in content

        # Browser should be closed after context exit
        # No assertion needed - test passes if no exception raised


class TestMultipleBrowserTypes:
    """Test different browser engines."""

    @pytest.mark.parametrize("browser_type", ["chromium", "firefox"])
    def test_browser_engine_navigation(self, browser_type: str) -> None:
        """Test navigation works across different browser engines."""
        with BrowserClient(headless=True, browser_type=browser_type) as browser:  # type: ignore
            page = browser.goto_url("https://example.com")
            content = browser.read_page_content(page)
            assert "Example Domain" in content
