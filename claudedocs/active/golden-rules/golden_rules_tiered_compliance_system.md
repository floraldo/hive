# Golden Rules: Tiered Compliance System

**Purpose**: Flexible architectural governance that adapts to development phase and maturity

**Philosophy**: "Fast in development, tight at milestones"

## Severity Level Framework

### 🔴 CRITICAL (Level 1) - Never Compromise
**When to enforce**: ALL development phases, from prototype to production

Rules that cause immediate system breakage, security vulnerabilities, or data corruption:

1. **No sys.path Manipulation** - Breaks package imports and deployment
2. **Python Syntax Validity** - Code must compile (prevents Code Red incidents)
3. **No Hardcoded Secrets/Env Values** - Security vulnerability
4. **Single Config Source** - Prevents setup.py/pyproject.toml conflicts
5. **Package vs App Discipline** - Core architectural boundary (apps→packages only, never reverse)

**Impact if violated**:
- System crashes, deployment failures
- Security breaches
- Architectural collapse requiring major refactoring

**Enforcement**: Pre-commit hooks, CI/CD blocks, immediate fix required

---

### 🟠 ERROR (Level 2) - Fix Before Merge
**When to enforce**: Feature branches, before PR approval, production releases

Rules that cause technical debt, maintainability issues, or gradual system degradation:

6. **Dependency Direction** - packages cannot import from apps
7. **Error Handling Standards** - Exceptions must inherit from BaseError
8. **Logging Standards** - Use hive_logging, no print() statements
9. **No Global State Access** - No deprecated get_config(), use DI pattern
10. **Async Pattern Consistency** - Async functions must follow naming conventions (_async suffix)
11. **Interface Contracts** - Public functions need type hints
12. **Communication Patterns** - Event bus usage patterns
13. **Service Layer Discipline** - Service layer separation from business logic

**Impact if violated**:
- Code becomes unmaintainable
- Bugs become harder to trace
- Team velocity slows over time

**Enforcement**: PR review required, CI/CD warnings, fix before merge to main

---

### 🟡 WARNING (Level 3) - Fix at Milestones
**When to enforce**: Sprint boundaries, version releases, quarterly reviews

Rules that improve code quality but don't block immediate progress:

14. **Test Coverage Mapping** - Each source file should have corresponding test file
15. **Test File Quality** - Tests should follow structure and naming patterns
16. **Inherit→Extend Pattern** - Proper layering of infrastructure vs business logic
17. **Package Naming Consistency** - Follow hive-* naming convention
18. **Development Tools Consistency** - Standardized tooling (ruff, black, mypy)
19. **CLI Pattern Consistency** - Command-line interface patterns
20. **PyProject Dependency Usage** - No unused dependencies declared

**Impact if violated**:
- Slower debugging
- Inconsistent developer experience
- Accumulating technical debt

**Enforcement**: Sprint retrospectives, milestone reviews, not blocking

---

### 🟢 INFO (Level 4) - Nice to Have
**When to enforce**: Major version releases, architecture reviews

Rules that represent best practices and long-term optimization:

21. **Unified Tool Configuration** - Consolidated config files
22. **Python Version Consistency** - Single Python version across platform
23. **No Synchronous Calls in Async Code** - Use aiofiles, not open() in async
24. **Colocated Tests** - Tests near source code (structural preference)

**Impact if violated**:
- Minor inefficiencies
- Slight inconsistencies
- Future optimization opportunities

**Enforcement**: Architecture reviews, documentation updates, optional fixes

---

## Development Phase Compliance Targets

### 🚀 Rapid Development (Prototype/PoC)
**Goal**: Move fast, validate concepts

```bash
python scripts/validate_golden_rules.py --level CRITICAL
```

**Rules enforced**: Only Level 1 (CRITICAL) - 5 rules
**Violations allowed**: Level 2-4 can accumulate
**Review frequency**: None required

---

### 🏗️ Active Development (Feature Work)
**Goal**: Build features with reasonable quality

```bash
python scripts/validate_golden_rules.py --level ERROR
```

**Rules enforced**: Level 1-2 (CRITICAL + ERROR) - 13 rules
**Violations allowed**: Level 3-4 can accumulate
**Review frequency**: Before each PR merge

---

### 📦 Sprint Boundaries (End of Sprint)
**Goal**: Clean up technical debt before next sprint

```bash
python scripts/validate_golden_rules.py --level WARNING
```

**Rules enforced**: Level 1-3 (CRITICAL + ERROR + WARNING) - 20 rules
**Violations allowed**: Only Level 4 (INFO)
**Review frequency**: End of each 2-week sprint

---

### 🎯 Major Milestones (Version Releases)
**Goal**: Ship high-quality, production-ready code

```bash
python scripts/validate_golden_rules.py --level INFO
# OR (equivalent)
python scripts/validate_golden_rules.py  # default = all rules
```

**Rules enforced**: ALL 24 rules
**Violations allowed**: Zero tolerance
**Review frequency**: Before v1.0, v2.0, etc.

---

## Implementation Plan

### Phase 1: Add Severity Metadata (30 min)
1. Add `SEVERITY` constants to architectural_validators.py
2. Map each validator function to severity level
3. Create severity filtering logic

### Phase 2: Update Validation Runner (30 min)
1. Add `--level` CLI argument to validate_golden_rules.py
2. Filter rules by severity level
3. Update output formatting to show severity

### Phase 3: Update Documentation (15 min)
1. Update .claude/CLAUDE.md with tiered compliance strategy
2. Add development phase guide
3. Update pre-commit hooks to use CRITICAL level

### Phase 4: CI/CD Integration (15 min)
1. Update GitHub workflows to use appropriate levels
2. Feature branches: ERROR level
3. Main branch: WARNING level
4. Release branches: INFO level (all rules)

---

## Usage Examples

### Quick Development
```bash
# Only check critical rules (fast, ~5s)
python scripts/validate_golden_rules.py --level CRITICAL

# Check specific files only
python scripts/validate_golden_rules.py --level ERROR --incremental
```

### Sprint Cleanup
```bash
# Check WARNING level before sprint end
python scripts/validate_golden_rules.py --level WARNING

# Fix test coverage issues
python scripts/validate_golden_rules.py --level WARNING --focus test-coverage
```

### Pre-Release Validation
```bash
# Full validation before v1.0 release
python scripts/validate_golden_rules.py --level INFO

# Same as:
python scripts/validate_golden_rules.py  # default = all rules
```

---

## Migration Strategy

### Week 1: Implement System
- Add severity metadata to validators
- Implement --level flag
- Test with existing codebase

### Week 2: Team Adoption
- Update documentation
- Train team on new system
- Set CI/CD to ERROR level

### Week 3: Sprint Integration
- Add sprint-end WARNING level checks
- Create automated reports
- Establish milestone review process

### Week 4: Optimization
- Tune severity assignments based on real usage
- Gather team feedback
- Adjust enforcement levels

---

## Benefits

✅ **Development Velocity**: Move fast during prototyping without test debt
✅ **Milestone Quality**: Ensure production readiness at key checkpoints
✅ **Team Autonomy**: Developers choose quality level for their context
✅ **Technical Debt Visibility**: Clear tracking of what's deferred
✅ **Gradual Improvement**: Natural progression from prototype to production
✅ **CI/CD Efficiency**: Faster builds during active development

## Anti-Patterns to Avoid

❌ **Don't**: Ignore CRITICAL rules "just to ship"
❌ **Don't**: Stay at WARNING level for months without cleanup
❌ **Don't**: Use INFO level during rapid prototyping
❌ **Don't**: Skip milestone reviews
❌ **Don't**: Disable rules individually (use levels instead)

---

## Success Metrics

**Development Phase**:
- CRITICAL violations: 0 (always)
- ERROR violations: < 50 (acceptable during development)
- WARNING violations: < 200 (cleanup before milestones)
- INFO violations: Track but don't block

**Milestone Phase**:
- All violations: 0 (zero tolerance at release)
- Review completion: 100%
- Time to fix violations: < 1 sprint

**Long-term**:
- Code Red incidents: 0 (prevent syntax errors)
- Architecture violations: Decreasing trend
- Developer satisfaction: Improving (less friction)