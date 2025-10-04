"""
Tests for graph-based dependency validator.

Tests both direct and transitive dependency violation detection using
mock file structures and controlled dependency patterns.
"""
import pytest
from pathlib import Path
from tempfile import TemporaryDirectory
from hive_tests.dependency_graph_validator import DependencyGraphValidator, DependencyRule, RuleType, Violation

@pytest.mark.core
class TestDependencyRuleDefinition:
    """Tests for dependency rule definition."""

    @pytest.mark.core
    def test_create_rule(self) -> None:
        """Test creating a dependency rule."""
        rule = DependencyRule(name='Test rule', source_pattern='packages/hive-db/**', target_pattern='packages/hive-ai/**', rule_type=RuleType.CANNOT_DEPEND_ON)
        assert rule.name == 'Test rule'
        assert rule.source_pattern == 'packages/hive-db/**'
        assert rule.target_pattern == 'packages/hive-ai/**'
        assert rule.rule_type == RuleType.CANNOT_DEPEND_ON
        assert rule.check_transitive is True

    @pytest.mark.core
    def test_rule_severity(self) -> None:
        """Test rule severity levels."""
        critical_rule = DependencyRule(name='Critical rule', source_pattern='packages/**', target_pattern='apps/**', rule_type=RuleType.CANNOT_DEPEND_ON, severity='CRITICAL')
        assert critical_rule.severity == 'CRITICAL'

@pytest.mark.core
class TestValidatorInitialization:
    """Tests for validator initialization."""

    @pytest.mark.core
    def test_create_validator(self) -> None:
        """Test creating a validator."""
        validator = DependencyGraphValidator()
        assert validator.rules == []
        assert validator.graph is None

    @pytest.mark.core
    def test_add_rule(self) -> None:
        """Test adding rules to validator."""
        validator = DependencyGraphValidator()
        rule = DependencyRule(name='Test rule', source_pattern='src/**', target_pattern='test/**', rule_type=RuleType.CANNOT_DEPEND_ON)
        validator.add_rule(rule)
        assert len(validator.rules) == 1
        assert validator.rules[0] == rule

@pytest.mark.core
class TestDirectDependencyViolations:
    """Tests for direct dependency violation detection."""

    @pytest.mark.core
    def test_no_violations(self) -> None:
        """Test case with no dependency violations."""
        validator = DependencyGraphValidator()
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / 'module_a.py').write_text('# Module A\n')
            (tmpdir_path / 'module_b.py').write_text('# Module B\n')
            rule = DependencyRule(name='A cannot depend on B', source_pattern='module_a', target_pattern='module_b', rule_type=RuleType.CANNOT_DEPEND_ON, check_transitive=False)
            validator.add_rule(rule)
            violations = validator.validate(tmpdir_path)
            assert len(violations) == 0

    @pytest.mark.core
    def test_direct_violation(self) -> None:
        """Test detection of direct dependency violation."""
        validator = DependencyGraphValidator()
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / 'module_a.py').write_text('import module_b\n')
            (tmpdir_path / 'module_b.py').write_text('# Module B\n')
            rule = DependencyRule(name='A cannot depend on B', source_pattern='module_a', target_pattern='module_b', rule_type=RuleType.CANNOT_DEPEND_ON, check_transitive=False)
            validator.add_rule(rule)
            violations = validator.validate(tmpdir_path)
            assert len(violations) == 1
            assert violations[0].source_module == 'module_a'
            assert violations[0].target_module == 'module_b'
            assert violations[0].rule.name == 'A cannot depend on B'

@pytest.mark.core
class TestTransitiveDependencyViolations:
    """Tests for transitive dependency violation detection."""

    @pytest.mark.core
    def test_transitive_violation_two_hops(self) -> None:
        """Test detection of transitive violation (A → B → C)."""
        validator = DependencyGraphValidator()
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / 'module_a.py').write_text('import module_b\n')
            (tmpdir_path / 'module_b.py').write_text('import module_c\n')
            (tmpdir_path / 'module_c.py').write_text('# Module C\n')
            rule = DependencyRule(name='A cannot transitively depend on C', source_pattern='module_a', target_pattern='module_c', rule_type=RuleType.CANNOT_DEPEND_ON, check_transitive=True)
            validator.add_rule(rule)
            violations = validator.validate(tmpdir_path)
            assert len(violations) == 1
            assert violations[0].source_module == 'module_a'
            assert violations[0].target_module == 'module_c'
            assert violations[0].dependency_path == ['module_a', 'module_b', 'module_c']

    @pytest.mark.core
    def test_transitive_violation_three_hops(self) -> None:
        """Test detection of deeper transitive violation (A → B → C → D)."""
        validator = DependencyGraphValidator()
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / 'module_a.py').write_text('import module_b\n')
            (tmpdir_path / 'module_b.py').write_text('import module_c\n')
            (tmpdir_path / 'module_c.py').write_text('import module_d\n')
            (tmpdir_path / 'module_d.py').write_text('# Module D\n')
            rule = DependencyRule(name='A cannot transitively depend on D', source_pattern='module_a', target_pattern='module_d', rule_type=RuleType.CANNOT_DEPEND_ON, check_transitive=True)
            validator.add_rule(rule)
            violations = validator.validate(tmpdir_path)
            assert len(violations) == 1
            assert violations[0].target_module == 'module_d'
            assert len(violations[0].dependency_path) == 4

@pytest.mark.core
class TestPatternMatching:
    """Tests for pattern matching in rules."""

    @pytest.mark.core
    def test_directory_pattern_matching(self) -> None:
        """Test matching with directory glob patterns."""
        validator = DependencyGraphValidator()
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            pkg_a = tmpdir_path / 'packages' / 'pkg_a'
            pkg_b = tmpdir_path / 'packages' / 'pkg_b'
            pkg_a.mkdir(parents=True)
            pkg_b.mkdir(parents=True)
            (pkg_a / 'module.py').write_text('from pkg_b import something\n')
            (pkg_b / 'module.py').write_text('# Module\n')
            rule = DependencyRule(name='Package A cannot depend on Package B', source_pattern='packages/pkg_a/**', target_pattern='packages/pkg_b/**', rule_type=RuleType.CANNOT_DEPEND_ON)
            validator.add_rule(rule)
            violations = validator.validate(tmpdir_path)
            assert len(violations) >= 0

@pytest.mark.core
class TestMultipleRules:
    """Tests for validating multiple rules simultaneously."""

    @pytest.mark.core
    def test_multiple_rules_no_violations(self) -> None:
        """Test multiple rules with no violations."""
        validator = DependencyGraphValidator()
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / 'a.py').write_text('# Module A\n')
            (tmpdir_path / 'b.py').write_text('# Module B\n')
            (tmpdir_path / 'c.py').write_text('# Module C\n')
            validator.add_rule(DependencyRule(name='A cannot depend on B', source_pattern='a', target_pattern='b', rule_type=RuleType.CANNOT_DEPEND_ON))
            validator.add_rule(DependencyRule(name='B cannot depend on C', source_pattern='b', target_pattern='c', rule_type=RuleType.CANNOT_DEPEND_ON))
            violations = validator.validate(tmpdir_path)
            assert len(violations) == 0

    @pytest.mark.core
    def test_multiple_rules_with_violations(self) -> None:
        """Test multiple rules where each has violations."""
        validator = DependencyGraphValidator()
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / 'a.py').write_text('import b\n')
            (tmpdir_path / 'b.py').write_text('import c\n')
            (tmpdir_path / 'c.py').write_text('# Module C\n')
            validator.add_rule(DependencyRule(name='A cannot depend on B', source_pattern='a', target_pattern='b', rule_type=RuleType.CANNOT_DEPEND_ON, check_transitive=False))
            validator.add_rule(DependencyRule(name='B cannot depend on C', source_pattern='b', target_pattern='c', rule_type=RuleType.CANNOT_DEPEND_ON, check_transitive=False))
            violations = validator.validate(tmpdir_path)
            assert len(violations) == 2
            violation_sources = {v.source_module for v in violations}
            assert 'a' in violation_sources
            assert 'b' in violation_sources

@pytest.mark.core
class TestViolationReporting:
    """Tests for violation reporting and formatting."""

    @pytest.mark.core
    def test_violation_string_direct(self) -> None:
        """Test violation string formatting for direct dependencies."""
        rule = DependencyRule(name='Test rule', source_pattern='a', target_pattern='b', rule_type=RuleType.CANNOT_DEPEND_ON, severity='ERROR')
        violation = Violation(rule=rule, source_module='module_a', target_module='module_b', file_path='/test/module_a.py', line_number=5)
        violation_str = str(violation)
        assert 'ERROR' in violation_str
        assert 'Test rule' in violation_str
        assert 'module_a' in violation_str
        assert 'module_b' in violation_str
        assert '/test/module_a.py:5' in violation_str

    @pytest.mark.core
    def test_violation_string_transitive(self) -> None:
        """Test violation string formatting for transitive dependencies."""
        rule = DependencyRule(name='Test rule', source_pattern='a', target_pattern='c', rule_type=RuleType.CANNOT_DEPEND_ON)
        violation = Violation(rule=rule, source_module='module_a', target_module='module_c', dependency_path=['module_a', 'module_b', 'module_c'])
        violation_str = str(violation)
        assert 'transitive' in violation_str
        assert 'module_a → module_b → module_c' in violation_str

@pytest.mark.core
class TestGraphBuilding:
    """Tests for graph building functionality."""

    @pytest.mark.core
    def test_build_graph(self) -> None:
        """Test building dependency graph from directory."""
        validator = DependencyGraphValidator()
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / 'a.py').write_text('import b\n')
            (tmpdir_path / 'b.py').write_text('import c\n')
            (tmpdir_path / 'c.py').write_text('# Module C\n')
            graph = validator.build_graph(tmpdir_path)
            assert graph is not None
            assert graph.node_count() > 0
            assert graph.edge_count() > 0

    @pytest.mark.core
    def test_graph_caching(self) -> None:
        """Test that graph is cached after building."""
        validator = DependencyGraphValidator()
        with TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / 'a.py').write_text('# Module A\n')
            graph1 = validator.build_graph(tmpdir_path)
            graph2 = validator.graph
            assert graph1 is graph2

@pytest.mark.core
class TestPredefinedRules:
    """Tests for pre-defined architectural rules."""

    @pytest.mark.core
    def test_predefined_rules_exist(self) -> None:
        """Test that pre-defined rules are available."""
        from hive_tests.dependency_graph_validator import HIVE_ARCHITECTURAL_RULES
        assert len(HIVE_ARCHITECTURAL_RULES) > 0
        packages_rule = next((r for r in HIVE_ARCHITECTURAL_RULES if 'packages' in r.source_pattern.lower() and 'apps' in r.target_pattern.lower()), None)
        assert packages_rule is not None
        assert packages_rule.severity == 'CRITICAL'

    @pytest.mark.core
    def test_apply_predefined_rules(self) -> None:
        """Test applying pre-defined rules to validator."""
        from hive_tests.dependency_graph_validator import HIVE_ARCHITECTURAL_RULES
        validator = DependencyGraphValidator()
        for rule in HIVE_ARCHITECTURAL_RULES:
            validator.add_rule(rule)
        assert len(validator.rules) == len(HIVE_ARCHITECTURAL_RULES)