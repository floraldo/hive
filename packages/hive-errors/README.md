# Hive Errors

Base error handling package for the Hive ecosystem.

Provides standardized error types and handling patterns that can be inherited and extended by Hive applications.

## Features

- Base `HiveError` class with structured error information
- Common error types: `HiveValidationError`, `HiveAPIError`, `HiveTimeoutError`
- Recovery suggestions and error context management
- JSON serialization support

## Usage

```python
from hive_errors import HiveError, HiveValidationError

# Basic usage
raise HiveError(
    message="Something went wrong",
    component="my-app",
    operation="data_processing"
)

# With recovery suggestions
raise HiveValidationError(
    message="Invalid input data",
    component="my-app",
    operation="validation",
    recovery_suggestions=["Check input format", "Verify data types"]
)
```

## Installation

```bash
pip install -e .
```