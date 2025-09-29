# Scripts Directory

**Reorganized**: 2025-09-29 14:15:00

This directory has been systematically reorganized to eliminate redundancy and improve maintainability.

## Directory Structure

```
scripts/
├── analysis/          # Code analysis and reporting tools
├── database/          # Database setup, optimization, and seeding
├── daemons/           # Long-running service scripts
├── maintenance/       # Repository hygiene and cleanup tools
│   └── fixers/        # Code fixing and modernization utilities
├── security/          # Security auditing and compliance tools
├── setup/             # Environment and system setup scripts
├── testing/           # Test runners and validation tools
├── utils/             # Utility scripts and system launchers
└── archive/           # Archived scripts (safe storage)
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

### Analysis
- `analysis/async_resource_patterns.py` - Async resource management patterns

### Database Management
- `database/setup.py` - Unified database operations

### Daemons
- `daemons/ai_planner_daemon.py` - AI planner service
- `daemons/ai_reviewer_daemon.py` - AI reviewer service

### Maintenance
- `maintenance/repository_hygiene.py` - Repository cleanup
- `maintenance/log_management.py` - Log file management
- `maintenance/fixers/code_fixers.py` - Code fixing tools

### Security
- `security/run_audit.py` - Security auditing and compliance

### Setup
- `setup/initial_setup.sh` - System initialization
- `setup/setup_pre_commit.sh` - Git hooks setup
- `setup/setup_github_secrets.sh` - CI/CD setup

### Testing
- `testing/run_tests.py` - Unified test runner
- `testing/health-check.sh` - System health checks
- `testing/dev-session.sh` - Development environment

### Utilities
- `utils/hive_queen.py` - Queen orchestrator launcher
- `utils/hive_dashboard.py` - Dashboard launcher
- `utils/start_async_hive.py` - Async orchestrator launcher

---

*This reorganization reduced 70 scripts to 32 organized tools while maintaining all functionality.*
