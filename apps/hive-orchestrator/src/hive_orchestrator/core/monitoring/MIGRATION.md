# Service Layer Migration Guide

## File: apps/hive-orchestrator/src/hive_orchestrator/core/monitoring/pipeline_monitor.py

### Steps to complete migration:

1. Move all business logic methods from service to implementation.py
2. Update service methods to delegate to self.impl
3. Ensure all tests still pass
4. Remove old business logic from service file

### Example:

**Before (in service):**
```python
def process_data(self, data):
    # Complex business logic here
    result = complex_calculation(data)
    return result
```

**After (in service):**
```python
def process_data(self, data):
    return self.impl.process_data(data)
```

**After (in implementation):**
```python
def process_data(self, data):
    # Complex business logic here
    result = complex_calculation(data)
    return result
```
