# Project Colossus - Layer 2 Week 5-6 Roadmap: Monitoring & Reliability

**Mission**: Transform parallel execution factory into production-ready autonomous system with comprehensive observability and resilience

**Prerequisites**: ✅ Week 3-4 Complete (ExecutorPool operational)

---

## Executive Summary

Week 5-6 focuses on **observability, reliability, and production readiness** for the parallel execution system. The factory now runs multiple assembly lines; we need quality control, health monitoring, and failure recovery to ensure stable autonomous operation.

**Key Goals**:
1. **Advanced Metrics & Monitoring**: Real-time visibility into pool performance and bottlenecks
2. **Error Recovery**: Automatic retry, circuit breaker, and dead letter queue patterns
3. **Structured Logging**: Trace-based correlation across workflow phases
4. **Resource Management**: Dynamic pool sizing and graceful degradation

---

## Phase 1: Advanced Metrics & Monitoring (Days 1-3)

### 1.1 Enhanced Pool Metrics

**Objective**: Provide comprehensive visibility into parallel execution performance

**Deliverables**:
```python
# apps/chimera-daemon/src/chimera_daemon/metrics.py (NEW)
class PoolMetrics:
    """Enhanced pool performance metrics."""

    # Utilization Metrics
    pool_utilization_pct: float  # (active / total) * 100
    avg_slot_wait_time_ms: float  # How long tasks wait for slots
    peak_utilization_pct: float   # Historical peak usage

    # Queue Depth Metrics
    queue_depth: int              # Tasks waiting for execution
    queue_depth_trend: str        # "increasing" | "stable" | "decreasing"
    avg_queue_time_ms: float      # Time tasks spend in queue

    # Workflow Performance
    p50_workflow_duration_ms: float  # 50th percentile
    p95_workflow_duration_ms: float  # 95th percentile
    p99_workflow_duration_ms: float  # 99th percentile

    # Failure Pattern Analysis
    failure_rate_by_phase: dict[str, float]  # Which phases fail most
    retry_success_rate: float     # How often retries succeed
    failure_trend: str            # Pattern over time
```

**Implementation**:
- Add metrics collection to ExecutorPool
- Implement sliding window for trend analysis (last 100 workflows)
- Add percentile calculations for latency distribution

**Testing**:
- Unit tests for metrics calculation accuracy
- Stress test with 50+ workflows to verify percentile accuracy

### 1.2 Real-Time Health Monitoring

**Objective**: Continuous health assessment with actionable alerts

**Deliverables**:
```python
# apps/chimera-daemon/src/chimera_daemon/health.py (NEW)
class HealthMonitor:
    """Continuous health monitoring with threshold alerts."""

    async def check_health(self) -> HealthStatus:
        """Comprehensive health check."""
        return HealthStatus(
            status="healthy" | "degraded" | "unhealthy",
            checks=[
                HealthCheck(
                    name="pool_capacity",
                    status="pass" | "warn" | "fail",
                    message="Pool at 95% capacity for 5 minutes",
                    threshold_exceeded=True,
                ),
                HealthCheck(
                    name="workflow_success_rate",
                    status="pass",
                    current_value=0.92,
                    threshold=0.80,
                ),
                # ... other checks
            ],
            recommendations=[
                "Increase max_concurrent from 5 to 8",
                "Investigate E2E_TEST_GENERATION phase failures",
            ],
        )
```

**Health Check Dimensions**:
- **Pool Capacity**: Utilization, slot availability, queue depth
- **Workflow Quality**: Success rate, phase completion, retry patterns
- **Resource Usage**: Memory, CPU, database connections
- **Latency**: Workflow duration, queue time, slot wait time

**Alert Thresholds**:
```yaml
critical:  # Auto-remediation required
  pool_utilization: "> 95% for > 5 min"
  success_rate: "< 50%"
  queue_depth: "> 100 tasks"

warning:  # Investigation recommended
  pool_utilization: "> 80% for > 10 min"
  success_rate: "< 80%"
  avg_workflow_duration: "> 2x baseline"

info:  # Informational
  pool_utilization: "> 60%"
  queue_depth: "> 20 tasks"
```

### 1.3 Metrics API Endpoint

**Objective**: Expose metrics via REST API for monitoring tools

**Deliverable**:
```python
# apps/chimera-daemon/src/chimera_daemon/api.py (MODIFY)
@app.get("/api/metrics", response_model=MetricsResponse)
async def get_pool_metrics() -> MetricsResponse:
    """Get ExecutorPool performance metrics.

    Note: Requires shared state between API and daemon.
    Implementation options:
    1. Redis pub/sub for metrics sharing
    2. Shared SQLite metrics table
    3. Daemon-hosted metrics endpoint (separate from API)
    """
    # Implementation depends on Week 5-6 architecture decision
    pass

@app.get("/api/health", response_model=HealthCheckResponse)
async def get_health_status() -> HealthCheckResponse:
    """Get comprehensive health status with recommendations."""
    pass
```

**Architecture Decision Required**: API and daemon currently run separately. Options:
- **Option A**: Shared Redis for real-time metrics
- **Option B**: SQLite metrics table (polling-based)
- **Option C**: Daemon hosts both API endpoints (combine processes)

---

## Phase 2: Error Recovery & Resilience (Days 4-6)

### 2.1 Automatic Retry Logic

**Objective**: Intelligent retry with exponential backoff for transient failures

**Deliverables**:
```python
# apps/chimera-daemon/src/chimera_daemon/retry.py (NEW)
class RetryPolicy:
    """Configurable retry policy for workflow failures."""

    max_retries: int = 3
    initial_delay_ms: int = 1000
    max_delay_ms: int = 30000
    backoff_multiplier: float = 2.0

    # Failure classification
    retryable_phases = {
        ChimeraPhase.E2E_TEST_GENERATION,
        ChimeraPhase.STAGING_DEPLOYMENT,
        ChimeraPhase.E2E_VALIDATION,
    }

    non_retryable_phases = {
        ChimeraPhase.GUARDIAN_REVIEW,  # Rejection is final
    }

    async def should_retry(
        self,
        workflow: ChimeraWorkflow,
        error: Exception,
    ) -> bool:
        """Determine if workflow should be retried."""
        # Logic based on phase, error type, retry count
        pass

    async def calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff + jitter."""
        delay = min(
            self.initial_delay_ms * (self.backoff_multiplier ** attempt),
            self.max_delay_ms,
        )
        # Add jitter: ±20% randomization
        jitter = delay * 0.2 * (random.random() * 2 - 1)
        return (delay + jitter) / 1000  # Convert to seconds
```

**Integration with ExecutorPool**:
```python
# apps/chimera-daemon/src/chimera_daemon/executor_pool.py (MODIFY)
class ExecutorPool:
    def __init__(self, ..., retry_policy: RetryPolicy | None = None):
        self.retry_policy = retry_policy or RetryPolicy()

    async def _execute_workflow(self, task: Task) -> None:
        for attempt in range(self.retry_policy.max_retries + 1):
            try:
                # Execute workflow
                workflow = await executor.execute_workflow(task)

                if workflow.current_phase == ChimeraPhase.COMPLETE:
                    return  # Success

                # Check if should retry
                if await self.retry_policy.should_retry(workflow, None):
                    delay = await self.retry_policy.calculate_delay(attempt)
                    await asyncio.sleep(delay)
                    continue

                break  # Non-retryable failure

            except Exception as e:
                if await self.retry_policy.should_retry(None, e):
                    delay = await self.retry_policy.calculate_delay(attempt)
                    await asyncio.sleep(delay)
                    continue
                raise
```

### 2.2 Dead Letter Queue (DLQ)

**Objective**: Isolate persistent failures for manual investigation

**Deliverable**:
```python
# apps/chimera-daemon/src/chimera_daemon/dlq.py (NEW)
class DeadLetterQueue:
    """Queue for workflows that exhausted retries."""

    async def enqueue_failed(
        self,
        task: Task,
        workflow: ChimeraWorkflow,
        error: str,
        retry_count: int,
    ) -> None:
        """Move failed workflow to DLQ."""
        await self.db.execute(
            """
            INSERT INTO dead_letter_queue
            (task_id, workflow_state, error, retry_count, failed_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (task.id, json.dumps(workflow.model_dump()), error, retry_count, datetime.now()),
        )

    async def get_dlq_tasks(self, limit: int = 50) -> list[DLQEntry]:
        """Retrieve DLQ entries for investigation."""
        pass

    async def requeue_dlq_task(self, dlq_id: str) -> None:
        """Manually requeue DLQ task after investigation."""
        pass
```

**Database Schema**:
```sql
CREATE TABLE dead_letter_queue (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    workflow_state TEXT NOT NULL,
    error TEXT NOT NULL,
    retry_count INTEGER NOT NULL,
    failed_at TEXT NOT NULL,
    investigated BOOLEAN DEFAULT 0,
    resolution TEXT,
    requeued_at TEXT
);
```

### 2.3 Circuit Breaker Pattern

**Objective**: Prevent cascade failures when agents are degraded

**Deliverable**:
```python
# apps/chimera-daemon/src/chimera_daemon/circuit_breaker.py (NEW)
class CircuitBreaker:
    """Circuit breaker for agent health protection."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_ms: int = 60000,
        half_open_max_calls: int = 3,
    ):
        self.state: CircuitState = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: datetime | None = None

    async def call(self, agent_name: str, action: Callable) -> Any:
        """Execute action through circuit breaker."""

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout elapsed
            if self._should_attempt_recovery():
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError(f"{agent_name} circuit breaker OPEN")

        try:
            result = await action()

            # Success in HALF_OPEN → transition to CLOSED
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0

            return result

        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()

            # Threshold exceeded → OPEN circuit
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.error(f"Circuit breaker OPEN for {agent_name} after {self.failure_count} failures")

            raise
```

**Integration**:
```python
# apps/chimera-daemon/src/chimera_daemon/executor_pool.py (MODIFY)
class ExecutorPool:
    def __init__(self, ..., circuit_breakers: dict[str, CircuitBreaker] | None = None):
        self.circuit_breakers = circuit_breakers or {
            agent_name: CircuitBreaker() for agent_name in agents_registry
        }

    async def _execute_phase(self, workflow, action):
        """Execute phase with circuit breaker protection."""
        agent_name = action["agent"]
        breaker = self.circuit_breakers[agent_name]

        return await breaker.call(
            agent_name,
            lambda: agent.execute(action),
        )
```

---

## Phase 3: Structured Logging & Traceability (Days 7-9)

### 3.1 Trace-Based Logging

**Objective**: Correlate logs across workflow phases with trace IDs

**Deliverable**:
```python
# apps/chimera-daemon/src/chimera_daemon/tracing.py (NEW)
class WorkflowTracer:
    """Distributed tracing for workflow execution."""

    def __init__(self):
        self.trace_context: contextvars.ContextVar[TraceContext] = contextvars.ContextVar('trace')

    def start_trace(self, task_id: str) -> str:
        """Start new trace for workflow."""
        trace_id = f"trace-{uuid.uuid4().hex[:16]}"
        context = TraceContext(
            trace_id=trace_id,
            task_id=task_id,
            started_at=datetime.now(),
            spans=[],
        )
        self.trace_context.set(context)
        return trace_id

    @contextmanager
    def span(self, name: str, **attributes):
        """Create trace span for operation."""
        context = self.trace_context.get()
        span_id = f"span-{uuid.uuid4().hex[:8]}"

        span = Span(
            span_id=span_id,
            name=name,
            started_at=datetime.now(),
            attributes=attributes,
        )

        try:
            yield span
        finally:
            span.completed_at = datetime.now()
            span.duration_ms = (span.completed_at - span.started_at).total_seconds() * 1000
            context.spans.append(span)
```

**Structured Log Format**:
```json
{
  "timestamp": "2025-10-05T14:32:15.123Z",
  "level": "INFO",
  "trace_id": "trace-a1b2c3d4e5f6g7h8",
  "span_id": "span-x1y2z3w4",
  "task_id": "chimera-abc123",
  "workflow_phase": "E2E_TEST_GENERATION",
  "component": "executor_pool",
  "message": "Phase execution started",
  "context": {
    "pool_utilization": 0.6,
    "active_workflows": 3,
    "agent": "e2e-tester-agent"
  }
}
```

**Integration**:
```python
# apps/chimera-daemon/src/chimera_daemon/executor_pool.py (MODIFY)
async def _execute_workflow(self, task: Task) -> None:
    trace_id = self.tracer.start_trace(str(task.id))

    with self.tracer.span("workflow_execution", task_id=str(task.id)):
        # Execute workflow with trace context
        with self.tracer.span("phase_execution", phase=workflow.current_phase):
            result = await executor.execute_phase(task, workflow)
```

### 3.2 Performance Profiling Hooks

**Objective**: Identify bottlenecks with granular timing

**Deliverable**:
```python
# apps/chimera-daemon/src/chimera_daemon/profiling.py (NEW)
class PerformanceProfiler:
    """Granular performance profiling for workflows."""

    async def profile_workflow(self, workflow_execution: Callable):
        """Profile workflow execution with detailed timing."""

        profile = WorkflowProfile(task_id=task.id)

        # Profile each phase
        for phase in workflow.phases:
            phase_start = time.perf_counter()

            # Profile agent communication
            with self._profile_section("agent_request"):
                result = await agent.execute(action)

            # Profile state transitions
            with self._profile_section("state_transition"):
                workflow.transition_to(next_phase, result)

            # Profile database operations
            with self._profile_section("db_update"):
                await task_queue.update_workflow_state(task.id, workflow.model_dump())

            phase_duration = (time.perf_counter() - phase_start) * 1000
            profile.add_phase_timing(phase.name, phase_duration)

        return profile
```

---

## Phase 4: Resource Management & Auto-Scaling (Days 10-12)

### 4.1 Dynamic Pool Sizing

**Objective**: Automatically adjust pool size based on load

**Deliverable**:
```python
# apps/chimera-daemon/src/chimera_daemon/autoscaler.py (NEW)
class PoolAutoscaler:
    """Dynamic pool sizing based on load patterns."""

    def __init__(
        self,
        min_concurrent: int = 3,
        max_concurrent: int = 10,
        scale_up_threshold: float = 0.8,   # 80% utilization
        scale_down_threshold: float = 0.3,  # 30% utilization
        scale_up_increment: int = 2,
        scale_down_increment: int = 1,
        cooldown_period_ms: int = 60000,   # 1 minute
    ):
        self.current_size = min_concurrent
        self.last_scale_time = datetime.now()

    async def evaluate_scaling(
        self,
        pool_metrics: PoolMetrics,
    ) -> ScalingDecision:
        """Determine if scaling action needed."""

        # Cooldown period check
        if self._in_cooldown():
            return ScalingDecision.NO_ACTION

        utilization = pool_metrics.pool_utilization_pct / 100

        # Scale up logic
        if utilization >= self.scale_up_threshold and self.current_size < self.max_concurrent:
            new_size = min(
                self.current_size + self.scale_up_increment,
                self.max_concurrent,
            )
            return ScalingDecision(
                action="scale_up",
                from_size=self.current_size,
                to_size=new_size,
                reason=f"Utilization {utilization:.1%} >= {self.scale_up_threshold:.1%}",
            )

        # Scale down logic
        if utilization <= self.scale_down_threshold and self.current_size > self.min_concurrent:
            new_size = max(
                self.current_size - self.scale_down_increment,
                self.min_concurrent,
            )
            return ScalingDecision(
                action="scale_down",
                from_size=self.current_size,
                to_size=new_size,
                reason=f"Utilization {utilization:.1%} <= {self.scale_down_threshold:.1%}",
            )

        return ScalingDecision.NO_ACTION
```

**Integration with ExecutorPool**:
```python
# apps/chimera-daemon/src/chimera_daemon/executor_pool.py (MODIFY)
class ExecutorPool:
    async def resize_pool(self, new_size: int) -> None:
        """Dynamically resize pool capacity."""
        old_size = self.max_concurrent

        if new_size > old_size:
            # Scale up: increase semaphore capacity
            additional_permits = new_size - old_size
            for _ in range(additional_permits):
                self._semaphore.release()

            self.max_concurrent = new_size
            self.logger.info(f"Pool scaled UP: {old_size} → {new_size}")

        elif new_size < old_size:
            # Scale down: wait for workflows to complete
            while self.active_count > new_size:
                await asyncio.sleep(0.5)

            # Reduce semaphore capacity
            permits_to_remove = old_size - new_size
            for _ in range(permits_to_remove):
                await self._semaphore.acquire()

            self.max_concurrent = new_size
            self.logger.info(f"Pool scaled DOWN: {old_size} → {new_size}")
```

### 4.2 Graceful Degradation

**Objective**: Maintain service during resource pressure

**Deliverable**:
```python
# apps/chimera-daemon/src/chimera_daemon/degradation.py (NEW)
class GracefulDegradation:
    """Maintain service quality under resource constraints."""

    async def evaluate_mode(
        self,
        system_metrics: SystemMetrics,
    ) -> OperationMode:
        """Determine operational mode based on resources."""

        # Check resource thresholds
        if system_metrics.memory_usage_pct > 90:
            return OperationMode.SURVIVAL  # Emergency mode

        if system_metrics.cpu_usage_pct > 85 or system_metrics.memory_usage_pct > 80:
            return OperationMode.DEGRADED  # Reduced capacity

        return OperationMode.NORMAL

    async def apply_mode(self, mode: OperationMode, pool: ExecutorPool):
        """Apply operational mode restrictions."""

        if mode == OperationMode.SURVIVAL:
            # Emergency: Accept only high-priority tasks
            await pool.resize_pool(2)  # Minimum capacity
            pool.priority_threshold = 8  # Only priority ≥ 8

        elif mode == OperationMode.DEGRADED:
            # Degraded: Reduce but maintain service
            await pool.resize_pool(pool.max_concurrent // 2)
            pool.priority_threshold = 5  # Priority ≥ 5

        else:
            # Normal: Full capacity
            await pool.resize_pool(pool.max_concurrent)
            pool.priority_threshold = 0  # All priorities
```

### 4.3 Intelligent Task Prioritization

**Objective**: Optimize task scheduling based on business value

**Deliverable**:
```python
# apps/chimera-daemon/src/chimera_daemon/scheduler.py (NEW)
class IntelligentScheduler:
    """Smart task prioritization and scheduling."""

    async def get_next_task(
        self,
        queue: TaskQueue,
        pool_state: PoolMetrics,
    ) -> Task | None:
        """Select optimal task based on multiple factors."""

        # Scoring factors
        tasks = await queue.get_pending_tasks(limit=10)

        scored_tasks = [
            (
                task,
                self._calculate_score(
                    priority=task.priority,
                    wait_time=(datetime.now() - task.created_at).total_seconds(),
                    estimated_duration=self._estimate_duration(task),
                    pool_state=pool_state,
                ),
            )
            for task in tasks
        ]

        # Select highest score
        if scored_tasks:
            best_task, score = max(scored_tasks, key=lambda x: x[1])
            return best_task

        return None

    def _calculate_score(
        self,
        priority: int,
        wait_time: float,
        estimated_duration: float,
        pool_state: PoolMetrics,
    ) -> float:
        """Calculate composite task score."""

        # Base priority weight
        score = priority * 10

        # Aging factor: increase score for waiting tasks
        aging_bonus = min(wait_time / 300, 5)  # Max +5 for 5+ min wait
        score += aging_bonus

        # Short task boost: prefer quick tasks when pool is busy
        if pool_state.pool_utilization_pct > 70 and estimated_duration < 60:
            score += 3  # Boost short tasks when busy

        return score
```

---

## Validation & Acceptance Criteria

### Week 5-6 Completion Checklist

**Metrics & Monitoring** (Phase 1):
- [ ] Enhanced pool metrics implemented (utilization, percentiles, trends)
- [ ] Real-time health monitoring with actionable alerts
- [ ] Metrics API endpoint exposed (architecture decision made)
- [ ] Grafana/monitoring dashboard template created

**Error Recovery** (Phase 2):
- [ ] Automatic retry with exponential backoff
- [ ] Dead letter queue for persistent failures
- [ ] Circuit breaker protecting agent calls
- [ ] 95%+ retry success rate on transient failures

**Logging & Tracing** (Phase 3):
- [ ] Trace-based logging with correlation IDs
- [ ] Structured JSON log format implemented
- [ ] Performance profiling hooks active
- [ ] Log aggregation configuration documented

**Resource Management** (Phase 4):
- [ ] Dynamic pool auto-scaling operational
- [ ] Graceful degradation under resource pressure
- [ ] Intelligent task prioritization active
- [ ] Load testing validates 10+ concurrent workflows

### Performance Benchmarks

**Target Metrics**:
- **Throughput**: 10x baseline (50 workflows/hour with 5 workers)
- **Availability**: 99.5% uptime (< 3.6 hours downtime/month)
- **Latency**: P95 workflow duration < 5 minutes
- **Retry Success**: 95% of transient failures resolved automatically
- **Resource Efficiency**: Auto-scaling reduces idle capacity by 40%

### Testing Requirements

**Unit Tests**: 90%+ coverage for new components
**Integration Tests**: End-to-end scenarios with failure injection
**Stress Tests**: 100+ concurrent workflows, sustained load
**Chaos Engineering**: Random agent failures, network issues, resource exhaustion

---

## Implementation Timeline

**Week 5** (Days 1-6):
- Days 1-3: Metrics & Monitoring (Phase 1)
- Days 4-6: Error Recovery (Phase 2)

**Week 6** (Days 7-12):
- Days 7-9: Logging & Tracing (Phase 3)
- Days 10-12: Resource Management (Phase 4)

**Buffer**: Days 13-14 for integration testing and documentation

---

## Success Criteria

**Week 5-6 Complete When**:
1. ✅ All 4 phases implemented and tested
2. ✅ System handles 10+ concurrent workflows reliably
3. ✅ Automatic recovery from 95%+ transient failures
4. ✅ Real-time monitoring with actionable insights
5. ✅ Production deployment documentation complete

**Next Steps**: Week 7-8 Production Deployment (systemd, Docker, scaling)

---

**Prepared by**: Project Colossus Team
**Date**: 2025-10-05
**Status**: READY FOR EXECUTION (Week 3-4 Complete)
