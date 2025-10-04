# QA Agent Workflow

**Purpose**: Systematic technical debt cleanup and quality consolidation

**Role**: Agent 4 - Quality Assurance Agent
**Profile**: Strict pre-commit, comprehensive validation, zero-violation standard

## Philosophy

The QA Agent operates in a **high-friction, strict environment** to maintain platform quality:

- ✅ **Enforce**: All quality gates (ruff, Golden Rules, syntax)
- ✅ **Block**: Any violations that could accumulate as technical debt
- ✅ **Clean**: Ensure every commit maintains zero-violation standard

Feature agents optimize for **velocity**. The QA agent optimizes for **quality**.

## Setup

### 1. Configure Strict Pre-Commit Profile
```bash
# Install strict pre-commit hooks (default)
pre-commit install

# Verify using strict config
cat .git/hooks/pre-commit | grep -q "pre-commit" && echo "✅ Strict profile active"
```

### 2. Apply QA Agent Git Configuration
```bash
# Apply QA agent Git config
git config --local include.path ../.git-config-qa-agent

# Set commit template
git config --local commit.template .git-commit-template-qa
```

### 3. Start QA Session
```bash
# Run QA agent startup script
bash scripts/qa/start-qa-session.sh

# This will:
# - Apply strict Git config
# - Display health metrics
# - Show prioritized task list
```

## Daily Workflow

### Step 1: Pull Latest Changes
```bash
# Pull feature agent work from main
git checkout main
git pull origin main

# Review what changed
git log --oneline --since="4 hours ago"
```

### Step 2: Run Health Metrics
```bash
# Generate comprehensive health dashboard
python scripts/qa/health-metrics.py --export claudedocs/qa_health_dashboard.md

# Quick health check
python scripts/qa/health-metrics.py
```

### Step 3: Review Bypass Log
```bash
# Review feature agent bypass justifications
python scripts/qa/review-bypasses.py

# Show recent bypasses
python scripts/qa/review-bypasses.py --show-recent 10
```

### Step 4: Identify Technical Debt
```bash
# Run full validation to get To-Do list
ruff check .

# Run Golden Rules validation
python scripts/validation/validate_golden_rules.py --level ERROR

# Check for syntax errors
python -m pytest --collect-only
```

### Step 5: Systematic Cleanup
```bash
# Fix violations incrementally
# Start with highest priority: syntax errors, then linting, then Golden Rules

# Auto-fix what's safe
ruff check . --fix

# Manual fixes for complex violations
# ... (edit files as needed)

# Validate fixes
python -m pytest --collect-only
python scripts/validation/validate_golden_rules.py --level ERROR
```

### Step 6: Commit Clean Codebase
```bash
# Stage all fixes
git add .

# Commit (strict pre-commit will validate)
git commit -m "refactor(quality): Consolidate and clean codebase

Violations fixed:
- Linting: <count>
- Syntax errors: <count>
- Bypasses reviewed: <count>

Health score: <before>% -> <after>%
"

# Push to main
git push origin main
```

### Step 7: Verify CI/CD
```bash
# Monitor CI/CD run
gh run watch

# If failures occur, they'll create new QA tasks automatically
# via the create-qa-task job in golden-gates.yml
```

## Task Prioritization

### High Priority (Fix Immediately)
- ❗ **Syntax errors**: Prevent test collection failures
- ❗ **Test collection failures**: Block all testing
- ❗ **Core package violations**: Gate 4A failures (packages/)

### Medium Priority (Fix Within 24 Hours)
- ⚠️ **Boy Scout Rule violations**: Linting debt growth
- ⚠️ **Crust validation failures**: Gate 4B failures (apps/)
- ⚠️ **Golden Rules ERROR level**: Architectural violations

### Low Priority (Fix During Sprint Cleanup)
- 💡 **Golden Rules WARNING level**: Best practices
- 💡 **Golden Rules INFO level**: Optimization opportunities
- 💡 **Documentation updates**: Outdated docs

## Quality Metrics Tracking

### Key Metrics
- **Linting violations trend**: Track total count over time
- **Bypass frequency**: How often feature agents use --no-verify
- **CI success rate**: Percentage of passing CI runs
- **Health score**: Weighted quality metric (0-100%)

### Health Score Calculation
```
Health Score = (
  (100 - syntax_errors * 10) * 0.4 +
  (100 - linting_violations / 50) * 0.3 +
  (100 - golden_rules_errors * 5) * 0.2 +
  (ci_success_rate) * 0.1
)
```

### Target Metrics
- ✅ Health Score: ≥ 90%
- ✅ Syntax Errors: 0
- ✅ Boy Scout Rule: No growth in linting violations
- ✅ CI Success Rate: ≥ 95%

## Tools Reference

### Health Metrics Dashboard
```bash
# Full dashboard export
python scripts/qa/health-metrics.py --export claudedocs/qa_health_dashboard.md

# Show 30-day trend
python scripts/qa/health-metrics.py --show-trend 30
```

### Bypass Review
```bash
# Review all bypasses
python scripts/qa/review-bypasses.py

# Show recent bypasses
python scripts/qa/review-bypasses.py --show-recent 10
```

### Validation Commands
```bash
# Syntax check
python -m pytest --collect-only

# Linting check
ruff check .

# Golden Rules validation
python scripts/validation/validate_golden_rules.py --level ERROR

# Full validation suite
bash scripts/validation/run_full_validation.sh
```

## Integration with Project Cornerstone

The QA Agent workflow integrates with Project Cornerstone (Core Infrastructure Stabilization):

### Phase 1: Core Package Stabilization
```bash
# QA Agent focuses on packages/ only
pytest packages/

# Fix all core package test failures
# Goal: 100% green core infrastructure
```

### Phase 2: Green Core CI Enforcement
```bash
# Verify core-infra-ci.yml is protecting packages/
gh workflow view core-infra-ci

# Monitor core package health
python scripts/qa/health-metrics.py --scope packages
```

### Phase 3: Application-Level Triage
```bash
# After core is stable, address apps/
pytest apps/

# Categorize failures: BUG, REFACTOR_TEST, DELETE_TEST
python scripts/qa/review-bypasses.py --categorize-failures
```

## Best Practices

### Do's ✅
- ✅ Run health metrics at start of every session
- ✅ Review bypass log to understand feature agent priorities
- ✅ Fix syntax errors immediately (highest priority)
- ✅ Commit incrementally (small, atomic commits)
- ✅ Validate before pushing (strict pre-commit enforces this)

### Don'ts ❌
- ❌ Never use --no-verify (QA agent always validates)
- ❌ Don't batch fixes into giant commits (hard to review)
- ❌ Don't skip health metrics (visibility is critical)
- ❌ Don't ignore bypass justifications (they guide priorities)

## Automation Opportunities

Future enhancements for QA Agent workflow:

1. **Auto-prioritization**: ML model to prioritize tasks based on impact
2. **Automated fixes**: Safe auto-fixes for common patterns
3. **Predictive analytics**: Forecast tech debt accumulation
4. **Integration with orchestrator**: QA tasks managed by hive-orchestrator

## Success Criteria

The QA Agent workflow is successful when:

- ✅ Health score maintained at ≥ 90%
- ✅ No syntax errors in main branch
- ✅ CI success rate ≥ 95%
- ✅ Feature agents report minimal friction
- ✅ Technical debt trend is flat or declining

---

**Remember**: The QA Agent is the "immune system" of the platform. Feature agents deliver velocity; the QA agent ensures sustainability.
