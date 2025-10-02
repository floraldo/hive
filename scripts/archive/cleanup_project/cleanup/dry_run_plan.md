# Scripts Refactoring Dry-Run Plan

**Generated**: 2025-09-29 04:45:13
**Total Operations**: 63

## Summary

### Consolidation Plans
- **cleanup_scripts**: 5 scripts -> maintenance/repository_hygiene.py
- **testing_scripts**: 13 scripts -> testing/run_tests.py
- **security_scripts**: 3 scripts -> security/run_audit.py
- **database_scripts**: 9 scripts -> database/setup.py
- **fixer_scripts**: 10 scripts -> maintenance/fixers/code_fixers.py
- **async_refactor_scripts**: 4 scripts -> archive/

### Operation Types
- **Create**: 11
- **Move**: 52
- **Copy**: 0
- **Delete**: 0

## Detailed Operations

### Directory Creation

### File Consolidations

#### cleanup_scripts
**Target**: maintenance/repository_hygiene.py
**Method**: merge
**Source Scripts**:
- comprehensive_code_cleanup.py
- hive_clean.py
- comprehensive_cleanup.py
- comprehensive_cleanup.py
- targeted_cleanup.py
**New Features**:
- File organization and cleanup
- Backup file removal
- Documentation consolidation
- Database cleanup (from hive_clean.py)
- Targeted cleanup modes

#### testing_scripts
**Target**: testing/run_tests.py
**Method**: merge
**Source Scripts**:
- run_comprehensive_integration_tests.py
- run_integration_tests.py
- simulate_planner_success.py
- standardize_tests.py
- step_by_step_cert.py
- v3_final_cert.py
- validate_golden_rules.py
- validate_integration_tests.py
- worker_async_patch.py
- seed_master_plan_task.py
- monitor_certification.py
- monitor_master_plan.py
- quick-test.sh
**New Features**:
- Comprehensive test execution
- Quick validation mode
- Performance benchmarking
- CI/CD integration

#### security_scripts
**Target**: security/run_audit.py
**Method**: merge
**Source Scripts**:
- audit_dependencies.py
- security_check.py
- security_audit.py
**New Features**:
- Comprehensive security scanning
- Quick security checks
- Vulnerability reporting
- Compliance validation

#### database_scripts
**Target**: database/setup.py
**Method**: split_merge
**Source Scripts**:
- hive_clean.py
- init_db_simple.py
- optimize_database.py
- optimize_lambdas.py
- optimize_performance.py
- seed_database.py
- seed_master_plan_task.py
- optimize_database_indexes.py
- initial_setup.sh
**New Features**:
- Database initialization and seeding
- Index optimization
- Performance tuning
- Migration support

#### fixer_scripts
**Target**: maintenance/fixers/code_fixers.py
**Method**: merge
**Source Scripts**:
- add_type_hints.py
- fix_all_golden_violations.py
- fix_ecosystemiser_logging.py
- fix_global_state.py
- fix_golden_violations.py
- fix_type_hints.py
- modernize_type_hints.py
- fix_all_syntax_errors.py
- fix_syspath_violations.py
- smart_final_fixer.py
**New Features**:
- Type hint fixes
- Global state fixes
- Logging standardization
- Async pattern fixes
- Golden rules compliance

#### async_refactor_scripts
**Target**: archive/
**Method**: archive
**Source Scripts**:
- async_worker.py
- enhance_async_resources.py
- queen_async_enhancement.py
- worker_async_patch.py
**New Features**:
- One-time refactoring completed

### File Operations
- **CREATE**:  -> database
  - Reason: Create new directory structure: database/
- **CREATE**:  -> maintenance
  - Reason: Create new directory structure: maintenance/
- **CREATE**:  -> fixers
  - Reason: Create new directory structure: maintenance/fixers/
- **CREATE**:  -> security
  - Reason: Create new directory structure: security/
- **CREATE**:  -> setup
  - Reason: Create new directory structure: setup/
- **CREATE**:  -> testing
  - Reason: Create new directory structure: testing/
- **CREATE**:  -> archive
  - Reason: Create new directory structure: archive/
- **MOVE**: v3_final_cert.py -> v3_final_cert.py
  - Reason: Archive deprecated script: v3_final_cert.py
- **MOVE**: step_by_step_cert.py -> step_by_step_cert.py
  - Reason: Archive deprecated script: step_by_step_cert.py
- **MOVE**: async_worker.py -> async_worker.py
  - Reason: Archive deprecated script: async_worker.py
- **MOVE**: worker_async_patch.py -> worker_async_patch.py
  - Reason: Archive deprecated script: worker_async_patch.py
- **MOVE**: queen_async_enhancement.py -> queen_async_enhancement.py
  - Reason: Archive deprecated script: queen_async_enhancement.py
- **MOVE**: simulate_planner_success.py -> simulate_planner_success.py
  - Reason: Archive deprecated script: simulate_planner_success.py
- **MOVE**: hive_complete_review.py -> hive_complete_review.py
  - Reason: Archive deprecated script: hive_complete_review.py
- **CREATE**:  -> repository_hygiene.py
  - Reason: Create consolidated script for cleanup_scripts
- **MOVE**: comprehensive_code_cleanup.py -> comprehensive_code_cleanup.py
  - Reason: Archive after consolidation: comprehensive_code_cleanup.py
- **MOVE**: hive_clean.py -> hive_clean.py
  - Reason: Archive after consolidation: hive_clean.py
- **MOVE**: comprehensive_cleanup.py -> comprehensive_cleanup.py
  - Reason: Archive after consolidation: comprehensive_cleanup.py
- **MOVE**: comprehensive_cleanup.py -> comprehensive_cleanup.py
  - Reason: Archive after consolidation: comprehensive_cleanup.py
- **MOVE**: targeted_cleanup.py -> targeted_cleanup.py
  - Reason: Archive after consolidation: targeted_cleanup.py
- **CREATE**:  -> run_tests.py
  - Reason: Create consolidated script for testing_scripts
- **MOVE**: run_comprehensive_integration_tests.py -> run_comprehensive_integration_tests.py
  - Reason: Archive after consolidation: run_comprehensive_integration_tests.py
- **MOVE**: run_integration_tests.py -> run_integration_tests.py
  - Reason: Archive after consolidation: run_integration_tests.py
- **MOVE**: simulate_planner_success.py -> simulate_planner_success.py
  - Reason: Archive after consolidation: simulate_planner_success.py
- **MOVE**: standardize_tests.py -> standardize_tests.py
  - Reason: Archive after consolidation: standardize_tests.py
- **MOVE**: step_by_step_cert.py -> step_by_step_cert.py
  - Reason: Archive after consolidation: step_by_step_cert.py
- **MOVE**: v3_final_cert.py -> v3_final_cert.py
  - Reason: Archive after consolidation: v3_final_cert.py
- **MOVE**: validate_golden_rules.py -> validate_golden_rules.py
  - Reason: Archive after consolidation: validate_golden_rules.py
- **MOVE**: validate_integration_tests.py -> validate_integration_tests.py
  - Reason: Archive after consolidation: validate_integration_tests.py
- **MOVE**: worker_async_patch.py -> worker_async_patch.py
  - Reason: Archive after consolidation: worker_async_patch.py
- **MOVE**: seed_master_plan_task.py -> seed_master_plan_task.py
  - Reason: Archive after consolidation: seed_master_plan_task.py
- **MOVE**: monitor_certification.py -> monitor_certification.py
  - Reason: Archive after consolidation: monitor_certification.py
- **MOVE**: monitor_master_plan.py -> monitor_master_plan.py
  - Reason: Archive after consolidation: monitor_master_plan.py
- **MOVE**: quick-test.sh -> quick-test.sh
  - Reason: Archive after consolidation: quick-test.sh
- **CREATE**:  -> run_audit.py
  - Reason: Create consolidated script for security_scripts
- **MOVE**: audit_dependencies.py -> audit_dependencies.py
  - Reason: Archive after consolidation: audit_dependencies.py
- **MOVE**: security_check.py -> security_check.py
  - Reason: Archive after consolidation: security_check.py
- **MOVE**: security_audit.py -> security_audit.py
  - Reason: Archive after consolidation: security_audit.py
- **CREATE**:  -> code_fixers.py
  - Reason: Create consolidated script for fixer_scripts
- **MOVE**: add_type_hints.py -> add_type_hints.py
  - Reason: Archive after consolidation: add_type_hints.py
- **MOVE**: fix_all_golden_violations.py -> fix_all_golden_violations.py
  - Reason: Archive after consolidation: fix_all_golden_violations.py
- **MOVE**: fix_ecosystemiser_logging.py -> fix_ecosystemiser_logging.py
  - Reason: Archive after consolidation: fix_ecosystemiser_logging.py
- **MOVE**: fix_global_state.py -> fix_global_state.py
  - Reason: Archive after consolidation: fix_global_state.py
- **MOVE**: fix_golden_violations.py -> fix_golden_violations.py
  - Reason: Archive after consolidation: fix_golden_violations.py
- **MOVE**: fix_type_hints.py -> fix_type_hints.py
  - Reason: Archive after consolidation: fix_type_hints.py
- **MOVE**: modernize_type_hints.py -> modernize_type_hints.py
  - Reason: Archive after consolidation: modernize_type_hints.py
- **MOVE**: fix_all_syntax_errors.py -> fix_all_syntax_errors.py
  - Reason: Archive after consolidation: fix_all_syntax_errors.py
- **MOVE**: fix_syspath_violations.py -> fix_syspath_violations.py
  - Reason: Archive after consolidation: fix_syspath_violations.py
- **MOVE**: smart_final_fixer.py -> smart_final_fixer.py
  - Reason: Archive after consolidation: smart_final_fixer.py
- **MOVE**: async_resource_patterns.py -> async_resource_patterns.py
  - Reason: Reorganize into new structure: async_resource_patterns.py
- **MOVE**: ai_planner_daemon.py -> ai_planner_daemon.py
  - Reason: Reorganize into new structure: ai_planner_daemon.py
- **MOVE**: ai_reviewer_daemon.py -> ai_reviewer_daemon.py
  - Reason: Reorganize into new structure: ai_reviewer_daemon.py
- **MOVE**: log_management.py -> log_management.py
  - Reason: Reorganize into new structure: log_management.py
- **MOVE**: initial_setup.sh -> initial_setup.sh
  - Reason: Reorganize into new structure: initial_setup.sh
- **MOVE**: setup_pre_commit.sh -> setup_pre_commit.sh
  - Reason: Reorganize into new structure: setup_pre_commit.sh
- **MOVE**: setup_pre_commit.bat -> setup_pre_commit.bat
  - Reason: Reorganize into new structure: setup_pre_commit.bat
- **MOVE**: setup_github_secrets.sh -> setup_github_secrets.sh
  - Reason: Reorganize into new structure: setup_github_secrets.sh
- **MOVE**: health-check.sh -> health-check.sh
  - Reason: Reorganize into new structure: health-check.sh
- **MOVE**: quick-test.sh -> quick-test.sh
  - Reason: Reorganize into new structure: quick-test.sh
- **MOVE**: dev-session.sh -> dev-session.sh
  - Reason: Reorganize into new structure: dev-session.sh
- **MOVE**: hive_queen.py -> hive_queen.py
  - Reason: Reorganize into new structure: hive_queen.py
- **MOVE**: hive_dashboard.py -> hive_dashboard.py
  - Reason: Reorganize into new structure: hive_dashboard.py
- **MOVE**: start_async_hive.py -> start_async_hive.py
  - Reason: Reorganize into new structure: start_async_hive.py


## Safety Checks Required

### Before Execution
1. **Backup Current State**: Create full backup of scripts/ directory
2. **Check Dependencies**: Verify no external references to scripts being moved
3. **CI/CD Verification**: Check GitHub workflows for script references
4. **Documentation Update**: Update any README files referencing old paths

### Verification After Execution
1. **Test Consolidated Scripts**: Verify all consolidated scripts work correctly
2. **Check Import Paths**: Ensure all internal script references are updated
3. **Run Golden Tests**: Verify no regressions in architectural compliance
4. **Integration Testing**: Run comprehensive integration tests

## Risk Assessment

### Low Risk Operations
- Moving launcher scripts (hive_queen.py, etc.)
- Creating new directories
- Moving setup scripts

### Medium Risk Operations  
- Consolidating test runners
- Moving daemon scripts
- Archiving old scripts

### High Risk Operations
- Consolidating cleanup scripts (many dependencies)
- Consolidating security scripts (CI/CD integration)
- Consolidating fixer scripts (complex logic)

## Rollback Plan

If issues occur:
1. Stop execution immediately
2. Restore from backup
3. Analyze specific failure
4. Update plan and retry

---

**IMPORTANT**: This is a DRY RUN plan. No files will be modified until explicitly approved and executed.
