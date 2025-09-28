# ADR-002: Golden Rules Architectural Governance

## Status
Accepted

## Context
As the Hive platform grew, architectural drift and technical debt accumulated without systematic detection. Manual code reviews were insufficient to catch all architectural violations, leading to:
- Inconsistent patterns across the codebase
- Security vulnerabilities from unsafe operations
- Performance degradation from synchronous calls in async contexts
- Accumulation of technical debt

## Decision
We will implement the Golden Rules framework as an automated architectural governance system with:
1. 15 core rules enforced via AST analysis
2. CI/CD integration blocking merges with violations
3. Suppression mechanism with mandatory justification
4. Regular expansion of rules based on emerging patterns

The rules cover:
- Dependency patterns (no circular imports, proper injection)
- Async discipline (no sync calls in async, proper naming)
- Security (no eval/exec, SQL injection prevention)
- Clean architecture (service layer discipline, no business logic in core)

## Consequences

### Positive
- **Automated Enforcement**: Violations caught before merge, not in production
- **Consistent Architecture**: Same patterns across entire codebase
- **Technical Debt Prevention**: Issues caught early when cheap to fix
- **Team Education**: Rules teach best practices through enforcement
- **Measurable Quality**: Architecture score provides objective metrics

### Negative
- **Initial Resistance**: Developers may find rules restrictive at first
- **False Positives**: May require suppression for legitimate edge cases
- **Maintenance Overhead**: Rules need updates as patterns evolve

## Implementation
The Golden Rules are implemented in `packages/hive-tests/src/hive_tests/architectural_validators.py` and run via:
```bash
# Local validation
python scripts/validate_golden_rules.py

# CI/CD pipeline
.github/workflows/golden-rules.yml

# Suppression when necessary
# golden-rule-ignore: rule-name - Justification for exception
```

## Metrics
- Current compliance: 95% (A++ grade)
- Target: 100% (Platinum grade)
- Suppression rate: <5% (indicates rule quality)

## Related
- ADR-001: Dependency Injection Pattern
- ADR-003: Async Function Naming Convention
- ADR-004: Service Layer Architecture