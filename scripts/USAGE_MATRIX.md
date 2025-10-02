# Scripts Usage Matrix

**Purpose**: Track which scripts are used where and by what systems.

**Last Updated**: 2025-09-30 18:30:00

---

## CI/CD Integration

Scripts actively used by GitHub Actions workflows:

| Workflow | Script Path | Purpose | Schedule |
|----------|-------------|---------|----------|
| `ai-cost-optimization.yml` | `performance/ai_cost_optimizer.py` | AI cost analysis | Daily |
| `automated-pool-tuning.yml` | `performance/pool_tuning_orchestrator.py` | Pool configuration tuning | Daily 2 AM |
| `ci-performance-audit.yml` | `utils/async_resource_patterns.py` | CI/CD performance metrics | Monthly |
| `log-intelligence.yml` | `monitoring/log_intelligence.py` | Log analysis and digests | Daily 6 AM |
| `predictive-monitoring.yml` | `monitoring/predictive_analysis_runner.py` | Predictive failure alerts | Every 5-15 min |
| `repository-hygiene.yml` | `maintenance/automated_hygiene.py` | Repository cleanup automation | Weekly Sunday 2 AM |
| `golden-rules.yml` | `validation/validate_golden_rules.py` | Golden rules validation | On PR |
| `ci.yml` | `testing/run_tests.py` | Comprehensive test runner | On PR/push |

---

## Manual/Interactive Scripts

Scripts intended for human execution:

### Database Management
- `database/setup.py` - Database initialization, seeding, optimization
  - Used by: Developers, DevOps
  - Frequency: As needed (setup, data refresh)

### Validation & Testing
- `validation/validate_golden_rules.py` - Golden rules compliance checking
  - Used by: Developers (pre-commit)
  - Frequency: Before commits, PRs
- `validation/check_current_violations.py` - Quick violation checker
  - Used by: Developers
  - Frequency: During development
- `validation/oracle_certification_validator.py` - Oracle system validation
  - Used by: QA, architects
  - Frequency: Sprint boundaries
- `testing/run_tests.py` - Test execution
  - Used by: Developers, CI/CD
  - Frequency: Continuous

### Maintenance & Cleanup
- `maintenance/repository_hygiene.py` - Manual repository cleanup
  - Used by: DevOps, tech leads
  - Frequency: Weekly/monthly
- `maintenance/documentation_analyzer.py` - Documentation quality analysis
  - Used by: Tech writers, maintainers
  - Frequency: Before releases
- `maintenance/git_branch_analyzer.py` - Branch cleanup analysis
  - Used by: DevOps
  - Frequency: Sprint boundaries
- `maintenance/log_management.py` - Log file management
  - Used by: DevOps
  - Frequency: As needed
- `maintenance/fixers/code_fixers.py` - Code quality fixes
  - Used by: Developers
  - Frequency: During refactoring
- `maintenance/fixers/emergency_syntax_fix_consolidated.py` - Emergency syntax repairs
  - Used by: Developers (emergency only)
  - Frequency: Rare (syntax errors blocking tests)

### Performance Analysis
- `performance/ai_cost_optimizer.py` - AI cost optimization analysis
  - Used by: AI team, DevOps
  - Frequency: Weekly (automated), ad-hoc
- `performance/benchmark_golden_rules.py` - Golden rules performance benchmarking
  - Used by: Performance engineers
  - Frequency: After optimization changes
- `performance/ci_performance_analyzer.py` - CI/CD performance metrics
  - Used by: DevOps
  - Frequency: Monthly (automated)
- `performance/ci_performance_baseline.py` - Performance regression detection
  - Used by: CI/CD
  - Frequency: On merge to main
- `performance/performance_audit.py` - Code performance auditing
  - Used by: Performance engineers
  - Frequency: Sprint boundaries
- `performance/pool_config_manager.py` - Pool configuration management
  - Used by: DevOps, SRE
  - Frequency: As needed
- `performance/pool_optimizer.py` - Pool optimization analysis
  - Used by: SRE, performance team
  - Frequency: Weekly (automated), ad-hoc
- `performance/pool_tuning_orchestrator.py` - Automated pool tuning
  - Used by: CI/CD (automated)
  - Frequency: Daily

### Monitoring & Alerting
- `monitoring/alert_validation_tracker.py` - Alert accuracy tracking
  - Used by: SRE, on-call engineers
  - Frequency: Continuous (automated)
- `monitoring/log_intelligence.py` - Log analysis
  - Used by: CI/CD (automated), SRE (ad-hoc)
  - Frequency: Daily digest + ad-hoc
- `monitoring/predictive_analysis_runner.py` - Predictive alerts
  - Used by: CI/CD (automated)
  - Frequency: Every 5-15 minutes
- `monitoring/production_monitor.py` - Production health monitoring
  - Used by: SRE, on-call
  - Frequency: Continuous
- `monitoring/test_monitoring_integration.py` - Monitoring integration tests
  - Used by: SRE, QA
  - Frequency: After monitoring changes

### Security
- `security/run_audit.py` - Security auditing
  - Used by: Security team, DevOps
  - Frequency: Weekly (automated), before releases

### Utilities
- `utils/hive_queen.py` - Queen orchestrator launcher
  - Used by: Developers, operators
  - Frequency: Development sessions
- `utils/hive_dashboard.py` - Dashboard launcher
  - Used by: Operators, stakeholders
  - Frequency: As needed
- `utils/start_async_hive.py` - Async orchestrator launcher
  - Used by: Developers
  - Frequency: Development sessions
- `utils/optimize_database_indexes.py` - Database index optimization
  - Used by: DBAs, performance team
  - Frequency: Monthly, after schema changes
- `utils/async_resource_patterns.py` - Async patterns library
  - Used by: CI/CD (performance analysis)
  - Frequency: Monthly

### Refactoring
- `refactoring/migrate_to_resilient_http.py` - HTTP client migration
  - Used by: Developers
  - Frequency: One-time migration

### Daemons
- `daemons/ai_planner_daemon.py` - AI planner service
  - Used by: Service orchestration
  - Frequency: Continuous (production service)
- `daemons/ai_reviewer_daemon.py` - AI reviewer service
  - Used by: Service orchestration
  - Frequency: Continuous (production service)

### Debug
- `debug/inspect_run.py` - Queen run inspection
  - Used by: Developers, debugging
  - Frequency: During troubleshooting

### Seed
- `seed/seed_database.py` - Database seeding
  - Used by: Developers, QA
  - Frequency: Test environment setup

---

## Shell Scripts

### Setup
- `setup/initial_setup.sh` - Initial environment setup
  - Used by: New developers, deployment
  - Frequency: Once per environment
- `setup/setup_pre_commit.sh` - Git hooks setup
  - Used by: Developers
  - Frequency: Once per clone
- `setup/setup_github_secrets.sh` - CI/CD secrets configuration
  - Used by: DevOps
  - Frequency: Once per repo

### Testing
- `testing/health-check.sh` - System health checks
  - Used by: CI/CD, operators
  - Frequency: Continuous
- `testing/dev-session.sh` - Development environment launcher
  - Used by: Developers
  - Frequency: Daily

### Validation
- `validation/check-golden-rules.sh` - Golden rules validation wrapper
  - Used by: Developers, CI/CD
  - Frequency: Pre-commit, CI/CD

---

## Consolidation Opportunities

### High Priority
1. **Monitoring Runner** - Consolidate 5 monitoring scripts
   - Target: `scripts/monitoring/monitor.py`
   - Subcommands: `--alerts`, `--logs`, `--predict`, `--production`, `--test`

2. **Performance Runner** - Consolidate 8 performance scripts
   - Target: `scripts/performance/performance.py`
   - Subcommands: `--ai-costs`, `--benchmark`, `--ci-analysis`, `--baseline`, `--audit`, `--pools`, `--tune`

### Medium Priority
3. **Maintenance Runner** - Consolidate maintenance scripts
   - Target: `scripts/maintenance/maintain.py`
   - Subcommands: `--hygiene`, `--docs`, `--branches`, `--logs`, `--fix`

### Low Priority
4. **Validation Runner** - Already mostly consolidated
   - Main: `validation/validate_golden_rules.py`
   - Helpers: Check scripts can remain separate

---

## Dependencies

### External Tools Required
- Python 3.11+
- Poetry (package management)
- Git
- GitHub CLI (`gh`) for some workflows

### Python Package Dependencies
- Most scripts use hive-* packages
- Some require: requests, python-dateutil, pydantic
- See individual script imports for full dependencies

---

## Deprecation Schedule

| Script | Status | Replacement | Deprecation Date |
|--------|--------|-------------|------------------|
| None currently | - | - | - |

---

## Change Log

### 2025-09-30
- Initial creation after Round 3 consolidation
- Documented all 36 active Python scripts + 8 shell scripts
- Identified consolidation opportunities (monitoring, performance runners)
