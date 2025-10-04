from hive_logging import get_logger

logger = get_logger(__name__)

"""
Hive Testing Utils - Architectural Validation and Testing Utilities

This package provides the "Golden Tests" that enforce platform-wide
architectural standards and patterns across the entire Hive ecosystem.
"""

__version__ = "0.1.0"

from .architectural_validators import (
    run_all_golden_rules,
    validate_app_contracts,
    validate_async_pattern_consistency,
    validate_cli_pattern_consistency,
    validate_colocated_tests,
    validate_communication_patterns,
    validate_dependency_direction,
    validate_development_tools_consistency,
    validate_error_handling_standards,
    validate_inherit_extend_pattern,
    validate_interface_contracts,
    validate_logging_standards,
    validate_no_syspath_hacks,
    validate_package_app_discipline,
    validate_package_naming_consistency,
    validate_service_layer_discipline,
    validate_single_config_source,
)
from .ast_validator import EnhancedValidator, GoldenRuleVisitor, Violation

# Test intelligence module (merged from hive-test-intelligence)
from .intelligence import (
    FailurePattern,
    FlakyTestResult,
    PackageHealthReport,
    TestIntelligenceStorage,
    TestResult,
    TestRun,
    TestStatus,
    TestType,
)
from .safe_autofix import AutofixResult, SafeGoldenRulesAutoFixer

__all__ = [
    "AutofixResult",
    # Enhanced AST-based validation
    "EnhancedValidator",
    "FailurePattern",
    "FlakyTestResult",
    "GoldenRuleVisitor",
    "PackageHealthReport",
    # Safe autofix (AST-ONLY, no regex)
    "SafeGoldenRulesAutoFixer",
    # Test intelligence (merged from hive-test-intelligence)
    "TestIntelligenceStorage",
    "TestResult",
    "TestRun",
    "TestStatus",
    "TestType",
    "Violation",
    # Orchestration
    "run_all_golden_rules",
    # Original validators
    "validate_app_contracts",
    "validate_async_pattern_consistency",
    "validate_cli_pattern_consistency",
    "validate_colocated_tests",
    "validate_communication_patterns",
    "validate_dependency_direction",
    "validate_development_tools_consistency",
    "validate_error_handling_standards",
    "validate_inherit_extend_pattern",
    "validate_interface_contracts",
    "validate_logging_standards",
    "validate_no_syspath_hacks",
    # Golden Rules validators
    "validate_package_app_discipline",
    "validate_package_naming_consistency",
    "validate_service_layer_discipline",
    "validate_single_config_source",
]
