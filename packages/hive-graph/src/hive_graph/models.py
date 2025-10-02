"""
Knowledge graph models for representing code structure and relationships.

Defines Pydantic models for nodes (code entities) and edges (relationships)
that form a semantic graph of the codebase.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import Field
from hive_models import BaseModel


# Edge Types
class EdgeType(str, Enum):
    """Types of relationships between code entities."""

    IMPORTS = "IMPORTS"  # Module A imports Module B
    CALLS = "CALLS"  # Function A calls Function B
    INHERITS_FROM = "INHERITS_FROM"  # Class A inherits from Class B
    DEFINED_IN = "DEFINED_IN"  # Entity is defined in File/Module
    USES = "USES"  # Function/Class uses another entity
    DECORATES = "DECORATES"  # Decorator decorates function/class
    REFERENCES = "REFERENCES"  # Generic reference relationship
    CONTAINS = "CONTAINS"  # Module contains class/function


# Node Models

class CodeFile(BaseModel):
    """Represents a source code file in the codebase."""

    path: str = Field(..., description="Absolute or relative path to the file")
    language: str = Field(..., description="Programming language (e.g., 'python', 'javascript')")
    size_bytes: int = Field(default=0, description="File size in bytes")
    hash: str | None = Field(default=None, description="Content hash (e.g., SHA256) for change detection")
    lines_of_code: int = Field(default=0, description="Total lines of code (excluding comments/blanks)")

    def get_id(self) -> str:
        """Get unique identifier for this node."""
        return f"file:{self.path}"


class ModuleDefinition(BaseModel):
    """Represents a Python module or package."""

    name: str = Field(..., description="Fully qualified module name (e.g., 'hive_graph.models')")
    file_path: str = Field(..., description="Path to the module file")
    docstring: str | None = Field(default=None, description="Module-level docstring")
    is_package: bool = Field(default=False, description="Whether this is a package (__init__.py)")

    def get_id(self) -> str:
        """Get unique identifier for this node."""
        return f"module:{self.name}"


class ClassDefinition(BaseModel):
    """Represents a class definition."""

    name: str = Field(..., description="Class name")
    qualified_name: str = Field(..., description="Fully qualified class name (e.g., 'module.ClassName')")
    file_path: str = Field(..., description="Path to file containing this class")
    line_start: int = Field(..., description="Starting line number")
    line_end: int = Field(..., description="Ending line number")
    docstring: str | None = Field(default=None, description="Class docstring")
    base_classes: list[str] = Field(default_factory=list, description="List of base class names")
    is_abstract: bool = Field(default=False, description="Whether this is an abstract class")
    decorators: list[str] = Field(default_factory=list, description="List of decorator names")

    def get_id(self) -> str:
        """Get unique identifier for this node."""
        return f"class:{self.qualified_name}"


class FunctionDefinition(BaseModel):
    """Represents a function or method definition."""

    name: str = Field(..., description="Function name")
    qualified_name: str = Field(..., description="Fully qualified function name")
    file_path: str = Field(..., description="Path to file containing this function")
    line_start: int = Field(..., description="Starting line number")
    line_end: int = Field(..., description="Ending line number")
    signature: str = Field(..., description="Function signature with parameters")
    docstring: str | None = Field(default=None, description="Function docstring")
    is_async: bool = Field(default=False, description="Whether this is an async function")
    is_method: bool = Field(default=False, description="Whether this is a class method")
    is_static: bool = Field(default=False, description="Whether this is a static method")
    is_classmethod: bool = Field(default=False, description="Whether this is a class method")
    decorators: list[str] = Field(default_factory=list, description="List of decorator names")
    return_type: str | None = Field(default=None, description="Return type annotation")
    parameters: list[dict[str, Any]] = Field(
        default_factory=list,
        description="List of parameters with name, type, default"
    )

    def get_id(self) -> str:
        """Get unique identifier for this node."""
        return f"function:{self.qualified_name}"


class ImportStatement(BaseModel):
    """Represents an import statement."""

    source_module: str = Field(..., description="Module doing the importing")
    target_module: str = Field(..., description="Module being imported")
    imported_names: list[str] = Field(
        default_factory=list,
        description="Specific names imported (empty for 'import module')"
    )
    alias: str | None = Field(default=None, description="Import alias (e.g., 'as np')")
    file_path: str = Field(..., description="Path to file containing this import")
    line_number: int = Field(..., description="Line number of import statement")

    def get_id(self) -> str:
        """Get unique identifier for this node."""
        return f"import:{self.source_module}:{self.target_module}:{self.line_number}"


# Edge Model

class Edge(BaseModel):
    """
    Represents a directed relationship between two code entities.

    Edges connect nodes in the code graph to represent relationships like
    function calls, inheritance, imports, etc.
    """

    source: str = Field(..., description="Source node ID (from get_id())")
    target: str = Field(..., description="Target node ID (from get_id())")
    edge_type: EdgeType = Field(..., description="Type of relationship")
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional edge properties (e.g., call count, line number)"
    )

    def __hash__(self) -> int:
        """Make edge hashable for set operations."""
        return hash((self.source, self.target, self.edge_type))


# Graph Container

class CodeGraph(BaseModel):
    """
    Container for a code knowledge graph.

    Stores nodes (code entities) and edges (relationships) forming a
    semantic representation of the codebase structure.
    """

    nodes: dict[str, Any] = Field(
        default_factory=dict,
        description="Nodes indexed by their ID (from get_id())"
    )
    edges: list[Edge] = Field(
        default_factory=list,
        description="List of all edges in the graph"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Graph-level metadata (e.g., creation time, version)"
    )

    def add_node(self, node: CodeFile | ModuleDefinition | ClassDefinition | FunctionDefinition | ImportStatement) -> None:
        """
        Add a node to the graph.

        Args:
            node: Code entity to add
        """
        node_id = node.get_id()
        self.nodes[node_id] = node

    def add_edge(self, edge: Edge) -> None:
        """
        Add an edge to the graph.

        Args:
            edge: Relationship to add
        """
        self.edges.append(edge)

    def get_node(self, node_id: str) -> Any | None:
        """
        Get a node by its ID.

        Args:
            node_id: Node identifier

        Returns:
            Node if found, None otherwise
        """
        return self.nodes.get(node_id)

    def get_edges_from(self, source_id: str) -> list[Edge]:
        """
        Get all edges originating from a node.

        Args:
            source_id: Source node ID

        Returns:
            List of outgoing edges
        """
        return [edge for edge in self.edges if edge.source == source_id]

    def get_edges_to(self, target_id: str) -> list[Edge]:
        """
        Get all edges pointing to a node.

        Args:
            target_id: Target node ID

        Returns:
            List of incoming edges
        """
        return [edge for edge in self.edges if edge.target == target_id]

    def get_edges_by_type(self, edge_type: EdgeType) -> list[Edge]:
        """
        Get all edges of a specific type.

        Args:
            edge_type: Type of edge to filter

        Returns:
            List of edges matching the type
        """
        return [edge for edge in self.edges if edge.edge_type == edge_type]

    def node_count(self) -> int:
        """Get total number of nodes in the graph."""
        return len(self.nodes)

    def edge_count(self) -> int:
        """Get total number of edges in the graph."""
        return len(self.edges)
