# Hive Documentation Index

**Quick navigation to active platform documentation**

---

## Essential Reading

**Start here** for AI agents and new developers:
- **[AI_AGENT_START_HERE.md](../AI_AGENT_START_HERE.md)** (root) - 5-minute onboarding guide
- **[.claude/CLAUDE.md](../.claude/CLAUDE.md)** - Complete development guide with golden rules
- **[ARCHITECTURE.md](../ARCHITECTURE.md)** - Platform architecture deep dive
- **[README.md](../README.md)** - Project overview and quick start

---

## Active Documentation

### Configuration & Standards (`active/config/`)

- **[COMMIT_STANDARDS.md](active/config/COMMIT_STANDARDS.md)**
  - Git commit message standards and conventions
  - Use when: Writing commits or reviewing PRs

- **[config_migration_guide_comprehensive.md](active/config/config_migration_guide_comprehensive.md)** (836 lines)
  - Complete DI pattern migration guide with examples
  - Gold standard: EcoSystemiser config bridge pattern
  - Use when: Migrating code to dependency injection

- **[config_system_audit.md](active/config/config_system_audit.md)** (545 lines)
  - Configuration architecture analysis and patterns
  - Use when: Understanding config system design

- **[hive_orchestration_migration_guide.md](active/config/hive_orchestration_migration_guide.md)**
  - Guide for migrating to hive-orchestration package
  - Use when: Moving orchestration logic to shared infrastructure

### Architecture & Design (`active/architecture/`)

- **[antipattern_assessment_and_remediation.md](active/architecture/antipattern_assessment_and_remediation.md)** (466 lines)
  - Code smell analysis and remediation strategies
  - Use when: Identifying and fixing code quality issues

- **[antipattern_implementation_summary.md](active/architecture/antipattern_implementation_summary.md)**
  - Summary of antipattern fixes implemented
  - Use when: Tracking architectural improvements

- **[architectural_roadmap_prioritized.md](active/architecture/architectural_roadmap_prioritized.md)**
  - Platform architecture evolution roadmap
  - Use when: Planning architectural improvements

- **[architecture_pattern_validation_core_extensions.md](active/architecture/architecture_pattern_validation_core_extensions.md)**
  - Core architecture pattern validation and extensions
  - Use when: Validating architectural decisions

- **[pkg_architecture_analysis_2025_09_30.md](active/architecture/pkg_architecture_analysis_2025_09_30.md)**
  - Package architecture analysis and dependency review
  - Use when: Understanding package structure

### Golden Rules & Validation (`active/golden-rules/`)

- **[golden_rules_tiered_compliance_system.md](active/golden-rules/golden_rules_tiered_compliance_system.md)**
  - 33 architectural validators with severity tiers (CRITICAL/ERROR/WARNING/INFO)
  - Use when: Understanding or enforcing golden rules

- **[ast_vs_graph_validator_safety_analysis.md](active/golden-rules/ast_vs_graph_validator_safety_analysis.md)**
  - AST validator vs graph validator safety comparison
  - Use when: Choosing validation approach

- **[phase1_graph_validator_integration_results.md](active/golden-rules/phase1_graph_validator_integration_results.md)**
  - Graph-based dependency validator integration results
  - Use when: Understanding graph validator deployment

- **[tiered_compliance_implementation_plan.md](active/golden-rules/tiered_compliance_implementation_plan.md)** (621 lines)
  - Future roadmap for compliance system enhancements
  - Use when: Planning compliance improvements

- **[tiered_compliance_status.md](active/golden-rules/tiered_compliance_status.md)**
  - Current compliance metrics and enforcement status
  - Use when: Checking compliance progress

- **[validator_dynamic_import_limitation.md](active/golden-rules/validator_dynamic_import_limitation.md)** (414 lines)
  - AST validator constraints and dynamic import challenges
  - Use when: Working on golden rules validation

### Workflows & Guides (`active/workflows/`)

- **[cicd_quality_gates_guide.md](active/workflows/cicd_quality_gates_guide.md)** (504 lines)
  - Automated quality enforcement and CI/CD pipeline setup
  - Use when: Setting up quality gates or CI/CD

- **[hybrid_solver_deployment_guide.md](active/workflows/hybrid_solver_deployment_guide.md)**
  - EcoSystemiser hybrid solver deployment procedures
  - Use when: Deploying hybrid solver updates

- **[python_311_upgrade_guide.md](active/workflows/python_311_upgrade_guide.md)**
  - Python 3.11 migration guide and compatibility notes
  - Use when: Upgrading Python version

- **[rag_deployment_guide.md](active/workflows/rag_deployment_guide.md)**
  - RAG (Retrieval-Augmented Generation) deployment procedures
  - Use when: Deploying RAG features

- **[rag_phase2_deployment_status.md](active/workflows/rag_phase2_deployment_status.md)**
  - RAG Phase 2 deployment status and progress
  - Use when: Tracking RAG deployment

- **[rag_phase2_deployment_success.md](active/workflows/rag_phase2_deployment_success.md)**
  - RAG Phase 2 deployment completion report
  - Use when: Understanding RAG deployment outcomes

- **[security_hardening_guide.md](active/workflows/security_hardening_guide.md)**
  - Security best practices and hardening procedures
  - Use when: Implementing security features or auditing

---

## Archived Documentation

### EcoSystemiser Projects (`archive/ecosystemiser/`)

6 files covering solver implementations, hardening, and optimization work.

### Syntax Fixes & Code Red (`archive/syntax-fixes/`)

6 files documenting emergency syntax fixes and trailing comma issues (Oct 2025).

### Completed Sessions & Milestones (`archive/2025-10/`)

53 files including:
- Phase 1/2/3 completion reports
- Session handoffs and status updates
- Platform status snapshots
- Completed project milestones (PROJECT AEGIS, RAG Platform, Guardian Agent)
- Foundation fortification missions
- Database integration phases
- Orchestration extraction and migration

---

## Quick Reference by Use Case

### I want to...

**Get started as an AI agent**
1. Read: [AI_AGENT_START_HERE.md](../AI_AGENT_START_HERE.md)
2. Then: [.claude/CLAUDE.md](../.claude/CLAUDE.md)
3. Reference: [ARCHITECTURE.md](../ARCHITECTURE.md)

**Understand the platform**
1. Start: [ARCHITECTURE.md](../ARCHITECTURE.md)
2. Deep dive: [Golden Rules System](active/golden-rules/golden_rules_tiered_compliance_system.md)
3. Reference: [Config System Audit](active/config/config_system_audit.md)

**Migrate to dependency injection**
1. Read: [Config Migration Guide](active/config/config_migration_guide_comprehensive.md)
2. Reference: EcoSystemiser config bridge examples
3. Validate: Golden Rule 24 enforcement

**Set up quality gates**
1. Follow: [CI/CD Quality Gates Guide](active/workflows/cicd_quality_gates_guide.md)
2. Reference: [Golden Rules System](active/golden-rules/golden_rules_tiered_compliance_system.md)
3. Check: [Compliance Status](active/golden-rules/tiered_compliance_status.md)

**Fix code quality issues**
1. Identify: [Antipattern Assessment](active/architecture/antipattern_assessment_and_remediation.md)
2. Remediate: Follow golden rules validation
3. Validate: Run `python scripts/validation/validate_golden_rules.py`

**Improve security**
1. Follow: [Security Hardening Guide](active/workflows/security_hardening_guide.md)
2. Validate: Security golden rules (Rule 26: no hardcoded paths)

**Deploy RAG features**
1. Read: [RAG Deployment Guide](active/workflows/rag_deployment_guide.md)
2. Check: [RAG Phase 2 Status](active/workflows/rag_phase2_deployment_status.md)

---

## By Complexity

### Comprehensive Guides (500+ lines)
- [Config Migration Guide](active/config/config_migration_guide_comprehensive.md) - 836 lines
- [Tiered Compliance Plan](active/golden-rules/tiered_compliance_implementation_plan.md) - 621 lines
- [Config System Audit](active/config/config_system_audit.md) - 545 lines
- [CI/CD Quality Gates](active/workflows/cicd_quality_gates_guide.md) - 504 lines

### Reference Documents (300-500 lines)
- [Antipattern Assessment](active/architecture/antipattern_assessment_and_remediation.md) - 466 lines
- [Validator Import Limitation](active/golden-rules/validator_dynamic_import_limitation.md) - 414 lines

### Quick References & Summaries
- All other active documentation files

---

## Directory Structure

```
claudedocs/
├── README.md              # This index file
├── INDEX.md               # (legacy, same content)
├── active/
│   ├── config/           # 4 files - Configuration standards
│   ├── architecture/     # 5 files - Architecture patterns
│   ├── golden-rules/     # 6 files - Validation and compliance
│   └── workflows/        # 7 files - Deployment and guides
└── archive/
    ├── ecosystemiser/    # 6 files - EcoSystemiser projects
    ├── syntax-fixes/     # 6 files - Emergency syntax fixes
    └── 2025-10/          # 53 files - Completed sessions and milestones
```

---

## Contributing to Documentation

### Adding New Docs
- Place in appropriate `active/` subdirectory
- Use descriptive filenames: `{topic}_{type}.md`
- Add entry to this INDEX.md
- Update last updated date below

### Archiving Docs
- Move to appropriate `archive/` subdirectory (by topic or date)
- Remove from active sections above
- Keep filename for traceability

### Updating Existing Docs
- Follow "Update, Don't Create" principle (see `.claude/CLAUDE.md`)
- Update comprehensive guides rather than creating new dated snapshots
- Update this INDEX.md if document purpose changes

---

**Last Updated**: 2025-10-03 (Configuration Hardening Complete)
**Active Files**: 22 files (4 config + 5 architecture + 6 golden-rules + 7 workflows)
**Archive Files**: 65 files (6 ecosystemiser + 6 syntax-fixes + 53 sessions/milestones)
