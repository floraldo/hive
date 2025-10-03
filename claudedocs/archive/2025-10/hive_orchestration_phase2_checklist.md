# Hive Orchestration Phase 2 - Implementation Wiring Checklist

**Status**: Ready to Begin
**Goal**: Wire operation interfaces to actual database implementations
**Estimated Time**: 2-3 hours

---

## Prerequisites ✅ Complete

- [x] Package structure created
- [x] All 18 operation interfaces defined
- [x] All 9 Pydantic models implemented
- [x] Client SDK created
- [x] Documentation complete
- [x] Architecture docs updated

---

## Phase 2 Tasks

### Step 1: Database Operations Setup

**1.1 Copy Database Schema** (15 min)
- [ ] Copy `init_db()` from hive-orchestrator/core/db/database.py
- [ ] Adapt to use hive_db package
- [ ] Create `src/hive_orchestration/database/__init__.py`
- [ ] Create `src/hive_orchestration/database/schema.py`

**1.2 Connection Management** (10 min)
- [ ] Copy connection pool logic
- [ ] Adapt `get_connection()` context manager
- [ ] Copy `transaction()` context manager
- [ ] Test basic connection

### Step 2: Task Operations Implementation

**2.1 Core Task Operations** (30 min)
- [ ] Implement `create_task()` in operations/tasks.py
  - Copy logic from database.py:275-328
  - Adapt to use package database
  - Test creation
- [ ] Implement `get_task()`
  - Copy logic from database.py:329-344
  - Test retrieval
- [ ] Implement `update_task_status()`
  - Copy logic from database.py:389-462
  - Test status updates
- [ ] Implement `get_tasks_by_status()`
  - Copy logic from database.py:594-627
  - Test querying
- [ ] Implement `get_queued_tasks()`
  - Copy logic from database.py:345-388
  - Test queue retrieval

**2.2 Task Operation Tests** (20 min)
- [ ] Write test_create_task()
- [ ] Write test_get_task()
- [ ] Write test_update_task_status()
- [ ] Write test_task_lifecycle()
- [ ] All tests passing

### Step 3: Worker Operations Implementation

**3.1 Worker Operations** (20 min)
- [ ] Implement `register_worker()`
  - Copy logic from database.py:628-652
- [ ] Implement `update_worker_heartbeat()`
  - Copy logic from database.py:653-677
- [ ] Implement `get_active_workers()`
  - Copy logic from database.py:678-702
- [ ] Implement `get_worker()`
  - New implementation (similar to get_task)

**3.2 Worker Operation Tests** (15 min)
- [ ] Write test_register_worker()
- [ ] Write test_worker_heartbeat()
- [ ] Write test_get_active_workers()
- [ ] All tests passing

### Step 4: Execution Plan Operations

**4.1 Plan Operations** (25 min)
- [ ] Implement `create_planned_subtasks_from_plan()`
  - Copy logic from database_enhanced.py:278-329
- [ ] Implement `get_execution_plan_status()`
  - Copy logic from database_enhanced.py:176-193
- [ ] Implement `check_subtask_dependencies()`
  - Copy logic from database_enhanced.py:130-175
- [ ] Implement `get_next_planned_subtask()`
  - Copy logic from database_enhanced.py:223-277
- [ ] Implement `mark_plan_execution_started()`
  - Copy logic from database_enhanced.py:194-222

**4.2 Optimized Plan Operations** (15 min)
- [ ] Implement `check_subtask_dependencies_batch()`
  - Copy from database_enhanced_optimized.py:189-260
- [ ] Implement `get_execution_plan_status_cached()`
  - Copy from database_enhanced_optimized.py:262-291

**4.3 Plan Operation Tests** (20 min)
- [ ] Write test_create_subtasks_from_plan()
- [ ] Write test_plan_status()
- [ ] Write test_dependency_checking()
- [ ] Write test_next_subtask()
- [ ] All tests passing

### Step 5: Integration Testing

**5.1 End-to-End Tests** (30 min)
- [ ] Write test_full_task_workflow()
  - Create task → assign worker → execute → complete
- [ ] Write test_execution_plan_workflow()
  - Create plan → create subtasks → execute in order
- [ ] Write test_worker_coordination()
  - Multiple workers → task assignment → completion
- [ ] Write test_client_sdk()
  - Test high-level client operations

**5.2 Database Integration** (15 min)
- [ ] Test with SQLite database
- [ ] Test connection pooling
- [ ] Test transaction handling
- [ ] Test error recovery

### Step 6: Documentation Updates

**6.1 Update Package Docs** (15 min)
- [ ] Update README with actual usage examples
- [ ] Add implementation notes
- [ ] Document database schema
- [ ] Add troubleshooting guide

**6.2 Update Migration Guide** (10 min)
- [ ] Add "Implementation Complete" status
- [ ] Update timeline
- [ ] Add testing instructions

---

## Implementation Notes

### Source Files to Copy From

**Primary Sources**:
```
apps/hive-orchestrator/src/hive_orchestrator/core/db/
├── database.py                    # Main database operations
├── database_enhanced.py           # AI planner integration
├── database_enhanced_optimized.py # Optimized operations
└── connection_pool.py             # Connection management
```

**Adaptation Strategy**:
1. Copy function logic
2. Replace `from .connection_pool import get_pooled_connection` with `from hive_db import get_sqlite_connection`
3. Replace `from hive_logging import get_logger` (already correct)
4. Keep function signatures identical (100% API compatibility)
5. Add type hints where missing
6. Add comprehensive docstrings

### Key Adaptation Points

**Database Connection**:
```python
# OLD (orchestrator)
from .connection_pool import get_pooled_connection

with get_pooled_connection() as conn:
    # ...

# NEW (package)
from hive_db import get_sqlite_connection
from hive_config import create_config_from_sources

config = create_config_from_sources()
db_path = config.orchestration.database_path  # New config key

with get_sqlite_connection(db_path) as conn:
    # ...
```

**Transaction Handling**:
```python
# Use hive_db transaction utilities
from hive_db import sqlite_transaction

with sqlite_transaction(conn) as cursor:
    # transactional operations
```

### Testing Strategy

**Test Layers**:
1. **Unit Tests**: Test individual operations in isolation
2. **Integration Tests**: Test operation combinations
3. **Client SDK Tests**: Test high-level interface
4. **Migration Tests**: Verify compatibility with orchestrator

**Test Database**:
- Use in-memory SQLite for speed: `:memory:`
- Use temporary file for persistence tests
- Clean up after each test

---

## Success Criteria

### Functional Requirements
- [ ] All 18 operations fully implemented
- [ ] All operations pass unit tests
- [ ] Integration tests pass
- [ ] Client SDK works end-to-end
- [ ] Database schema compatible with orchestrator

### Quality Requirements
- [ ] 100% API compatibility maintained
- [ ] All functions have type hints
- [ ] All functions have docstrings
- [ ] Zero syntax errors
- [ ] Zero import errors

### Performance Requirements
- [ ] Operations complete in <100ms (single task)
- [ ] Batch operations 60% faster than individual
- [ ] Connection pooling functional
- [ ] No memory leaks

---

## Risk Mitigation

### Risk 1: Database Schema Mismatch
- **Mitigation**: Use identical schema from orchestrator
- **Validation**: Run schema comparison tests
- **Fallback**: Document differences, provide migration

### Risk 2: Missing Dependencies
- **Mitigation**: Thorough dependency analysis before copying
- **Validation**: Test imports after each function
- **Fallback**: Add dependencies to pyproject.toml

### Risk 3: Performance Regression
- **Mitigation**: Profile operations, compare with orchestrator
- **Validation**: Performance benchmarks
- **Fallback**: Optimize critical paths

---

## Estimated Timeline

**Total Time**: 2-3 hours

**Breakdown**:
- Setup (Step 1): 25 min
- Task Operations (Step 2): 50 min
- Worker Operations (Step 3): 35 min
- Plan Operations (Step 4): 60 min
- Integration Testing (Step 5): 45 min
- Documentation (Step 6): 25 min

**Buffer**: 30 min for unexpected issues

---

## Next Steps After Phase 2

**Phase 3: App Migrations**
1. Migrate ai-planner
2. Migrate ai-deployer
3. Verify functionality

**Phase 4: Cleanup**
1. Remove platform app exception
2. Final validation
3. Archive migration docs

---

**Ready to Begin**: All prerequisites complete
**Expected Outcome**: Fully functional hive-orchestration package
**Next Session**: Start with Step 1.1 (Copy Database Schema)

---

*Checklist prepared: 2025-10-02*
*Agent: pkg (Architecture Analysis & Package Design)*
*Status: Ready for implementation*
