# Project Signal: Phase 4.1 - AI Reviewer Instrumentation Plan

**Date**: 2025-10-05
**Status**: Planning
**Target Functions**: 12 (following Phase 3 pattern)

## Executive Summary

Instrument ai-reviewer app with hive-performance decorators to achieve comprehensive observability of the autonomous code review and auto-fix pipeline.

### Target Coverage

**P0 Critical: Claude AI Execution** (2 functions)
- RobustClaudeBridge.review_code() - Primary LLM review call
- (Future) AsyncReviewEngine.review_async() - Async review path

**P0 Critical: Auto-Fix Pipeline** (3 functions)
- FixGenerator.generate_fix() - Fix generation
- FixGenerator.batch_generate_fixes() - Batch fix generation
- ErrorAnalyzer.analyze_errors() - Error analysis

**P1 High: Agent Orchestration** (4 functions)
- ReviewAgent.run() - Main agent loop
- ReviewAgent.process_task() - Task processing
- ReviewAgent._execute_fix_retry_loop() - Fix-retry orchestration
- ReviewAgent._apply_fixes() - Fix application

**P1 High: Database Operations** (3 functions)
- DatabaseAdapter.get_pending_reviews() - Queue polling
- DatabaseAdapter.update_review_result() - Result persistence
- DatabaseAdapter.record_fix_attempt() - Fix tracking

---

## Critical Path Analysis

### 1. Claude AI Execution (PRIMARY BOTTLENECK)

#### RobustClaudeBridge.review_code()
**File**: `apps/ai-reviewer/src/ai_reviewer/robust_claude_bridge.py:91`

**Current Implementation**:
```python
def review_code(
    self,
    task_id: str,
    task_description: str,
    code_files: dict[str, str],
    test_results: dict[str, Any] | None = None,
    objective_analysis: dict[str, Any] | None = None,
    transcript: str | None = None,
) -> dict[str, Any]:
```

**Instrumentation**:
```python
@track_adapter_request("claude_code_review")
def review_code(
    self,
    task_id: str,
    task_description: str,
    code_files: dict[str, str],
    test_results: dict[str, Any] | None = None,
    objective_analysis: dict[str, Any] | None = None,
    transcript: str | None = None,
) -> dict[str, Any]:
```

**Metrics Generated**:
- `adapter.claude_code_review.duration` - Review execution time (P95, P99)
- `adapter.claude_code_review.calls{status="success|failure|timeout"}` - Review outcomes
- `adapter.claude_code_review.errors{error_type="..."}` - Error classification

**Key Insights**:
- Identify review latency bottlenecks
- Track timeout patterns
- Measure JSON parsing success rate

---

### 2. Auto-Fix Generation (CRITICAL PATH)

#### FixGenerator.generate_fix()
**File**: `apps/ai-reviewer/src/ai_reviewer/auto_fix/fix_generator.py:41`

**Instrumentation**:
```python
@track_request("auto_fix_generate", labels={"component": "fix_generator"})
def generate_fix(self, error: ParsedError, file_content: str, context_lines: int = 5) -> GeneratedFix | None:
```

**Metrics**:
- `auto_fix_generate.duration` - Fix generation time
- `auto_fix_generate.calls{fix_type="import|type|logic"}` - Fix type distribution

#### FixGenerator.batch_generate_fixes()
**File**: `apps/ai-reviewer/src/ai_reviewer/auto_fix/fix_generator.py:182`

**Instrumentation**:
```python
@track_request("auto_fix_batch", labels={"component": "fix_generator", "batch": "true"})
def batch_generate_fixes(self, errors: list[ParsedError], file_content: str) -> list[GeneratedFix]:
```

**Metrics**:
- `auto_fix_batch.duration` - Batch processing time
- `auto_fix_batch.calls{batch_size_bucket="1-5|6-10|11+"}` - Batch size analysis

#### ErrorAnalyzer.analyze_errors()
**File**: `apps/ai-reviewer/src/ai_reviewer/auto_fix/error_analyzer.py:~50`

**Instrumentation**:
```python
@track_request("error_analysis", labels={"component": "error_analyzer"})
def analyze_errors(self, validation_output: str) -> list[ParsedError]:
```

**Metrics**:
- `error_analysis.duration` - Analysis time
- `error_analysis.calls{tool="ruff|pytest|mypy"}` - Tool distribution

---

### 3. Agent Orchestration (HIGH PRIORITY)

#### ReviewAgent.run()
**File**: `apps/ai-reviewer/src/ai_reviewer/agent.py:~150`

**Instrumentation**:
```python
@track_request("review_agent_cycle", labels={"component": "review_agent", "mode": "autonomous"})
async def run(self) -> None:
```

**Metrics**:
- `review_agent_cycle.duration` - Full agent cycle time
- `review_agent_cycle.calls` - Cycle count

#### ReviewAgent.process_task()
**File**: `apps/ai-reviewer/src/ai_reviewer/agent.py:~200`

**Instrumentation**:
```python
@track_request("review_process_task", labels={"component": "review_agent"})
async def process_task(self, task: dict[str, Any]) -> None:
```

**Metrics**:
- `review_process_task.duration` - Task processing time
- `review_process_task.calls{decision="approve|reject|rework|escalate"}` - Decision distribution

#### ReviewAgent._execute_fix_retry_loop()
**File**: `apps/ai-reviewer/src/ai_reviewer/agent.py:~300`

**Instrumentation**:
```python
@track_request("review_fix_retry_loop", labels={"component": "review_agent", "auto_fix": "enabled"})
async def _execute_fix_retry_loop(self, task: dict[str, Any], review_result: dict[str, Any]) -> bool:
```

**Metrics**:
- `review_fix_retry_loop.duration` - Fix-retry loop time
- `review_fix_retry_loop.calls{outcome="fixed|escalated"}` - Loop outcomes

#### ReviewAgent._apply_fixes()
**File**: `apps/ai-reviewer/src/ai_reviewer/agent.py:~400`

**Instrumentation**:
```python
@track_request("review_apply_fixes", labels={"component": "review_agent"})
async def _apply_fixes(self, task_id: str, fixes: list[GeneratedFix]) -> bool:
```

**Metrics**:
- `review_apply_fixes.duration` - Fix application time
- `review_apply_fixes.calls{success="true|false"}` - Application success rate

---

### 4. Database Operations (PERSISTENCE)

#### DatabaseAdapter.get_pending_reviews()
**File**: `apps/ai-reviewer/src/ai_reviewer/database_adapter.py:~50`

**Instrumentation**:
```python
@track_adapter_request("sqlite")
def get_pending_reviews(self, limit: int = 10) -> list[dict[str, Any]]:
```

**Metrics**:
- `adapter.sqlite.duration{operation="get_pending"}` - Queue query time
- `adapter.sqlite.calls{operation="get_pending"}` - Query frequency

#### DatabaseAdapter.update_review_result()
**File**: `apps/ai-reviewer/src/ai_reviewer/database_adapter.py:~100`

**Instrumentation**:
```python
@track_adapter_request("sqlite")
def update_review_result(self, task_id: str, result: dict[str, Any]) -> bool:
```

**Metrics**:
- `adapter.sqlite.duration{operation="update_result"}` - Update latency
- `adapter.sqlite.calls{operation="update_result"}` - Update frequency

#### DatabaseAdapter.record_fix_attempt()
**File**: `apps/ai-reviewer/src/ai_reviewer/database_adapter.py:~150`

**Instrumentation**:
```python
@track_adapter_request("sqlite")
def record_fix_attempt(self, task_id: str, fix_data: dict[str, Any]) -> bool:
```

**Metrics**:
- `adapter.sqlite.duration{operation="record_fix"}` - Record time
- `adapter.sqlite.calls{operation="record_fix"}` - Fix tracking frequency

---

## Metrics Dashboard Design

### Dashboard: AI Reviewer Observability

**Row 1: Executive Summary**
- Review throughput (reviews/hour)
- Auto-fix success rate (%)
- Average review time (seconds)
- Current queue depth

**Row 2: Claude Review Performance** (CRITICAL)
- Claude execution time (P50, P95, P99)
- Review outcomes (approve/reject/rework/escalate) - Pie chart
- Timeout rate (%) - Gauge with alert
- JSON parsing success rate (%)

**Row 3: Auto-Fix Pipeline**
- Fix generation time - Histogram
- Fix type distribution (import/type/logic) - Stacked bar
- Batch efficiency (time per fix) - Line graph
- Fix application success rate (%)

**Row 4: Agent Orchestration**
- Agent cycle time - Line graph
- Task processing latency - Histogram
- Fix-retry loop outcomes - Stacked area
- Escalation rate (%)

**Row 5: Database Performance**
- Queue query latency - Line graph
- Result update latency - Line graph
- Database throughput (ops/sec)
- Database error rate (%)

---

## Implementation Steps

### Step 1: Import hive-performance decorators
```python
# Add to each instrumented file
from hive_performance import track_adapter_request, track_request
```

### Step 2: Apply decorators to critical paths
- RobustClaudeBridge.review_code() → `@track_adapter_request("claude_code_review")`
- FixGenerator.generate_fix() → `@track_request("auto_fix_generate")`
- ReviewAgent.run() → `@track_request("review_agent_cycle")`

### Step 3: Validate syntax and imports
```bash
python -m py_compile apps/ai-reviewer/src/ai_reviewer/robust_claude_bridge.py
python -m py_compile apps/ai-reviewer/src/ai_reviewer/auto_fix/fix_generator.py
python -m py_compile apps/ai-reviewer/src/ai_reviewer/agent.py
python -m py_compile apps/ai-reviewer/src/ai_reviewer/database_adapter.py
```

### Step 4: Run tests to verify non-breaking
```bash
python -m pytest apps/ai-reviewer/tests/ -v
```

### Step 5: Generate validation report
Create `PROJECT_SIGNAL_PHASE_4_1_COMPLETE.md` with:
- Functions instrumented (12 total)
- Metrics generated
- Validation results
- Dashboard design

---

## Success Criteria

### Instrumentation Coverage
- ✅ Claude AI: 100% (primary review path)
- ✅ Auto-Fix: 100% (generation + application)
- ✅ Orchestration: 80% (main loops + processing)
- ✅ Database: 75% (core CRUD operations)

### Technical Validation
- ✅ All syntax checks pass
- ✅ All imports resolve
- ✅ Tests pass without modification
- ✅ Zero breaking changes

### Metrics Quality
- ✅ Cardinality < 100 series
- ✅ Labels enable aggregation
- ✅ Decorator overhead < 10%

---

## Next Steps After Phase 4.1

**Phase 4.2**: Instrument ai-planner
**Phase 4.3**: Instrument ai-deployer
**Phase 4.4**: Create unified dashboard for all AI apps
**Phase 4.5**: Golden Rule 35 enforcement

---

**Estimated Completion**: 2-3 hours
**Risk Level**: Low (following proven Phase 3 pattern)
**Dependencies**: hive-performance v1.0 (stable)
