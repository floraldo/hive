"""
Comprehensive tests for hive-graph Pydantic models.

Tests all node types, edge relationships, and CodeGraph operations.
"""
import pytest
from pydantic import ValidationError
from hive_graph import ClassDefinition, CodeFile, CodeGraph, Edge, EdgeType, FunctionDefinition, ImportStatement, ModuleDefinition

@pytest.mark.core
class TestCodeFile:
    """Tests for CodeFile model."""

    @pytest.mark.core
    def test_create_minimal(self) -> None:
        """Test creating a CodeFile with minimal required fields."""
        file = CodeFile(path='/test/file.py', language='python')
        assert file.path == '/test/file.py'
        assert file.language == 'python'
        assert file.size_bytes == 0
        assert file.hash is None
        assert file.lines_of_code == 0

    @pytest.mark.core
    def test_create_full(self) -> None:
        """Test creating a CodeFile with all fields."""
        file = CodeFile(path='/test/file.py', language='python', size_bytes=1024, hash='abc123', lines_of_code=50)
        assert file.path == '/test/file.py'
        assert file.size_bytes == 1024
        assert file.hash == 'abc123'
        assert file.lines_of_code == 50

    @pytest.mark.core
    def test_get_id(self) -> None:
        """Test get_id() method returns correct format."""
        file = CodeFile(path='/test/file.py', language='python')
        assert file.get_id() == 'file:/test/file.py'

    @pytest.mark.core
    def test_validation_error(self) -> None:
        """Test that missing required fields raise ValidationError."""
        with pytest.raises(ValidationError):
            CodeFile(path='/test/file.py')

@pytest.mark.core
class TestModuleDefinition:
    """Tests for ModuleDefinition model."""

    @pytest.mark.core
    def test_create_module(self) -> None:
        """Test creating a module definition."""
        module = ModuleDefinition(name='hive_graph.models', file_path='/src/hive_graph/models.py')
        assert module.name == 'hive_graph.models'
        assert module.file_path == '/src/hive_graph/models.py'
        assert module.docstring is None
        assert module.is_package is False

    @pytest.mark.core
    def test_create_package(self) -> None:
        """Test creating a package (with __init__.py)."""
        package = ModuleDefinition(name='hive_graph', file_path='/src/hive_graph/__init__.py', docstring='Knowledge graph package', is_package=True)
        assert package.is_package is True
        assert package.docstring == 'Knowledge graph package'

    @pytest.mark.core
    def test_get_id(self) -> None:
        """Test get_id() method returns correct format."""
        module = ModuleDefinition(name='test.module', file_path='/test.py')
        assert module.get_id() == 'module:test.module'

@pytest.mark.core
class TestClassDefinition:
    """Tests for ClassDefinition model."""

    @pytest.mark.core
    def test_create_simple_class(self) -> None:
        """Test creating a simple class definition."""
        cls = ClassDefinition(name='MyClass', qualified_name='module.MyClass', file_path='/test/module.py', line_start=10, line_end=20)
        assert cls.name == 'MyClass'
        assert cls.qualified_name == 'module.MyClass'
        assert cls.line_start == 10
        assert cls.line_end == 20
        assert cls.base_classes == []
        assert cls.is_abstract is False

    @pytest.mark.core
    def test_create_class_with_inheritance(self) -> None:
        """Test creating a class with base classes."""
        cls = ClassDefinition(name='MyClass', qualified_name='module.MyClass', file_path='/test/module.py', line_start=10, line_end=20, base_classes=['BaseClass', 'Mixin'])
        assert cls.base_classes == ['BaseClass', 'Mixin']

    @pytest.mark.core
    def test_create_abstract_class(self) -> None:
        """Test creating an abstract class."""
        cls = ClassDefinition(name='MyClass', qualified_name='module.MyClass', file_path='/test/module.py', line_start=10, line_end=20, is_abstract=True)
        assert cls.is_abstract is True

    @pytest.mark.core
    def test_class_with_decorators(self) -> None:
        """Test creating a class with decorators."""
        cls = ClassDefinition(name='MyClass', qualified_name='module.MyClass', file_path='/test/module.py', line_start=10, line_end=20, decorators=['dataclass', 'frozen'])
        assert cls.decorators == ['dataclass', 'frozen']

    @pytest.mark.core
    def test_get_id(self) -> None:
        """Test get_id() method returns correct format."""
        cls = ClassDefinition(name='MyClass', qualified_name='module.MyClass', file_path='/test/module.py', line_start=10, line_end=20)
        assert cls.get_id() == 'class:module.MyClass'

@pytest.mark.core
class TestFunctionDefinition:
    """Tests for FunctionDefinition model."""

    @pytest.mark.core
    def test_create_simple_function(self) -> None:
        """Test creating a simple function definition."""
        func = FunctionDefinition(name='my_function', qualified_name='module.my_function', file_path='/test/module.py', line_start=5, line_end=10, signature='def my_function(x: int) -> str')
        assert func.name == 'my_function'
        assert func.qualified_name == 'module.my_function'
        assert func.is_async is False
        assert func.is_method is False
        assert func.is_static is False

    @pytest.mark.core
    def test_create_async_function(self) -> None:
        """Test creating an async function."""
        func = FunctionDefinition(name='my_async_function', qualified_name='module.my_async_function', file_path='/test/module.py', line_start=5, line_end=10, signature='async def my_async_function() -> None', is_async=True)
        assert func.is_async is True

    @pytest.mark.core
    def test_create_method(self) -> None:
        """Test creating a class method."""
        func = FunctionDefinition(name='my_method', qualified_name='MyClass.my_method', file_path='/test/module.py', line_start=5, line_end=10, signature='def my_method(self, x: int) -> None', is_method=True)
        assert func.is_method is True

    @pytest.mark.core
    def test_create_classmethod(self) -> None:
        """Test creating a classmethod."""
        func = FunctionDefinition(name='my_classmethod', qualified_name='MyClass.my_classmethod', file_path='/test/module.py', line_start=5, line_end=10, signature='def my_classmethod(cls) -> None', is_classmethod=True, decorators=['classmethod'])
        assert func.is_classmethod is True
        assert 'classmethod' in func.decorators

    @pytest.mark.core
    def test_function_with_parameters(self) -> None:
        """Test function with parameter metadata."""
        func = FunctionDefinition(name='my_function', qualified_name='module.my_function', file_path='/test/module.py', line_start=5, line_end=10, signature="def my_function(x: int, y: str = 'default') -> bool", parameters=[{'name': 'x', 'type': 'int', 'default': None}, {'name': 'y', 'type': 'str', 'default': "'default'"}], return_type='bool')
        assert len(func.parameters) == 2
        assert func.return_type == 'bool'

    @pytest.mark.core
    def test_get_id(self) -> None:
        """Test get_id() method returns correct format."""
        func = FunctionDefinition(name='my_function', qualified_name='module.my_function', file_path='/test/module.py', line_start=5, line_end=10, signature='def my_function() -> None')
        assert func.get_id() == 'function:module.my_function'

@pytest.mark.core
class TestImportStatement:
    """Tests for ImportStatement model."""

    @pytest.mark.core
    def test_create_simple_import(self) -> None:
        """Test creating a simple import statement."""
        imp = ImportStatement(source_module='my_module', target_module='os', file_path='/test/module.py', line_number=1)
        assert imp.source_module == 'my_module'
        assert imp.target_module == 'os'
        assert imp.imported_names == []
        assert imp.alias is None

    @pytest.mark.core
    def test_create_from_import(self) -> None:
        """Test creating a 'from X import Y' statement."""
        imp = ImportStatement(source_module='my_module', target_module='os.path', imported_names=['join', 'exists'], file_path='/test/module.py', line_number=2)
        assert imp.imported_names == ['join', 'exists']

    @pytest.mark.core
    def test_create_import_with_alias(self) -> None:
        """Test creating an import with alias."""
        imp = ImportStatement(source_module='my_module', target_module='numpy', alias='np', file_path='/test/module.py', line_number=3)
        assert imp.alias == 'np'

    @pytest.mark.core
    def test_get_id(self) -> None:
        """Test get_id() method returns correct format."""
        imp = ImportStatement(source_module='my_module', target_module='os', file_path='/test/module.py', line_number=1)
        assert imp.get_id() == 'import:my_module:os:1'

@pytest.mark.core
class TestEdge:
    """Tests for Edge model."""

    @pytest.mark.core
    def test_create_edge(self) -> None:
        """Test creating an edge."""
        edge = Edge(source='file:/test/file.py', target='module:test', edge_type=EdgeType.DEFINED_IN)
        assert edge.source == 'file:/test/file.py'
        assert edge.target == 'module:test'
        assert edge.edge_type == EdgeType.DEFINED_IN
        assert edge.metadata == {}

    @pytest.mark.core
    def test_create_edge_with_metadata(self) -> None:
        """Test creating an edge with metadata."""
        edge = Edge(source='function:module.func_a', target='function:module.func_b', edge_type=EdgeType.CALLS, metadata={'line_number': 42, 'count': 5})
        assert edge.metadata['line_number'] == 42
        assert edge.metadata['count'] == 5

    @pytest.mark.core
    def test_edge_hashable(self) -> None:
        """Test that edges are hashable for set operations."""
        edge1 = Edge(source='a', target='b', edge_type=EdgeType.CALLS)
        edge2 = Edge(source='a', target='b', edge_type=EdgeType.CALLS)
        assert hash(edge1) == hash(edge2)
        edge_set = {edge1, edge2}
        assert len(edge_set) == 1

    @pytest.mark.core
    def test_all_edge_types(self) -> None:
        """Test creating edges with all EdgeType values."""
        edge_types = [EdgeType.IMPORTS, EdgeType.CALLS, EdgeType.INHERITS_FROM, EdgeType.DEFINED_IN, EdgeType.USES, EdgeType.DECORATES, EdgeType.REFERENCES, EdgeType.CONTAINS]
        for edge_type in edge_types:
            edge = Edge(source='a', target='b', edge_type=edge_type)
            assert edge.edge_type == edge_type

@pytest.mark.core
class TestCodeGraph:
    """Tests for CodeGraph model."""

    @pytest.mark.core
    def test_create_empty_graph(self) -> None:
        """Test creating an empty graph."""
        graph = CodeGraph()
        assert graph.node_count() == 0
        assert graph.edge_count() == 0
        assert graph.nodes == {}
        assert graph.edges == []

    @pytest.mark.core
    def test_add_node(self) -> None:
        """Test adding nodes to graph."""
        graph = CodeGraph()
        file = CodeFile(path='/test/file.py', language='python')
        graph.add_node(file)
        assert graph.node_count() == 1
        assert graph.get_node('file:/test/file.py') == file

    @pytest.mark.core
    def test_add_multiple_nodes(self) -> None:
        """Test adding multiple different node types."""
        graph = CodeGraph()
        file = CodeFile(path='/test/file.py', language='python')
        module = ModuleDefinition(name='test', file_path='/test/file.py')
        cls = ClassDefinition(name='TestClass', qualified_name='test.TestClass', file_path='/test/file.py', line_start=1, line_end=10)
        graph.add_node(file)
        graph.add_node(module)
        graph.add_node(cls)
        assert graph.node_count() == 3

    @pytest.mark.core
    def test_add_edge(self) -> None:
        """Test adding edges to graph."""
        graph = CodeGraph()
        edge = Edge(source='file:/test/file.py', target='module:test', edge_type=EdgeType.DEFINED_IN)
        graph.add_edge(edge)
        assert graph.edge_count() == 1

    @pytest.mark.core
    def test_get_edges_from(self) -> None:
        """Test querying outgoing edges from a node."""
        graph = CodeGraph()
        edge1 = Edge(source='a', target='b', edge_type=EdgeType.CALLS)
        edge2 = Edge(source='a', target='c', edge_type=EdgeType.CALLS)
        edge3 = Edge(source='b', target='c', edge_type=EdgeType.CALLS)
        graph.add_edge(edge1)
        graph.add_edge(edge2)
        graph.add_edge(edge3)
        edges_from_a = graph.get_edges_from('a')
        assert len(edges_from_a) == 2
        assert edge1 in edges_from_a
        assert edge2 in edges_from_a

    @pytest.mark.core
    def test_get_edges_to(self) -> None:
        """Test querying incoming edges to a node."""
        graph = CodeGraph()
        edge1 = Edge(source='a', target='c', edge_type=EdgeType.CALLS)
        edge2 = Edge(source='b', target='c', edge_type=EdgeType.CALLS)
        edge3 = Edge(source='c', target='d', edge_type=EdgeType.CALLS)
        graph.add_edge(edge1)
        graph.add_edge(edge2)
        graph.add_edge(edge3)
        edges_to_c = graph.get_edges_to('c')
        assert len(edges_to_c) == 2
        assert edge1 in edges_to_c
        assert edge2 in edges_to_c

    @pytest.mark.core
    def test_get_edges_by_type(self) -> None:
        """Test querying edges by type."""
        graph = CodeGraph()
        edge1 = Edge(source='a', target='b', edge_type=EdgeType.CALLS)
        edge2 = Edge(source='a', target='c', edge_type=EdgeType.INHERITS_FROM)
        edge3 = Edge(source='b', target='c', edge_type=EdgeType.CALLS)
        graph.add_edge(edge1)
        graph.add_edge(edge2)
        graph.add_edge(edge3)
        call_edges = graph.get_edges_by_type(EdgeType.CALLS)
        assert len(call_edges) == 2
        assert edge1 in call_edges
        assert edge3 in call_edges
        inherit_edges = graph.get_edges_by_type(EdgeType.INHERITS_FROM)
        assert len(inherit_edges) == 1
        assert edge2 in inherit_edges

    @pytest.mark.core
    def test_graph_with_metadata(self) -> None:
        """Test creating graph with metadata."""
        graph = CodeGraph(metadata={'created_at': '2025-10-02', 'version': '1.0', 'description': 'Test graph'})
        assert graph.metadata['version'] == '1.0'
        assert graph.metadata['description'] == 'Test graph'

    @pytest.mark.core
    def test_complex_graph_scenario(self) -> None:
        """Test a complex graph with multiple nodes and edges."""
        graph = CodeGraph()
        file = CodeFile(path='/test/module.py', language='python')
        module = ModuleDefinition(name='test.module', file_path='/test/module.py')
        cls = ClassDefinition(name='MyClass', qualified_name='test.module.MyClass', file_path='/test/module.py', line_start=10, line_end=30, base_classes=['BaseClass'])
        func = FunctionDefinition(name='my_method', qualified_name='test.module.MyClass.my_method', file_path='/test/module.py', line_start=15, line_end=20, signature='def my_method(self) -> None', is_method=True)
        graph.add_node(file)
        graph.add_node(module)
        graph.add_node(cls)
        graph.add_node(func)
        graph.add_edge(Edge(source=module.get_id(), target=file.get_id(), edge_type=EdgeType.DEFINED_IN))
        graph.add_edge(Edge(source=cls.get_id(), target=module.get_id(), edge_type=EdgeType.CONTAINS))
        graph.add_edge(Edge(source=func.get_id(), target=cls.get_id(), edge_type=EdgeType.CONTAINS))
        assert graph.node_count() == 4
        assert graph.edge_count() == 3
        cls_edges = graph.get_edges_from(cls.get_id())
        assert len(cls_edges) == 1
        assert cls_edges[0].edge_type == EdgeType.CONTAINS