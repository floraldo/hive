# hive-graph

**Knowledge graph package for building and querying semantic representations of the Hive codebase.**

`hive-graph` provides infrastructure for creating and analyzing a knowledge graph of code structure and relationships. It enables deep code intelligence capabilities by capturing not just the text of code, but its semantic structure—the relationships between functions, classes, modules, and their interactions.

## Overview

### Purpose

The `hive-graph` package addresses a key limitation in traditional code analysis: while text-based approaches (like RAG) understand what code says, they don't deeply understand how code is structured. By representing code as a graph of entities (nodes) and relationships (edges), we can:

- **Enhanced Context Retrieval**: Find related code based on structural relationships, not just text similarity
- **Architectural Rule Checking**: Validate that code follows architectural patterns by querying graph structure
- **Dependency Analysis**: Trace function calls, class inheritance, and module imports
- **Impact Assessment**: Understand ripple effects of changes through relationship tracking

### Core Capabilities

```
Source Code → AST Parsing → Graph Construction → Semantic Queries
```

1. **AST Parsing**: Extract code entities from Python source files
2. **Graph Construction**: Build a semantic graph of nodes (files, classes, functions) and edges (calls, imports, inheritance)
3. **Graph Querying**: Find entities, trace relationships, analyze structure

## Installation

Add to your Poetry dependencies:

```toml
[tool.poetry.dependencies]
hive-graph = {path = "../hive-graph", develop = true}
```

Or install directly:

```bash
cd packages/hive-graph
poetry install
```

## Quick Start

### Basic Usage

```python
from pathlib import Path
from hive_graph import CodeGraph, ASTParser

# Create a new graph
graph = CodeGraph()

# Parse a Python file
parser = ASTParser()
nodes, edges = parser.parse_file(Path("my_module.py"))

# Add entities to graph
for node in nodes:
    graph.add_node(node)
for edge in edges:
    graph.add_edge(edge)

# Query the graph
print(f"Graph has {graph.node_count()} nodes and {graph.edge_count()} edges")
```

### Working with Nodes

```python
from hive_graph import CodeFile, ClassDefinition, FunctionDefinition

# Create a code file node
code_file = CodeFile(
    path="/src/hive_graph/models.py",
    language="python",
    size_bytes=1024,
    lines_of_code=50,
)

# Create a class node
my_class = ClassDefinition(
    name="MyClass",
    qualified_name="hive_graph.models.MyClass",
    file_path="/src/hive_graph/models.py",
    line_start=10,
    line_end=30,
    base_classes=["BaseModel"],
    docstring="A sample class",
)

# Create a function node
my_function = FunctionDefinition(
    name="my_method",
    qualified_name="hive_graph.models.MyClass.my_method",
    file_path="/src/hive_graph/models.py",
    line_start=15,
    line_end=20,
    signature="def my_method(self, x: int) -> str",
    is_method=True,
    is_async=False,
)

# Add to graph
graph.add_node(code_file)
graph.add_node(my_class)
graph.add_node(my_function)
```

### Working with Edges

```python
from hive_graph import Edge, EdgeType

# Create a "defined in" relationship
edge = Edge(
    source=my_class.get_id(),
    target=code_file.get_id(),
    edge_type=EdgeType.DEFINED_IN,
)
graph.add_edge(edge)

# Create an inheritance relationship
inheritance_edge = Edge(
    source="class:hive_graph.MyClass",
    target="class:hive_models.BaseModel",
    edge_type=EdgeType.INHERITS_FROM,
)
graph.add_edge(inheritance_edge)

# Create a call relationship with metadata
call_edge = Edge(
    source="function:module.caller",
    target="function:module.callee",
    edge_type=EdgeType.CALLS,
    metadata={"line_number": 42, "call_count": 3},
)
graph.add_edge(call_edge)
```

### Querying the Graph

```python
# Get a node by ID
node = graph.get_node("class:hive_graph.models.MyClass")

# Find all edges from a node (outgoing relationships)
outgoing = graph.get_edges_from("function:module.my_function")
for edge in outgoing:
    print(f"{edge.source} --[{edge.edge_type}]--> {edge.target}")

# Find all edges to a node (incoming relationships)
incoming = graph.get_edges_to("class:module.MyClass")
for edge in incoming:
    print(f"{edge.source} --[{edge.edge_type}]--> {edge.target}")

# Find all edges of a specific type
calls = graph.get_edges_by_type(EdgeType.CALLS)
print(f"Found {len(calls)} function calls")

imports = graph.get_edges_by_type(EdgeType.IMPORTS)
print(f"Found {len(imports)} import statements")
```

## API Reference

### Node Types

All nodes inherit from `hive_models.BaseModel` and provide a `get_id()` method for unique identification.

#### CodeFile

Represents a source code file.

```python
CodeFile(
    path: str,                 # File path (absolute or relative)
    language: str,             # Programming language (e.g., "python")
    size_bytes: int = 0,       # File size in bytes
    hash: str | None = None,   # Content hash for change detection
    lines_of_code: int = 0,    # Total lines of code
)
```

**ID Format**: `file:/path/to/file.py`

#### ModuleDefinition

Represents a Python module or package.

```python
ModuleDefinition(
    name: str,                      # Fully qualified module name
    file_path: str,                 # Path to module file
    docstring: str | None = None,   # Module docstring
    is_package: bool = False,       # True if __init__.py
)
```

**ID Format**: `module:fully.qualified.name`

#### ClassDefinition

Represents a class definition.

```python
ClassDefinition(
    name: str,                       # Class name
    qualified_name: str,             # Fully qualified name
    file_path: str,                  # Path to file
    line_start: int,                 # Starting line number
    line_end: int,                   # Ending line number
    docstring: str | None = None,    # Class docstring
    base_classes: list[str] = [],    # Base class names
    is_abstract: bool = False,       # Abstract class flag
    decorators: list[str] = [],      # Decorator names
)
```

**ID Format**: `class:fully.qualified.ClassName`

#### FunctionDefinition

Represents a function or method definition.

```python
FunctionDefinition(
    name: str,                           # Function name
    qualified_name: str,                 # Fully qualified name
    file_path: str,                      # Path to file
    line_start: int,                     # Starting line number
    line_end: int,                       # Ending line number
    signature: str,                      # Function signature
    docstring: str | None = None,        # Function docstring
    is_async: bool = False,              # Async function flag
    is_method: bool = False,             # Method flag
    is_static: bool = False,             # Static method flag
    is_classmethod: bool = False,        # Class method flag
    decorators: list[str] = [],          # Decorator names
    return_type: str | None = None,      # Return type annotation
    parameters: list[dict] = [],         # Parameter metadata
)
```

**ID Format**: `function:fully.qualified.function_name`

#### ImportStatement

Represents an import statement.

```python
ImportStatement(
    source_module: str,              # Module doing the importing
    target_module: str,              # Module being imported
    imported_names: list[str] = [],  # Specific imported names
    alias: str | None = None,        # Import alias
    file_path: str,                  # Path to file
    line_number: int,                # Line number of import
)
```

**ID Format**: `import:source:target:line`

### Edge Types

Edges represent relationships between code entities.

```python
class EdgeType(str, Enum):
    IMPORTS = "IMPORTS"               # Module imports another
    CALLS = "CALLS"                   # Function calls another
    INHERITS_FROM = "INHERITS_FROM"   # Class inherits from another
    DEFINED_IN = "DEFINED_IN"         # Entity defined in file/module
    USES = "USES"                     # Entity uses another
    DECORATES = "DECORATES"           # Decorator decorates target
    REFERENCES = "REFERENCES"         # Generic reference
    CONTAINS = "CONTAINS"             # Module/class contains entity
```

#### Edge

```python
Edge(
    source: str,                    # Source node ID
    target: str,                    # Target node ID
    edge_type: EdgeType,            # Type of relationship
    metadata: dict = {},            # Additional properties
)
```

Edges are **hashable** and can be used in sets for deduplication.

### CodeGraph

Container for managing the knowledge graph.

```python
graph = CodeGraph(
    nodes: dict[str, Any] = {},      # Nodes indexed by ID
    edges: list[Edge] = [],          # List of edges
    metadata: dict = {},             # Graph-level metadata
)
```

**Methods**:

- `add_node(node)`: Add a node to the graph
- `add_edge(edge)`: Add an edge to the graph
- `get_node(node_id)`: Retrieve a node by ID
- `get_edges_from(source_id)`: Get outgoing edges from a node
- `get_edges_to(target_id)`: Get incoming edges to a node
- `get_edges_by_type(edge_type)`: Get all edges of a specific type
- `node_count()`: Get total number of nodes
- `edge_count()`: Get total number of edges

### ASTParser

Parser for extracting knowledge graph entities from Python source code.

```python
parser = ASTParser()

# Parse a single file
nodes, edges = parser.parse_file(
    file_path: Path,
    module_name: str | None = None
)

# Parse a directory
nodes, edges = parser.parse_directory(
    directory: Path,
    package_name: str | None = None,
    recursive: bool = True
)
```

**Note**: Phase 1 provides the interface. Full AST parsing implementation coming in Phase 2.

## Integration Points

### RAG System Integration

The knowledge graph enhances RAG (Retrieval-Augmented Generation) by providing structural context:

```python
# Find all classes that inherit from a base class
base_class_id = "class:hive_models.BaseModel"
subclasses = [
    edge.source
    for edge in graph.get_edges_to(base_class_id)
    if edge.edge_type == EdgeType.INHERITS_FROM
]

# Use subclass information to enhance RAG context
# This gives the LLM not just text, but architectural understanding
```

### Guardian Agent Integration

Use graph queries to validate architectural rules:

```python
# Check: "No cross-app imports"
# Find all IMPORTS edges where source and target are in different apps
violations = []
for edge in graph.get_edges_by_type(EdgeType.IMPORTS):
    source_node = graph.get_node(edge.source)
    target_node = graph.get_node(edge.target)

    if is_cross_app_import(source_node, target_node):
        violations.append(edge)

if violations:
    print(f"Found {len(violations)} cross-app import violations")
```

### Dependency Analysis

Trace dependencies and assess change impact:

```python
def find_all_callers(function_id: str, graph: CodeGraph) -> set[str]:
    """Find all functions that call this function (direct or transitive)."""
    callers = set()

    for edge in graph.get_edges_to(function_id):
        if edge.edge_type == EdgeType.CALLS:
            callers.add(edge.source)
            # Recursively find callers of the caller
            callers.update(find_all_callers(edge.source, graph))

    return callers

# Find impact of changing a function
affected = find_all_callers("function:module.critical_function", graph)
print(f"Changing this function affects {len(affected)} other functions")
```

## Architecture

### Design Philosophy

1. **Pydantic Models**: All entities are Pydantic models for validation and serialization
2. **Unique IDs**: Every node has a unique ID from `get_id()` method
3. **Typed Relationships**: EdgeType enum ensures valid relationship types
4. **Extensible**: Metadata fields allow future enhancements without model changes
5. **Graph-Agnostic**: Core models work with any graph backend (NetworkX, Neo4j, etc.)

### Extensibility

The package is designed for future enhancements:

- **Phase 2**: Full AST parsing implementation
- **Phase 3**: Graph database backends (Neo4j, NetworkX persistence)
- **Phase 4**: Advanced queries (shortest path, centrality, community detection)
- **Phase 5**: Cross-language support (JavaScript, TypeScript, etc.)

### Performance Considerations

Current implementation uses in-memory storage. For large codebases:

1. Consider graph database backends (Neo4j, ArangoDB)
2. Use incremental parsing (only parse changed files)
3. Cache parsed results between runs
4. Implement lazy loading for large graphs

## Development

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run smoke tests
poetry run pytest tests/unit/test_smoke.py -v

# Run model tests
poetry run pytest tests/unit/test_models.py -v

# Run with coverage
poetry run pytest --cov=hive_graph --cov-report=html
```

### Code Quality

```bash
# Type checking
poetry run mypy src/hive_graph

# Linting
poetry run ruff check src/hive_graph

# Formatting
poetry run black src/hive_graph
```

## Roadmap

### Phase 1: Foundation ✅ (Current)

- [x] Pydantic models for nodes and edges
- [x] CodeGraph container
- [x] ASTParser interface
- [x] Comprehensive test suite
- [x] Documentation

### Phase 2: AST Parsing (Next)

- [ ] Full Python AST parsing implementation
- [ ] Extract classes, functions, imports from source files
- [ ] Build CALLS edges from function call analysis
- [ ] Build INHERITS_FROM edges from class hierarchy
- [ ] Directory traversal and module inference

### Phase 3: Graph Persistence

- [ ] NetworkX backend for graph operations
- [ ] Neo4j backend for production deployments
- [ ] Graph serialization (JSON, GraphML)
- [ ] Incremental updates (parse only changed files)

### Phase 4: Advanced Queries

- [ ] Shortest path between entities
- [ ] Centrality metrics (identify critical functions)
- [ ] Community detection (find logical modules)
- [ ] Dead code detection (unreachable nodes)

### Phase 5: Multi-Language

- [ ] JavaScript/TypeScript parsing
- [ ] Cross-language calls (Python → JS)
- [ ] Unified graph across languages

## Contributing

This package follows Hive platform standards:

- **Type Hints**: All functions must have type annotations
- **Docstrings**: All public APIs must be documented
- **Tests**: Minimum 85% coverage required
- **No Tuple Bugs**: Use modern Python 3.11+ syntax with trailing commas
- **Pydantic Models**: Inherit from `hive_models.BaseModel`

See `.claude/CLAUDE.md` for full platform guidelines.

## License

Part of the Hive Platform - Internal use only.

---

**Version**: 0.1.0
**Status**: Phase 1 Complete - Production-ready foundation
**Next**: Phase 2 - AST Parsing Implementation
