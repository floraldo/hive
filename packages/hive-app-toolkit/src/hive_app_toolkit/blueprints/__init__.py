"""Service blueprints for Hive Application Toolkit."""

from __future__ import annotations

from typing import Any

from ..cli.generator import ServiceType
from .api_service import API_SERVICE_BLUEPRINT
from .batch_processor import BATCH_PROCESSOR_BLUEPRINT
from .event_worker import EVENT_WORKER_BLUEPRINT

__all__ = [
    "API_SERVICE_BLUEPRINT",
    "BATCH_PROCESSOR_BLUEPRINT",
    "EVENT_WORKER_BLUEPRINT",
    "get_blueprint",
]


def get_blueprint(service_type: ServiceType) -> dict[str, Any]:
    """Get blueprint configuration for service type.

    Args:
        service_type: Type of service

    Returns:
        Blueprint configuration dictionary

    Raises:
        ValueError: If service type is not supported

    """
    blueprints = {
        ServiceType.API: API_SERVICE_BLUEPRINT,
        ServiceType.WORKER: EVENT_WORKER_BLUEPRINT,
        ServiceType.BATCH: BATCH_PROCESSOR_BLUEPRINT,
        ServiceType.WEBHOOK: API_SERVICE_BLUEPRINT,  # Webhook uses API blueprint
    }

    if service_type not in blueprints:
        raise ValueError(f"Unsupported service type: {service_type}")

    return blueprints[service_type]
