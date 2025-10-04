# hive-browser

Browser automation toolkit using Playwright for end-to-end testing and web interaction.

## Overview

`hive-browser` provides a high-level API for browser automation, built on top of Playwright. It enables agents to interact with web UIs, read documentation, and perform end-to-end testing.

## Features

- **Browser Automation**: Navigate, click, fill forms, read content
- **Screenshot Capture**: Visual debugging and test artifacts
- **Smart Waiting**: Auto-wait for elements (eliminates flakiness)
- **Multi-Browser Support**: Chromium, Firefox, WebKit
- **Resource Management**: Automatic cleanup and error handling

## Installation

```bash
poetry install
poetry run playwright install chromium
```

## Usage

### Basic Browser Automation

```python
from hive_browser import BrowserClient

# Initialize browser
browser = BrowserClient(headless=True)

try:
    # Navigate to URL
    page = browser.goto_url("https://example.com")

    # Click element
    browser.click_element(page, "button#submit")

    # Fill form
    browser.fill_form(page, "input[name='email']", "test@example.com")

    # Read content
    content = browser.read_page_content(page)

    # Take screenshot
    browser.take_screenshot(page, "screenshot.png")

finally:
    # Always cleanup
    browser.close()
```

### Context Manager Pattern

```python
from hive_browser import BrowserClient

with BrowserClient() as browser:
    page = browser.goto_url("https://example.com")
    browser.click_element(page, "a.login")
    # Automatic cleanup on exit
```

## API Reference

### BrowserClient

#### `__init__(headless: bool = True, browser_type: str = "chromium")`
Initialize browser instance.

#### `goto_url(url: str) -> Page`
Navigate to URL with auto-waiting for DOM load.

#### `click_element(page: Page, selector: str) -> None`
Click element with smart waiting.

#### `fill_form(page: Page, selector: str, text: str) -> None`
Fill form field with text.

#### `read_page_content(page: Page) -> str`
Extract text content from page body.

#### `take_screenshot(page: Page, path: str) -> None`
Capture screenshot for debugging.

#### `close() -> None`
Cleanup browser resources.

## Architecture

- **BrowserClient**: High-level API for browser operations
- **Selectors**: CSS/XPath selector utilities
- **Assertions**: Page state validation helpers
- **Errors**: Browser-specific error handling

## Testing

```bash
# Unit tests (mocked browser)
pytest tests/unit -v

# Integration tests (real browser)
pytest tests/integration -v
```

## Project Chimera

This package is part of Project Chimera - the Human-Interface Agent initiative. It provides the "eyes and hands" for agents to interact with web UIs.

### Chimera Workflow Integration

1. **E2E Test Generation**: Generate browser-based tests
2. **Code Implementation**: Agents write code to pass tests
3. **Guardian Review**: Validate architectural compliance
4. **E2E Validation**: Run tests against deployed feature

## Dependencies

- **playwright**: Browser automation engine
- **hive-logging**: Structured logging
- **hive-errors**: Error handling framework

## License

Internal Hive Platform component
