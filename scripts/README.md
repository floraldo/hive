# Scripts Directory

**Reorganized**: 2025-09-29 14:15:00
**Round 2 Consolidation**: 2025-09-30 17:00:00
**Round 3 Consolidation**: 2025-09-30 18:15:00

This directory has been systematically reorganized through three consolidation phases to eliminate redundancy, fix broken CI/CD paths, and align with industry best practices.

## Directory Structure

```
scripts/
├── daemons/           # Long-running service scripts (2 scripts)
├── database/          # Database setup and operations (1 script: setup.py)
├── debug/             # Debugging and inspection utilities (1 script: inspect_run.py)
├── maintenance/       # Repository hygiene and cleanup tools (6 scripts)
│   └── fixers/        # Code fixing and modernization utilities (2 scripts)
├── monitoring/        # Production monitoring and alerting (5 scripts)
├── performance/       # Performance analysis and optimization (8 scripts)
├── refactoring/       # Code refactoring tools (1 script)
├── security/          # Security auditing and compliance tools (1 script)
├── seed/              # Database seeding utilities (1 script)
├── setup/             # Environment and system setup scripts (4 shell scripts)
├── testing/           # Test runners and validation tools (3 scripts)
├── utils/             # Utility scripts and system launchers (5 scripts)
├── validation/        # Golden rules and validation checks (5 scripts)
└── archive/           # Archived scripts (69+ historical scripts, categorized)
    ├── fixes/         # Historical code fixing scripts (13 scripts)
    ├── maintenance/   # Historical cleanup tools (11 scripts)
    ├── security/      # Historical security audits (3 scripts)
    ├── testing/       # Historical test validation (6 scripts)
    ├── workers/       # Historical worker scripts (4 scripts)
    ├── cleanup_project/ # Phase 1 consolidation tooling (9 scripts)
    └── legacy_root_scripts/ # Phase 1 root cleanup (19 scripts)
```

## Consolidated Tools

The following consolidated tools replace multiple overlapping scripts:

- **maintenance/repository_hygiene.py** - Comprehensive cleanup and organization
- **testing/run_tests.py** - Unified test execution and validation
- **security/run_audit.py** - Complete security scanning and auditing
- **database/setup.py** - Database initialization, seeding, and optimization
- **maintenance/fixers/code_fixers.py** - Code fixing and modernization

## Migration Notes

- All original scripts have been safely archived in `archive/`
- No functionality has been lost - only consolidated and organized
- Backup of original structure: `../scripts_backup_*`

## Usage

Each consolidated tool includes comprehensive help:

```bash
python maintenance/repository_hygiene.py --help
python testing/run_tests.py --help
python security/run_audit.py --help
python database/setup.py --help
python maintenance/fixers/code_fixers.py --help
```

## Key Scripts by Category

### Database Management (1 script)
- `database/setup.py` - Unified database operations (init, seed, optimize)

### Daemons (2 scripts)
- `daemons/ai_planner_daemon.py` - AI planner service daemon
- `daemons/ai_reviewer_daemon.py` - AI reviewer service daemon

### Debug (1 script)
- `debug/inspect_run.py` - Runtime inspection tools for Queen orchestrator

### Maintenance (6 scripts)
- `maintenance/automated_hygiene.py` - Automated repository hygiene (branch analysis, link checking, TODO scanning)
- `maintenance/documentation_analyzer.py` - Documentation quality analysis
- `maintenance/git_branch_analyzer.py` - Git branch and workflow analysis
- `maintenance/repository_hygiene.py` - Comprehensive repository cleanup
- `maintenance/log_management.py` - Log file management
- `maintenance/fixers/code_fixers.py` - Code fixing and modernization
- `maintenance/fixers/emergency_syntax_fix_consolidated.py` - Emergency syntax repairs

### Monitoring (5 scripts)
- `monitoring/alert_validation_tracker.py` - Alert accuracy tracking
- `monitoring/log_intelligence.py` - Centralized log analysis
- `monitoring/predictive_analysis_runner.py` - Predictive failure detection
- `monitoring/production_monitor.py` - Production health monitoring
- `monitoring/test_monitoring_integration.py` - Monitoring integration tests

### Performance (6 scripts)
- `performance/ai_cost_optimizer.py` - AI model cost analysis and optimization
- `performance/benchmark_golden_rules.py` - Golden rules performance benchmarking
- `performance/ci_performance_analyzer.py` - CI/CD performance metrics
- `performance/ci_performance_baseline.py` - Performance regression checking
- `performance/performance_audit.py` - Code performance auditing
- `performance/pool_optimizer.py` - Connection pool optimization

### Refactoring (1 script)
- `refactoring/migrate_to_resilient_http.py` - HTTP client migration tool

### Security (1 script)
- `security/run_audit.py` - Comprehensive security auditing

### Seed (1 script)
- `seed/seed_database.py` - Database seeding utilities

### Setup (4 shell scripts)
- `setup/initial_setup.sh` - System initialization
- `setup/setup_pre_commit.sh` - Git hooks setup (with .bat variant)
- `setup/setup_github_secrets.sh` - CI/CD secrets configuration

### Testing (3 scripts)
- `testing/run_tests.py` - Unified test runner with golden rules validation
- `testing/health-check.sh` - System health checks
- `testing/dev-session.sh` - Development environment launcher

### Utilities (4 scripts)
- `utils/hive_queen.py` - Queen orchestrator launcher
- `utils/hive_dashboard.py` - Dashboard launcher
- `utils/start_async_hive.py` - Async orchestrator launcher
- `utils/optimize_database_indexes.py` - Database index optimization

### Validation (5 scripts)
- **`validation/validate_golden_rules.py`** - TIERED COMPLIANCE SYSTEM - Main validator with severity levels
- `validation/check_current_violations.py` - Current violations checker
- `validation/oracle_certification_validator.py` - Oracle certification validation
- `validation/check-golden-rules.sh` - Golden rules validation (with .bat variant)

## 🎯 Tiered Compliance System (NEW)

**Main Script**: `validation/validate_golden_rules.py`

**Philosophy**: "Fast in development, tight at milestones"

### Severity Levels

| Level | Rules | When to Use | Speed | Command |
|-------|-------|-------------|-------|---------|
| 🔴 **CRITICAL** | 5 | Always enforced | ~5s | `--level CRITICAL` |
| 🟠 **ERROR** | 13 | Before PR merge | ~15s | `--level ERROR` |
| 🟡 **WARNING** | 20 | Sprint boundaries | ~25s | `--level WARNING` |
| 🟢 **INFO** | 24 | Major releases | ~30s | `--level INFO` (default) |

### Usage Examples

```bash
# Rapid development - only critical rules
python scripts/validation/validate_golden_rules.py --level CRITICAL

# Active development - before PR
python scripts/validation/validate_golden_rules.py --level ERROR --incremental

# Sprint cleanup
python scripts/validation/validate_golden_rules.py --level WARNING

# Production release - all rules
python scripts/validation/validate_golden_rules.py --level INFO
python scripts/validation/validate_golden_rules.py  # same as INFO
```

### Key Features
- **Fast iteration**: CRITICAL level checks only 5 rules in ~5 seconds
- **Flexible enforcement**: Choose severity based on development phase
- **Incremental validation**: Use `--incremental` to check only changed files
- **App-scoped**: Use `--app <name>` to validate specific application

**Documentation**: See `claudedocs/golden_rules_tiered_compliance_system.md`

---

## Consolidation History

### Phase 1 (2025-09-29)
- Consolidated 70 scripts → 32 organized tools
- Created category-based directory structure
- Archived 55+ legacy and one-time fix scripts
- Reduced root directory from 26+ scripts to 1 (validate_golden_rules.py)

### Phase 2 (2025-09-30)
- Moved check-golden-rules scripts from testing/ to validation/
- Removed empty operational_excellence/ directory
- Reorganized archive/ into 5 categories (fixes, maintenance, security, testing, workers)
- Created comprehensive archive/README.md documentation
- Better categorized 65+ archived scripts for historical reference

---

*Current state: 49 active Python scripts + 6 shell scripts organized in 15 purpose-based directories, with 65+ archived scripts safely categorized for reference.*




















