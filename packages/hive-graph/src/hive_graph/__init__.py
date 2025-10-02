"""
hive-graph: Knowledge graph package for semantic codebase representation.

This package provides infrastructure for building and querying a knowledge graph
of the Hive codebase, enabling deep code intelligence capabilities.

Core Components:
- models: Pydantic models for code entities (nodes) and relationships (edges)
- parser: AST parser for extracting graph structure from source code
- CodeGraph: Container for managing nodes and edges

Example Usage:
    >>> from hive_graph import CodeGraph, ASTParser
    >>> from pathlib import Path
    >>>
    >>> # Create a new graph
    >>> graph = CodeGraph()
    >>>
    >>> # Parse a file and add to graph
    >>> parser = ASTParser()
    >>> nodes, edges = parser.parse_file(Path("my_module.py"))
    >>> for node in nodes:
    ...     graph.add_node(node)
    >>> for edge in edges:
    ...     graph.add_edge(edge)
    >>>
    >>> # Query the graph
    >>> print(f"Graph has {graph.node_count()} nodes and {graph.edge_count()} edges")
"""

from .models import (
    ClassDefinition,
    CodeFile,
    CodeGraph,
    Edge,
    EdgeType,
    FunctionDefinition,
    ImportStatement,
    ModuleDefinition,
)
from .parser import ASTParser

__version__ = "0.1.0"

__all__ = [
    # Models
    "CodeFile",
    "ModuleDefinition",
    "ClassDefinition",
    "FunctionDefinition",
    "ImportStatement",
    "Edge",
    "EdgeType",
    "CodeGraph",
    # Parser
    "ASTParser",
]
