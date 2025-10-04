# PROJECT SIGNAL: Phase 4.2+4.3 - AI Planner + AI Deployer Instrumentation Plan

**Status**: 🔄 IN PROGRESS
**Date**: 2025-10-05
**Phase**: 4.2+4.3 - Combined AI Apps Instrumentation
**Project**: Hive Performance Instrumentation

---

## Executive Summary

Combining Phase 4.2 and 4.3 into a single instrumentation effort due to smaller-than-expected app sizes:
- **ai-planner**: 12 Python files (~8-10 functions to instrument)
- **ai-deployer**: 17 Python files (~12-15 functions to instrument)
- **Combined Estimated**: ~20-25 total functions

This approach maximizes efficiency by instrumenting both AI completion apps (planning + deployment) in a single phase.

---

## AI Planner Instrumentation (Phase 4.2)

### Architecture Overview
- **Purpose**: Intelligent task planning and workflow generation
- **Files**: 12 Python files
- **Key Components**:
  - `agent.py` - Synchronous AIPlanner agent
  - `async_agent.py` - AsyncAIPlanner with V4.2 optimizations
  - `claude_bridge.py` - RobustClaudePlannerBridge for intelligent planning

### Target Functions (8-10 functions)

#### P0 Critical: Claude Planning (2 functions)
**Business Impact**: Primary bottleneck - Claude planning latency affects overall planning throughput

1. **RobustClaudePlannerBridge.generate_execution_plan()**
   - File: `apps/ai-planner/src/ai_planner/claude_bridge.py:362`
   - Decorator: `@track_adapter_request("claude_planning")`
   - Metrics: `adapter.claude_planning.{duration,calls,errors}`
   - Tracks: Claude API latency for intelligent plan generation

2. **AsyncClaudeService.generate_execution_plan_async()**
   - File: `apps/ai-planner/src/ai_planner/async_agent.py:54`
   - Decorator: `@track_adapter_request("async_claude_planning")`
   - Metrics: `adapter.async_claude_planning.{duration,calls,errors}`
   - Tracks: Async Claude planning performance

#### P0 Critical: Database Operations (2 functions)
**Business Impact**: Queue polling and plan persistence latency

3. **AIPlanner.get_next_task()**
   - File: `apps/ai-planner/src/ai_planner/agent.py:249`
   - Decorator: `@track_adapter_request("database_planning_queue_poll")`
   - Metrics: `adapter.database_planning_queue_poll.{duration,calls,errors}`
   - Tracks: Planning queue polling latency

4. **AIPlanner.save_execution_plan()**
   - File: `apps/ai-planner/src/ai_planner/agent.py:555`
   - Decorator: `@track_adapter_request("database_save_plan")`
   - Metrics: `adapter.database_save_plan.{duration,calls,errors}`
   - Tracks: Plan persistence duration

#### P1 High: Agent Orchestration (3 functions)
**Business Impact**: Agent loop efficiency - orchestration overhead

5. **AIPlanner.run()**
   - File: `apps/ai-planner/src/ai_planner/agent.py:775`
   - Decorator: `@track_request("planner_agent_loop", labels={"component": "ai_planner"})`
   - Metrics: `planner_agent_loop.{duration,calls}`
   - Tracks: Main planning loop performance

6. **AIPlanner.process_task()**
   - File: `apps/ai-planner/src/ai_planner/agent.py:699`
   - Decorator: `@track_request("planning_process_task", labels={"component": "ai_planner"})`
   - Metrics: `planning_process_task.{duration,calls}`
   - Tracks: Single task planning duration (end-to-end)

7. **AsyncAIPlanner.generate_plan_async()**
   - File: `apps/ai-planner/src/ai_planner/async_agent.py:516`
   - Decorator: `@track_request("async_plan_generation", labels={"component": "async_ai_planner"})`
   - Metrics: `async_plan_generation.{duration,calls}`
   - Tracks: Async plan generation performance

#### P1 High: Async Operations (2-3 functions)
**Business Impact**: V4.2 async performance improvement validation

8. **AsyncAIPlanner.run_forever_async()**
   - File: `apps/ai-planner/src/ai_planner/async_agent.py:686`
   - Decorator: `@track_request("async_planner_loop", labels={"component": "async_ai_planner"})`
   - Metrics: `async_planner_loop.{duration,calls}`
   - Tracks: Async main loop performance

9. **AsyncAIPlanner.process_planning_queue_async()**
   - File: `apps/ai-planner/src/ai_planner/async_agent.py:648`
   - Decorator: `@track_request("async_process_queue", labels={"component": "async_ai_planner"})`
   - Metrics: `async_process_queue.{duration,calls}`
   - Tracks: Async queue processing with concurrency

---

## AI Deployer Instrumentation (Phase 4.3)

### Architecture Overview
- **Purpose**: Autonomous deployment of approved applications
- **Files**: 17 Python files
- **Key Components**:
  - `agent.py` - Main deployment agent daemon
  - `deployer.py` - Deployment orchestration
  - `database_adapter.py` - Database operations
  - `strategies/` - Deployment strategy implementations (SSH, Docker, Kubernetes)

### Target Functions (12-15 functions)

#### P0 Critical: Deployment Execution (3 functions)
**Business Impact**: Primary bottleneck - deployment execution time affects delivery speed

10. **DeploymentOrchestrator.execute_deployment()**
    - File: `apps/ai-deployer/src/ai_deployer/deployer.py` (estimate)
    - Decorator: `@track_request("deployment_execution", labels={"component": "deployer"})`
    - Metrics: `deployment_execution.{duration,calls}`
    - Tracks: End-to-end deployment duration

11. **SSHStrategy.deploy()**
    - File: `apps/ai-deployer/src/ai_deployer/strategies/ssh.py` (estimate)
    - Decorator: `@track_request("ssh_deployment", labels={"strategy": "ssh"})`
    - Metrics: `ssh_deployment.{duration,calls}`
    - Tracks: SSH deployment performance

12. **DockerStrategy.deploy()**
    - File: `apps/ai-deployer/src/ai_deployer/strategies/docker.py` (estimate)
    - Decorator: `@track_request("docker_deployment", labels={"strategy": "docker"})`
    - Metrics: `docker_deployment.{duration,calls}`
    - Tracks: Docker deployment duration

#### P0 Critical: Health Checks (2 functions)
**Business Impact**: Deployment validation - health check latency affects total deployment time

13. **DeploymentOrchestrator.verify_deployment_health()**
    - File: `apps/ai-deployer/src/ai_deployer/deployer.py` (estimate)
    - Decorator: `@track_request("deployment_health_check", labels={"component": "deployer"})`
    - Metrics: `deployment_health_check.{duration,calls}`
    - Tracks: Health verification duration

14. **DeploymentOrchestrator.rollback_deployment()**
    - File: `apps/ai-deployer/src/ai_deployer/deployer.py` (estimate)
    - Decorator: `@track_request("deployment_rollback", labels={"component": "deployer"})`
    - Metrics: `deployment_rollback.{duration,calls}`
    - Tracks: Rollback execution time

#### P1 High: Agent Orchestration (3 functions)
**Business Impact**: Agent efficiency - deployment queue processing overhead

15. **DeploymentAgent.run()**
    - File: `apps/ai-deployer/src/ai_deployer/agent.py` (estimate)
    - Decorator: `@track_request("deployer_agent_loop", labels={"component": "deployment_agent"})`
    - Metrics: `deployer_agent_loop.{duration,calls}`
    - Tracks: Main deployment loop performance

16. **DeploymentAgent.process_deployment_queue()**
    - File: `apps/ai-deployer/src/ai_deployer/agent.py` (estimate)
    - Decorator: `@track_request("process_deployment_queue", labels={"component": "deployment_agent"})`
    - Metrics: `process_deployment_queue.{duration,calls}`
    - Tracks: Queue processing cycle latency

17. **DeploymentAgent.handle_deployment_task()**
    - File: `apps/ai-deployer/src/ai_deployer/agent.py` (estimate)
    - Decorator: `@track_request("handle_deployment_task", labels={"component": "deployment_agent"})`
    - Metrics: `handle_deployment_task.{duration,calls}`
    - Tracks: Single deployment task handling

#### P1 High: Database Operations (3 functions)
**Business Impact**: Database overhead - polling and persistence latency

18. **DatabaseAdapter.get_pending_deployments()**
    - File: `apps/ai-deployer/src/ai_deployer/database_adapter.py` (estimate)
    - Decorator: `@track_adapter_request("database_deployment_queue_poll")`
    - Metrics: `adapter.database_deployment_queue_poll.{duration,calls,errors}`
    - Tracks: Deployment queue polling latency

19. **DatabaseAdapter.update_deployment_status()**
    - File: `apps/ai-deployer/src/ai_deployer/database_adapter.py` (estimate)
    - Decorator: `@track_adapter_request("database_update_deployment")`
    - Metrics: `adapter.database_update_deployment.{duration,calls,errors}`
    - Tracks: Deployment status update duration

20. **DatabaseAdapter.store_deployment_result()**
    - File: `apps/ai-deployer/src/ai_deployer/database_adapter.py` (estimate)
    - Decorator: `@track_adapter_request("database_store_deployment")`
    - Metrics: `adapter.database_store_deployment.{duration,calls,errors}`
    - Tracks: Deployment result persistence time

#### P2 Medium: Strategy-Specific (2-3 functions)
**Optional**: Instrument if time permits

21. **KubernetesStrategy.deploy()** (Optional)
22. **DockerStrategy.build_image()** (Optional)
23. **SSHStrategy.validate_connection()** (Optional)

---

## Dashboard Design

### Row 1: P0 Critical - Claude Planning Performance
**Panels**: 4 panels
```promql
# Claude planning latency (P95)
histogram_quantile(0.95, adapter_claude_planning_duration_seconds_bucket)

# Async Claude speedup
histogram_quantile(0.95, adapter_async_claude_planning_duration_seconds_bucket) /
histogram_quantile(0.95, adapter_claude_planning_duration_seconds_bucket)

# Planning error rate
rate(adapter_claude_planning_errors_total[5m])

# Planning throughput
rate(adapter_claude_planning_calls_total{status="success"}[5m])
```

### Row 2: P0 Critical - Deployment Execution
**Panels**: 4 panels
```promql
# Deployment duration by strategy
histogram_quantile(0.95, deployment_execution_duration_seconds_bucket) by (strategy)

# Deployment success rate
rate(deployment_execution_calls_total{status="success"}[5m]) /
rate(deployment_execution_calls_total[5m])

# Health check latency
histogram_quantile(0.95, deployment_health_check_duration_seconds_bucket)

# Rollback frequency
rate(deployment_rollback_calls_total[5m])
```

### Row 3: P1 High - Agent Orchestration
**Panels**: 4 panels
```promql
# Planner loop latency
histogram_quantile(0.95, planner_agent_loop_duration_seconds_bucket)

# Deployer loop latency
histogram_quantile(0.95, deployer_agent_loop_duration_seconds_bucket)

# Queue processing rate
rate(planning_process_task_calls_total[5m])
rate(process_deployment_queue_calls_total[5m])

# End-to-end latency
histogram_quantile(0.95, planning_process_task_duration_seconds_bucket)
histogram_quantile(0.95, handle_deployment_task_duration_seconds_bucket)
```

### Row 4: P1 High - Database Performance
**Panels**: 4 panels
```promql
# Database latency by operation
histogram_quantile(0.95, adapter_database_planning_queue_poll_duration_seconds_bucket)
histogram_quantile(0.95, adapter_database_deployment_queue_poll_duration_seconds_bucket)

# Database write latency
histogram_quantile(0.95, adapter_database_save_plan_duration_seconds_bucket)
histogram_quantile(0.95, adapter_database_store_deployment_duration_seconds_bucket)

# Database error rate
rate(adapter_database_planning_queue_poll_errors_total[5m])
rate(adapter_database_deployment_queue_poll_errors_total[5m])

# Database throughput
rate(adapter_database_save_plan_calls_total[5m])
rate(adapter_database_update_deployment_calls_total[5m])
```

### Row 5: Async Performance Validation
**Panels**: 4 panels
```promql
# Async speedup factor
histogram_quantile(0.95, async_plan_generation_duration_seconds_bucket) /
histogram_quantile(0.95, planning_process_task_duration_seconds_bucket)

# Concurrent planning peak
max_over_time(async_planner_concurrent_plans[5m])

# Async queue processing rate
rate(async_process_queue_calls_total[5m])

# Async error rate
rate(async_plan_generation_errors_total[5m])
```

---

## Implementation Strategy

### Phase 1: AI Planner (Estimated: 1 session)
1. Instrument RobustClaudePlannerBridge.generate_execution_plan()
2. Instrument AsyncClaudeService.generate_execution_plan_async()
3. Instrument AIPlanner database operations (2 functions)
4. Instrument AIPlanner orchestration (3 functions)
5. Instrument AsyncAIPlanner (3 functions)
6. Validate syntax and imports
7. Run subset of tests

### Phase 2: AI Deployer (Estimated: 1-2 sessions)
1. Read deployer.py and identify key functions
2. Instrument deployment execution (3 functions)
3. Instrument health checks (2 functions)
4. Instrument agent orchestration (3 functions)
5. Instrument database operations (3 functions)
6. Validate syntax and imports
7. Run subset of tests

### Phase 3: Validation & Documentation
1. Golden Rules validation
2. Combined test run
3. Create completion report with dashboard designs
4. Commit with comprehensive message

---

## Success Criteria

1. **Coverage**: ≥20 functions instrumented across both apps
2. **Critical Path**: 100% P0 critical functions instrumented
3. **Non-Invasive**: All decorators applied, no logic changes
4. **Validation**: All syntax checks passed, imports verified
5. **Performance**: Expected overhead <10% (from Phase 2 testing)
6. **Compliance**: Golden Rules validation passed
7. **Documentation**: Complete plan and completion reports

---

## Estimated Timeline

- **AI Planner**: 1 session (~8-10 functions)
- **AI Deployer**: 1-2 sessions (~12-15 functions)
- **Validation & Documentation**: Included in implementation
- **Total**: 2-3 sessions for complete Phase 4.2+4.3

---

## Dependencies

- **Requires**: Phase 4.1 completion (ai-reviewer instrumentation)
- **Enables**: Phase 4.4 (Unified AI Apps Dashboard)
- **Follows**: Phase 3 instrumentation pattern (hive-orchestrator)

---

**Generated**: 2025-10-05
**Author**: Claude Code (Master Agent)
**Phase**: Project Signal - Hive Performance Instrumentation
**Status**: 🔄 IN PROGRESS
