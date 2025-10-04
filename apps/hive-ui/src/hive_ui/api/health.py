"""Health check endpoints for hive-ui."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter

router = APIRouter()


@router.get("/live")
async def liveness() -> dict[str, str]:
    """Liveness probe - is the service running?

    Kubernetes uses this endpoint to determine if the pod is alive.
    If this fails, Kubernetes will restart the pod.

    Returns:
        Status dictionary with "alive" status

    """
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "hive-ui",
    }


@router.get("/ready")
async def readiness() -> dict[str, str]:
    """Readiness probe - is the service ready to accept traffic?

    Kubernetes uses this endpoint to determine if the pod is ready.
    If this fails, Kubernetes will not route traffic to this pod.

    Returns:
        Status dictionary with "ready" status

    """
    # TODO: Add checks for database, cache, etc.
    # Check cache connectivity
    # cache_healthy = await check_cache()

    return {
        "status": "ready",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "hive-ui",
    }
