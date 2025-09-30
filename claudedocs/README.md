# Hive Platform Documentation

**Purpose**: Claude-generated documentation for architectural decisions, implementation progress, and operational guides.

**Last Updated**: 2025-09-30
**Documentation Count**: 20 active files + 60 archived files

---

## Documentation Structure

This directory contains AI-generated documentation tracking the platform's evolution. Documents are organized by relevance and lifecycle:

### Active Documentation (20 files)

**Use these files** for current development, architecture decisions, and operational guidance.

### Archived Documentation (archive/)

**Historical reference only** - Progress reports, session summaries, and completed migration logs organized by category:
- `archive/sessions/` - Agent coordination logs, hardening rounds, phase reports (44 files)
- `archive/migration/` - Completed migration strategies and audits (11 files)
- `archive/optimization/` - Historical optimization reports and violation cleanup (5 files)

---

## Quick Navigation

### For Development
- [Configuration Guide](config_migration_guide_comprehensive.md) - DI patterns and best practices (836 lines)
- [CI/CD Quality Gates](cicd_quality_gates_guide.md) - Automated quality enforcement (504 lines)
- [Security Hardening](security_hardening_guide.md) - Security best practices

### For Architecture
- [Platform Status](platform_status_2025_09_30.md) - Current state and metrics (445 lines)
- [Golden Rules System](golden_rules_tiered_compliance_system.md) - 24 architectural validators
- [Validator Limitations](validator_dynamic_import_limitation.md) - AST validation constraints
- [Config System Audit](config_system_audit.md) - Configuration architecture (545 lines)

### For Current Work
- [Antipattern Assessment](antipattern_assessment_and_remediation.md) - Code smell analysis (466 lines)
- [Architectural Fixes](architectural_fix_summary.md) - Recent session work
- [Phase 3 Progress](phase3_test_implementation_progress.md) - Test implementation status

### For Historical Context
- [Project Aegis Complete](PROJECT_AEGIS_COMPLETE.md) - Configuration modernization milestone
- [Phase 2 Hardening](PHASE2_HARDENING_REPORT.md) - Code quality improvements
- [Compliance Plan](tiered_compliance_implementation_plan.md) - Future roadmap (621 lines)

### For Component History
- [Guardian Agent Refactoring](GUARDIAN_AGENT_TOOLKIT_REFACTORING_REPORT.md) - AI agent toolkit
- [QR Service Certification](QR_SERVICE_CERTIFICATION_REPORT.md) - QR service component

---

## Documentation Philosophy

### What Gets Documented Here

**DO document in claudedocs/**:
- Architectural decision records (ADRs)
- Migration strategies and completion reports
- Platform status snapshots
- Quality gate configurations
- System audits and assessments
- Session summaries of significant work

**DON'T document in claudedocs/**:
- API documentation (goes in package READMEs)
- User guides (goes in project root docs/)
- Code comments (goes in source files)
- Test documentation (goes with test files)

### Lifecycle Management

**Active Documentation**:
- Updated regularly as platform evolves
- Referenced by current development work
- Kept under 20 files for discoverability

**Archive Documentation**:
- Historical value only, not operational
- Session logs and progress reports
- Completed migrations and optimization work
- Organized by category for easy navigation

**Deprecated Documentation**:
- Removed entirely when superseded
- Duplicate reports consolidated
- Obsolete strategies replaced by current

---

## File Naming Conventions

**Active files** use descriptive names:
- `{topic}_{type}.md` - e.g., `config_migration_guide_comprehensive.md`
- `{component}_{purpose}.md` - e.g., `platform_status_2025_09_30.md`
- `{PROJECT_NAME}_{STATUS}.md` - e.g., `PROJECT_AEGIS_COMPLETE.md`

**Archive files** retain original names for traceability:
- Session logs: `agent2_session_complete.md`, `hardening_round7_complete.md`
- Phase reports: `phase1_completion_report.md`, `project_aegis_phase2_complete.md`
- Migration logs: `ast_migration_complete.md`, `config_di_migration_guide.md`

---

## Maintenance Guidelines

### When to Archive
- Session summaries after work completion
- Phase reports when phase finishes
- Migration guides when migration completes
- Optimization reports when changes stabilize

### When to Update Active Docs
- Platform status: after major milestones
- Architecture guides: when patterns change
- Quality gates: when rules added/modified
- Security guides: when threats discovered

### When to Deprecate
- Duplicate information consolidated elsewhere
- Obsolete strategies superseded by better approaches
- Historical logs with no reference value

---

## Archive Organization

### archive/sessions/ (44 files)
Agent coordination logs, hardening rounds 1-9, phase 1-5 reports, Project Aegis sub-phases

**Browse when**: Understanding historical decision-making process, tracking bug fix progression

### archive/migration/ (11 files)
AST migration strategy, config DI migration, golden rules compliance, validator deployment

**Browse when**: Learning from past migrations, understanding architectural evolution

### archive/optimization/ (5 files)
Optimization sessions, violation cleanup strategies, golden rules optimization results

**Browse when**: Understanding performance improvement history, code quality trends

---

## Documentation Quality Standards

**Comprehensive**: Cover problem, solution, reasoning, outcomes
**Actionable**: Include code examples, commands, validation steps
**Searchable**: Use clear headings, keywords, cross-references
**Maintainable**: Date-stamp, version, mark superseded content
**Professional**: No marketing language, objective assessments

---

## Getting Help

**For documentation questions**: Check [INDEX.md](INDEX.md) for categorized listing

**For platform questions**: See main project [README.md](../README.md) and [.claude/CLAUDE.md](../.claude/CLAUDE.md)

**For AI agent questions**: Reference `.claude/` configuration files in project root

---

**Documentation maintained by**: AI agents (Claude Code)
**Archive policy**: 80% deprecation target, keep only operational docs active
**Review cadence**: Major milestones and quarterly cleanup
