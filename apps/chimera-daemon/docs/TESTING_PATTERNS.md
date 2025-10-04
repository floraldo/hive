# Testing Patterns for Chimera Daemon

## FastAPI Testing Pattern

### Problem: TestClient + Async Fixtures
**Issue**: FastAPI's `TestClient` is synchronous and doesn't trigger async startup events (`@app.on_event("startup")`).

**Symptom**: Database not initialized, resources not available in tests.

### Solution: Manual Initialization in Sync Fixture

```python
import asyncio
from pathlib import Path
import tempfile

import pytest
from fastapi.testclient import TestClient
from hive_config import HiveConfig

from chimera_daemon.api import create_app
from chimera_daemon.task_queue import TaskQueue

@pytest.fixture
def test_app():
    """Create test API app with temporary database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test config
        config = HiveConfig(
            environment="test",
            database={"path": Path(tmpdir) / "test.db"},
        )

        # Create app
        app = create_app(config=config)

        # Manually initialize async resources
        # (TestClient doesn't trigger async startup events)
        db_path = config.database.path.parent / "chimera_tasks.db"
        queue = TaskQueue(db_path=db_path)

        # Run async initialization in sync context
        asyncio.run(queue.initialize())

        # Return sync TestClient
        client = TestClient(app)
        yield client

# Test functions are SYNC (not async)
def test_submit_task(test_app):
    """Test submitting task via API."""
    response = test_app.post(
        "/api/tasks",
        json={"feature": "User login", "target_url": "https://app.dev", "priority": 5},
    )
    assert response.status_code == 200
```

### Key Points

1. **Fixture is sync** (`def`, not `async def`) because TestClient is sync
2. **Manual async initialization** using `asyncio.run()` for async resources
3. **Test functions are sync** (not `@pytest.mark.asyncio`)
4. **TestClient usage** is straightforward sync API calls

### When to Use This Pattern

✅ **Use when**:
- Testing FastAPI endpoints with TestClient
- Async startup/shutdown events need to run
- Resources (DB, cache, etc.) need async initialization

❌ **Don't use when**:
- Testing pure async functions (use `@pytest.mark.asyncio`)
- Using httpx.AsyncClient (that supports native async)

### Alternative: httpx.AsyncClient

For fully async testing:
```python
import httpx
import pytest

@pytest.fixture
async def test_app():  # Async fixture
    """Create test API app."""
    app = create_app()
    # Startup events run automatically
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_submit_task(test_app):  # Async test
    """Test submitting task via API."""
    client = await test_app
    response = await client.post("/api/tasks", json={...})
    assert response.status_code == 200
```

## References

- FastAPI Testing Guide: https://fastapi.tiangolo.com/tutorial/testing/
- pytest-asyncio: https://pytest-asyncio.readthedocs.io/
- TestClient limitations: https://www.starlette.io/testclient/
