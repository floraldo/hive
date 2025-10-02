# Hive Platform Commit Message Standards

**Purpose**: Consistent, traceable commit messages with agent attribution and clear structure.

---

## Standard Format

```
<type>(<scope>)[agent:<agent-name>]: <subject>

<body - optional but recommended for significant changes>

<footer - optional: breaking changes, issue references>

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## Components

### 1. Type (Required)
Semantic commit type indicating change category:

- **feat**: New feature or capability
- **fix**: Bug fix or error correction
- **docs**: Documentation only changes
- **style**: Code style/formatting (no logic change)
- **refactor**: Code restructuring (no behavior change)
- **perf**: Performance improvement
- **test**: Adding or updating tests
- **chore**: Maintenance, tooling, dependencies
- **ci**: CI/CD pipeline changes
- **build**: Build system or dependencies

### 2. Scope (Required)
Component or package affected:

**Packages**:
- `hive-ai`, `hive-async`, `hive-bus`, `hive-cache`, `hive-config`, `hive-db`,
- `hive-deployment`, `hive-errors`, `hive-logging`, `hive-performance`,
- `hive-service-discovery`, `hive-tests`, `hive-orchestration`

**Apps**:
- `ecosystemiser`, `hive-orchestrator`, `ai-planner`, `ai-reviewer`,
- `guardian-agent`, `qr-service`

**Infrastructure**:
- `ci`, `docker`, `scripts`, `workflows`

**Meta**:
- `platform`, `architecture`, `docs`

### 3. Agent Tag (Optional but Recommended)
Indicates which AI agent made the changes:

Format: `[agent:<name>]` after scope, before colon

**Agent Names**:
- `golden` - Golden rules validation, CI/CD quality gates
- `guardian` - Guardian Agent development and enhancement
- `frontend` - UI/UX and frontend architecture
- `backend` - API, services, and backend systems
- `infrastructure` - DevOps, deployment, orchestration
- `data` - Database, caching, data pipelines
- `security` - Security scanning, vulnerability fixes
- `performance` - Performance optimization, profiling
- `docs` - Documentation specialist
- `qa` - Quality assurance and testing

**Example**: `feat(guardian)[agent:golden]: Add feedback tracking system`

### 4. Subject (Required)
Brief description of change (50-72 characters):

- **Use imperative mood**: "Add feature" not "Added feature"
- **No period at end**
- **Capitalize first letter**
- **Be specific**: "Add RAG feedback tracking" not "Update code"

### 5. Body (Optional, Recommended for Complex Changes)
Detailed explanation wrapped at 72 characters:

- **What changed**: Specific files/components modified
- **Why it changed**: Business/technical rationale
- **How it changed**: Key implementation details
- **Impact**: User-facing changes, breaking changes

**Blank line** required between subject and body.

### 6. Footer (Optional)
Additional metadata:

- **Breaking changes**: `BREAKING CHANGE: <description>`
- **Issue references**: `Closes #123`, `Fixes #456`, `Relates to #789`
- **Reviewers**: `Reviewed-by: @username`
- **Dependencies**: `Depends-on: <commit-hash>`

---

## Examples

### Simple Feature (No Body)
```
feat(guardian)[agent:golden]: Add human feedback footer to PR comments

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Complex Feature (With Body)
```
feat(guardian)[agent:golden]: Integrate RAG engine into PR review workflow

Phase 2 Guardian Agent activation - connects real RAG engine to CI/CD.

Changes:
- Created CLI review script (cli_review.py) for RAG-enhanced analysis
- Updated workflow to call real engine vs placeholder
- Added confidence threshold (80%) and rate limiting (5 comments max)
- Implemented graceful fallback on review failures

Integration features:
- RAG context from indexed codebase
- Golden rule violation detection
- Multi-file diff analysis with line-level comments
- JSON output compatible with GitHub PR API

Next: Add human feedback loop and performance metrics

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Bug Fix
```
fix(hive-cache)[agent:performance]: Correct Redis connection pool exhaustion

Fixed memory leak in PerformanceCache where connections were not properly
released back to the pool after failed operations.

- Added try/finally blocks for connection cleanup
- Implemented connection health checks before reuse
- Added pool size monitoring and alerts

Fixes #234

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Breaking Change
```
refactor(hive-config)[agent:golden]: Replace global state with dependency injection

BREAKING CHANGE: get_config() function removed, use create_config_from_sources()

Migrated all packages and apps from deprecated global state pattern to
dependency injection for improved testability and thread safety.

Migration guide: claudedocs/config_migration_guide_comprehensive.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### CI/CD Change
```
ci(workflows)[agent:golden]: Disable noisy production monitoring workflow

Renamed predictive-monitoring.yml to .disabled to stop false-positive
failures. Workflow was checking localhost services in isolated GitHub
runner where no services are running.

Next: Create proper system-health-check.yml integration test

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

### Documentation
```
docs(guardian)[agent:golden]: Complete Phase 2 & 2.5 activation summary

Comprehensive documentation of Guardian Agent evolution from infrastructure
to production-ready RAG-enhanced code reviewer with feedback loop.

Covers:
- Phase 2: RAG engine integration and CI/CD workflow
- Phase 2.5: Human feedback system and performance metrics
- Technical achievements and architecture patterns
- Phase 3 roadmap with priorities and estimates

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

---

## Best Practices

### DO
- ✅ Include agent tag for AI-generated commits
- ✅ Use semantic types consistently
- ✅ Specify precise scope (package or app name)
- ✅ Write imperative subject lines
- ✅ Add body for non-trivial changes
- ✅ Reference issues when applicable
- ✅ Include Claude Code attribution footer

### DON'T
- ❌ Generic subjects: "Update files", "Fix bug", "Changes"
- ❌ Mixing multiple unrelated changes in one commit
- ❌ Omitting scope: `feat: Add feature` (which component?)
- ❌ Past tense: "Added feature" (use "Add feature")
- ❌ Breaking changes without BREAKING CHANGE footer
- ❌ Commits without running quality gates first

---

## Tooling

### Pre-Commit Message Template
Configure git to use template:

```bash
git config commit.template .claude/commit_template.txt
```

### Commit Message Validation Hook
Add to `.pre-commit-config.yaml`:

```yaml
- repo: local
  hooks:
    - id: commit-msg-format
      name: Validate commit message format
      entry: python scripts/validation/validate_commit_message.py
      language: system
      stages: [commit-msg]
```

### Automated Agent Tag Insertion
Claude Code agents should automatically insert `[agent:<name>]` tag based on
active agent context.

---

## Migration Strategy

### Phase 1: Documentation (Current)
- ✅ Create COMMIT_STANDARDS.md
- Document format and examples
- Share with team for feedback

### Phase 2: Enforcement (Next)
- Add commit message validation hook
- Update agent prompts to include tags
- Create commit message template

### Phase 3: Automation (Future)
- Auto-detect agent from context
- Generate commit messages from changeset analysis
- Integrate with PR descriptions

---

## Why This Matters

### Traceability
- **Agent attribution**: Know which AI agent made changes
- **Scope clarity**: Instantly identify affected components
- **Semantic types**: Automated changelog generation

### Quality
- **Consistent format**: Easier code review and git log reading
- **Detailed context**: Body explains the "why" behind changes
- **Breaking change tracking**: Clear warnings for API consumers

### Automation
- **CI/CD integration**: Trigger workflows based on commit type
- **Release notes**: Auto-generate from semantic commits
- **Blame analysis**: Better debugging with clear commit history

---

**Status**: v1.0 - Active from 2025-10-02
**Owner**: Golden Agent
**Review Cadence**: Quarterly
**Next Review**: 2026-01-02

🤖 Generated with [Claude Code](https://claude.com/claude-code)
