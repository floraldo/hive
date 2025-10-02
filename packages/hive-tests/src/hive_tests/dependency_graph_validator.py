"""
Graph-based dependency validator using hive-graph for architectural rule enforcement.

This module provides sophisticated dependency validation by building a complete
dependency graph of the codebase and enforcing architectural rules through
graph traversal and analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from hive_graph import ASTParser, CodeGraph, EdgeType

from hive_logging import get_logger

logger = get_logger(__name__)


class RuleType(str, Enum):
    """Types of dependency rules that can be enforced."""

    CANNOT_DEPEND_ON = "CANNOT_DEPEND_ON"
    MUST_DEPEND_ON = "MUST_DEPEND_ON"
    ONLY_DEPEND_ON = "ONLY_DEPEND_ON"


@dataclass
class DependencyRule:
    """
    Declarative dependency rule definition.

    Examples:
        >>> # Layer enforcement
        >>> DependencyRule(
        ...     name="No DB → AI dependencies",
        ...     source_pattern="packages/hive-db/**",
        ...     target_pattern="packages/hive-ai/**",
        ...     rule_type=RuleType.CANNOT_DEPEND_ON,
        ... )

        >>> # Architecture boundaries
        >>> DependencyRule(
        ...     name="Packages cannot depend on apps",
        ...     source_pattern="packages/**",
        ...     target_pattern="apps/**",
        ...     rule_type=RuleType.CANNOT_DEPEND_ON,
        ... )
    """

    name: str
    source_pattern: str
    target_pattern: str
    rule_type: RuleType
    check_transitive: bool = True
    severity: str = "ERROR"


@dataclass
class Violation:
    """Represents a dependency rule violation."""

    rule: DependencyRule
    source_module: str
    target_module: str
    dependency_path: list[str] | None = None
    file_path: str | None = None
    line_number: int | None = None

    def __str__(self) -> str:
        """Human-readable violation description."""
        if self.dependency_path and len(self.dependency_path) > 2:
            path_str = " → ".join(self.dependency_path)
            return (
                f"[{self.rule.severity}] {self.rule.name}: "
                f"{self.source_module} has transitive dependency on {self.target_module} "
                f"via path: {path_str}"
            )
        else:
            location = f" at {self.file_path}:{self.line_number}" if self.file_path else ""
            return (
                f"[{self.rule.severity}] {self.rule.name}: "
                f"{self.source_module} depends on {self.target_module}{location}"
            )


class DependencyGraphValidator:
    """
    Validates architectural dependency rules using knowledge graph analysis.

    Uses hive-graph to build a complete dependency graph and enforces rules
    through graph traversal, catching both direct and transitive violations.

    Example:
        >>> validator = DependencyGraphValidator()
        >>> validator.add_rule(DependencyRule(
        ...     name="No cross-layer dependencies",
        ...     source_pattern="packages/hive-db/**",
        ...     target_pattern="packages/hive-ai/**",
        ...     rule_type=RuleType.CANNOT_DEPEND_ON,
        ... ))
        >>> violations = validator.validate(Path("packages/"))
        >>> for violation in violations:
        ...     print(violation)
    """

    def __init__(self) -> None:
        """Initialize the dependency graph validator."""
        self.rules: list[DependencyRule] = []
        self.graph: CodeGraph | None = None
        self._module_to_file: dict[str, str] = {}

    def add_rule(self, rule: DependencyRule) -> None:
        """
        Add a dependency rule to enforce.

        Args:
            rule: Dependency rule to add
        """
        self.rules.append(rule)
        logger.debug(f"Added rule: {rule.name}")

    def build_graph(self, root_path: Path) -> CodeGraph:
        """
        Build complete dependency graph for the codebase.

        Args:
            root_path: Root directory to parse

        Returns:
            Complete code graph with all dependencies
        """
        logger.info(f"Building dependency graph from {root_path}")

        parser = ASTParser()
        nodes, edges = parser.parse_directory(root_path, recursive=True)

        graph = CodeGraph()
        for node in nodes:
            graph.add_node(node)
        for edge in edges:
            graph.add_edge(edge)

        # Build module → file mapping for violation reporting
        for node_id, node in graph.nodes.items():
            if node_id.startswith("module:"):
                module_name = node_id.replace("module:", "")
                if hasattr(node, "file_path"):
                    self._module_to_file[module_name] = node.file_path

        logger.info(
            f"Graph built: {graph.node_count()} nodes, {graph.edge_count()} edges"
        )

        self.graph = graph
        return graph

    def validate(self, root_path: Path) -> list[Violation]:
        """
        Validate all dependency rules against the codebase.

        Args:
            root_path: Root directory to validate

        Returns:
            List of violations found
        """
        if self.graph is None:
            self.build_graph(root_path)

        violations: list[Violation] = []

        for rule in self.rules:
            logger.debug(f"Checking rule: {rule.name}")
            rule_violations = self._check_rule(rule)
            violations.extend(rule_violations)

            if rule_violations:
                logger.warning(
                    f"Found {len(rule_violations)} violations for rule: {rule.name}"
                )

        return violations

    def _check_rule(self, rule: DependencyRule) -> list[Violation]:
        """
        Check a single dependency rule.

        Args:
            rule: Rule to check

        Returns:
            List of violations for this rule
        """
        if self.graph is None:
            return []

        violations: list[Violation] = []

        # Get IMPORTS edges from the graph
        import_edges = self.graph.get_edges_by_type(EdgeType.IMPORTS)

        for edge in import_edges:
            source_module = edge.source.replace("module:", "")
            target_module = edge.target.replace("module:", "")

            # Check if this edge matches the rule pattern
            if self._matches_pattern(source_module, rule.source_pattern):
                if rule.rule_type == RuleType.CANNOT_DEPEND_ON:
                    # Check direct dependency
                    if self._matches_pattern(target_module, rule.target_pattern):
                        violation = Violation(
                            rule=rule,
                            source_module=source_module,
                            target_module=target_module,
                            file_path=self._module_to_file.get(source_module),
                            line_number=edge.metadata.get("line_number"),
                        )
                        violations.append(violation)

                    # Check transitive dependencies if enabled
                    elif rule.check_transitive:
                        transitive_violations = self._check_transitive_dependencies(
                            source_module, rule
                        )
                        violations.extend(transitive_violations)

        return violations

    def _check_transitive_dependencies(
        self, source_module: str, rule: DependencyRule
    ) -> list[Violation]:
        """
        Check for transitive dependency violations using graph traversal.

        Args:
            source_module: Starting module
            rule: Rule to check

        Returns:
            List of transitive violations
        """
        if self.graph is None:
            return []

        violations: list[Violation] = []

        # Find all modules reachable from source via IMPORTS edges
        reachable = self._find_reachable_modules(source_module, max_depth=10)

        for target_module, path in reachable.items():
            if self._matches_pattern(target_module, rule.target_pattern):
                # Found transitive violation
                violation = Violation(
                    rule=rule,
                    source_module=source_module,
                    target_module=target_module,
                    dependency_path=path,
                )
                violations.append(violation)

        return violations

    def _find_reachable_modules(
        self, start_module: str, max_depth: int = 10
    ) -> dict[str, list[str]]:
        """
        Find all modules reachable from start module via IMPORTS edges.

        Uses BFS to find reachable modules and track paths.

        Args:
            start_module: Starting module
            max_depth: Maximum traversal depth

        Returns:
            Dict mapping target module to dependency path
        """
        if self.graph is None:
            return {}

        reachable: dict[str, list[str]] = {}
        visited: set[str] = set()
        queue: list[tuple[str, list[str], int]] = [(start_module, [start_module], 0)]

        while queue:
            current, path, depth = queue.pop(0)

            if current in visited or depth > max_depth:
                continue

            visited.add(current)

            # Find all modules imported by current module
            current_id = f"module:{current}"
            import_edges = [
                e
                for e in self.graph.get_edges_from(current_id)
                if e.edge_type == EdgeType.IMPORTS
            ]

            for edge in import_edges:
                target_module = edge.target.replace("module:", "")

                if target_module not in visited:
                    new_path = path + [target_module]
                    reachable[target_module] = new_path
                    queue.append((target_module, new_path, depth + 1))

        return reachable

    def _matches_pattern(self, module_path: str, pattern: str) -> bool:
        """
        Check if a module path matches a glob pattern.

        Args:
            module_path: Module path to check
            pattern: Glob pattern (e.g., "packages/hive-db/**")

        Returns:
            True if module matches pattern
        """
        # Convert module name to file path for pattern matching
        if "/" in pattern or "\\" in pattern:
            # Pattern is a file path pattern
            file_path = self._module_to_file.get(module_path, "")
            if not file_path:
                return False

            # Normalize paths for comparison
            file_path = file_path.replace("\\", "/")
            pattern = pattern.replace("\\", "/")

            # Simple glob matching
            if pattern.endswith("/**"):
                # Match directory and all subdirectories
                base_pattern = pattern[:-3]
                return file_path.startswith(base_pattern)
            elif pattern.endswith("/*"):
                # Match directory only (no subdirectories)
                base_pattern = pattern[:-2]
                return file_path.startswith(base_pattern) and "/" not in file_path[
                    len(base_pattern) + 1 :
                ]
            else:
                # Exact match
                return file_path == pattern
        else:
            # Pattern is a module name pattern
            if pattern.endswith("*"):
                return module_path.startswith(pattern[:-1])
            else:
                return module_path == pattern


# Pre-defined architectural rules for Hive platform
HIVE_ARCHITECTURAL_RULES = [
    DependencyRule(
        name="Packages cannot depend on apps",
        source_pattern="packages/**",
        target_pattern="apps/**",
        rule_type=RuleType.CANNOT_DEPEND_ON,
        severity="CRITICAL",
    ),
    DependencyRule(
        name="No DB layer to AI layer dependencies",
        source_pattern="packages/hive-db/**",
        target_pattern="packages/hive-ai/**",
        rule_type=RuleType.CANNOT_DEPEND_ON,
        severity="ERROR",
    ),
    DependencyRule(
        name="No infrastructure to business logic dependencies",
        source_pattern="packages/hive-cache/**",
        target_pattern="apps/**",
        rule_type=RuleType.CANNOT_DEPEND_ON,
        severity="ERROR",
    ),
    DependencyRule(
        name="No circular dependencies between core packages",
        source_pattern="packages/hive-config/**",
        target_pattern="packages/hive-logging/**",
        rule_type=RuleType.CANNOT_DEPEND_ON,
        severity="ERROR",
    ),
]
