# Hive Errors

Standardized error handling and reporting infrastructure.

## Features

- Base error classes with structured context
- Async error handling utilities
- Error monitoring and reporting
- Recovery strategy patterns

## Usage

```python
from hive_errors import BaseError, ErrorReporter

class MyError(BaseError):
    pass

reporter = ErrorReporter()
await reporter.report(error, context)
```
