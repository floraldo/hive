"""
Smoke tests for hive-graph package.

Validates that the package can be imported and all main exports are accessible.
"""
import pytest

@pytest.mark.core
def test_package_import() -> None:
    """Test that hive_graph package can be imported."""
    import hive_graph
    assert hive_graph is not None
    assert hasattr(hive_graph, '__version__')
    assert hive_graph.__version__ == '0.1.0'

@pytest.mark.core
def test_models_import() -> None:
    """Test that all model classes can be imported."""
    from hive_graph import ClassDefinition, CodeFile, CodeGraph, Edge, EdgeType, FunctionDefinition, ImportStatement, ModuleDefinition
    assert CodeFile is not None
    assert ModuleDefinition is not None
    assert ClassDefinition is not None
    assert FunctionDefinition is not None
    assert ImportStatement is not None
    assert Edge is not None
    assert EdgeType is not None
    assert CodeGraph is not None

@pytest.mark.core
def test_parser_import() -> None:
    """Test that parser class can be imported."""
    from hive_graph import ASTParser
    assert ASTParser is not None

@pytest.mark.core
def test_all_exports() -> None:
    """Test that __all__ contains expected exports."""
    import hive_graph
    expected_exports = {'CodeFile', 'ModuleDefinition', 'ClassDefinition', 'FunctionDefinition', 'ImportStatement', 'Edge', 'EdgeType', 'CodeGraph', 'ASTParser'}
    assert hasattr(hive_graph, '__all__')
    actual_exports = set(hive_graph.__all__)
    assert actual_exports == expected_exports

@pytest.mark.core
def test_edge_type_enum() -> None:
    """Test EdgeType enum values are accessible."""
    from hive_graph import EdgeType
    assert EdgeType.IMPORTS == 'IMPORTS'
    assert EdgeType.CALLS == 'CALLS'
    assert EdgeType.INHERITS_FROM == 'INHERITS_FROM'
    assert EdgeType.DEFINED_IN == 'DEFINED_IN'
    assert EdgeType.USES == 'USES'
    assert EdgeType.DECORATES == 'DECORATES'
    assert EdgeType.REFERENCES == 'REFERENCES'
    assert EdgeType.CONTAINS == 'CONTAINS'

@pytest.mark.core
def test_basic_instantiation() -> None:
    """Test that basic model instances can be created."""
    from hive_graph import CodeFile, CodeGraph, Edge, EdgeType
    code_file = CodeFile(path='/test/file.py', language='python')
    assert code_file.path == '/test/file.py'
    assert code_file.get_id() == 'file:/test/file.py'
    edge = Edge(source='file:/test/file.py', target='module:test', edge_type=EdgeType.DEFINED_IN)
    assert edge.source == 'file:/test/file.py'
    assert edge.edge_type == EdgeType.DEFINED_IN
    graph = CodeGraph()
    assert graph.node_count() == 0
    assert graph.edge_count() == 0