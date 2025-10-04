"""Batch processor blueprint configuration."""

from __future__ import annotations

from typing import Any

BATCH_PROCESSOR_BLUEPRINT: dict[str, Any] = {
    "service_type": "batch",
    "description": "Scheduled batch processing service with job management and monitoring",
    "hive_packages": [
        "hive-logging",
        "hive-config",
        "hive-db",
        "hive-errors",
    ],
    "optional_packages": {
        "cache": ["hive-cache"],
        "performance": ["hive-performance"],
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
        "src/{app_module}/jobs": ["__init__.py"],
        "src/{app_module}/processors": ["__init__.py"],
        "tests": ["__init__.py", "conftest.py", "test_golden_rules.py"],
        "tests/integration": ["__init__.py"],
        "tests/unit": ["__init__.py"],
        "config": [".env.example", "settings.yaml"],
        "data": [],
        "data/input": [],
        "data/output": [],
        "logs": [],
        "k8s": ["deployment.yaml"],
    },
    "context_variables": {
        "needs_database": True,
        "needs_cache": False,
        "needs_event_bus": False,
        "needs_performance_monitoring": True,
        "port": 8000,
        "workers": 1,
        "replicas": 1,
        "schedule_cron": "0 0 * * *",  # Daily at midnight
        "batch_size": 1000,
        "max_retries": 3,
    },
    "post_generation_steps": [
        "Install dependencies: poetry install",
        "Run tests: pytest",
        "Start batch processor: poetry run python -m {app_module}.main",
        "Build Docker image: docker build -t {app_name}:latest .",
        "Deploy to Kubernetes: kubectl apply -f k8s/deployment.yaml",
    ],
}
