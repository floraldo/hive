"""Unit tests for BrowserClient using mocked Playwright."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from hive_browser import BrowserClient
from hive_browser.errors import ElementNotFoundError, NavigationError, ScreenshotError


class TestBrowserClientInitialization:
    """Test browser initialization and configuration."""

    @patch("hive_browser.client.sync_playwright")
    def test_init_chromium_headless(self, mock_playwright: Mock) -> None:
        """Test initialization with default chromium headless."""
        mock_pw = MagicMock()
        mock_playwright.return_value.start.return_value = mock_pw

        browser = BrowserClient(headless=True, browser_type="chromium")

        mock_pw.chromium.launch.assert_called_once_with(headless=True)
        assert browser.headless is True
        assert browser.browser_type == "chromium"

    @patch("hive_browser.client.sync_playwright")
    def test_init_firefox_visible(self, mock_playwright: Mock) -> None:
        """Test initialization with Firefox in visible mode."""
        mock_pw = MagicMock()
        mock_playwright.return_value.start.return_value = mock_pw

        browser = BrowserClient(headless=False, browser_type="firefox")

        mock_pw.firefox.launch.assert_called_once_with(headless=False)
        assert browser.headless is False
        assert browser.browser_type == "firefox"

    @patch("hive_browser.client.sync_playwright")
    def test_init_webkit(self, mock_playwright: Mock) -> None:
        """Test initialization with WebKit."""
        mock_pw = MagicMock()
        mock_playwright.return_value.start.return_value = mock_pw

        _browser = BrowserClient(headless=True, browser_type="webkit")

        mock_pw.webkit.launch.assert_called_once_with(headless=True)

    @patch("hive_browser.client.sync_playwright")
    def test_init_invalid_browser_type(self, mock_playwright: Mock) -> None:
        """Test initialization with invalid browser type raises error."""
        mock_pw = MagicMock()
        mock_playwright.return_value.start.return_value = mock_pw

        with pytest.raises(ValueError) as exc_info:
            BrowserClient(browser_type="invalid")  # type: ignore

        assert "Unsupported browser type" in str(exc_info.value)


class TestBrowserNavigation:
    """Test browser navigation operations."""

    @patch("hive_browser.client.sync_playwright")
    def test_goto_url_success(self, mock_playwright: Mock) -> None:
        """Test successful navigation to URL."""
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_playwright.return_value.start.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        browser = BrowserClient()
        page = browser.goto_url("https://example.com")

        mock_browser.new_page.assert_called_once()
        mock_page.goto.assert_called_once_with(
            "https://example.com", wait_until="domcontentloaded", timeout=30000,
        )
        assert page == mock_page

    @patch("hive_browser.client.sync_playwright")
    def test_goto_url_navigation_failure(self, mock_playwright: Mock) -> None:
        """Test navigation failure raises NavigationError."""
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_playwright.return_value.start.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page
        mock_page.goto.side_effect = Exception("Network error")

        browser = BrowserClient()

        with pytest.raises(NavigationError) as exc_info:
            browser.goto_url("https://invalid.com")

        assert "Network error" in str(exc_info.value)
        assert exc_info.value.url == "https://invalid.com"

    @patch("hive_browser.client.sync_playwright")
    def test_goto_url_custom_timeout(self, mock_playwright: Mock) -> None:
        """Test navigation with custom timeout."""
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_playwright.return_value.start.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_page.return_value = mock_page

        browser = BrowserClient()
        browser.goto_url("https://example.com", timeout=60000)

        mock_page.goto.assert_called_once_with(
            "https://example.com", wait_until="domcontentloaded", timeout=60000,
        )


class TestBrowserInteractions:
    """Test browser interaction methods."""

    @patch("hive_browser.client.sync_playwright")
    def test_click_element_success(self, mock_playwright: Mock) -> None:
        """Test successful element click."""
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_playwright.return_value.start.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser

        browser = BrowserClient()
        browser.click_element(mock_page, "button#submit")

        mock_page.click.assert_called_once_with("button#submit", timeout=30000)

    @patch("hive_browser.client.sync_playwright")
    def test_click_element_not_found(self, mock_playwright: Mock) -> None:
        """Test clicking non-existent element raises error."""
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_playwright.return_value.start.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser
        mock_page.click.side_effect = Exception("Element not found")

        browser = BrowserClient()

        with pytest.raises(ElementNotFoundError) as exc_info:
            browser.click_element(mock_page, "button#missing")

        assert "button#missing" in str(exc_info.value)

    @patch("hive_browser.client.sync_playwright")
    def test_fill_form_success(self, mock_playwright: Mock) -> None:
        """Test successful form filling."""
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_playwright.return_value.start.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser

        browser = BrowserClient()
        browser.fill_form(mock_page, "input[name='email']", "test@example.com")

        mock_page.fill.assert_called_once_with("input[name='email']", "test@example.com", timeout=30000)

    @patch("hive_browser.client.sync_playwright")
    def test_fill_form_element_not_found(self, mock_playwright: Mock) -> None:
        """Test filling non-existent form raises error."""
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_playwright.return_value.start.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser
        mock_page.fill.side_effect = Exception("Element not found")

        browser = BrowserClient()

        with pytest.raises(ElementNotFoundError):
            browser.fill_form(mock_page, "input#missing", "text")


class TestBrowserContentReading:
    """Test reading page content."""

    @patch("hive_browser.client.sync_playwright")
    def test_read_page_content(self, mock_playwright: Mock) -> None:
        """Test reading page content."""
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_playwright.return_value.start.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser
        mock_page.inner_text.return_value = "Page content text"

        browser = BrowserClient()
        content = browser.read_page_content(mock_page)

        mock_page.inner_text.assert_called_once_with("body")
        assert content == "Page content text"


class TestBrowserScreenshots:
    """Test screenshot functionality."""

    @patch("hive_browser.client.sync_playwright")
    def test_take_screenshot_success(self, mock_playwright: Mock, tmp_path: Path) -> None:
        """Test successful screenshot capture."""
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_playwright.return_value.start.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser

        browser = BrowserClient()
        screenshot_path = tmp_path / "screenshot.png"

        browser.take_screenshot(mock_page, str(screenshot_path))

        mock_page.screenshot.assert_called_once_with(path=str(screenshot_path))

    @patch("hive_browser.client.sync_playwright")
    def test_take_screenshot_creates_directory(self, mock_playwright: Mock, tmp_path: Path) -> None:
        """Test screenshot creates parent directory if missing."""
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_playwright.return_value.start.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser

        browser = BrowserClient()
        screenshot_path = tmp_path / "nested" / "dir" / "screenshot.png"

        browser.take_screenshot(mock_page, screenshot_path)

        assert screenshot_path.parent.exists()
        mock_page.screenshot.assert_called_once()

    @patch("hive_browser.client.sync_playwright")
    def test_take_screenshot_failure(self, mock_playwright: Mock) -> None:
        """Test screenshot failure raises ScreenshotError."""
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_playwright.return_value.start.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser
        mock_page.screenshot.side_effect = Exception("Disk full")

        browser = BrowserClient()

        with pytest.raises(ScreenshotError) as exc_info:
            browser.take_screenshot(mock_page, "/invalid/path/screenshot.png")

        assert "Disk full" in str(exc_info.value)


class TestBrowserUtilities:
    """Test utility methods."""

    @patch("hive_browser.client.sync_playwright")
    def test_is_element_visible_true(self, mock_playwright: Mock) -> None:
        """Test element visibility check returns True."""
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_playwright.return_value.start.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser
        mock_page.is_visible.return_value = True

        browser = BrowserClient()
        visible = browser.is_element_visible(mock_page, "button#submit")

        assert visible is True
        mock_page.is_visible.assert_called_once_with("button#submit")

    @patch("hive_browser.client.sync_playwright")
    def test_is_element_visible_false(self, mock_playwright: Mock) -> None:
        """Test element visibility check returns False."""
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_page = MagicMock()

        mock_playwright.return_value.start.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser
        mock_page.is_visible.return_value = False

        browser = BrowserClient()
        visible = browser.is_element_visible(mock_page, "button#hidden")

        assert visible is False


class TestBrowserCleanup:
    """Test resource cleanup."""

    @patch("hive_browser.client.sync_playwright")
    def test_close_cleanup(self, mock_playwright: Mock) -> None:
        """Test close method cleans up resources."""
        mock_pw = MagicMock()
        mock_browser = MagicMock()

        mock_playwright.return_value.start.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser

        browser = BrowserClient()
        browser.close()

        mock_browser.close.assert_called_once()
        mock_pw.stop.assert_called_once()

    @patch("hive_browser.client.sync_playwright")
    def test_context_manager(self, mock_playwright: Mock) -> None:
        """Test context manager auto-cleanup."""
        mock_pw = MagicMock()
        mock_browser = MagicMock()

        mock_playwright.return_value.start.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser

        with BrowserClient() as browser:
            assert browser is not None

        mock_browser.close.assert_called_once()
        mock_pw.stop.assert_called_once()

    @patch("hive_browser.client.sync_playwright")
    def test_close_handles_errors(self, mock_playwright: Mock) -> None:
        """Test close handles cleanup errors gracefully."""
        mock_pw = MagicMock()
        mock_browser = MagicMock()

        mock_playwright.return_value.start.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.close.side_effect = Exception("Cleanup error")

        browser = BrowserClient()
        browser.close()  # Should not raise, just log warning

        mock_browser.close.assert_called_once()
