"""
Security utilities for Hive AI components.

Provides input validation, secret management, and security controls
to prevent common security vulnerabilities in AI operations.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass
from enum import Enum
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


class SecurityLevel(Enum):
    """Security validation levels."""

    BASIC = "basic"
    STANDARD = "standard"
    STRICT = "strict"


@dataclass
class ValidationResult:
    """Result of input validation."""

    is_valid: bool
    sanitized_input: str | None = None
    violations: List[str] = None
    risk_level: str = "low"

    def __post_init__(self) -> None:
        """Initialize violations list if None."""
        if self.violations is None:
            self.violations = []


class InputValidator:
    """Validates and sanitizes inputs for AI operations."""

    # Common injection patterns to detect
    INJECTION_PATTERNS = [
        r"<script[^>]*>.*?</script>",  # Script tags,
        r"javascript:",  # JavaScript URLs,
        r"data:text/html",  # Data URLs with HTML,
        r"vbscript:",  # VBScript URLs,
        r"on\w+\s*=",  # Event handlers,
        r"expression\s*\(",  # CSS expressions,
        r'import\s+["\']',  # Python imports,
        r"exec\s*\(",  # Code execution,
        r"eval\s*\(",  # Code evaluation,
        r"__import__",  # Direct imports,
        r"subprocess",  # System commands,
        r"os\.system",  # OS commands,
        r"shell=True",  # Shell execution
    ]

    # Patterns that might indicate prompt injection
    PROMPT_INJECTION_PATTERNS = [
        r"ignore\s+previous\s+instructions"
        r"forget\s+everything"
        r"act\s+as\s+if",
        r"pretend\s+to\s+be",
        r"system\s*:\s*",
        r"assistant\s*:\s*"
        r"human\s*:\s*"
        r"\\n\\n",  # Multiple newlines
        r"\[INST\]",  # Instruction markers
        r"\[/INST\]" r"</s>",  # Special tokens
        r"<s>",
    ]

    def __init__(self, security_level: SecurityLevel = SecurityLevel.STANDARD) -> None:
        """Initialize validator with specified security level.

        Args:
            security_level: Level of security validation to apply.
        """
        self.security_level = security_level
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for performance."""
        self.injection_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.INJECTION_PATTERNS]
        self.prompt_injection_regex = [re.compile(pattern, re.IGNORECASE) for pattern in self.PROMPT_INJECTION_PATTERNS]

    def validate_prompt(self, prompt: str, max_length: int = 50000) -> ValidationResult:
        """Validate and sanitize prompt input.

        Args:
            prompt: Input prompt to validate.
            max_length: Maximum allowed prompt length.

        Returns:
            ValidationResult with validation status and sanitized input.
        """
        violations = []
        risk_level = "low"

        # Basic validation
        if not isinstance(prompt, str):
            return ValidationResult(is_valid=False, violations=["Input must be a string"], risk_level="high")

        if len(prompt) > max_length:
            violations.append(f"Prompt exceeds maximum length of {max_length} characters")
            risk_level = "medium"

        # Check for potential injection attempts
        injection_found = False
        for pattern in self.injection_regex:
            if pattern.search(prompt):
                violations.append(f"Potential code injection detected: {pattern.pattern}")
                injection_found = True
                risk_level = "high"

        # Check for prompt injection patterns
        prompt_injection_found = False
        if self.security_level in [SecurityLevel.STANDARD, SecurityLevel.STRICT]:
            for pattern in self.prompt_injection_regex:
                if pattern.search(prompt):
                    violations.append(f"Potential prompt injection detected: {pattern.pattern}")
                    prompt_injection_found = True
                    if risk_level != "high":
                        risk_level = "medium"

        # Sanitize input
        sanitized = self._sanitize_prompt(prompt) if not injection_found else None

        is_valid = len(violations) == 0 or (self.security_level == SecurityLevel.BASIC and not injection_found)

        return ValidationResult(
            is_valid=is_valid,
            sanitized_input=sanitized,
            violations=violations,
            risk_level=risk_level,
        )

    def _sanitize_prompt(self, prompt: str) -> str:
        """Sanitize prompt by removing potentially dangerous content.

        Args:
            prompt: Input prompt to sanitize.

        Returns:
            Sanitized prompt string.
        """
        sanitized = prompt

        # Remove script tags and JavaScript
        sanitized = re.sub(r"<script[^>]*>.*?</script>", "", sanitized, flags=re.IGNORECASE | re.DOTALL)
        sanitized = re.sub(r"javascript:", "", sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r"vbscript:", "", sanitized, flags=re.IGNORECASE)

        # Remove event handlers
        sanitized = re.sub(r'on\w+\s*=\s*["\'][^"\']*["\']', "", sanitized, flags=re.IGNORECASE)

        # Normalize whitespace
        sanitized = re.sub(r"\s+", " ", sanitized).strip()

        return sanitized

    def validate_metadata(self, metadata: dict[str, Any]) -> ValidationResult:
        """Validate metadata dictionary for safety.

        Args:
            metadata: Metadata dictionary to validate.

        Returns:
            ValidationResult with validation status.
        """
        violations = []
        risk_level = "low"

        if not isinstance(metadata, dict):
            return ValidationResult(
                is_valid=False,
                violations=["Metadata must be a dictionary"],
                risk_level="high",
            )

        # Check for dangerous keys
        dangerous_keys = {
            "__class__",
            "__module__",
            "__dict__",
            "__globals__",
            "exec",
            "eval",
        }
        found_dangerous = dangerous_keys.intersection(metadata.keys())
        if found_dangerous:
            violations.append(f"Dangerous metadata keys detected: {found_dangerous}")
            risk_level = "high"

        # Validate values
        for key, value in metadata.items():
            if isinstance(value, str):
                result = self.validate_prompt(value, max_length=10000)
                if not result.is_valid:
                    violations.extend([f"Metadata key '{key}': {v}" for v in result.violations])
                    if result.risk_level == "high":
                        risk_level = "high"
                    elif result.risk_level == "medium" and risk_level != "high":
                        risk_level = "medium"

        return ValidationResult(is_valid=len(violations) == 0, violations=violations, risk_level=risk_level)


class SecretManager:
    """Manages API keys and sensitive data securely."""

    def __init__(self) -> None:
        """Initialize secret manager."""
        self._masked_prefixes = {"sk-", "pk-", "api_", "key_", "secret_"}

    def mask_secret(self, secret: str, visible_chars: int = 4) -> str:
        """Mask a secret for logging/display purposes.

        Args:
            secret: Secret string to mask.
            visible_chars: Number of characters to show at the end.

        Returns:
            Masked secret string.
        """
        if not secret or len(secret) <= visible_chars:
            return "*" * 8

        if visible_chars <= 0:
            return "*" * 8

        return "*" * (len(secret) - visible_chars) + secret[-visible_chars:]

    def is_potential_secret(self, value: str) -> bool:
        """Check if a string looks like it might be a secret.

        Args:
            value: String to check.

        Returns:
            True if the string appears to be a secret.
        """
        if not isinstance(value, str) or len(value) < 8:
            return False

        # Check for common secret prefixes
        value_lower = value.lower()
        if any(value_lower.startswith(prefix) for prefix in self._masked_prefixes):
            return True

        # Check for high entropy (random-looking strings)
        if len(value) > 20 and self._calculate_entropy(value) > 3.5:
            return True

        return False

    def _calculate_entropy(self, text: str) -> float:
        """Calculate Shannon entropy of a string.

        Args:
            text: String to calculate entropy for.

        Returns:
            Entropy value.
        """
        if not text:
            return 0.0

        # Count character frequencies
        char_counts = {}
        for char in text:
            char_counts[char] = char_counts.get(char, 0) + 1

        # Calculate entropy
        entropy = 0.0
        text_len = len(text)
        for count in char_counts.values():
            probability = count / text_len
            if probability > 0:
                entropy -= probability * (probability.bit_length() - 1)

        return entropy

    def sanitize_for_logging(self, data: Any) -> Any:
        """Sanitize data structure for safe logging.

        Args:
            data: Data structure to sanitize.

        Returns:
            Sanitized copy of the data.
        """
        if isinstance(data, dict):
            return {key: self.sanitize_for_logging(value) for key, value in data.items()}
        elif isinstance(data, (list, tuple)):
            return type(data)(self.sanitize_for_logging(item) for item in data)
        elif isinstance(data, str):
            if self.is_potential_secret(data):
                return self.mask_secret(data)
            return data
        else:
            return data


class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, max_requests: int = 60, window_seconds: int = 60) -> None:
        """Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed in the window.
            window_seconds: Time window in seconds.
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, List[float]] = {}

    def is_allowed(self, identifier: str) -> bool:
        """Check if a request is allowed.

        Args:
            identifier: Unique identifier for the requester.

        Returns:
            True if request is allowed, False if rate limited.
        """
        import time

        current_time = time.time()

        if identifier not in self._requests:
            self._requests[identifier] = []

        # Remove old requests outside the window
        self._requests[identifier] = [
            req_time for req_time in self._requests[identifier] if current_time - req_time < self.window_seconds
        ]

        # Check if we're under the limit
        if len(self._requests[identifier]) < self.max_requests:
            self._requests[identifier].append(current_time)
            return True

        return False

    def get_reset_time(self, identifier: str) -> float | None:
        """Get the time when rate limit resets for identifier.

        Args:
            identifier: Unique identifier for the requester.

        Returns:
            Unix timestamp when rate limit resets, or None if not limited.
        """
        if identifier not in self._requests or not self._requests[identifier]:
            return None

        oldest_request = min(self._requests[identifier])
        return oldest_request + self.window_seconds


def generate_request_id() -> str:
    """Generate a secure random request ID.

    Returns:
        Random request ID string.
    """
    return secrets.token_urlsafe(16)


def hash_content(content: str) -> str:
    """Generate a hash of content for caching/deduplication.

    Args:
        content: Content to hash.

    Returns:
        SHA-256 hash of the content.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# Global instances for convenience
default_validator = InputValidator()
secret_manager = SecretManager()
