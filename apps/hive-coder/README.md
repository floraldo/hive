# Hive Coder - The Hands of Project Colossus

**Autonomous code generator that transforms ExecutionPlans into production-ready services**

## Mission

The Coder Agent is the "Hands" of Project Colossus - it executes the task breakdown created by the Architect Agent, generating complete, production-ready services using the hive-app-toolkit.

## Architecture

```
Architect Agent (Brain)
    ↓
ExecutionPlan (JSON contract)
    ↓
Coder Agent (Hands)
    ↓
Generated Service (Production code)
```

## Flow

1. **Load ExecutionPlan** - Read JSON plan from Architect
2. **Validate Plan** - Ensure all dependencies and templates exist
3. **Order Tasks** - Topological sort based on dependencies
4. **Execute Tasks** - Generate code using hive-app-toolkit
5. **Validate Output** - Run syntax checks, Golden Rules, tests
6. **Report Results** - Return execution summary with status

## Core Components

### CoderAgent
Main orchestrator that coordinates the entire code generation process.

```python
from hive_coder import CoderAgent

agent = CoderAgent()
result = agent.execute_plan("execution_plan.json", output_dir="generated/my-service")
```

### TaskExecutor
Executes individual tasks from the ExecutionPlan:
- **SCAFFOLD**: Generate project structure using hive-app-toolkit
- **DATABASE_MODEL**: Add database schemas and migrations
- **API_ENDPOINT**: Create API routes and handlers
- **SERVICE_LOGIC**: Implement business logic
- **TEST_SUITE**: Generate comprehensive test suites
- **DEPLOYMENT**: Create Docker and K8s manifests
- **DOCUMENTATION**: Generate README and API docs

### DependencyResolver
Ensures tasks execute in correct order based on dependencies.

### CodeValidator
Validates generated code meets quality standards:
- Syntax validation (python -m py_compile)
- Golden Rules compliance
- Test execution
- Type checking (mypy)

## Usage

```python
from hive_coder import CoderAgent
from hive_architect import ArchitectAgent

# Step 1: Generate plan with Architect
architect = ArchitectAgent()
plan = architect.create_plan(
    "Create a 'feedback-service' API that stores user feedback",
    output_path="plans/feedback-service-plan.json"
)

# Step 2: Execute plan with Coder
coder = CoderAgent()
result = coder.execute_plan(
    plan_file="plans/feedback-service-plan.json",
    output_dir="generated/feedback-service"
)

# Step 3: Review results
print(f"Status: {result.status}")
print(f"Tasks completed: {result.tasks_completed}/{result.total_tasks}")
print(f"Generated files: {len(result.files_created)}")
```

## Integration with hive-app-toolkit

The Coder leverages hive-app-toolkit blueprints:

- **API services** → `hive-toolkit init {name} --type api`
- **Event workers** → `hive-toolkit init {name} --type worker`
- **Batch processors** → `hive-toolkit init {name} --type batch`

Additional features added programmatically:
- Database models via SQLAlchemy templates
- API endpoints via FastAPI route templates
- Business logic via service layer templates

## Quality Standards

All generated code must:
- Pass syntax validation (zero errors)
- Pass Golden Rules validation (CRITICAL + ERROR levels)
- Include comprehensive tests (>80% coverage)
- Follow DI config pattern
- Use hive packages for infrastructure

## Project Colossus Vision

**Phase 1 (Current)**: Requirements → Architect → Coder → Service
**Phase 2 (Future)**: Add refinement loop and testing feedback
**Phase 3 (Future)**: Full autonomous development with quality gates

## Files

```
apps/hive-coder/
├── src/hive_coder/
│   ├── agent.py              # Main CoderAgent orchestrator
│   ├── executor.py           # TaskExecutor for code generation
│   ├── resolver.py           # DependencyResolver for task ordering
│   ├── validator.py          # CodeValidator for quality checks
│   └── models.py             # ExecutionResult and supporting models
├── tests/
│   ├── test_agent.py         # CoderAgent integration tests
│   ├── test_executor.py      # TaskExecutor unit tests
│   ├── test_resolver.py      # DependencyResolver tests
│   └── test_validator.py     # CodeValidator tests
└── README.md                 # This file
```

## Status

**Version**: 0.1.0
**Phase**: Milestone 2 - Initial Implementation
**Dependencies**: hive-architect, hive-app-toolkit

---

Part of **Project Colossus** - Autonomous Development Engine
