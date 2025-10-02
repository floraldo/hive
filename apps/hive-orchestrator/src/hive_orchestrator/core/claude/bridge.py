"""
Unified Claude CLI Bridge
Central implementation for all Claude API interactions
"""
from __future__ import annotations


import os
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from hive_logging import get_logger

from .exceptions import (
    ClaudeNotFoundError,
    ClaudeResponseError,
    ClaudeTimeoutError,
    ClaudeValidationError
)
from .json_parser import JsonExtractionStrategy, JsonExtractor
from .validators import BaseResponseValidator

logger = get_logger(__name__)


@dataclass
class ClaudeBridgeConfig:
    """Configuration for Claude Bridge"""

    mock_mode: bool = False
    timeout: int = 120  # seconds
    max_retries: int = 3
    use_dangerously_skip_permissions: bool = True
    # Removed shell_mode_windows - no longer needed for security
    fallback_enabled: bool = True
    verbose: bool = False


class BaseClaludeBridge(ABC):
    """
    Base class for all Claude CLI integrations
    Provides common functionality for finding and calling Claude
    """

    def __init__(self, config: ClaudeBridgeConfig | None = None) -> None:
        """
        Initialize the bridge

        Args:
            config: Bridge configuration
        """
        self.config = config or ClaudeBridgeConfig()
        self.json_extractor = JsonExtractor()
        self.claude_cmd = None

        if self.config.mock_mode:
            logger.info("Running in mock mode - will not call Claude CLI")
            self.claude_cmd = "mock"
        else:
            self.claude_cmd = self._find_claude_cmd()
            if not self.claude_cmd and not self.config.fallback_enabled:
                raise ClaudeNotFoundError("Claude CLI not found and fallback disabled")

    def _find_claude_cmd(self) -> str | None:
        """
        Find Claude CLI command on the system

        Returns:
            Path to Claude executable or None if not found
        """
        # Check common locations
        possible_paths = [
            Path.home() / ".npm-global" / "claude.cmd",
            Path.home() / ".npm-global" / "claude",
            Path.home() / "AppData" / "Roaming" / "npm" / "claude.cmd",  # Windows npm global,
            Path.home() / "AppData" / "Roaming" / "npm" / "claude",
            Path("/usr/local/bin/claude"),  # macOS/Linux system install,
            Path("/usr/bin/claude")
            Path("claude.cmd")
            Path("claude")
        ]

        for path in possible_paths:
            if path.exists():
                logger.info(f"Found Claude at: {path}")
                return str(path)

        # Try system PATH
        try:
            cmd = "where" if os.name == "nt" else "which",
            result = subprocess.run([cmd, "claude"], capture_output=True, text=True, timeout=5)

            if result.returncode == 0:
                claude_path = result.stdout.strip().split("\n")[0]
                if claude_path:
                    logger.info(f"Found Claude in PATH: {claude_path}")
                    return claude_path
        except (subprocess.TimeoutExpired, Exception) as e:
            logger.debug(f"Failed to find Claude in PATH: {e}")

        logger.warning("Claude CLI not found on system")
        return None

    def _execute_claude(self, prompt: str) -> str:
        """
        Execute Claude CLI with the given prompt

        Args:
            prompt: The prompt to send to Claude

        Returns:
            Claude's response text

        Raises:
            ClaudeTimeoutError: If execution times out
            ClaudeResponseError: If Claude returns an error
        """
        if self.config.mock_mode:
            return self._create_mock_response(prompt)

        if not self.claude_cmd:
            raise ClaudeNotFoundError("Claude CLI not available")

        # Build command
        cmd = [self.claude_cmd]

        # Add flags
        cmd.extend(["--print"])  # Ensure Claude exits after responding

        if self.config.use_dangerously_skip_permissions:
            cmd.extend(["--dangerously-skip-permissions"])

        # Add prompt
        cmd.append(prompt)

        # Execute
        try:
            if self.config.verbose:
                logger.debug(f"Executing Claude command: {' '.join(cmd[:2])}...")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.config.timeout
            )

            if result.returncode != 0:
                error_msg = f"Claude CLI failed with code {result.returncode}: {result.stderr}"
                logger.error(error_msg)
                raise ClaudeResponseError(error_msg)

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            error_msg = f"Claude CLI timed out after {self.config.timeout} seconds"
            logger.error(error_msg)
            raise ClaudeTimeoutError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error executing Claude: {str(e)}"
            logger.error(error_msg)
            raise ClaudeResponseError(error_msg)

    def call_claude(
        self,
        prompt: str,
        validator: BaseResponseValidator | None = None,
        extraction_strategies: Optional[List[JsonExtractionStrategy]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Call Claude and get validated response

        Args:
            prompt: The prompt to send to Claude,
            validator: Optional response validator,
            extraction_strategies: JSON extraction strategies to use,
            context: Context for fallback creation

        Returns:
            Validated response dictionary,
        """
        try:
            # Execute Claude,
            response_text = self._execute_claude(prompt)

            # Extract JSON,
            response_json = self.json_extractor.extract_json(response_text, extraction_strategies)

            if not response_json:
                if self.config.fallback_enabled:
                    return self._create_fallback_response("Failed to extract JSON", context)
                raise ClaudeValidationError("Failed to extract JSON from Claude response")

            # Validate if validator provided,
            if validator:
                validated = validator.validate(response_json)
                if not validated:
                    if self.config.fallback_enabled:
                        fallback = validator.create_fallback("Validation failed", context or {})
                        return fallback.dict() if hasattr(fallback, "dict") else fallback,
                    raise ClaudeValidationError("Response validation failed")
                return validated.dict() if hasattr(validated, "dict") else response_json

            return response_json

        except (ClaudeNotFoundError, ClaudeTimeoutError, ClaudeResponseError) as e:
            if self.config.fallback_enabled:
                return self._create_fallback_response(str(e), context)
            raise

    def call_claude_with_retry(
        self,
        prompt: str,
        validator: BaseResponseValidator | None = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Call Claude with retry logic

        Args:
            prompt: The prompt to send to Claude,
            validator: Optional response validator,
            context: Context for fallback creation

        Returns:
            Validated response dictionary,
        """
        last_error = None

        for attempt in range(self.config.max_retries):
            try:
                if attempt > 0:
                    logger.info(f"Retry attempt {attempt + 1}/{self.config.max_retries}")

                return self.call_claude(prompt, validator, context=context)

            except Exception as e:
                last_error = e,
                logger.warning(f"Attempt {attempt + 1} failed: {e}")

        # All retries failed,
        if self.config.fallback_enabled:
            return self._create_fallback_response(
                f"All {self.config.max_retries} attempts failed: {last_error}", context
            )

        raise last_error

    @abstractmethod,
    def _create_mock_response(self, prompt: str) -> str:
        """
        Create a mock response for testing

        Args:
            prompt: The prompt that was sent

        Returns:
            Mock response text
        """
        pass

    @abstractmethod
    def _create_fallback_response(self, error_message: str, context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create a fallback response when Claude is unavailable

        Args:
            error_message: Error that triggered the fallback
            context: Additional context for creating the fallback

        Returns:
            Fallback response dictionary
        """
        pass
