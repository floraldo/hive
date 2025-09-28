# Hive Logging

Centralized logging infrastructure with structured logging support.

## Features

- Standardized logger configuration
- Structured logging with context
- Performance logging utilities
- Integration with monitoring systems

## Usage

```python
from hive_logging import get_logger

logger = get_logger(__name__)
logger.info("Operation completed", extra={"duration": 1.23})
```
