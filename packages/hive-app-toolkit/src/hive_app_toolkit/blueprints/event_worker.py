"""Event worker blueprint configuration."""

from __future__ import annotations

from typing import Any

EVENT_WORKER_BLUEPRINT: dict[str, Any] = {
    "service_type": "worker",
    "description": "Async event worker for processing queue messages and webhooks",
    "hive_packages": [
        "hive-logging",
        "hive-config",
        "hive-bus",
        "hive-errors",
        "hive-async",
    ],
    "optional_packages": {
        "database": ["hive-db"],
        "cache": ["hive-cache"],
    },
    "templates": [
        "python/pyproject.toml.j2",
        "python/main.py.j2",
        "python/__init__.py.j2",
        "python/config.py.j2",
        "tests/conftest.py.j2",
        "tests/test_golden_rules.py.j2",
        "docs/README.md.j2",
        "config/.gitignore.j2",
        "config/.env.example.j2",
        "config/settings.yaml.j2",
        "docker/Dockerfile.j2",
        "k8s/deployment.yaml.j2",
    ],
    "directory_structure": {
        "src/{app_module}": ["__init__.py", "main.py", "config.py"],
        "src/{app_module}/workers": ["__init__.py"],
        "src/{app_module}/handlers": ["__init__.py"],
        "tests": ["__init__.py", "conftest.py", "test_golden_rules.py"],
        "tests/integration": ["__init__.py"],
        "tests/unit": ["__init__.py"],
        "config": [".env.example", "settings.yaml"],
        "data": [],
        "logs": [],
        "k8s": ["deployment.yaml"],
    },
    "context_variables": {
        "needs_database": False,
        "needs_cache": True,
        "needs_event_bus": True,
        "needs_performance_monitoring": False,
        "port": 8000,
        "workers": 4,
        "replicas": 2,
        "queue_name": "{app_name}-queue",
        "max_concurrent_tasks": 10,
    },
    "post_generation_steps": [
        "Install dependencies: poetry install",
        "Run tests: pytest",
        "Start worker: poetry run python -m {app_module}.main",
        "Build Docker image: docker build -t {app_name}:latest .",
        "Deploy to Kubernetes: kubectl apply -f k8s/deployment.yaml",
    ],
}
