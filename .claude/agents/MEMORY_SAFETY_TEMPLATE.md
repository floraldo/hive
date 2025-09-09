# Memory-Safe Agent Template

## Standard Memory Safety Patterns Applied to All Agents

### Core Principles (NON-NEGOTIABLE)
- **BRUTAL HONESTY**: Reality-first analysis, no wishful thinking
- **BOUNDED OPERATIONS**: Process limited items per task (max 5-10 items)
- **MEMORY SAFE**: No external databases or unlimited context loading
- **FILE-BASED ONLY**: Work exclusively with local files
- **CONTEXT LIMITS**: Maximum 5KB context per operation

### Memory Safety Replacements Made:

#### REMOVED (Memory Leak Patterns):
- ❌ "unlimited context through SPARC's external memory system"
- ❌ "Complete file history, decisions, and workflow phases via Supabase"
- ❌ "Vector search of relevant implementations via Qdrant"  
- ❌ "select * from project_memorys" database queries
- ❌ Infinite loops and unbounded iterations
- ❌ "Store in external memory for reuse"
- ❌ Recursive agent calls without limits

#### ADDED (Memory-Safe Patterns):
- ✅ **Bounded Context**: Maximum 5 files per operation
- ✅ **File Limits**: Specific file count limits for all operations
- ✅ **Memory Cleanup**: Clear context between operations
- ✅ **Iteration Limits**: Maximum iteration counts (typically 3-5)
- ✅ **Timeout Controls**: 30-second limits on operations
- ✅ **Context Validation**: Size limits on loaded content
- ✅ **Local State Only**: Use `.sparc/state/` directory for state tracking

### Standard Memory Management Protocol:
```markdown
## Memory Management Protocol
- **Context Limits**: Maximum [X] items/files per operation
- **File Scope**: Process one [module/feature/area] at a time  
- **Iteration Control**: Maximum [N] cycles per task
- **Timeout Management**: [X]-second limits on operations
- **Memory Cleanup**: Clear context between [operations/tasks/phases]
```

### Standard Completion Criteria:
```markdown
## Completion Criteria
[Task type] complete when:
1. **Bounded Completion**: All items processed within limits
2. **Quality Standards**: Output meets defined criteria  
3. **Memory Safety**: No unbounded context or memory leaks
4. **File-Based Output**: Results exist as local files
5. **Ready for Next Phase**: Clear handoff criteria met
```

### Standard Reporting Protocol:
```markdown
## Reporting Protocol
Your completion messages must include:
- **Self-Assessment Score**: Rate work quality 1-100
- **Items Processed**: Count and list of items handled
- **Memory Safety**: Confirmation of bounded operations
- **Files Created/Modified**: List of output files
- **Next Phase Readiness**: Transition criteria confirmation
```

This template ensures all agents follow consistent memory-safe patterns.