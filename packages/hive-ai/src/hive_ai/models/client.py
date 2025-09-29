"""
Unified client for AI model interactions across providers.

Provides consistent interface for all AI operations with
built-in resilience, cost tracking, and observability.
"""
from __future__ import annotations


import time
from typing import Any, AsyncIterable, Dict

from hive_async import AsyncCircuitBreaker, async_retry
from hive_logging import get_logger

from ..core.config import AIConfig
from ..core.exceptions import CostLimitError, ModelError, ModelUnavailableError
from ..core.interfaces import ModelResponse, TokenUsage
from ..core.security import default_validator, generate_request_id, secret_manager
from .metrics import ModelMetrics
from .registry import ModelRegistry

logger = get_logger(__name__)


class ModelClient:
    """
    Unified client for AI model operations.

    Provides consistent interface across all providers with
    resilience patterns, cost management, and metrics collection.
    """

    def __init__(self, config: AIConfig) -> None:
        self.config = config
        self.registry = ModelRegistry(config)
        self.metrics = ModelMetrics()
        self._circuit_breakers: Dict[str, AsyncCircuitBreaker] = {}

    def _get_circuit_breaker(self, provider: str) -> AsyncCircuitBreaker:
        """Get or create circuit breaker for provider."""
        if provider not in self._circuit_breakers:
            self._circuit_breakers[provider] = AsyncCircuitBreaker(
                failure_threshold=self.config.failure_threshold, recovery_timeout=self.config.recovery_timeout
            )
        return self._circuit_breakers[provider]

    async def _check_cost_limits_async(self, estimated_cost: float) -> None:
        """Check if operation would exceed cost limits."""
        daily_cost = await self.metrics.get_daily_cost_async()
        monthly_cost = await self.metrics.get_monthly_cost_async()

        if daily_cost + estimated_cost > self.config.daily_cost_limit:
            raise CostLimitError(
                f"Operation would exceed daily cost limit",
                current_cost=daily_cost,
                limit=self.config.daily_cost_limit,
                period="daily"
            )

        if monthly_cost + estimated_cost > self.config.monthly_cost_limit:
            raise CostLimitError(
                f"Operation would exceed monthly cost limit",
                current_cost=monthly_cost,
                limit=self.config.monthly_cost_limit,
                period="monthly"
            )

    def _estimate_cost(self, model_name: str, prompt: str) -> float:
        """Estimate cost for operation based on prompt length."""
        model_config = self.registry.get_model_config(model_name)

        # Rough token estimation (4 chars = 1 token)
        estimated_tokens = len(prompt) / 4
        return estimated_tokens * model_config.cost_per_token

    async def generate_async(
        self,
        prompt: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs
    ) -> ModelResponse:
        """
        Generate completion from AI model.

        Args:
            prompt: Input prompt for generation,
            model: Model name (uses default if not specified),
            temperature: Sampling temperature override,
            max_tokens: Maximum tokens override,
            **kwargs: Additional provider-specific parameters

        Returns:
            ModelResponse with content and metadata

        Raises:
            ModelError: Model or provider errors,
            CostLimitError: Cost limit exceeded,
            ModelUnavailableError: Model not available,
        """
        model_name = model or self.config.default_model
        model_config = self.registry.get_model_config(model_name)

        # Validate model availability
        if not self.registry.validate_model_available(model_name):
            raise ModelUnavailableError(
                f"Model '{model_name}' is not available",
                model=model_name,
                provider=model_config.provider,
                available_models=self.registry.list_healthy_models()
            )

        # Check cost limits
        estimated_cost = self._estimate_cost(model_name, prompt)
        await self._check_cost_limits_async(estimated_cost)

        # Get provider and circuit breaker
        provider = self.registry.get_provider_for_model(model_name)
        circuit_breaker = self._get_circuit_breaker(model_config.provider)

        # Prepare parameters
        generation_params = {
            "temperature": temperature or model_config.temperature,
            "max_tokens": max_tokens or model_config.max_tokens,
            **kwargs
        }

        start_time = time.time()

        try:
            # Execute with circuit breaker and retry
            @async_retry(max_attempts=3, delay=1.0)
            async def _generate_async():
                return await circuit_breaker.call_async(
                    provider.generate_async, prompt, model_config.name, **generation_params
                )

            response = await _generate_async()
            latency_ms = int((time.time() - start_time) * 1000)

            # Record successful metrics
            token_usage = TokenUsage(
                prompt_tokens=response.tokens_used // 2,  # Rough split,
                completion_tokens=response.tokens_used // 2,
                total_tokens=response.tokens_used,
                estimated_cost=response.cost
            )

            await self.metrics.record_model_usage_async(
                model=model_name,
                provider=model_config.provider,
                tokens=token_usage,
                latency_ms=latency_ms,
                success=True
            )

            logger.info(
                f"Model generation successful: {model_name} "
                f"({response.tokens_used} tokens, {latency_ms}ms, ${response.cost:.4f})"
            )

            return response

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)

            # Record failed metrics
            await self.metrics.record_model_usage_async(
                model=model_name,
                provider=model_config.provider,
                tokens=TokenUsage(0, 0, 0, 0.0),
                latency_ms=latency_ms,
                success=False
            )

            logger.error(f"Model generation failed: {model_name} " f"({latency_ms}ms) - {str(e)}")

            raise ModelError(
                f"Generation failed for model '{model_name}': {str(e)}"
                model=model_name,
                provider=model_config.provider
            ) from e

    async def generate_stream_async(
        self
        prompt: str,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs
    ) -> AsyncIterable[str]:
        """
        Generate streaming completion from AI model.

        Args:
            prompt: Input prompt for generation,
            model: Model name (uses default if not specified),
            temperature: Sampling temperature override,
            max_tokens: Maximum tokens override,
            **kwargs: Additional provider-specific parameters

        Yields:
            String chunks from streaming response

        Raises:
            ModelError: Model or provider errors,
            CostLimitError: Cost limit exceeded,
            ModelUnavailableError: Model not available,
        """
        model_name = model or self.config.default_model
        model_config = self.registry.get_model_config(model_name)

        # Validate model availability
        if not self.registry.validate_model_available(model_name):
            raise ModelUnavailableError(
                f"Model '{model_name}' is not available",
                model=model_name,
                provider=model_config.provider,
                available_models=self.registry.list_healthy_models()
            )

        # Check cost limits
        estimated_cost = self._estimate_cost(model_name, prompt)
        await self._check_cost_limits_async(estimated_cost)

        # Get provider and circuit breaker
        provider = self.registry.get_provider_for_model(model_name)
        circuit_breaker = self._get_circuit_breaker(model_config.provider)

        # Prepare parameters
        generation_params = {
            "temperature": temperature or model_config.temperature,
            "max_tokens": max_tokens or model_config.max_tokens,
            **kwargs
        }

        start_time = time.time()

        try:

            async def _stream_async() -> None:
                async for chunk in circuit_breaker.call_async(
                    provider.generate_stream_async, prompt, model_config.name, **generation_params
                ):
                    yield chunk

            async for chunk in _stream_async():
                yield chunk

            latency_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Streaming generation completed: {model_name} ({latency_ms}ms)")

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)

            await self.metrics.record_model_usage_async(
                model=model_name,
                provider=model_config.provider,
                tokens=TokenUsage(0, 0, 0, 0.0),
                latency_ms=latency_ms,
                success=False
            )

            logger.error(f"Streaming generation failed: {model_name} - {str(e)}")

            raise ModelError(
                f"Streaming generation failed for model '{model_name}': {str(e)}"
                model=model_name,
                provider=model_config.provider
            ) from e

    async def list_models_async(self) -> Dict[str, Any]:
        """Get detailed information about available models."""
        models_info = {}

        for model_name in self.registry.list_available_models():
            config = self.registry.get_model_config(model_name)
            is_healthy = self.registry.validate_model_available(model_name)

            models_info[model_name] = {
                "provider": config.provider,
                "type": config.model_type,
                "max_tokens": config.max_tokens,
                "cost_per_token": config.cost_per_token,
                "healthy": is_healthy,
                "temperature": config.temperature
            }

        return models_info

    async def get_usage_stats_async(self) -> Dict[str, Any]:
        """Get comprehensive usage statistics."""
        return await self.metrics.get_usage_summary_async()

    async def health_check_async(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        health_status = self.registry.refresh_health_status()
        registry_stats = self.registry.get_registry_stats()

        return {
            "healthy": registry_stats["health_percentage"] > 50,
            "provider_health": health_status,
            "registry_stats": registry_stats,
            "circuit_breakers": {provider: cb.get_stats() for provider, cb in self._circuit_breakers.items()}
        }
