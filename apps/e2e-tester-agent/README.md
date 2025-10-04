# E2E Tester Agent

AI-powered end-to-end test generation and execution agent for Project Chimera.

## Overview

The E2E Tester Agent generates comprehensive browser-based tests from natural language feature descriptions, executes them using Playwright, and reports results for autonomous development workflows.

## Features

- **AI Test Generation**: Uses Sequential Thinking to generate pytest scripts from feature descriptions
- **Browser Automation**: Leverages hive-browser (Playwright) for reliable E2E testing
- **Page Object Pattern**: Generates maintainable test code with page objects
- **Smart Assertions**: Automatically generates appropriate assertions from feature requirements
- **Scenario Parsing**: Extracts user actions and expected outcomes from natural language
- **Execution Reporting**: JSON-formatted test results for orchestration integration

## Architecture

```
e2e-tester-agent/
├── src/e2e_tester/
│   ├── agent.py              # Main agent orchestration
│   ├── test_generator.py     # AI-powered test generation
│   ├── test_executor.py      # pytest execution and reporting
│   ├── scenario_parser.py    # Natural language → test scenarios
│   ├── assertion_builder.py  # Generate test assertions
│   └── cli.py                # Command-line interface
├── templates/
│   ├── test_template.py.jinja2      # pytest test template
│   └── page_object.py.jinja2        # Page object template
└── tests/
    └── unit/                  # Unit tests
```

## Installation

```bash
poetry install
```

## Usage

### Generate E2E Test from Feature Description

```bash
e2e-tester generate \
  --feature "User can login with Google OAuth" \
  --url "https://myapp.dev/login" \
  --output tests/e2e/test_google_login.py
```

### Execute E2E Test

```bash
e2e-tester execute \
  --test tests/e2e/test_google_login.py \
  --report results/google_login_report.json
```

### End-to-End Workflow

```bash
e2e-tester run \
  --feature "User can login with Google OAuth" \
  --url "https://myapp.dev/login"
```

## API Usage

### Test Generation

```python
from e2e_tester import TestGenerator

generator = TestGenerator()

test_code = await generator.generate_test(
    feature="User can login with Google OAuth",
    url="https://myapp.dev/login",
    additional_context={
        "success_indicator": "User dashboard visible",
        "failure_indicator": "Error message displayed"
    }
)

print(test_code)
```

### Test Execution

```python
from e2e_tester import TestExecutor

executor = TestExecutor()

result = executor.execute_test(
    test_path="tests/e2e/test_google_login.py",
    capture_screenshots=True
)

print(f"Status: {result.status}")
print(f"Duration: {result.duration}s")
print(f"Screenshots: {result.screenshots}")
```

## Generated Test Example

```python
# tests/e2e/test_google_login.py (AI-generated)
import pytest
from hive_browser import BrowserClient

class LoginPage:
    \"\"\"Page object for login functionality.\"\"\"

    def __init__(self, page):
        self.page = page
        self.google_button = "button[data-testid='google-login']"

    def navigate(self, url):
        self.page.goto(url)

    def click_google_login(self):
        self.page.click(self.google_button)

    def is_google_button_visible(self):
        return self.page.is_visible(self.google_button)

@pytest.fixture
def browser():
    client = BrowserClient(headless=True)
    yield client
    client.close()

def test_google_login_button_exists(browser):
    \"\"\"Verify Google login button is visible on login page.\"\"\"
    page = browser.goto_url("https://myapp.dev/login")
    login_page = LoginPage(page)

    assert login_page.is_google_button_visible(), "Google login button not found"

    browser.take_screenshot(page, "screenshots/login_page.png")
```

## Integration with Chimera Workflow

### Phase 1: Generate Failing Test (Red)

```python
from e2e_tester import TestGenerator
from hive_orchestration import create_task

# Orchestrator creates E2E test generation task
task = create_task(
    "Generate E2E test for Google login",
    task_type="e2e_test_generation"
)

# E2E Tester generates failing test
generator = TestGenerator()
test_code = await generator.generate_test(
    feature="Add Google login button",
    url="https://myapp.dev/login"
)

# Test fails (button doesn't exist yet)
```

### Phase 2: Coder Implements Feature (Green)

```python
# Coder Agent writes code to make test pass
# (React component, OAuth integration, etc.)
```

### Phase 3: E2E Validation

```python
from e2e_tester import TestExecutor

# Execute test against deployed feature
executor = TestExecutor()
result = executor.execute_test(
    test_path="tests/e2e/test_google_login.py",
    url="https://staging.myapp.dev/login"
)

# Test passes → Task complete!
```

## Configuration

### Environment Variables

```bash
E2E_HEADLESS=true              # Run browser in headless mode
E2E_BROWSER=chromium           # Browser type (chromium, firefox, webkit)
E2E_TIMEOUT=30000              # Default timeout in milliseconds
E2E_SCREENSHOT_ON_FAILURE=true # Capture screenshots on test failure
E2E_REPORT_FORMAT=json         # Report format (json, html)
```

### Sequential Thinking Integration

The agent uses Sequential Thinking MCP for structured test generation:

```python
from e2e_tester.test_generator import TestGenerator

generator = TestGenerator(
    use_sequential_thinking=True,
    max_reasoning_tokens=4000
)
```

## Testing

```bash
# Unit tests
pytest tests/unit -v

# Integration tests (requires real browser)
pytest tests/integration -v

# All tests
pytest -v
```

## Project Chimera

This agent is part of Project Chimera - The Human-Interface Agent initiative. It closes the autonomous development loop by:

1. **Generating E2E tests** from feature descriptions (TDD Red phase)
2. **Validating implementations** against user requirements (Green phase)
3. **Enabling full-stack autonomy** through browser interaction

## License

Internal Hive Platform component
