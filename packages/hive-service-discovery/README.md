# Hive Service Discovery

Service discovery and load balancing infrastructure.

## Features

- Service registration and discovery
- Health check integration
- Load balancing algorithms
- Circuit breaker integration

## Usage

```python
from hive_service_discovery import ServiceRegistry, LoadBalancer

registry = ServiceRegistry()
balancer = LoadBalancer()
```

## Components

- `discovery_client.py`: Service discovery client
- `load_balancer.py`: Load balancing algorithms
- `service_registry.py`: Service registration management
