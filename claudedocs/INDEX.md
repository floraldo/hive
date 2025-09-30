# Hive Documentation Index

**Quick reference guide to all active documentation** (20 files)

---

## Architecture & Design

### Platform Architecture
- **[Platform Status 2025-09-30](platform_status_2025_09_30.md)** (445 lines)
  - Current metrics, component health, technical debt status
  - **Use when**: Getting overall platform state snapshot

- **[Config System Audit](config_system_audit.md)** (545 lines)
  - Configuration architecture, patterns, dependency injection
  - **Use when**: Understanding config system design

- **[Validator Dynamic Import Limitation](validator_dynamic_import_limitation.md)** (414 lines)
  - AST validator constraints, dynamic import challenges
  - **Use when**: Working on golden rules validation

### Component Architecture
- **[Guardian Agent Toolkit Refactoring](GUARDIAN_AGENT_TOOLKIT_REFACTORING_REPORT.md)**
  - AI agent framework refactoring report
  - **Use when**: Understanding agent architecture evolution

- **[QR Service Certification](QR_SERVICE_CERTIFICATION_REPORT.md)**
  - QR service component certification and validation
  - **Use when**: Understanding QR service design

---

## Development Guides

### Configuration Management
- **[Config Migration Guide - Comprehensive](config_migration_guide_comprehensive.md)** (836 lines)
  - Complete DI pattern migration guide with recipes and examples
  - **Use when**: Migrating code to dependency injection
  - **Gold standard**: EcoSystemiser config bridge pattern

### Quality & Testing
- **[CI/CD Quality Gates Guide](cicd_quality_gates_guide.md)** (504 lines)
  - Automated quality enforcement, pre-commit hooks, validation
  - **Use when**: Setting up quality gates or CI/CD pipelines

- **[Golden Rules Tiered Compliance System](golden_rules_tiered_compliance_system.md)**
  - 24 architectural validators with severity tiers
  - **Use when**: Understanding or modifying golden rules

- **[Tiered Compliance Status](tiered_compliance_status.md)**
  - Current compliance metrics and enforcement status
  - **Use when**: Checking compliance progress

- **[Tiered Compliance Implementation Plan](tiered_compliance_implementation_plan.md)** (621 lines)
  - Future roadmap for compliance system enhancements
  - **Use when**: Planning compliance improvements

### Security
- **[Security Hardening Guide](security_hardening_guide.md)**
  - Security best practices and hardening procedures
  - **Use when**: Implementing security features or auditing

---

## Current Work & Progress

### Active Development
- **[Architectural Fix Summary](architectural_fix_summary.md)**
  - Recent architectural violation fixes (Agent 18 session)
  - **Use when**: Understanding recent architectural work

- **[Phase 3 Test Implementation Progress](phase3_test_implementation_progress.md)**
  - Test implementation status for hive-ai package
  - **Use when**: Tracking test coverage progress

### Code Quality
- **[Antipattern Assessment and Remediation](antipattern_assessment_and_remediation.md)** (466 lines)
  - Code smell analysis, antipattern identification, fixes
  - **Use when**: Understanding code quality issues

- **[Antipattern Implementation Summary](antipattern_implementation_summary.md)**
  - Summary of antipattern fixes implemented
  - **Use when**: Tracking antipattern remediation

- **[EcoSystemiser Hardening Progress](ecosystemiser_hardening_progress.md)**
  - EcoSystemiser-specific code hardening work
  - **Use when**: Working on EcoSystemiser quality

- **[EcoSystemiser Performance Optimization](ecosystemiser_performance_optimization.md)**
  - Performance improvements for EcoSystemiser
  - **Use when**: Optimizing EcoSystemiser performance

---

## Project Milestones

### Completed Projects
- **[PROJECT AEGIS COMPLETE](PROJECT_AEGIS_COMPLETE.md)**
  - Configuration modernization project completion
  - **Use when**: Understanding config modernization history

- **[PHASE2 HARDENING REPORT](PHASE2_HARDENING_REPORT.md)**
  - Code quality hardening phase 2 completion
  - **Use when**: Understanding hardening progress

### Ongoing Work
- **[Scripts Round 3 Consolidation Complete](scripts_round3_consolidation_complete.md)**
  - Scripts organization and consolidation work
  - **Use when**: Understanding scripts reorganization

---

## By Use Case

### I want to...

**Understand the platform**
1. Start: [Platform Status](platform_status_2025_09_30.md)
2. Then: [Config System Audit](config_system_audit.md)
3. Deep dive: [Golden Rules System](golden_rules_tiered_compliance_system.md)

**Migrate to dependency injection**
1. Read: [Config Migration Guide](config_migration_guide_comprehensive.md)
2. Reference: EcoSystemiser config bridge examples
3. Validate: Golden Rule 24 enforcement

**Set up quality gates**
1. Follow: [CI/CD Quality Gates Guide](cicd_quality_gates_guide.md)
2. Reference: [Golden Rules System](golden_rules_tiered_compliance_system.md)
3. Check: [Compliance Status](tiered_compliance_status.md)

**Fix code quality issues**
1. Identify: [Antipattern Assessment](antipattern_assessment_and_remediation.md)
2. Remediate: [Antipattern Implementation Summary](antipattern_implementation_summary.md)
3. Validate: [Platform Status](platform_status_2025_09_30.md) metrics

**Improve security**
1. Follow: [Security Hardening Guide](security_hardening_guide.md)
2. Audit: Component-specific security docs
3. Validate: Security golden rules

**Add tests**
1. Check: [Phase 3 Test Progress](phase3_test_implementation_progress.md)
2. Follow: Test patterns in hive-ai tests/
3. Validate: Test coverage golden rule

---

## By File Size

### Comprehensive Guides (500+ lines)
1. [Config Migration Guide](config_migration_guide_comprehensive.md) - 836 lines
2. [Tiered Compliance Plan](tiered_compliance_implementation_plan.md) - 621 lines
3. [Config System Audit](config_system_audit.md) - 545 lines
4. [CI/CD Quality Gates](cicd_quality_gates_guide.md) - 504 lines

### Reference Documents (300-500 lines)
1. [Antipattern Assessment](antipattern_assessment_and_remediation.md) - 466 lines
2. [Platform Status](platform_status_2025_09_30.md) - 445 lines
3. [Validator Import Limitation](validator_dynamic_import_limitation.md) - 414 lines

### Reports & Summaries (< 300 lines)
- All milestone reports, progress summaries, component certifications

---

## Recently Updated

**2025-09-30** (today):
- Platform Status, Architectural Fix Summary, Phase 3 Progress
- Antipattern Assessment, Config Migration Guide
- Golden Rules updates, Compliance Status

**2025-09-29** (yesterday):
- Hardening reports, Optimization summaries
- QR Service Certification, Guardian Agent Refactoring

---

## Archive Navigation

**Need historical context?** See [archive/](archive/) directories:

- **[archive/sessions/](archive/sessions/)** (44 files) - Agent logs, hardening rounds, phase reports
- **[archive/migration/](archive/migration/)** (11 files) - Completed migrations, audits
- **[archive/optimization/](archive/optimization/)** (5 files) - Historical optimization work

**Archive policy**: 80% deprecation - Keep only operational docs active

---

## Contributing to Documentation

### Adding New Docs
- Place in `claudedocs/` root for active operational docs
- Use descriptive filenames: `{topic}_{type}.md`
- Add entry to this INDEX.md
- Update README.md last updated date

### Archiving Docs
- Move to appropriate `archive/` subdirectory
- Remove from this INDEX.md
- Keep filename for traceability

### Deprecating Docs
- Consolidate information into active docs
- Move duplicates to archive or delete
- Update references

---

**Last Updated**: 2025-09-30
**Active Documentation**: 20 files
**Archive Documentation**: 60 files
**Deprecation Target**: Achieved (75% archived)
