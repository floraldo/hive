# Hive Enhanced Context System

## Overview

The Hive system now features an enhanced context management system that addresses the inherent challenges of stateless workers while preserving the benefits of isolation and reliability.

## Key Features

### 1. Enhanced Result Metadata

Workers now automatically track and report:
- **Files created**: New files generated during task execution
- **Files modified**: Existing files that were changed
- **Context hints**: Key insights for dependent tasks (optional)

Example result JSON:
```json
{
  "status": "success",
  "notes": "Calculator module created successfully",
  "files": {
    "created": ["calculator.py", "test_calculator.py"],
    "modified": []
  },
  "context_hints": "Basic math operations implemented with error handling"
}
```

### 2. Context-From Field

Tasks can now reference outputs from previous tasks using the `context_from` field:

```json
{
  "id": "extend-calculator",
  "title": "Extend Calculator Module",
  "context_from": ["basic-calculator"],
  "instruction": "Build upon the existing calculator..."
}
```

When a worker processes this task, it automatically receives:
- Status of referenced tasks
- Files created/modified by those tasks
- Any context hints provided
- Notes from task completion

### 3. Workspace Modes

Two distinct workspace modes with clear semantics:

#### Fresh Mode (Default)
- **Always starts clean** - removes any existing workspace
- Creates new empty directory every run
- Perfect for testing and isolated tasks
- Ensures reproducible, predictable environments

#### Repo Mode
- Creates git worktree on first run  
- **Automatically reuses** existing worktree for subsequent runs
- Workspace persists until PR is merged
- Enables version control and iterative development

#### Key Difference
- **Fresh**: Always clean slate (testing, isolated tasks)
- **Repo**: Persistent workspace (development, iterative work)

Example:
```bash
# Fresh mode - always starts clean
python worker.py backend --local --task-id test-auth --mode fresh  # Clean workspace
python worker.py backend --local --task-id test-auth --mode fresh  # Clean again!

# Repo mode - persistent workspace
python worker.py backend --local --task-id create-auth --mode repo  # Creates worktree
python worker.py backend --local --task-id create-auth --mode repo  # Reuses worktree
# After PR merge, worktree is cleaned up automatically
```

### 4. Task Dependencies

The existing `depends_on` field ensures proper execution order:

```json
{
  "id": "deploy-app",
  "depends_on": ["build-app", "run-tests"],
  "context_from": ["build-app", "run-tests"]
}
```

## Usage Examples

### Example 1: Sequential Task Chain

```json
// Task 1: Create base module
{
  "id": "create-auth",
  "title": "Create Authentication Module",
  "instruction": "Create JWT authentication system",
  "workspace": "fresh"
}

// Task 2: Add tests (depends on Task 1)
{
  "id": "test-auth",
  "title": "Test Authentication Module",
  "depends_on": ["create-auth"],
  "context_from": ["create-auth"],
  "instruction": "Write comprehensive tests for auth module"
}

// Task 3: Add documentation (depends on Tasks 1 & 2)
{
  "id": "document-auth",
  "title": "Document Authentication System",
  "depends_on": ["test-auth"],
  "context_from": ["create-auth", "test-auth"],
  "instruction": "Create API documentation and usage guide"
}
```

### Example 2: Refinement Task

```json
{
  "id": "refine-ui-r1",
  "title": "Refinement: Improve UI Components",
  "parent_task": "create-ui",
  "workspace": "continue",
  "instruction": "Address the following issues:\n1. Add accessibility attributes\n2. Improve responsive design"
}
```

## Benefits

1. **Preserved Isolation**: Each worker still starts clean, maintaining reliability
2. **Explicit Context**: Context is passed deliberately, not accidentally
3. **Traceable Dependencies**: Clear lineage of task relationships
4. **Flexible Continuation**: Support for both fresh starts and building on existing work
5. **Improved Debugging**: File tracking makes it easy to see what each task produced

## Migration Guide

### For Existing Tasks

No changes required! Existing tasks continue to work as before. The context system is fully backward compatible.

### For New Tasks

To leverage context features:

1. Add `context_from` field to reference previous tasks
2. Use `depends_on` to ensure execution order
3. Consider using `continue` mode for refinement tasks
4. Workers automatically track file changes - no code changes needed

## Architecture

The context system follows the principle: **"The Hive Mind is in the Tasks, Not the Workers"**

- **Workers remain stateless**: Clean execution environment every time
- **Queen orchestrates context**: Manages task dependencies and result aggregation
- **Tasks carry knowledge**: Context explicitly defined in task definitions
- **Results preserve history**: Enhanced metadata captures task outputs

## Future Enhancements

Planned improvements include:
- Shared knowledge base for cross-task learning
- Automatic context inference based on file dependencies
- Visual dependency graphs in the UI
- Context compression for large result sets

## Testing

Run the context system tests:

```bash
# Test base task
python worker.py backend --local --task-id test-context-base --phase apply

# Test dependent task (after base completes)
python worker.py backend --local --task-id test-context-dependent --phase apply
```

The dependent task will automatically receive context from the base task, demonstrating the enhanced context system in action.