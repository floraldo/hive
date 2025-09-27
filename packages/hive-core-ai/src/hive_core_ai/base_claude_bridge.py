#!/usr/bin/env python3
"""
Base Claude Bridge for AI agents - shared implementation for CLI interaction
"""

import os
import re
import json
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class BaseClaudeBridge(ABC):
    """
    Base class for Claude CLI integration - shared by AI Planner and AI Reviewer

    Improvements:
    - Single source of truth for Claude CLI detection
    - Shared subprocess execution with retry logic
    - Consistent error handling and fallback behavior
    - Automatic CLI flag management
    """

    def __init__(self, mock_mode: bool = False, timeout: int = 60):
        """
        Initialize base Claude bridge

        Args:
            mock_mode: If True, use mock responses instead of real Claude
            timeout: Timeout in seconds for Claude CLI calls
        """
        self.mock_mode = mock_mode
        self.timeout = timeout
        self.retry_attempts = 3

        if mock_mode:
            logger.info("Running in mock mode - will not call Claude CLI")
            self.claude_cmd = None
        else:
            self.claude_cmd = self._find_claude_cmd()
            if not self.claude_cmd:
                logger.warning("Claude CLI not found - will use fallback mode")

    def _find_claude_cmd(self) -> Optional[str]:
        """Find Claude CLI command with intelligent detection"""

        # Priority order: npm-global > PATH > fallback
        possible_paths = [
            Path.home() / ".npm-global" / "claude.cmd",  # Windows npm
            Path.home() / ".npm-global" / "claude",      # Unix npm
            Path.home() / "bin" / "claude",              # User bin
            Path("/usr/local/bin") / "claude",           # System bin
        ]

        # Check explicit paths first
        for path in possible_paths:
            if path.exists():
                logger.info(f"Found Claude CLI at: {path}")
                # Verify it's executable and working
                if self._verify_claude_cmd(str(path)):
                    return str(path)

        # Try system PATH
        try:
            result = subprocess.run(
                ["where" if os.name == "nt" else "which", "claude"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                claude_path = result.stdout.strip().split('\n')[0]
                if claude_path and self._verify_claude_cmd(claude_path):
                    logger.info(f"Found Claude CLI in PATH: {claude_path}")
                    return claude_path
        except Exception as e:
            logger.debug(f"PATH search failed: {e}")

        return None

    def _verify_claude_cmd(self, cmd_path: str) -> bool:
        """Verify Claude CLI is working"""
        try:
            result = subprocess.run(
                [cmd_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                shell=True if os.name == 'nt' else False
            )
            if result.returncode == 0 and "Claude" in result.stdout:
                logger.info(f"Verified Claude CLI version: {result.stdout.strip()}")
                return True
        except Exception as e:
            logger.debug(f"Failed to verify {cmd_path}: {e}")
        return False

    def execute_claude_prompt(self, prompt: str, retry_on_failure: bool = True) -> Optional[str]:
        """
        Execute a prompt with Claude CLI

        Args:
            prompt: The prompt to send to Claude
            retry_on_failure: Whether to retry on failure

        Returns:
            Claude's response or None on failure
        """
        if self.mock_mode:
            return self._generate_mock_response(prompt)

        if not self.claude_cmd:
            logger.error("Claude CLI not available")
            return None

        attempts = self.retry_attempts if retry_on_failure else 1

        for attempt in range(attempts):
            try:
                # Prepare command with standard flags
                cmd = [
                    self.claude_cmd,
                    '--print',  # Exit after response
                    '--dangerously-skip-permissions'  # For automation
                ]

                # Add additional flags if needed
                if os.environ.get('CLAUDE_MAX_TOKENS'):
                    cmd.extend(['--max-tokens', os.environ['CLAUDE_MAX_TOKENS']])

                cmd.append(prompt)

                logger.info(f"Executing Claude CLI (attempt {attempt + 1}/{attempts})")

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=self.timeout,
                    shell=True if os.name == 'nt' else False
                )

                if result.returncode == 0:
                    response = result.stdout.strip()
                    if response:
                        logger.info("Claude CLI responded successfully")
                        return response
                    else:
                        logger.warning("Claude CLI returned empty response")
                else:
                    logger.error(f"Claude CLI failed with code {result.returncode}")
                    logger.error(f"Error: {result.stderr[:500]}")

            except subprocess.TimeoutExpired:
                logger.error(f"Claude CLI timeout after {self.timeout}s")
            except Exception as e:
                logger.error(f"Claude CLI execution error: {e}")

            if attempt < attempts - 1:
                logger.info(f"Retrying in {2 ** attempt} seconds...")
                import time
                time.sleep(2 ** attempt)

        return None

    def extract_json_from_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        Extract JSON from Claude's response

        Handles multiple formats:
        - Plain JSON
        - JSON in markdown code blocks
        - JSON with surrounding text
        """
        if not response:
            return None

        # Try direct JSON parse first
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try to find JSON in markdown code blocks
        patterns = [
            r'```json\s*(\{.*?\})\s*```',  # JSON code block
            r'```\s*(\{.*?\})\s*```',       # Generic code block
            r'(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})',  # Nested JSON
        ]

        for pattern in patterns:
            match = re.search(pattern, response, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue

        logger.error("Could not extract valid JSON from response")
        return None

    @abstractmethod
    def _generate_mock_response(self, prompt: str) -> str:
        """Generate mock response for testing - must be implemented by subclasses"""
        pass

    @abstractmethod
    def create_fallback_response(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Create fallback response when Claude is unavailable - must be implemented"""
        pass


class ClaudeBridgeConfig:
    """Configuration for Claude bridge instances"""

    # Environment variable configuration
    CLAUDE_TIMEOUT = int(os.environ.get('CLAUDE_TIMEOUT', '60'))
    CLAUDE_RETRY_ATTEMPTS = int(os.environ.get('CLAUDE_RETRY_ATTEMPTS', '3'))
    CLAUDE_MOCK_MODE = os.environ.get('CLAUDE_MOCK_MODE', 'false').lower() == 'true'

    # Performance optimizations
    CACHE_RESPONSES = os.environ.get('CLAUDE_CACHE_RESPONSES', 'false').lower() == 'true'
    MAX_CACHE_SIZE = int(os.environ.get('CLAUDE_MAX_CACHE_SIZE', '100'))

    @classmethod
    def get_config(cls) -> Dict[str, Any]:
        """Get current configuration"""
        return {
            'timeout': cls.CLAUDE_TIMEOUT,
            'retry_attempts': cls.CLAUDE_RETRY_ATTEMPTS,
            'mock_mode': cls.CLAUDE_MOCK_MODE,
            'cache_responses': cls.CACHE_RESPONSES,
            'max_cache_size': cls.MAX_CACHE_SIZE
        }