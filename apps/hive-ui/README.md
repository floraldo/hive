# hive-ui

hive-ui - Hive platform service

## Overview

**Service Type**: api
**Version**: 0.1.0
**Environment**: development

## Features

- FastAPI-based REST API
- Health check endpoints (liveness/readiness probes)
- OpenAPI documentation
- CORS middleware
- Caching layer
- Performance monitoring
- Structured logging (hive_logging)
- Configuration management (DI pattern)
- Golden Rules compliance
- Production-ready Docker container
- Kubernetes deployment manifests

## Quick Start

### Prerequisites

- Python 3.11+
- Poetry
- Docker (optional)
- Kubernetes (optional)

### Installation

```bash
# Install dependencies
poetry install

# Activate virtual environment
poetry shell
```

### Configuration

Create a `.env` file from the example:

```bash
cp config/.env.example .env
```

Edit `.env` with your configuration:

```bash
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
ENVIRONMENT=development
```

### Running

```bash
# Development server
poetry run python -m hive_ui.main

# Production server with uvicorn
poetry run uvicorn hive_ui.api.main:create_app --host 0.0.0.0 --port 8000
```

The API will be available at:
- API: http://localhost:8000
- Docs: http://localhost:8000/api/docs
- Health: http://localhost:8000/health/live

### Testing

```bash
# Run all tests
poetry run pytest

# Run with coverage
poetry run pytest --cov=hive_ui --cov-report=html

# Run Golden Rules compliance tests
poetry run pytest tests/test_golden_rules.py -v
```

## Development

### Project Structure

```
hive-ui/
├── src/
│   └── hive_ui/
│       ├── __init__.py
│       ├── main.py           # Entry point
│       ├── config.py          # Configuration (DI pattern)
│       └── api/
│           ├── __init__.py
│           ├── main.py        # FastAPI app
│           └── health.py      # Health endpoints
├── tests/
│   ├── conftest.py           # Pytest fixtures
│   ├── test_health.py        # Health tests
│   └── test_golden_rules.py  # Compliance tests
├── config/
│   ├── .env.example          # Environment template
│   └── settings.yaml         # Configuration file
├── k8s/
│   └── deployment.yaml       # Kubernetes manifests
├── Dockerfile                # Docker build
├── pyproject.toml            # Dependencies
└── README.md                 # This file
```

### Code Quality

```bash
# Format code
poetry run black src/ tests/

# Lint code
poetry run ruff check src/ tests/

# Type check
poetry run mypy src/
```

## Deployment

### Docker

```bash
# Build image
docker build -t hive-ui:0.1.0 .

# Run container
docker run -p 8000:8000 hive-ui:0.1.0
```

### Kubernetes

```bash
# Apply manifests
kubectl apply -f k8s/deployment.yaml

# Check status
kubectl get pods -l app=hive-ui

# View logs
kubectl logs -l app=hive-ui -f
```

## API Documentation

See [API.md](API.md) for detailed API documentation.

### Health Endpoints

- `GET /health/live` - Liveness probe
- `GET /health/ready` - Readiness probe

### API Endpoints

*Add your API endpoints here*

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `HOST` | API host | `0.0.0.0` |
| `PORT` | API port | `8000` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `ENVIRONMENT` | Environment | `development` |
| `CACHE_ENABLED` | Enable caching | `true` |
| `CACHE_TTL` | Cache TTL (seconds) | `3600` |
## Monitoring

### Metrics

Prometheus metrics are exposed at `/metrics`

### Logging

Structured JSON logging with hive_logging

## Contributing

This service follows Hive platform standards:

- **Architecture**: Modular monolith with inherit→extend pattern
- **Configuration**: Dependency Injection (no global state)
- **Logging**: hive_logging (no print statements)
- **Quality**: Golden Rules compliance
- **Testing**: Comprehensive test coverage

## License

Hive Platform - Internal Use Only
