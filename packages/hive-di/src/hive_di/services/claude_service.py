"""
Claude Service Implementation

Injectable Claude service that replaces the global Claude service singleton.
Provides Claude AI integration with proper dependency injection and configuration.
"""

import time
import json
from typing import Any, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timezone

from ..interfaces import IClaudeService, IConfigurationService, IErrorReportingService, IDisposable


@dataclass
class RateLimitState:
    """Rate limiting state tracking"""
    requests_made: int = 0
    window_start: float = 0.0
    requests_limit: int = 100
    window_duration: int = 60  # seconds


class ClaudeService(IClaudeService, IDisposable):
    """
    Injectable Claude service

    Replaces the global Claude service singleton with a proper service that can be
    configured and injected independently.
    """

    def __init__(self,
                 configuration_service: IConfigurationService,
                 error_reporting_service: IErrorReportingService,
                 config: Optional[Dict[str, Any]] = None):
        """
        Initialize Claude service

        Args:
            configuration_service: Configuration service for getting Claude settings
            error_reporting_service: Error reporting service for error handling
            config: Optional override configuration
        """
        self._config_service = configuration_service
        self._error_service = error_reporting_service
        self._override_config = config or {}

        # Get Claude configuration
        claude_config = self._config_service.get_claude_config()
        self._config = {**claude_config, **self._override_config}

        # Claude service settings
        self.mock_mode = self._config.get('mock_mode', False)
        self.timeout = self._config.get('timeout', 30.0)
        self.api_key = self._config.get('api_key')

        # Rate limiting
        self._rate_limit = RateLimitState(
            requests_limit=self._config.get('rate_limit_requests', 100),
            window_duration=self._config.get('rate_limit_window', 60)
        )

        # Service state
        self._service_status = "initialized"
        self._total_requests = 0
        self._successful_requests = 0
        self._failed_requests = 0

    def _check_rate_limit(self) -> bool:
        """Check if request is within rate limits"""
        current_time = time.time()

        # Reset window if needed
        if current_time - self._rate_limit.window_start >= self._rate_limit.window_duration:
            self._rate_limit.window_start = current_time
            self._rate_limit.requests_made = 0

        # Check if under limit
        if self._rate_limit.requests_made >= self._rate_limit.requests_limit:
            return False

        # Increment counter
        self._rate_limit.requests_made += 1
        return True

    def _create_mock_response(self, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Create a mock response for testing"""
        return {
            "response": f"Mock response to: {message[:50]}...",
            "status": "success",
            "mock": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "context": context or {}
        }

    def _send_real_message(self, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send actual message to Claude service (placeholder implementation)"""
        # This would be the actual Claude API integration
        # For now, return a placeholder response

        if not self.api_key:
            raise ValueError("Claude API key not configured")

        # Placeholder for actual Claude API call
        # In real implementation, this would use the Claude SDK
        return {
            "response": f"Processed message: {message[:50]}...",
            "status": "success",
            "mock": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "context": context or {},
            "usage": {
                "input_tokens": len(message.split()),
                "output_tokens": 50,  # Placeholder
                "total_tokens": len(message.split()) + 50
            }
        }

    # IClaudeService interface implementation

    def send_message(self, message: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a message to Claude service"""
        try:
            self._total_requests += 1

            # Check rate limits
            if not self._check_rate_limit():
                error = RuntimeError("Rate limit exceeded")
                self._error_service.report_error(
                    error,
                    context={
                        'component': 'claude_service',
                        'operation': 'send_message',
                        'additional_data': {'message_length': len(message)}
                    },
                    severity='warning'
                )
                raise error

            # Send message (mock or real)
            if self.mock_mode:
                response = self._create_mock_response(message, context)
            else:
                response = self._send_real_message(message, context)

            self._successful_requests += 1
            self._service_status = "operational"
            return response

        except Exception as e:
            self._failed_requests += 1
            self._service_status = "error"

            # Report error
            error_id = self._error_service.report_error(
                e,
                context={
                    'component': 'claude_service',
                    'operation': 'send_message',
                    'additional_data': {
                        'message_length': len(message),
                        'context': context
                    }
                },
                severity='error'
            )

            # Re-raise with error ID
            raise RuntimeError(f"Claude service error (ID: {error_id}): {str(e)}")

    async def send_message_async(self, message: str,
                                context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a message to Claude service asynchronously"""
        # For now, just call the sync version
        # In a real implementation, this would use async HTTP client
        return self.send_message(message, context)

    def get_service_status(self) -> Dict[str, Any]:
        """Get Claude service status"""
        return {
            "status": self._service_status,
            "mock_mode": self.mock_mode,
            "total_requests": self._total_requests,
            "successful_requests": self._successful_requests,
            "failed_requests": self._failed_requests,
            "success_rate": (
                self._successful_requests / self._total_requests
                if self._total_requests > 0 else 0.0
            ),
            "configuration": {
                "timeout": self.timeout,
                "api_key_configured": bool(self.api_key),
                "rate_limit": self._rate_limit.requests_limit,
                "rate_window": self._rate_limit.window_duration
            }
        }

    def get_rate_limit_status(self) -> Dict[str, Any]:
        """Get rate limiting status"""
        current_time = time.time()
        time_until_reset = max(0,
            self._rate_limit.window_duration -
            (current_time - self._rate_limit.window_start)
        )

        return {
            "requests_made": self._rate_limit.requests_made,
            "requests_limit": self._rate_limit.requests_limit,
            "window_duration": self._rate_limit.window_duration,
            "time_until_reset": time_until_reset,
            "requests_remaining": max(0,
                self._rate_limit.requests_limit - self._rate_limit.requests_made
            ),
            "rate_limited": self._rate_limit.requests_made >= self._rate_limit.requests_limit
        }

    def reset_rate_limits(self) -> None:
        """Reset rate limiting counters"""
        self._rate_limit.requests_made = 0
        self._rate_limit.window_start = time.time()

    # IDisposable interface implementation

    def dispose(self) -> None:
        """Clean up Claude service resources"""
        self._service_status = "disposed"

    # Additional utility methods

    def test_connection(self) -> bool:
        """Test Claude service connection"""
        try:
            response = self.send_message("Test connection", {"test": True})
            return response.get("status") == "success"
        except Exception:
            return False

    def get_configuration(self) -> Dict[str, Any]:
        """Get current Claude service configuration"""
        return {
            "mock_mode": self.mock_mode,
            "timeout": self.timeout,
            "api_key_configured": bool(self.api_key),
            "rate_limit_requests": self._rate_limit.requests_limit,
            "rate_limit_window": self._rate_limit.window_duration
        }

    def update_configuration(self, updates: Dict[str, Any]) -> None:
        """Update Claude service configuration"""
        if 'mock_mode' in updates:
            self.mock_mode = updates['mock_mode']
        if 'timeout' in updates:
            self.timeout = updates['timeout']
        if 'api_key' in updates:
            self.api_key = updates['api_key']
        if 'rate_limit_requests' in updates:
            self._rate_limit.requests_limit = updates['rate_limit_requests']
        if 'rate_limit_window' in updates:
            self._rate_limit.window_duration = updates['rate_limit_window']