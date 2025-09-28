# AI Planner → Queen → Worker Integration Pipeline

## Overview

This document describes the complete integration pipeline that enables autonomous task execution in the Hive system. The pipeline connects AI Planner (task planning), Queen (task orchestration), and Workers (task execution) into a seamless autonomous workflow.

## Architecture

```
Planning Queue → AI Planner → Execution Plans → Queen → Workers → Completion
     ↓              ↓              ↓           ↓        ↓         ↓
  📝 Tasks      🤖 Planning    📋 Subtasks   👑 Assign  ⚙️ Execute  ✅ Results
```

### Components

1. **AI Planner** (`apps/ai-planner/`)
   - Monitors `planning_queue` table for new tasks
   - Generates structured execution plans with subtasks
   - Creates executable subtasks in `tasks` table
   - Provides intelligent task decomposition

2. **Queen** (`apps/hive-orchestrator/`)
   - Enhanced task pickup with `get_queued_tasks_with_planning()`
   - Processes both regular tasks and planned subtasks
   - Manages dependency resolution and parallel execution
   - Synchronizes status back to execution plans

3. **Workers** (`apps/hive-orchestrator/worker.py`)
   - Execute individual tasks and subtasks
   - Report status through database updates
   - Handle both regular and planned task types

4. **Planning Integration** (`core/db/planning_integration.py`)
   - Bridges AI Planner output with Queen execution
   - Provides dependency resolution and status sync
   - Manages execution plan lifecycle

## Database Schema

### Core Tables

```sql
-- Input queue for AI Planner
planning_queue (
    id, task_description, priority, status,
    requestor, context_data, assigned_agent, created_at
)

-- AI Planner output
execution_plans (
    id, planning_task_id, plan_data, status,
    estimated_complexity, estimated_duration
)

-- Executable tasks (regular + planned subtasks)
tasks (
    id, title, task_type, status, assignee,
    payload, created_at, priority
)

-- Worker execution tracking
runs (
    id, task_id, worker_id, phase, status, result
)
```

### Key Relationships

- `execution_plans.planning_task_id` → `planning_queue.id`
- `tasks.payload.parent_plan_id` → `execution_plans.id`
- `runs.task_id` → `tasks.id`

## Integration Flow

### 1. Task Submission
```python
# Submit task to planning queue
task_id = create_planning_task(
    description="Implement authentication system",
    priority=75,
    context={"complexity": "high", "files_affected": 10}
)
```

### 2. AI Planner Processing
```python
# AI Planner picks up task
task = planner.get_next_task()  # Returns task from planning_queue

# Generate execution plan
plan = planner.generate_execution_plan(task)

# Save plan and create subtasks
planner.save_execution_plan(plan)  # Creates subtasks in tasks table
```

### 3. Queen Enhanced Pickup
```python
# Queen gets enhanced task list
tasks = get_queued_tasks_with_planning_optimized(limit=10)
# Returns both regular tasks AND ready planned subtasks

# Process with dependency checking
for task in tasks:
    if task['task_type'] == 'planned_subtask':
        # Verify dependencies are met
        if task.get('dependencies_met', True):
            queen.spawn_worker(task, worker, phase)
```

### 4. Status Synchronization
```python
# Worker completes subtask
worker.complete_task(task_id, status='completed')

# Status syncs back to execution plan
planning_integration.sync_subtask_status_to_plan(task_id, 'completed')

# Plan progress updated automatically
completion = planning_integration.get_plan_completion_status(plan_id)
```

## Enhanced Features

### Dependency Resolution

The integration provides intelligent dependency resolution:

```python
# Subtasks with dependencies only become available when dependencies are met
subtask = {
    "dependencies": ["design_subtask_id"],  # Must complete first
    "workflow_phase": "implementation"
}

# Queen automatically checks dependency satisfaction
ready_subtasks = planning_integration.get_ready_planned_subtasks()
```

### Status Pipeline

Bidirectional status flow ensures consistency:

```
Planning Queue → Execution Plan → Subtasks → Workers
     ↑               ↑              ↑          ↓
   Status         Progress      Individual   Results
  Updates        Tracking       Status
```

### Error Handling

Comprehensive error handling and recovery:

- Stuck task detection and recovery
- Failed subtask retry logic
- Plan execution monitoring
- Automatic status synchronization

## Configuration

### Enhanced Queen Configuration

```python
# Use enhanced Queen with planning integration
from hive_orchestrator.queen_planning_enhanced import QueenPlanningEnhanced

queen = QueenPlanningEnhanced(hive_core, live_output=True)
queen.run_forever_enhanced()  # Enhanced mode with planning integration
```

### Monitoring Configuration

```python
# Enable pipeline monitoring
from hive_orchestrator.core.monitoring.pipeline_monitor import pipeline_monitor

# Get current status
status = pipeline_monitor.collect_metrics()
health, alerts = pipeline_monitor.check_health(status)
```

## Performance Optimizations

### Database Optimizations

1. **Single Query Task Pickup**: Combines regular and planned tasks in one query
2. **Batch Dependency Checking**: Checks multiple dependencies simultaneously
3. **Connection Pooling**: Reduces database connection overhead
4. **Optimized Indexes**: Supports fast task filtering and dependency lookups

### Parallel Processing

1. **Concurrent Subtask Execution**: Multiple subtasks from same plan execute in parallel
2. **Dependency-Aware Scheduling**: Only starts subtasks when dependencies are met
3. **Resource-Aware Assignment**: Respects worker capacity limits

### Async Support (Phase 4.1)

```python
# Async mode for 3-5x performance improvement
queen = QueenPlanningEnhanced(hive_core)
await queen.run_forever_enhanced_async()
```

## Monitoring and Observability

### Pipeline Monitoring

The integration includes comprehensive monitoring:

```python
# Real-time pipeline metrics
metrics = {
    'pending_planning_tasks': 5,
    'executing_plans': 3,
    'completed_subtasks': 42,
    'error_rate_percentage': 2.1,
    'pipeline_throughput_per_hour': 15.3
}

# Health checking with alerts
health_status = monitor.check_health(metrics)
# Returns: HEALTHY, WARNING, or CRITICAL
```

### Event Bus Integration

Cross-component communication via event bus:

```python
# AI Planner publishes plan generation events
event_bus.publish("workflow.plan_generated", {
    "plan_id": plan_id,
    "task_id": task_id,
    "subtask_count": len(subtasks)
})

# Queen subscribes and auto-triggers execution
queen.subscribe("workflow.plan_generated", auto_trigger_execution)
```

## Testing

### Integration Tests

Comprehensive test suite validates the complete pipeline:

```bash
# Run integration tests
pytest tests/test_ai_planner_queen_integration.py -v

# Run end-to-end tests
pytest tests/test_end_to_end_integration.py -v
```

### Test Coverage

- Planning queue → AI Planner handoff
- Execution plan generation and storage
- Queen enhanced task pickup
- Dependency resolution correctness
- Status synchronization accuracy
- Error handling and recovery
- Performance under load

## Usage Examples

### Basic Autonomous Task

```python
# 1. Submit high-level task
task_id = create_planning_task(
    "Create REST API for user management",
    priority=60,
    context={"api_endpoints": 5, "auth_required": True}
)

# 2. AI Planner automatically processes and creates plan

# 3. Queen automatically picks up and executes subtasks

# 4. Monitor progress
completion = get_plan_completion_status(plan_id)
print(f"Progress: {completion['completion_percentage']}%")
```

### Complex Multi-Phase Project

```python
# Submit complex project
project_task_id = create_planning_task(
    "Implement complete e-commerce checkout system",
    priority=90,
    context={
        "components": ["payment", "inventory", "shipping", "notifications"],
        "complexity": "high",
        "estimated_duration_hours": 40
    }
)

# AI Planner creates multi-phase execution plan:
# Phase 1: Design and architecture
# Phase 2: Backend implementation
# Phase 3: Frontend integration
# Phase 4: Testing and deployment

# Queen executes phases in dependency order
# Workers handle individual subtasks within each phase
```

### Status Monitoring

```python
# Get comprehensive pipeline status
status = get_pipeline_status()

print(f"Health: {status['health']}")
print(f"Active Plans: {status['metrics']['executing_plans']}")
print(f"Completion Rate: {status['metrics']['avg_plan_completion_percentage']}%")

# Check for alerts
if status['alerts']:
    for alert in status['alerts']:
        print(f"⚠️ {alert['message']}")
```

## Troubleshooting

### Common Issues

1. **Subtasks Not Picked Up**
   - Check execution plan status is 'generated' or 'executing'
   - Verify dependencies are satisfied
   - Check Queen is using enhanced task pickup

2. **Status Not Syncing**
   - Verify `planning_integration` is properly initialized
   - Check database foreign key relationships
   - Ensure event bus is functioning

3. **Performance Issues**
   - Enable connection pooling
   - Use async mode for high throughput
   - Monitor and tune database indexes

### Debug Commands

```python
# Check planning queue status
cursor.execute("SELECT status, COUNT(*) FROM planning_queue GROUP BY status")

# Check execution plan details
plan_status = planning_integration.get_plan_completion_status(plan_id)

# Verify task dependencies
ready_tasks = planning_integration.get_ready_planned_subtasks(limit=100)
```

## Future Enhancements

### Planned Improvements

1. **AI-Powered Plan Optimization**
   - Dynamic resource allocation
   - Intelligent dependency optimization
   - Adaptive retry strategies

2. **Advanced Monitoring**
   - Predictive failure detection
   - Performance trend analysis
   - Automated capacity scaling

3. **Enhanced Error Recovery**
   - Automatic plan rebalancing
   - Intelligent task redistribution
   - Self-healing capabilities

### Extension Points

The integration is designed for extensibility:

- Custom planning strategies
- Pluggable dependency resolvers
- Advanced monitoring hooks
- Custom worker specializations

## API Reference

### Core Functions

```python
# Planning Integration
planning_integration.get_ready_planned_subtasks(limit=20)
planning_integration.sync_subtask_status_to_plan(task_id, status)
planning_integration.trigger_plan_execution(plan_id)

# Enhanced Database Functions
get_queued_tasks_with_planning_optimized(limit=10, task_type=None)
check_subtask_dependencies_batch(task_ids)
create_planned_subtasks_optimized(plan_id)

# Monitoring Functions
pipeline_monitor.collect_metrics()
pipeline_monitor.check_health(metrics)
get_pipeline_status()
```

### Configuration Options

```python
# Planning Integration Config
PlanningIntegration(use_pool=True)

# Pipeline Monitor Config
PipelineMonitor(alert_thresholds={
    "stuck_task_minutes": 30,
    "error_rate_percentage": 10.0,
    "low_throughput_per_hour": 1.0
})

# Enhanced Queen Config
QueenPlanningEnhanced(hive_core, live_output=False)
```

This integration provides a robust, scalable foundation for autonomous task execution in the Hive system. The combination of intelligent planning, reliable orchestration, and comprehensive monitoring ensures high-quality autonomous operation.