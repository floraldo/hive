# Phase 4 Week 1 - Next Steps & Deployment Guide

**Status**: ✅ Code committed, awaiting package reinstall
**Date**: 2025-10-05
**Phase**: A - Infrastructure Complete

---

## Immediate Next Steps

### 1. Reinstall Packages (Required)

The new unified infrastructure requires package reinstallation to be usable:

```bash
# Reinstall hive-bus (now includes unified events)
cd packages/hive-bus
pip install -e .

# Reinstall hive-orchestration (now includes agent framework)
cd ../hive-orchestration
pip install -e .
```

**Why?** Python is currently using the old installed versions from `site-packages`. The new code is in the repository but not yet installed.

---

### 2. Verify Installation

After reinstalling, run verification:

```python
# Test unified infrastructure
from hive_orchestration import (
    AgentRegistry,
    AgentCapability,
    auto_register_adapters
)
from hive_bus import UnifiedEvent, UnifiedEventType, TopicRegistry

# Create and populate registry
registry = AgentRegistry()
auto_register_adapters(registry)

# Should show 5 agents registered
print(registry.get_stats())

# Should show 28 event types
print(f"Event types: {len([e for e in UnifiedEventType])}")
```

**Expected Output**:
```
{'total_agents': 5, 'agent_types': 5, 'capabilities': 5, ...}
Event types: 28
```

---

### 3. Database Migration Status

The Alembic migration has already been applied:

```bash
# Check current migration
cd packages/hive-orchestration
python -m alembic current
# Should show: f97f94fd1a27 (head)

# Verify tables exist
sqlite3 ../../hive/db/hive-internal.db ".tables"
# Should show: unified_tasks, unified_review_tasks,
#              unified_workflow_tasks, unified_deployment_tasks
```

**Status**: ✅ Migration applied, tables created

---

## Phase B Planning (Week 2-4)

### Objective
Enable event emission in existing agents with feature flags.

### Approach
1. **Week 2**: Add event emission to one agent (ai-reviewer) behind feature flag
2. **Week 3**: Monitor and validate event flow
3. **Week 4**: Roll out to remaining agents

### Implementation Plan

#### Step 1: Feature Flag Configuration

Add to `packages/hive-config/src/hive_config/schemas.py`:

```python
@dataclass
class FeatureFlags:
    """Feature flags for gradual rollout."""
    enable_unified_events: bool = False
    enable_dual_write: bool = False
    enable_agent_adapters: bool = False
```

Update config to include flags:

```python
@dataclass
class HiveConfig:
    # ... existing fields ...
    features: FeatureFlags = field(default_factory=FeatureFlags)
```

#### Step 2: Add Event Emission to AI Reviewer

In `apps/ai-reviewer/src/ai_reviewer/core.py`:

```python
from hive_config import create_config_from_sources
from hive_bus import UnifiedEventType, create_task_event

class AIReviewer:
    def __init__(self):
        self.config = create_config_from_sources()
        # ... existing init ...

    async def review_code(self, code_path: str, correlation_id: str):
        # Existing review logic
        result = await self._do_review(code_path)

        # NEW: Emit unified event if enabled
        if self.config.features.enable_unified_events:
            event = create_task_event(
                event_type=UnifiedEventType.REVIEW_COMPLETED,
                task_id=self.current_task_id,
                correlation_id=correlation_id,
                source_agent='ai-reviewer',
                additional_data={'review_score': result.score}
            )
            self.event_bus.emit(event)

        return result
```

#### Step 3: Monitor Event Flow

Create monitoring dashboard:

```python
# scripts/monitoring/event_monitor.py
from hive_bus import get_global_registry, UnifiedEventType

registry = get_global_registry()
registry.register('*', lambda event: print(f"Event: {event.event_type}"))

# Run and watch events flow
```

#### Step 4: Gradual Rollout

1. Enable for ai-reviewer (1 agent)
2. Monitor for 3-7 days
3. Enable for ai-planner, ai-deployer (2 more agents)
4. Monitor for 3-7 days
5. Enable for remaining agents

---

## Phase C Planning (Q2 2025)

### Objective
Begin using unified schema in read paths.

### Key Activities
1. Update orchestrator to read from unified_tasks
2. Enable dual-write for all task operations
3. Validate data consistency
4. Monitor performance impact

---

## Phase D Planning (Q3 2025)

### Objective
Complete migration and deprecate legacy schema.

### Key Activities
1. Switch all reads to unified schema
2. Stop writing to legacy schema
3. Archive legacy data
4. Drop legacy tables
5. Remove dual-write infrastructure

---

## Rollback Procedures

### If Event Emission Causes Issues

```python
# Disable in config
config.features.enable_unified_events = False
```

**Impact**: Zero - agents fall back to existing event system

### If Dual-Write Causes Issues

```python
# In dual_writer.py
class DualWriteTaskRepository:
    def __init__(self):
        self.enable_unified_writes = False  # Disable unified writes
```

**Impact**: Minimal - writes only to legacy schema

### If Need to Rollback Migration

```bash
cd packages/hive-orchestration
python -m alembic downgrade -1
```

**Impact**: Removes unified tables, preserves all data in legacy schema

---

## Monitoring & Metrics

### Key Metrics to Track (Phase B onwards)

1. **Event Emission**:
   - Events emitted per minute
   - Event latency (emit to delivery)
   - Event processing errors

2. **Dual-Write Performance**:
   - Write latency (legacy vs unified)
   - Transaction rollback rate
   - Data consistency checks

3. **Agent Health**:
   - Agent registration count
   - Health check success rate
   - Task execution latency

### Dashboard Recommendations

Create Grafana dashboards for:
- Event flow visualization
- Agent registry status
- Database write metrics
- Migration progress tracking

---

## Documentation Updates Needed

### Before Phase B

- [ ] Update README.md files for hive-bus and hive-orchestration
- [ ] Create migration guide for agent developers
- [ ] Document feature flag usage
- [ ] Create troubleshooting guide

### Example README Update

**packages/hive-bus/README.md**:

```markdown
## Unified Events (New in v2.0)

The hive-bus package now includes unified event types for cross-agent
coordination:

\`\`\`python
from hive_bus import UnifiedEvent, UnifiedEventType

event = UnifiedEvent(
    event_type=UnifiedEventType.TASK_CREATED,
    correlation_id='workflow-123',
    payload={'task_id': 'task-456'},
    source_agent='orchestrator'
)
\`\`\`

### Migration from BaseEvent

Existing code using BaseEvent continues to work unchanged. Unified
events are optional and enabled via feature flags.

See [Migration Guide](./docs/MIGRATION.md) for details.
```

---

## Success Criteria for Phase B

- [ ] Event emission working in at least 1 agent
- [ ] Zero production incidents
- [ ] Event correlation IDs tracked correctly
- [ ] Monitoring dashboard operational
- [ ] All existing functionality preserved
- [ ] Performance impact < 5% overhead

---

## Risk Assessment

### Phase A (Current - Complete)
**Risk**: 🟢 MINIMAL
- Zero production impact (infrastructure only)
- All changes backwards compatible
- Easy rollback

### Phase B (Next - Event Emission)
**Risk**: 🟡 LOW-MODERATE
- Feature flagged rollout
- Can disable at any time
- Monitoring in place

### Phase C (Q2 2025 - Dual-Write)
**Risk**: 🟡 MODERATE
- Write performance impact
- Data consistency concerns
- Requires careful monitoring

### Phase D (Q3 2025 - Complete Migration)
**Risk**: 🟠 MODERATE-HIGH
- Point of no return
- Requires extensive testing
- Needs stakeholder sign-off

---

## Communication Plan

### Stakeholder Updates

**Weekly** (during Phase B):
- Event emission metrics
- Agent health status
- Any issues encountered

**Bi-weekly** (during Phase C):
- Dual-write performance
- Data consistency reports
- Migration progress

**Monthly** (during Phase D):
- Complete migration status
- Deprecation timeline
- Final validation results

---

## Contact & Support

**Technical Lead**: Genesis Agent (Project Genesis Phase 4)
**Documentation**: `claudedocs/PROJECT_GENESIS_PHASE4_WEEK1_COMPLETE.md`
**Architecture**: `.claude/ARCHITECTURE_PATTERNS.md`

For questions or issues:
1. Check documentation in `claudedocs/`
2. Review rollback procedures above
3. Consult with platform team

---

**Status**: Ready for Phase B kickoff
**Next Checkpoint**: Package reinstall verification
**Next Phase**: Week 2-4 (Event Emission with Feature Flags)
