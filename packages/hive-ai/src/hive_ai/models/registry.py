"""
Model registry for managing AI model configurations and providers.

Provides centralized management of available models with
dynamic registration and health monitoring.
"""

from typing import Dict, List, Optional, Type

from hive_cache import CacheManager
from hive_logging import get_logger

from ..core.config import AIConfig, ModelConfig
from ..core.exceptions import ModelUnavailableError
from ..core.interfaces import ModelProviderInterface

logger = get_logger(__name__)


class ModelRegistry:
    """
    Central registry for AI models and providers.

    Manages model configurations, provider instances, and
    health status with caching for performance.
    """

    def __init__(self, config: AIConfig) -> None:
        self.config = config
        self._providers: Dict[str, ModelProviderInterface] = {}
        self._provider_classes: Dict[str, Type[ModelProviderInterface]] = {}
        self._health_status: Dict[str, bool] = {}
        self._cache = CacheManager("model_registry")

    def register_provider(self, provider_name: str, provider_class: Type[ModelProviderInterface]) -> None:
        """Register a model provider class."""
        logger.info(f"Registering provider: {provider_name}")
        self._provider_classes[provider_name] = provider_class

    def get_provider(self, provider_name: str) -> ModelProviderInterface:
        """Get or create provider instance."""
        if provider_name not in self._providers:
            if provider_name not in self._provider_classes:
                raise ModelUnavailableError(
                    f"Provider '{provider_name}' not registered",
                    model="",
                    provider=provider_name,
                    available_models=self.list_available_models(),
                )

            # Create provider instance
            provider_class = self._provider_classes[provider_name]
            self._providers[provider_name] = provider_class(self.config)

        return self._providers[provider_name]

    def get_model_config(self, model_name: str) -> ModelConfig:
        """Get configuration for specific model."""
        try:
            return self.config.get_model_config(model_name)
        except ValueError as e:
            raise ModelUnavailableError(
                str(e), model=model_name, provider="", available_models=self.list_available_models()
            )

    def list_available_models(self) -> List[str]:
        """Get list of all configured models."""
        return list(self.config.models.keys())

    def list_healthy_models(self) -> List[str]:
        """Get list of models with healthy providers."""
        healthy = []
        for model_name in self.list_available_models():
            model_config = self.config.models[model_name]
            if self.is_provider_healthy(model_config.provider):
                healthy.append(model_name)
        return healthy

    def is_provider_healthy(self, provider_name: str) -> bool:
        """Check if provider is healthy (cached result)."""
        cache_key = f"health_{provider_name}"
        cached_health = self._cache.get(cache_key)

        if cached_health is not None:
            return cached_health

        try:
            provider = self.get_provider(provider_name)
            health = provider.validate_connection()
            # Cache health status for 5 minutes
            self._cache.set(cache_key, health, ttl=300)
            return health
        except Exception as e:
            logger.warning(f"Health check failed for {provider_name}: {e}")
            self._cache.set(cache_key, False, ttl=60)  # Cache failure for 1 minute
            return False

    def refresh_health_status(self) -> Dict[str, bool]:
        """Force refresh of all provider health status."""
        self._cache.clear()  # Clear cached health status

        status = {}
        for provider_name in self._provider_classes:
            status[provider_name] = self.is_provider_healthy(provider_name)

        logger.info(f"Health status refreshed: {status}")
        return status

    def get_provider_for_model(self, model_name: str) -> ModelProviderInterface:
        """Get provider instance for specific model."""
        model_config = self.get_model_config(model_name)
        return self.get_provider(model_config.provider)

    def validate_model_available(self, model_name: str) -> bool:
        """Validate that model is configured and provider is healthy."""
        if model_name not in self.config.models:
            return False

        model_config = self.config.models[model_name]
        return self.is_provider_healthy(model_config.provider)

    def get_models_by_type(self, model_type: str) -> List[str]:
        """Get models filtered by type (chat, completion, embedding)."""
        models = []
        for name, config in self.config.models.items():
            if config.model_type == model_type:
                models.append(name)
        return models

    def get_cheapest_model(self, model_type: str) -> Optional[str]:
        """Get the cheapest available model of specified type."""
        models = self.get_models_by_type(model_type)
        if not models:
            return None

        cheapest = None
        lowest_cost = float("inf")

        for model_name in models:
            if not self.validate_model_available(model_name):
                continue

            config = self.config.models[model_name]
            if config.cost_per_token < lowest_cost:
                lowest_cost = config.cost_per_token
                cheapest = model_name

        return cheapest

    def get_registry_stats(self) -> Dict[str, int]:
        """Get registry statistics."""
        total_models = len(self.config.models)
        healthy_models = len(self.list_healthy_models())
        providers = len(self._provider_classes)

        return {
            "total_models": total_models,
            "healthy_models": healthy_models,
            "total_providers": providers,
            "health_percentage": int((healthy_models / total_models * 100) if total_models > 0 else 0),
        }
