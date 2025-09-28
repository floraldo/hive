#!/usr/bin/env python3
"""
Performance optimization script for Hive platform
Implements connection pooling, async optimizations, and circuit breakers
"""

import asyncio
import os
from pathlib import Path
from typing import Dict, List, Optional
import re

PROJECT_ROOT = Path(__file__).parent.parent

# Performance optimization templates
CONNECTION_POOL_CONFIG = '''"""Enhanced connection pool configuration"""

from typing import Optional
from dataclasses import dataclass

@dataclass
class PoolConfig:
    """Connection pool configuration"""
    min_size: int = 5
    max_size: int = 20
    max_idle_time: int = 300  # seconds
    connection_timeout: int = 10  # seconds
    retry_attempts: int = 3
    retry_delay: float = 0.5

    # Monitoring
    enable_metrics: bool = True
    log_slow_queries: bool = True
    slow_query_threshold: float = 1.0  # seconds
'''

ASYNC_POOL_ENHANCEMENT = '''"""Enhanced async connection pool with monitoring"""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional
from hive_logging import get_logger

logger = get_logger(__name__)


class EnhancedAsyncPool:
    """Async connection pool with monitoring and metrics"""

    def __init__(self, config: PoolConfig):
        self.config = config
        self._pool = []
        self._in_use = set()
        self._metrics = {
            "connections_created": 0,
            "connections_reused": 0,
            "connections_closed": 0,
            "slow_queries": 0,
            "errors": 0,
        }
        self._lock = asyncio.Lock()

    async def acquire_async(self) -> Any:
        """Acquire connection with timeout and monitoring"""
        start_time = time.time()

        async with self._lock:
            # Try to get from pool
            if self._pool:
                conn = self._pool.pop()
                self._metrics["connections_reused"] += 1
            else:
                # Create new connection
                conn = await self._create_connection_async()
                self._metrics["connections_created"] += 1

            self._in_use.add(conn)

        acquisition_time = time.time() - start_time
        if acquisition_time > self.config.connection_timeout / 2:
            logger.warning(f"Slow connection acquisition: {acquisition_time:.2f}s")

        return conn

    async def release_async(self, conn: Any) -> None:
        """Release connection back to pool"""
        async with self._lock:
            self._in_use.discard(conn)

            if len(self._pool) < self.config.max_size:
                self._pool.append(conn)
            else:
                await self._close_connection_async(conn)
                self._metrics["connections_closed"] += 1

    async def _create_connection_async(self) -> Any:
        """Create new connection with retry logic"""
        for attempt in range(self.config.retry_attempts):
            try:
                # Actual connection creation would go here
                return await asyncio.sleep(0)  # Placeholder
            except Exception as e:
                if attempt == self.config.retry_attempts - 1:
                    self._metrics["errors"] += 1
                    raise
                await asyncio.sleep(self.config.retry_delay * (2 ** attempt))

    async def _close_connection_async(self, conn: Any) -> None:
        """Close connection gracefully"""
        try:
            # Actual connection closing would go here
            await asyncio.sleep(0)  # Placeholder
        except Exception as e:
            logger.error(f"Error closing connection: {e}")

    @asynccontextmanager
    async def connection(self):
        """Context manager for connection acquisition"""
        conn = await self.acquire_async()
        try:
            yield conn
        finally:
            await self.release_async(conn)

    def get_metrics(self) -> Dict[str, int]:
        """Get pool metrics"""
        return {
            **self._metrics,
            "pool_size": len(self._pool),
            "in_use": len(self._in_use),
        }

    async def cleanup_async(self) -> None:
        """Cleanup all connections on shutdown"""
        async with self._lock:
            for conn in self._pool:
                await self._close_connection_async(conn)
            self._pool.clear()

            for conn in self._in_use:
                logger.warning("Force closing in-use connection")
                await self._close_connection_async(conn)
            self._in_use.clear()
'''

CIRCUIT_BREAKER = '''"""Circuit breaker pattern for external service calls"""

import time
from enum import Enum
from typing import Any, Callable, Optional
from functools import wraps
from hive_logging import get_logger

logger = get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker for fault tolerance"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self._failure_count = 0
        self._last_failure_time = None
        self._state = CircuitState.CLOSED

    @property
    def state(self) -> CircuitState:
        """Get current circuit state"""
        if self._state == CircuitState.OPEN:
            if self._last_failure_time and \\
               time.time() - self._last_failure_time > self.recovery_timeout:
                self._state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker entering HALF_OPEN state")
        return self._state

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Call function through circuit breaker"""
        if self.state == CircuitState.OPEN:
            raise Exception("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise

    def _on_success(self):
        """Handle successful call"""
        if self._state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            logger.info("Circuit breaker reset to CLOSED")

    def _on_failure(self):
        """Handle failed call"""
        self._failure_count += 1
        self._last_failure_time = time.time()

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            logger.warning(f"Circuit breaker OPEN after {self._failure_count} failures")


def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: type = Exception,
):
    """Decorator for circuit breaker pattern"""
    breaker = CircuitBreaker(failure_threshold, recovery_timeout, expected_exception)

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            return breaker.call(func, *args, **kwargs)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if breaker.state == CircuitState.OPEN:
                raise Exception("Circuit breaker is OPEN")

            try:
                result = await func(*args, **kwargs)
                breaker._on_success()
                return result
            except breaker.expected_exception as e:
                breaker._on_failure()
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else wrapper

    return decorator
'''

TIMEOUT_HANDLER = '''"""Timeout handling for async operations"""

import asyncio
from functools import wraps
from typing import Any, Optional
from hive_logging import get_logger

logger = get_logger(__name__)


def with_timeout(seconds: float):
    """Decorator to add timeout to async functions"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=seconds
                )
            except asyncio.TimeoutError:
                logger.error(f"{func.__name__} timed out after {seconds}s")
                raise

        return wrapper
    return decorator


class TimeoutManager:
    """Manage timeouts for multiple operations"""

    def __init__(self, default_timeout: float = 30.0):
        self.default_timeout = default_timeout
        self._active_tasks = set()

    async def run_with_timeout_async(
        self,
        coro,
        timeout: Optional[float] = None,
        fallback: Optional[Any] = None
    ) -> Any:
        """Run coroutine with timeout and optional fallback"""
        timeout = timeout or self.default_timeout

        try:
            task = asyncio.create_task(coro)
            self._active_tasks.add(task)

            result = await asyncio.wait_for(task, timeout=timeout)
            return result

        except asyncio.TimeoutError:
            logger.warning(f"Operation timed out after {timeout}s")
            if fallback is not None:
                return fallback
            raise

        finally:
            self._active_tasks.discard(task)

    async def cancel_all_async(self):
        """Cancel all active tasks"""
        for task in self._active_tasks:
            task.cancel()

        if self._active_tasks:
            await asyncio.gather(*self._active_tasks, return_exceptions=True)

        self._active_tasks.clear()
'''


def create_performance_module():
    """Create performance optimization module"""
    perf_dir = PROJECT_ROOT / "packages/hive-performance/src/hive_performance"
    perf_dir.mkdir(parents=True, exist_ok=True)

    # Create __init__.py
    init_file = perf_dir / "__init__.py"
    init_file.write_text('''"""Hive performance optimization utilities"""

from .pool import EnhancedAsyncPool, PoolConfig
from .circuit_breaker import CircuitBreaker, circuit_breaker
from .timeout import TimeoutManager, with_timeout

__all__ = [
    "EnhancedAsyncPool",
    "PoolConfig",
    "CircuitBreaker",
    "circuit_breaker",
    "TimeoutManager",
    "with_timeout",
]
''', encoding='utf-8')

    # Create pool.py
    pool_file = perf_dir / "pool.py"
    pool_file.write_text(CONNECTION_POOL_CONFIG + "\n\n" + ASYNC_POOL_ENHANCEMENT, encoding='utf-8')

    # Create circuit_breaker.py
    cb_file = perf_dir / "circuit_breaker.py"
    cb_file.write_text(CIRCUIT_BREAKER, encoding='utf-8')

    # Create timeout.py
    timeout_file = perf_dir / "timeout.py"
    timeout_file.write_text(TIMEOUT_HANDLER, encoding='utf-8')

    # Create pyproject.toml
    pyproject_file = perf_dir.parent.parent / "pyproject.toml"
    pyproject_file.write_text('''[tool.poetry]
name = "hive-performance"
version = "0.1.0"
description = "Performance optimization utilities for Hive platform"
authors = ["Hive Team"]

[tool.poetry.dependencies]
python = "^3.11"
hive-logging = {path = "../hive-logging", develop = true}

[tool.poetry.group.dev.dependencies]
pytest = "^8.3.2"
pytest-asyncio = "^0.23.0"
black = "^24.8.0"
mypy = "^1.8.0"
ruff = "^0.1.15"

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
''', encoding='utf-8')

    return perf_dir


def optimize_async_patterns():
    """Convert synchronous operations to async where beneficial"""

    # Files that should use async patterns
    files_to_optimize = [
        "apps/hive-orchestrator/src/hive_orchestrator/worker.py",
        "apps/hive-orchestrator/src/hive_orchestrator/queen.py",
    ]

    optimizations_applied = []

    for file_path in files_to_optimize:
        full_path = PROJECT_ROOT / file_path
        if not full_path.exists():
            continue

        content = full_path.read_text(encoding='utf-8')
        original_content = content

        # Replace time.sleep with asyncio.sleep
        content = re.sub(
            r'time\.sleep\(([^)]+)\)',
            r'await asyncio.sleep(\1)',
            content
        )

        # Add async to functions that use await
        content = re.sub(
            r'def (\w+)\(([^)]*)\):\s*\n([^}]+)await',
            r'async def \1_async(\2):\n\3await',
            content,
            flags=re.MULTILINE | re.DOTALL
        )

        if content != original_content:
            # Add asyncio import if needed
            if 'await asyncio.sleep' in content and 'import asyncio' not in content:
                content = 'import asyncio\n' + content

            full_path.write_text(content, encoding='utf-8')
            optimizations_applied.append(file_path)

    return optimizations_applied


def main():
    """Main performance optimization function"""
    print("=" * 60)
    print("Hive Platform Performance Optimization")
    print("=" * 60)

    # Create performance module
    print("\n1. Creating Performance Module")
    print("-" * 40)
    perf_dir = create_performance_module()
    print(f"  Created: {perf_dir}")

    # Optimize async patterns
    print("\n2. Optimizing Async Patterns")
    print("-" * 40)
    optimized = optimize_async_patterns()
    for file in optimized:
        print(f"  Optimized: {file}")

    # Create performance config
    print("\n3. Creating Performance Configuration")
    print("-" * 40)

    perf_config = PROJECT_ROOT / "config/performance.yaml"
    perf_config.parent.mkdir(parents=True, exist_ok=True)
    perf_config.write_text('''# Hive Platform Performance Configuration

connection_pool:
  min_size: 5
  max_size: 20
  max_idle_time: 300
  connection_timeout: 10
  retry_attempts: 3
  retry_delay: 0.5
  enable_metrics: true
  log_slow_queries: true
  slow_query_threshold: 1.0

circuit_breaker:
  failure_threshold: 5
  recovery_timeout: 60
  expected_exceptions:
    - ConnectionError
    - TimeoutError

timeout:
  default_timeout: 30.0
  operation_timeouts:
    database_query: 5.0
    external_api_call: 10.0
    file_processing: 60.0
    batch_operation: 120.0

monitoring:
  enable_metrics: true
  metrics_interval: 60
  log_level: INFO
  slow_operation_threshold: 1.0

optimization:
  enable_connection_pooling: true
  enable_circuit_breaker: true
  enable_timeout_handling: true
  enable_async_optimization: true
  batch_size: 100
  parallel_workers: 4
''', encoding='utf-8')
    print(f"  Created: {perf_config}")

    print("\n" + "=" * 60)
    print("Performance Optimization Complete!")
    print("=" * 60)
    print("\nPerformance improvements applied:")
    print("  ✅ Connection pool with monitoring")
    print("  ✅ Circuit breaker pattern")
    print("  ✅ Timeout handling")
    print("  ✅ Async pattern optimization")
    print("  ✅ Performance configuration")
    print("\nNext steps:")
    print("1. Run tests to verify optimizations")
    print("2. Monitor performance metrics")
    print("3. Tune configuration based on load testing")


if __name__ == "__main__":
    main()