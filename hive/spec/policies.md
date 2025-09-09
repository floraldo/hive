# Hive Headless MAS - Policies and Standards

## Coding Standards

### General Principles
- **DRY**: Don't repeat yourself - abstract common functionality
- **KISS**: Keep it simple and straightforward
- **YAGNI**: You aren't gonna need it - no speculative features
- **Single Responsibility**: Each component has one reason to change
- **Fail Fast**: Detect and report errors as early as possible

### Code Quality
- **Minimum 80% test coverage** for all new code
- **Type hints required** for Python functions
- **JSDoc required** for JavaScript/TypeScript functions  
- **Error handling** - all functions must handle expected errors gracefully
- **No hardcoded values** - use configuration files or environment variables

### Git Workflow
- **Feature branches** - never commit directly to main
- **Descriptive commits** - follow conventional commit format
- **Small, atomic commits** - one logical change per commit
- **PR reviews required** - all code must be reviewed before merge
- **CI must pass** - tests, linting, and security checks required

## Task Management

### Task Requirements
- **Clear acceptance criteria** - each task must have measurable success conditions
- **Estimated effort** - provide time estimates for planning
- **Dependencies declared** - list blocking tasks or requirements
- **Tags for organization** - categorize by area, priority, and type

### Task Lifecycle
```
queued → assigned → in_progress → ready_for_review → pr_open → done
```

### Priority Levels
- **critical** - Production issues, security vulnerabilities (immediate)
- **high** - Important features, significant bugs (within 24h)
- **normal** - Standard features, minor bugs (within week)
- **low** - Nice-to-have features, cleanup (when convenient)

## Safety and Security

### Branch Protection
- **Separate branches** for each worker to prevent conflicts
- **Git worktrees** for parallel development without repo duplication
- **Automatic cleanup** of merged branches to prevent clutter

### Permission Scoping
- **Minimal permissions** - only grant access to necessary tools
- **No dangerous operations** - avoid `--dangerously-skip-permissions` in production
- **Sandbox environments** - test changes in isolated environments first
- **Audit logging** - all worker actions logged for review

### Error Recovery
- **Rollback capability** - all changes must be reversible via git
- **Circuit breakers** - stop worker if too many failures occur
- **Timeout limits** - prevent infinite loops or hanging processes
- **Resource monitoring** - track CPU, memory, disk usage

## Testing Standards

### Test Types
- **Unit tests** - test individual functions and classes
- **Integration tests** - test component interactions
- **End-to-end tests** - test complete user workflows
- **Performance tests** - verify acceptable response times

### Test Requirements
- **Tests before implementation** - TDD approach preferred
- **Independent tests** - each test should run in isolation
- **Deterministic results** - tests should not be flaky or random
- **Fast execution** - test suite should complete quickly for rapid feedback

## Documentation

### Code Documentation
- **README files** - clear setup and usage instructions
- **API documentation** - document all public interfaces
- **Architecture decisions** - record important design choices
- **Troubleshooting guides** - common issues and solutions

### Task Documentation
- **Work logs** - record what was done and why
- **Decision rationale** - explain choices made during implementation
- **Known limitations** - document current constraints or technical debt
- **Future improvements** - suggest potential enhancements

## Communication

### Worker Reporting
- **Status updates** - regular heartbeat with current activity
- **Progress reports** - completion percentage and blockers
- **Error notifications** - immediate alert for failures
- **Success confirmations** - explicit completion messages

### Task Assignment
- **Clear specifications** - unambiguous requirements
- **Context provided** - background information and constraints
- **Examples included** - reference implementations when available
- **Success criteria** - measurable completion conditions

## Resource Management

### Compute Resources
- **Process limits** - prevent runaway CPU usage
- **Memory monitoring** - alert on excessive memory consumption
- **Disk cleanup** - remove temporary files after completion
- **Concurrent task limits** - prevent system overload

### Infrastructure
- **Environment separation** - dev/staging/prod boundaries
- **Backup procedures** - regular snapshots of important data
- **Monitoring alerts** - automated notification of issues
- **Capacity planning** - scale resources based on demand

---

*These policies ensure safe, reliable, and maintainable autonomous development while preserving system stability and code quality.*