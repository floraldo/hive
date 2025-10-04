"""Data models for E2E test generation and execution."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class TestStatus(str, Enum):
    """Test execution status."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"


class UserAction(str, Enum):
    """Types of user actions in E2E tests."""

    NAVIGATE = "navigate"
    CLICK = "click"
    FILL = "fill"
    SELECT = "select"
    SUBMIT = "submit"
    WAIT = "wait"
    VERIFY = "verify"


class AssertionType(str, Enum):
    """Types of test assertions."""

    VISIBLE = "visible"
    NOT_VISIBLE = "not_visible"
    TEXT_CONTAINS = "text_contains"
    URL_MATCHES = "url_matches"
    ELEMENT_EXISTS = "element_exists"
    ATTRIBUTE_EQUALS = "attribute_equals"


class TestScenario(BaseModel):
    """Parsed test scenario from feature description."""

    feature_name: str = Field(description="Name of the feature being tested")
    description: str = Field(description="Detailed feature description")
    target_url: str = Field(description="URL to test against")

    # User journey
    actions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Sequence of user actions",
    )

    # Expected outcomes
    success_assertions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Assertions for successful scenario",
    )
    failure_assertions: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Assertions for failure scenario",
    )

    # Page objects
    page_elements: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of element names to selectors",
    )


class TestResult(BaseModel):
    """Result from test execution."""

    test_path: str = Field(description="Path to executed test file")
    status: TestStatus = Field(description="Overall test status")
    duration: float = Field(description="Execution time in seconds")

    # Execution details
    tests_run: int = Field(default=0, description="Number of tests executed")
    tests_passed: int = Field(default=0, description="Number of tests passed")
    tests_failed: int = Field(default=0, description="Number of tests failed")
    tests_skipped: int = Field(default=0, description="Number of tests skipped")

    # Output
    stdout: str = Field(default="", description="Standard output")
    stderr: str = Field(default="", description="Standard error")

    # Artifacts
    screenshots: list[str] = Field(
        default_factory=list,
        description="Paths to captured screenshots",
    )

    # Metadata
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="Execution timestamp",
    )
    browser_type: str = Field(default="chromium", description="Browser used")
    headless: bool = Field(default=True, description="Headless mode")


class GeneratedTest(BaseModel):
    """Generated test code and metadata."""

    test_code: str = Field(description="Generated pytest code")
    test_name: str = Field(description="Name of generated test")
    page_object_code: str | None = Field(
        default=None,
        description="Generated page object class (if applicable)",
    )

    # Generation metadata
    feature_description: str = Field(description="Original feature description")
    target_url: str = Field(description="Target URL")
    generated_at: datetime = Field(
        default_factory=datetime.now,
        description="Generation timestamp",
    )

    # AI metadata
    tokens_used: int | None = Field(default=None, description="Tokens consumed")
    reasoning_steps: int | None = Field(
        default=None,
        description="Sequential thinking steps",
    )


class E2ETaskConfig(BaseModel):
    """Configuration for E2E test generation/execution task."""

    feature_description: str = Field(description="Feature to test")
    target_url: str = Field(description="URL to test against")

    # Generation options
    generate_page_object: bool = Field(
        default=True,
        description="Generate page object pattern",
    )
    include_failure_tests: bool = Field(
        default=True,
        description="Generate negative test cases",
    )

    # Execution options
    headless: bool = Field(default=True, description="Run browser headless")
    browser_type: str = Field(default="chromium", description="Browser to use")
    timeout: int = Field(default=30000, description="Timeout in milliseconds")
    capture_screenshots: bool = Field(
        default=True,
        description="Capture screenshots on failure",
    )

    # Output
    output_path: Path | None = Field(
        default=None,
        description="Path to save generated test",
    )
    report_path: Path | None = Field(
        default=None,
        description="Path to save execution report",
    )
