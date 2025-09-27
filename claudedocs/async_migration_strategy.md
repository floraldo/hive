# Hive Async Migration Strategy - Phase 4.1

## 🎯 Objective
Convert the entire Hive platform from synchronous to async-first architecture for 3-5x performance improvement in concurrent task handling.

## 📊 Current State Analysis

### Synchronous Components
1. **Database Layer (`hive-core-db`)**
   - SQLite with `sqlite3` library (blocking I/O)
   - Connection pool with synchronous acquire/release
   - ~50ms average query time blocks entire thread

2. **Agent Main Loops**
   - QueenLite: Blocking poll → process → sleep cycle
   - AI Planner: Blocking Claude CLI calls (30-120s)
   - AI Reviewer: Blocking review operations (15-45s)

3. **Worker Process Management**
   - Synchronous `subprocess.run()` calls
   - Sequential task processing
   - Thread-blocking wait for completion

### Performance Bottlenecks
- **Concurrency Limit**: ~10-20 parallel tasks
- **I/O Blocking**: Database queries block entire agent
- **Sequential Processing**: Workers wait for each other
- **Resource Underutilization**: CPU idle during I/O waits

---

## 🚀 Migration Strategy: "Gradual Async Adoption"

### Phase 4.1.1: Database Layer (Weeks 1-2)

#### Async Database Foundation
```python
# packages/hive-core-db/src/hive_core_db/async_connection_pool.py
import aiosqlite
import asyncio
from contextlib import asynccontextmanager

class AsyncConnectionPool:
    def __init__(self, database_path: str, max_connections: int = 20):
        self.database_path = database_path
        self.max_connections = max_connections
        self._pool = asyncio.Queue(maxsize=max_connections)
        self._connections_created = 0

    async def initialize(self):
        """Create initial pool of connections"""
        for _ in range(min(5, self.max_connections)):
            conn = await aiosqlite.connect(self.database_path)
            await self._pool.put(conn)
            self._connections_created += 1

    @asynccontextmanager
    async def acquire(self):
        """Async context manager for connection acquisition"""
        conn = None
        try:
            # Try to get existing connection
            try:
                conn = await asyncio.wait_for(self._pool.get(), timeout=5.0)
            except asyncio.TimeoutError:
                # Create new connection if pool is busy
                if self._connections_created < self.max_connections:
                    conn = await aiosqlite.connect(self.database_path)
                    self._connections_created += 1
                else:
                    raise ConnectionPoolExhausted()

            yield conn

        finally:
            if conn:
                await self._pool.put(conn)
```

#### Backward Compatibility Layer
```python
# packages/hive-core-db/src/hive_core_db/compat.py
import asyncio
from functools import wraps

def sync_wrapper(async_func):
    """Wrapper to call async functions from sync code"""
    @wraps(async_func)
    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(async_func(*args, **kwargs))
    return wrapper

# Backward compatible sync interface
@sync_wrapper
async def get_connection():
    """Sync wrapper for async connection acquisition"""
    async with get_async_connection() as conn:
        yield SyncConnectionWrapper(conn)
```

#### Migration Implementation
```python
# Step 1: Add async methods alongside existing sync methods
class DatabaseManager:
    # Existing sync methods (preserved)
    def create_task(self, task_data):
        return asyncio.run(self.create_task_async(task_data))

    # New async methods
    async def create_task_async(self, task_data):
        async with get_async_connection() as conn:
            await conn.execute(INSERT_TASK_SQL, task_data)
            await conn.commit()

    async def get_queued_tasks_async(self, limit=10):
        async with get_async_connection() as conn:
            cursor = await conn.execute(SELECT_QUEUED_TASKS_SQL, (limit,))
            return await cursor.fetchall()
```

### Phase 4.1.2: Event Bus Async Integration (Week 3)

#### Async Event Publishing
```python
# packages/hive-bus/src/hive_bus/async_event_bus.py
class AsyncEventBus(EventBus):
    async def publish_async(self, event, correlation_id=None):
        """Async version of event publishing"""
        if correlation_id:
            event.correlation_id = correlation_id

        async with get_async_connection() as conn:
            await conn.execute("""
                INSERT INTO events (
                    event_id, event_type, timestamp, source_agent,
                    correlation_id, payload, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id, event.event_type, event.timestamp.isoformat(),
                event.source_agent, event.correlation_id,
                json.dumps(event.payload), json.dumps(event.metadata)
            ))
            await conn.commit()

        # Async notification to subscribers
        await self._notify_subscribers_async(event)
        return event.event_id

    async def subscribe_async(self, pattern, callback, subscriber_name):
        """Async subscription with async callback support"""
        subscriber = AsyncEventSubscriber(
            pattern=pattern,
            callback=callback,
            subscriber_name=subscriber_name
        )
        # Store subscription...
        return subscriber.subscription_id
```

### Phase 4.1.3: Agent Loop Conversion (Weeks 4-5)

#### QueenLite Async Main Loop
```python
# apps/hive-orchestrator/src/hive_orchestrator/async_queen.py
class AsyncQueenLite(QueenLite):
    async def run_forever_async(self):
        """Async version of main orchestration loop"""
        self.log("Starting async orchestration loop")

        while self.running:
            try:
                # Parallel task processing
                await asyncio.gather(
                    self._process_queued_tasks_async(),
                    self._monitor_workers_async(),
                    self._cleanup_completed_async(),
                    self._send_heartbeat_async()
                )

                await asyncio.sleep(self.config.get_int("status_refresh_seconds", 10))

            except Exception as e:
                self.log(f"Error in async main loop: {e}", "ERROR")
                await asyncio.sleep(5)

    async def _process_queued_tasks_async(self):
        """Process multiple tasks concurrently"""
        tasks = await self.hive_core.get_queued_tasks_async(limit=20)

        if tasks:
            # Process up to 10 tasks concurrently
            semaphore = asyncio.Semaphore(10)
            await asyncio.gather(*[
                self._process_single_task_async(task, semaphore)
                for task in tasks
            ])

    async def _process_single_task_async(self, task, semaphore):
        """Process a single task with concurrency control"""
        async with semaphore:
            worker_type = self._determine_worker_type(task)
            phase = self._determine_phase(task)

            process = await self._spawn_worker_async(task, worker_type, phase)
            if process:
                self.active_workers[task['id']] = {
                    'process': process,
                    'task': task,
                    'started_at': time.time()
                }

    async def _spawn_worker_async(self, task, worker_type, phase):
        """Async worker spawning with non-blocking execution"""
        command = self._build_worker_command(task, worker_type, phase)

        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=PROJECT_ROOT
            )

            # Don't wait for completion - let it run async
            return process

        except Exception as e:
            self.log(f"Failed to spawn async worker: {e}", "ERROR")
            return None
```

#### AI Planner Async Integration
```python
# apps/ai-planner/src/ai_planner/async_agent.py
class AsyncAIPlanner(AIPlanner):
    async def run_agent_async(self):
        """Async agent main loop"""
        while self.running:
            try:
                # Get planning tasks concurrently
                planning_tasks = await self._get_planning_tasks_async()

                if planning_tasks:
                    # Process multiple planning requests concurrently
                    semaphore = asyncio.Semaphore(3)  # Limit concurrent Claude calls
                    await asyncio.gather(*[
                        self._process_planning_task_async(task, semaphore)
                        for task in planning_tasks
                    ])

                await asyncio.sleep(30)  # Check every 30 seconds

            except Exception as e:
                self.log(f"Error in async planner loop: {e}", "ERROR")
                await asyncio.sleep(10)

    async def _process_planning_task_async(self, task, semaphore):
        """Process planning task with concurrency control"""
        async with semaphore:
            try:
                # Async Claude call
                plan = await self._generate_plan_async(task)

                # Async database update
                await self._store_plan_async(task['id'], plan)

                # Async event publishing
                await self._publish_plan_event_async(task['id'], plan)

            except Exception as e:
                await self._handle_planning_error_async(task, e)

    async def _generate_plan_async(self, task):
        """Async Claude planning call"""
        # Use asyncio subprocess for Claude CLI
        process = await asyncio.create_subprocess_shell(
            self._build_claude_command(task),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode == 0:
            return self._parse_plan_response(stdout.decode())
        else:
            raise PlanGenerationError(f"Claude failed: {stderr.decode()}")
```

### Phase 4.1.4: Performance Optimization (Week 6)

#### Concurrent Task Limits
```python
# Configuration for async performance
ASYNC_PERFORMANCE_CONFIG = {
    # QueenLite concurrency
    "max_concurrent_tasks": 50,
    "max_concurrent_workers": 20,
    "worker_spawn_semaphore": 10,

    # AI Planner concurrency
    "max_concurrent_plans": 5,
    "claude_call_semaphore": 3,
    "plan_generation_timeout": 300,

    # AI Reviewer concurrency
    "max_concurrent_reviews": 8,
    "review_timeout": 120,

    # Database concurrency
    "db_connection_pool_size": 25,
    "db_query_timeout": 30,

    # Event bus concurrency
    "max_concurrent_events": 100,
    "event_batch_size": 50
}
```

#### Performance Monitoring
```python
# packages/hive-metrics/src/hive_metrics/async_monitor.py
class AsyncPerformanceMonitor:
    async def monitor_performance(self):
        """Monitor async performance metrics"""
        while True:
            metrics = await self._collect_metrics_async()
            await self._log_metrics_async(metrics)
            await asyncio.sleep(60)  # Every minute

    async def _collect_metrics_async(self):
        """Collect performance metrics"""
        return {
            "active_tasks": len(asyncio.all_tasks()),
            "pending_db_connections": await self._count_pending_connections(),
            "queue_lengths": await self._get_queue_lengths(),
            "worker_utilization": await self._calculate_worker_utilization(),
            "event_throughput": await self._calculate_event_throughput()
        }
```

---

## 🛠️ Implementation Plan

### Week 1: Database Async Foundation
- [ ] Create `AsyncConnectionPool` with `aiosqlite`
- [ ] Implement backward compatibility wrappers
- [ ] Add async versions of core database methods
- [ ] Unit tests for async database operations

### Week 2: Database Migration Completion
- [ ] Convert all database operations to async
- [ ] Performance testing vs sync version
- [ ] Integration testing with existing agents
- [ ] Documentation and migration guide

### Week 3: Event Bus Async Integration
- [ ] Add async event publishing/subscribing
- [ ] Async notification system
- [ ] Event correlation tracking with async
- [ ] Performance benchmarking

### Week 4: QueenLite Async Conversion
- [ ] Implement `AsyncQueenLite` class
- [ ] Async task processing with semaphores
- [ ] Async worker spawning and monitoring
- [ ] Backward compatibility mode

### Week 5: AI Agent Async Conversion
- [ ] `AsyncAIPlanner` implementation
- [ ] `AsyncAIReviewer` implementation
- [ ] Concurrent Claude CLI calls
- [ ] Error handling and recovery

### Week 6: Performance Optimization
- [ ] Tune concurrency limits
- [ ] Performance monitoring system
- [ ] Load testing and benchmarking
- [ ] Production readiness checklist

---

## 📈 Expected Performance Improvements

### Throughput Improvements
| Component | Current (sync) | Target (async) | Improvement |
|-----------|----------------|----------------|-------------|
| QueenLite Tasks/min | 10-20 | 50-100 | 3-5x |
| AI Planner Plans/hour | 20-30 | 60-120 | 3-4x |
| AI Reviewer Reviews/hour | 40-60 | 150-300 | 3-5x |
| Database Queries/sec | 50-100 | 200-500 | 3-5x |

### Resource Utilization
- **CPU**: 40-60% → 70-85% (better utilization)
- **Memory**: Similar (async overhead ~10%)
- **I/O**: Dramatically improved concurrent handling

---

## 🛡️ Risk Mitigation

### Technical Risks
1. **Async/Await Complexity**
   - *Mitigation*: Gradual migration with extensive testing
   - *Fallback*: Sync wrappers for compatibility

2. **Race Conditions**
   - *Mitigation*: Proper async synchronization primitives
   - *Testing*: Stress testing with high concurrency

3. **Memory Usage**
   - *Mitigation*: Connection pooling and task limits
   - *Monitoring*: Real-time memory tracking

### Compatibility Risks
1. **Breaking Changes**
   - *Mitigation*: Maintain sync interfaces during transition
   - *Timeline*: 6-month deprecation period

2. **Third-party Dependencies**
   - *Mitigation*: Async wrapper utilities
   - *Alternative*: Thread pool execution for blocking code

### Performance Risks
1. **Async Overhead**
   - *Mitigation*: Benchmarking at each step
   - *Threshold*: No more than 10% overhead for single tasks

2. **Complexity Increase**
   - *Mitigation*: Comprehensive documentation and training
   - *Monitoring*: Code complexity metrics

---

## 🧪 Testing Strategy

### Unit Testing
```python
# Test async database operations
@pytest.mark.asyncio
async def test_async_database_operations():
    async with get_async_connection() as conn:
        task_id = await create_task_async(test_task_data)
        task = await get_task_async(task_id)
        assert task['id'] == task_id

# Test concurrent operations
@pytest.mark.asyncio
async def test_concurrent_task_processing():
    tasks = [create_test_task() for _ in range(20)]
    results = await asyncio.gather(*[
        process_task_async(task) for task in tasks
    ])
    assert len(results) == 20
    assert all(result.success for result in results)
```

### Load Testing
```python
# Stress test concurrent limits
async def stress_test_concurrency():
    semaphore = asyncio.Semaphore(100)
    tasks = []

    for i in range(1000):
        task = asyncio.create_task(
            concurrent_operation(i, semaphore)
        )
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)
    analyze_results(results)
```

### Performance Benchmarking
```python
# Benchmark sync vs async performance
async def benchmark_performance():
    # Sync baseline
    sync_start = time.time()
    sync_results = [process_task_sync(task) for task in test_tasks]
    sync_duration = time.time() - sync_start

    # Async comparison
    async_start = time.time()
    async_results = await asyncio.gather(*[
        process_task_async(task) for task in test_tasks
    ])
    async_duration = time.time() - async_start

    improvement = sync_duration / async_duration
    assert improvement >= 2.0  # At least 2x improvement
```

---

## 📚 Documentation & Training

### Developer Documentation
1. **Async Programming Guide**
   - Best practices for async/await in Hive
   - Common patterns and anti-patterns
   - Performance optimization tips

2. **Migration Guide**
   - Step-by-step conversion process
   - Before/after code examples
   - Troubleshooting common issues

3. **API Reference**
   - Async method signatures
   - Backward compatibility notes
   - Performance characteristics

### Training Materials
1. **Video Tutorials**
   - Converting sync agents to async
   - Debugging async issues
   - Performance monitoring

2. **Code Examples**
   - Real-world async patterns
   - Error handling strategies
   - Testing approaches

---

## ✅ Success Criteria

### Performance Targets
- [ ] 3x improvement in concurrent task handling
- [ ] <10% increase in memory usage
- [ ] <5% increase in single-task latency
- [ ] 99% backward compatibility

### Quality Targets
- [ ] 100% test coverage for async operations
- [ ] Zero regressions in existing functionality
- [ ] <1% error rate under load
- [ ] Sub-second response times for simple operations

### Operational Targets
- [ ] Smooth migration with zero downtime
- [ ] Complete documentation coverage
- [ ] Developer training completion
- [ ] Production monitoring implementation

---

This async migration strategy provides a systematic path to dramatically improve Hive's performance while maintaining stability and backward compatibility throughout the transition process.