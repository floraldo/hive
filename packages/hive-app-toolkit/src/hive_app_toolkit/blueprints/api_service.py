"""API service blueprint configuration."""

from __future__ import annotations

from typing import Any

API_SERVICE_BLUEPRINT: dict[str, Any] = {
    "service_type": "api",
    "description": "Production-ready FastAPI service with health endpoints, metrics, and Kubernetes deployment",
    "hive_packages": [
        "hive-logging",
        "hive-config",
        "hive-errors",
        "hive-app-toolkit",
    ],
    "optional_packages": {
        "database": ["hive-db"],
        "cache": ["hive-cache"],
        "performance": ["hive-performance"],
    },
    "templates": [
        "python/pyproject.toml.j2",
        "python/main.py.j2",
        "python/__init__.py.j2",
        "python/config.py.j2",
        "python/api/__init__.py.j2",
        "python/api/main.py.j2",
        "python/api/health.py.j2",
        "tests/conftest.py.j2",
        "tests/test_health.py.j2",
        "tests/test_golden_rules.py.j2",
        "docs/README.md.j2",
        "docs/API.md.j2",
        "config/.gitignore.j2",
        "config/.env.example.j2",
        "config/settings.yaml.j2",
        "docker/Dockerfile.j2",
        "k8s/deployment.yaml.j2",
    ],
    "directory_structure": {
        "src/{app_module}": ["__init__.py", "main.py", "config.py"],
        "src/{app_module}/api": ["__init__.py", "main.py", "health.py"],
        "tests": ["__init__.py", "conftest.py", "test_health.py", "test_golden_rules.py"],
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
        "needs_event_bus": False,
        "needs_performance_monitoring": True,
        "port": 8000,
        "workers": 4,
        "replicas": 2,
        "health_check_path": "/health/live",
        "readiness_check_path": "/health/ready",
    },
    "post_generation_steps": [
        "Install dependencies: poetry install",
        "Run tests: pytest",
        "Start development server: poetry run python -m {app_module}.main",
        "Build Docker image: docker build -t {app_name}:latest .",
        "Deploy to Kubernetes: kubectl apply -f k8s/deployment.yaml",
    ],
}
