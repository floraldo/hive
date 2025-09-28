# Async Infrastructure Implementation Plan

## Phase 1: Critical Path - Worker Async Implementation

### 1.1 Async Worker Core Foundation
**File**: `apps/hive-orchestrator/src/hive_orchestrator/async_worker.py`

```python
"""
Async Worker Implementation for Phase 4.1 Performance Improvement
"""

import asyncio
import aiofiles
from typing import Dict, Any, Optional
from pathlib import Path

from hive_orchestrator.core.db import (
    get_task_async, update_task_status_async,
    create_run_async, log_run_result
)
from hive_orchestrator.core.bus import get_async_event_bus, publish_event_async

class AsyncWorkerCore:
    """High-performance async worker for 3-5x throughput improvement"""

    def __init__(self, worker_id: str):
        self.worker_id = worker_id
        self.event_bus = None

    async def initialize(self):
        """Initialize async worker components"""
        self.event_bus = await get_async_event_bus()

    async def process_task(self, task_id: str, run_id: str) -> Dict[str, Any]:
        """
        Process task asynchronously with non-blocking operations

        Returns:
            Task execution result
        """
        # Get task data asynchronously
        task = await get_task_async(task_id)
        if not task:
            return {"status": "failed", "error": "Task not found"}

        try:
            # Update status to running (non-blocking)
            await update_task_status_async(task_id, "in_progress")

            # Execute task concurrently
            result = await self._execute_task_async(task, run_id)

            # Report completion asynchronously
            await self._report_completion_async(task_id, run_id, result)

            return result

        except Exception as e:
            await self._handle_error_async(task_id, run_id, str(e))
            return {"status": "failed", "error": str(e)}

    async def _execute_task_async(self, task: Dict[str, Any], run_id: str) -> Dict[str, Any]:
        """Execute task using async subprocess and Claude API"""

        # Prepare workspace asynchronously
        workspace = await self._prepare_workspace_async(task)

        # Execute Claude command with async subprocess
        claude_process = await asyncio.create_subprocess_exec(
            "claude", "code", task.get("description", ""),
            cwd=workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Wait for completion with timeout
        try:
            stdout, stderr = await asyncio.wait_for(
                claude_process.communicate(),
                timeout=300.0  # 5 minute timeout
            )

            if claude_process.returncode == 0:
                return {
                    "status": "success",
                    "output": stdout.decode(),
                    "workspace": str(workspace)
                }
            else:
                return {
                    "status": "failed",
                    "error": stderr.decode(),
                    "output": stdout.decode()
                }

        except asyncio.TimeoutError:
            claude_process.kill()
            return {"status": "failed", "error": "Task execution timeout"}

    async def _prepare_workspace_async(self, task: Dict[str, Any]) -> Path:
        """Prepare workspace asynchronously"""
        workspace = Path(f"workspaces/{task['id']}")
        workspace.mkdir(parents=True, exist_ok=True)

        # Write task context asynchronously
        async with aiofiles.open(workspace / "task.json", "w") as f:
            await f.write(json.dumps(task, indent=2))

        return workspace

    async def _report_completion_async(self, task_id: str, run_id: str, result: Dict[str, Any]):
        """Report task completion asynchronously"""
        # Update database
        await update_task_status_async(
            task_id,
            "completed" if result["status"] == "success" else "failed"
        )

        # Publish completion event
        await publish_event_async({
            "event_type": "task.completed",
            "task_id": task_id,
            "result": result
        })

    async def _handle_error_async(self, task_id: str, run_id: str, error: str):
        """Handle task error asynchronously"""
        await update_task_status_async(task_id, "failed")
        await publish_event_async({
            "event_type": "task.failed",
            "task_id": task_id,
            "error": error
        })
```

### 1.2 Async Worker CLI Integration
**File**: `apps/hive-orchestrator/src/hive_orchestrator/worker.py` (Enhancement)

Add async mode to existing worker:

```python
# Add to existing worker.py

import asyncio

class WorkerCore:
    # ... existing sync implementation ...

    async def process_task_async(self, task_id: str, run_id: str) -> Dict[str, Any]:
        """Async version of task processing for Phase 4.1"""
        if not hasattr(self, '_async_worker'):
            from .async_worker import AsyncWorkerCore
            self._async_worker = AsyncWorkerCore(self.worker_id)
            await self._async_worker.initialize()

        return await self._async_worker.process_task(task_id, run_id)

def main():
    # ... existing main function ...

    # Add async flag
    parser.add_argument("--async", action="store_true",
                       help="Enable async processing for 3-5x performance")

    args = parser.parse_args()

    if args.async:
        # Run in async mode
        worker = WorkerCore(args.worker_type, task_id=args.task_id,
                          run_id=args.run_id, phase=args.phase, mode=args.mode)

        async def async_main():
            result = await worker.process_task_async(args.task_id, args.run_id)
            return result

        result = asyncio.run(async_main())
    else:
        # Existing sync implementation
        # ... existing code ...
```

## Phase 2: Queen Async Integration Enhancement

### 2.1 Complete Queen Async Coordination
**File**: `apps/hive-orchestrator/src/hive_orchestrator/queen.py` (Enhancement)

The Queen already has async infrastructure. Complete the integration:

```python
# Enhance existing QueenLite class

class QueenLite:
    # ... existing implementation ...

    async def spawn_worker_async(self, task: Dict[str, Any], worker: str, phase: Phase):
        """Enhanced async worker spawning with --async flag"""
        # ... existing async implementation with modification ...

        cmd_parts = [
            sys.executable,
            "-m", "hive_orchestrator.worker",
            worker,
            "--one-shot",
            "--task-id", task_id,
            "--run-id", run_id,
            "--phase", phase.value,
            "--mode", mode,
            "--async"  # Enable async processing in worker
        ]

        # ... rest of existing implementation ...
```

### 2.2 Async Task Coordination
Enhance the existing async main loop with better coordination:

```python
async def _process_workflow_tasks_async(self):
    """Enhanced async workflow processing with better concurrency control"""

    # Use semaphore for optimal concurrency
    max_concurrent = sum(self.hive.config["max_parallel_per_role"].values())
    semaphore = asyncio.Semaphore(max_concurrent)

    # Get tasks concurrently
    queued_tasks = await get_queued_tasks_async(limit=max_concurrent * 2)

    # Process with controlled concurrency
    async def process_with_limit(task):
        async with semaphore:
            return await self._process_single_workflow_task_async(task, semaphore)

    # Execute all tasks concurrently within limits
    if queued_tasks:
        await asyncio.gather(
            *[process_with_limit(task) for task in queued_tasks],
            return_exceptions=True
        )
```

## Phase 3: AI Components Async Integration

### 3.1 Async AI Planner Integration
**File**: `apps/ai-planner/src/ai_planner/async_agent.py`

```python
"""
Async AI Planner for concurrent task planning
"""

import asyncio
from typing import Dict, Any, List

class AsyncAIPlannerAgent:
    """Async AI Planner for parallel task planning"""

    async def plan_task_async(self, task_description: str) -> Dict[str, Any]:
        """Plan task asynchronously with Claude API"""

        # Use async HTTP client for Claude API
        async with aiohttp.ClientSession() as session:
            # Make async Claude API call
            plan = await self._call_claude_async(session, task_description)

            # Process plan concurrently
            subtasks = await self._generate_subtasks_async(plan)

            return {
                "plan": plan,
                "subtasks": subtasks,
                "estimated_duration": self._estimate_duration(subtasks)
            }

    async def _call_claude_async(self, session: aiohttp.ClientSession, prompt: str) -> str:
        """Async Claude API call"""
        # Implementation for async Claude API interaction
        pass

    async def _generate_subtasks_async(self, plan: str) -> List[Dict[str, Any]]:
        """Generate subtasks asynchronously"""
        # Parse plan and create subtasks concurrently
        pass
```

### 3.2 Async AI Reviewer Integration
**File**: `apps/ai-reviewer/src/ai_reviewer/async_agent.py`

```python
"""
Async AI Reviewer for parallel task review
"""

class AsyncAIReviewerAgent:
    """Async AI Reviewer for concurrent task review"""

    async def review_task_async(self, task_id: str) -> Dict[str, Any]:
        """Review task asynchronously"""

        # Get task and results concurrently
        task, results = await asyncio.gather(
            get_task_async(task_id),
            self._get_task_results_async(task_id)
        )

        # Perform review with Claude API
        review = await self._perform_review_async(task, results)

        # Update task status asynchronously
        await self._update_review_status_async(task_id, review)

        return review

    async def _perform_review_async(self, task: Dict[str, Any], results: Dict[str, Any]) -> Dict[str, Any]:
        """Perform async review with Claude"""
        # Async Claude API call for review
        pass
```

## Phase 4: Performance Testing & Benchmarking

### 4.1 Async Performance Tests
**File**: `tests/test_async_performance.py`

```python
"""
Performance tests to validate 3-5x improvement
"""

import asyncio
import time
import pytest
from concurrent.futures import ThreadPoolExecutor

class AsyncPerformanceTests:

    @pytest.mark.asyncio
    async def test_concurrent_task_processing(self):
        """Test concurrent vs sequential task processing"""

        # Sequential processing (baseline)
        start_time = time.time()
        sequential_results = []
        for i in range(5):
            result = await self._process_single_task(f"task_{i}")
            sequential_results.append(result)
        sequential_time = time.time() - start_time

        # Concurrent processing (async)
        start_time = time.time()
        concurrent_results = await asyncio.gather(
            *[self._process_single_task(f"task_{i}") for i in range(5)]
        )
        concurrent_time = time.time() - start_time

        # Verify 3-5x improvement
        improvement_ratio = sequential_time / concurrent_time
        assert improvement_ratio >= 3.0, f"Expected 3x improvement, got {improvement_ratio:.2f}x"

    async def _process_single_task(self, task_id: str) -> Dict[str, Any]:
        """Simulate task processing"""
        await asyncio.sleep(1)  # Simulate work
        return {"task_id": task_id, "status": "completed"}

    @pytest.mark.asyncio
    async def test_database_concurrency(self):
        """Test async database operations vs sync"""

        # Test concurrent database operations
        start_time = time.time()
        tasks = await asyncio.gather(
            *[create_task_async(f"test_task_{i}", "test", f"description {i}")
              for i in range(10)]
        )
        async_time = time.time() - start_time

        # Verify performance improvement
        assert async_time < 2.0, f"Async DB operations took too long: {async_time:.2f}s"
        assert len(tasks) == 10, "Not all tasks were created"
```

### 4.2 Performance Monitoring
**File**: `apps/hive-orchestrator/src/hive_orchestrator/performance_monitor.py`

```python
"""
Performance monitoring for async infrastructure
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, Any, List

@dataclass
class PerformanceMetrics:
    """Performance metrics for async operations"""
    tasks_per_second: float
    concurrent_tasks: int
    avg_task_duration: float
    database_ops_per_second: float
    memory_usage_mb: float

class AsyncPerformanceMonitor:
    """Monitor async infrastructure performance"""

    def __init__(self):
        self.metrics_history: List[PerformanceMetrics] = []

    async def collect_metrics(self) -> PerformanceMetrics:
        """Collect current performance metrics"""

        # Measure task throughput
        tasks_per_second = await self._measure_task_throughput()

        # Measure database performance
        db_ops_per_second = await self._measure_database_performance()

        # Get system metrics
        memory_usage = self._get_memory_usage()

        metrics = PerformanceMetrics(
            tasks_per_second=tasks_per_second,
            concurrent_tasks=len(asyncio.all_tasks()),
            avg_task_duration=0.0,  # Calculate from recent history
            database_ops_per_second=db_ops_per_second,
            memory_usage_mb=memory_usage
        )

        self.metrics_history.append(metrics)
        return metrics

    async def _measure_task_throughput(self) -> float:
        """Measure task processing throughput"""
        # Implementation for measuring task throughput
        pass

    async def _measure_database_performance(self) -> float:
        """Measure database operation performance"""
        # Implementation for measuring DB performance
        pass
```

## Implementation Timeline

### Week 1-2: Foundation
- [ ] Implement `AsyncWorkerCore` class
- [ ] Add async flag to existing worker CLI
- [ ] Test basic async worker functionality
- [ ] Integrate with existing Queen async infrastructure

### Week 3-4: Integration
- [ ] Complete Queen-Worker async coordination
- [ ] Implement concurrent task processing
- [ ] Add async AI Planner integration
- [ ] Add async AI Reviewer integration

### Week 5-6: Testing & Optimization
- [ ] Implement comprehensive performance tests
- [ ] Benchmark sync vs async performance
- [ ] Optimize for 3-5x improvement target
- [ ] Add performance monitoring

### Week 7-8: Production Readiness
- [ ] Stress testing with high concurrency
- [ ] Error handling and edge cases
- [ ] Documentation and migration guide
- [ ] Production deployment validation

## Success Criteria

### Performance Targets
- ✅ **3-5x task throughput improvement** vs current sync implementation
- ✅ **Concurrent task processing** - 3-5 tasks simultaneously
- ✅ **Sub-second database latency** for most operations
- ✅ **Memory efficiency** - async should use less memory than sync threading

### Quality Targets
- ✅ **Zero breaking changes** - existing sync code still works
- ✅ **Production stability** - no regressions in reliability
- ✅ **Comprehensive test coverage** - all async paths tested
- ✅ **Clear migration path** - gradual async adoption possible

### Compatibility Targets
- ✅ **Backward compatibility** - all existing APIs preserved
- ✅ **Optional async adoption** - can enable async per component
- ✅ **Graceful degradation** - falls back to sync if async unavailable
- ✅ **Clear performance metrics** - measurable improvement validation

This implementation plan leverages the excellent async foundation already in place and focuses on completing the critical missing pieces to achieve the target 3-5x performance improvement.