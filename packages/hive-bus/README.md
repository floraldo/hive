# Hive Bus

Event bus and messaging infrastructure for inter-service communication.

## Features

- Async event publishing and subscription
- Message routing and filtering
- Dead letter queue handling
- Circuit breaker integration

## Usage

```python
from hive_bus import EventBus

bus = EventBus()
await bus.publish("event.type", payload)
```
