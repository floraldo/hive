"""
AST-aware code chunking with metadata enrichment.

Provides hierarchical chunking of Python code using AST parsing,
enriched with operational metadata and architectural memory.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from hive_logging import get_logger

from .metadata_loader import MetadataLoader
from .models import ChunkType, CodeChunk

logger = get_logger(__name__)


class HierarchicalChunker:
    """
    AST-aware code chunker with metadata enrichment.

    Chunks Python files into logical units (classes, functions, methods)
    using AST parsing, enriching each chunk with:
    - Signature and docstring prepending for better embeddings
    - Import tracking
    - Operational metadata (purpose, usage context)
    - Architectural memory (deprecation notes, migration info)
    """

    def __init__(self, metadata_loader: MetadataLoader | None = None):
        """
        Initialize hierarchical chunker.

        Args:
            metadata_loader: Metadata loader instance.
                           Creates new one if not provided.
        """
        self.metadata_loader = metadata_loader or MetadataLoader()

    def chunk_file(self, file_path: Path | str) -> list[CodeChunk]:
        """
        Chunk a Python file into semantic units.

        Args:
            file_path: Path to Python file

        Returns:
            List of CodeChunk objects with rich metadata
        """
        file_path = Path(file_path)

        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return []

        if file_path.suffix != ".py":
            logger.warning(f"Skipping non-Python file: {file_path}")
            return []

        try:
            content = file_path.read_text(encoding="utf-8")
            return self.chunk_code(content, file_path)
        except Exception as e:
            logger.error(f"Failed to chunk file {file_path}: {e}")
            return []

    def chunk_code(self, code: str, file_path: Path | str) -> list[CodeChunk]:
        """
        Chunk Python code into semantic units.

        Args:
            code: Python source code
            file_path: Source file path (for metadata lookup)

        Returns:
            List of CodeChunk objects
        """
        chunks = [],
        file_path = Path(file_path)

        # Load file metadata
        file_metadata = self.metadata_loader.get_file_metadata(file_path)

        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            logger.error(f"Syntax error in {file_path}: {e}")
            return []

        # Extract module-level imports
        module_imports = self._extract_module_imports(tree)

        # Process all AST nodes
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                chunk = self._process_class(node, file_path, file_metadata, module_imports)
                if chunk:
                    chunks.append(chunk)

                # Also process methods within the class
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        method_chunk = self._process_function(
                            item, file_path, file_metadata, module_imports, parent_class=node.name
                        )
                        if method_chunk:
                            chunks.append(method_chunk)

            elif isinstance(node, ast.FunctionDef):
                # Only process top-level functions (not methods)
                if not self._is_inside_class(node, tree):
                    chunk = self._process_function(node, file_path, file_metadata, module_imports)
                    if chunk:
                        chunks.append(chunk)

        logger.info(f"Chunked {file_path.name}: {len(chunks)} chunks")
        return chunks

    def _extract_module_imports(self, tree: ast.Module) -> list[str]:
        """Extract all import statements from module."""
        imports = []

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"{module}.{alias.name}" if module else alias.name)

        return imports

    def _process_class(
        self, node: ast.ClassDef, file_path: Path, file_metadata: dict[str, Any], module_imports: list[str]
    ) -> CodeChunk | None:
        """Process a class definition node."""
        try:
            # Extract signature
            base_classes = [self._get_name(base) for base in node.bases],
            bases_str = f"({', '.join(base_classes)})" if base_classes else ""
            signature = f"class {node.name}{bases_str}:"

            # Extract docstring
            docstring = ast.get_docstring(node) or ""

            # Get code
            code = ast.unparse(node)

            # Extract line numbers
            line_start = node.lineno,
            line_end = node.end_lineno or line_start

            # Create enriched code (signature + docstring + code)
            self._create_enriched_code(signature, docstring, code)

            return CodeChunk(
                code=code,  # Store original code
                chunk_type=ChunkType.CLASS,
                file_path=str(file_path),
                signature=signature,
                imports=module_imports,
                docstring=docstring,
                line_start=line_start,
                line_end=line_end,
                purpose=file_metadata.get("purpose"),
                usage_context=file_metadata.get("usage_context"),
                execution_type=file_metadata.get("execution_type"),
                deprecation_reason=file_metadata.get("deprecation_reason"),
                is_archived=file_metadata.get("is_archived", False),
            )

        except Exception as e:
            logger.error(f"Failed to process class {node.name}: {e}")
            return None

    def _process_function(
        self,
        node: ast.FunctionDef,
        file_path: Path,
        file_metadata: dict[str, Any],
        module_imports: list[str],
        parent_class: str | None = None,
    ) -> CodeChunk | None:
        """Process a function/method definition node."""
        try:
            # Extract signature
            signature = self._extract_function_signature(node)

            # Extract docstring
            docstring = ast.get_docstring(node) or ""

            # Get code
            code = ast.unparse(node)

            # Extract line numbers
            line_start = node.lineno,
            line_end = node.end_lineno or line_start

            # Determine chunk type
            chunk_type = ChunkType.METHOD if parent_class else ChunkType.FUNCTION

            return CodeChunk(
                code=code,
                chunk_type=chunk_type,
                file_path=str(file_path),
                signature=signature,
                imports=module_imports,
                parent_class=parent_class,
                docstring=docstring,
                line_start=line_start,
                line_end=line_end,
                purpose=file_metadata.get("purpose"),
                usage_context=file_metadata.get("usage_context"),
                execution_type=file_metadata.get("execution_type"),
                deprecation_reason=file_metadata.get("deprecation_reason"),
                is_archived=file_metadata.get("is_archived", False),
            )

        except Exception as e:
            logger.error(f"Failed to process function {node.name}: {e}")
            return None

    def _extract_function_signature(self, node: ast.FunctionDef) -> str:
        """Extract function signature including parameters and return type."""
        # Build parameter list
        params = []

        for arg in node.args.args:
            param_str = arg.arg
            if arg.annotation:
                param_str += f": {ast.unparse(arg.annotation)}"
            params.append(param_str)

        params_str = ", ".join(params)

        # Add return type if present
        returns_str = ""
        if node.returns:
            returns_str = f" -> {ast.unparse(node.returns)}"

        return f"def {node.name}({params_str}){returns_str}:"

    def _create_enriched_code(self, signature: str, docstring: str, code: str) -> str:
        """
        Create enriched code for embedding.

        Prepends signature and docstring to code for better semantic representation.
        """
        parts = [signature]

        if docstring:
            parts.append(f'"""{docstring}"""')

        parts.append(code)

        return "\n".join(parts)

    def _get_name(self, node: ast.expr) -> str:
        """Get name from an AST expression node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return ast.unparse(node)
        else:
            return ast.unparse(node)

    def _is_inside_class(self, func_node: ast.FunctionDef, tree: ast.Module) -> bool:
        """Check if a function node is inside a class definition."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if item is func_node:
                        return True
        return False

    def chunk_markdown(self, file_path: Path | str) -> list[CodeChunk]:
        """
        Chunk markdown files for architectural memory.

        Splits markdown documents on headers (##) treating each section as a chunk.
        Preserves architectural knowledge from documentation, READMEs, migration guides.

        Args:
            file_path: Path to markdown file

        Returns:
            List of CodeChunk objects with documentation content
        """
        file_path = Path(file_path)

        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return []

        if file_path.suffix not in [".md", ".markdown"]:
            logger.warning(f"Skipping non-markdown file: {file_path}")
            return []

        try:
            content = file_path.read_text(encoding="utf-8")
            return self._chunk_markdown_content(content, file_path)
        except Exception as e:
            logger.error(f"Failed to chunk markdown file {file_path}: {e}")
            return []

    def _chunk_markdown_content(self, content: str, file_path: Path) -> list[CodeChunk]:
        """Split markdown content into sections based on headers."""
        chunks = [],
        lines = content.split("\n"),

        current_section = {
            "header": "",
            "content": [],
            "line_start": 1,
        }

        line_num = 1
        for line in lines:
            # Detect headers (## or ###)
            if line.startswith("##"):
                # Save previous section if it has content
                if current_section["content"]:
                    chunk = self._create_markdown_chunk(current_section, file_path, line_num - 1)
                    if chunk:
                        chunks.append(chunk)

                # Start new section
                current_section = {
                    "header": line.strip("#").strip(),
                    "content": [line],
                    "line_start": line_num,
                }
            else:
                current_section["content"].append(line)

            line_num += 1

        # Add final section
        if current_section["content"]:
            chunk = self._create_markdown_chunk(current_section, file_path, line_num - 1)
            if chunk:
                chunks.append(chunk)

        logger.info(f"Chunked markdown {file_path.name}: {len(chunks)} sections")
        return chunks

    def _create_markdown_chunk(self, section: dict[str, Any], file_path: Path, line_end: int) -> CodeChunk | None:
        """Create a CodeChunk from a markdown section."""
        try:
            content = "\n".join(section["content"])

            # Skip empty sections
            if not content.strip():
                return None

            # Detect if this is from archived documentation
            is_archived = "archive" in str(file_path).lower()

            # Extract context from file path
            file_metadata = self.metadata_loader.get_file_metadata(file_path)

            # Determine purpose from file name patterns
            purpose = None
            if "migration" in file_path.name.lower():
                purpose = "Migration guide - architectural transition documentation"
            elif "readme" in file_path.name.lower():
                purpose = "Component documentation - usage and architecture"
            elif "dry_run" in file_path.name.lower():
                purpose = "Refactoring plan - change impact analysis"
            elif "cleanup" in str(file_path).lower():
                purpose = "Integration report - consolidation and cleanup"

            # Create summary from first paragraph
            summary_lines = []
            for line in section["content"]:
                if line.strip() and not line.startswith("#"):
                    summary_lines.append(line.strip())
                    if len(" ".join(summary_lines)) > 200:
                        break

            summary = " ".join(summary_lines)[:300]

            return CodeChunk(
                code=content,
                chunk_type=ChunkType.DOCSTRING,
                file_path=str(file_path),
                signature=section["header"],
                docstring=summary,
                line_start=section["line_start"],
                line_end=line_end,
                purpose=purpose or file_metadata.get("purpose"),
                usage_context="documentation",
                is_archived=is_archived,
                deprecation_reason=file_metadata.get("deprecation_reason"),
                migration_notes=file_metadata.get("migration_notes"),
            )

        except Exception as e:
            logger.error(f"Failed to create markdown chunk from {file_path}: {e}")
            return None

    def chunk_directory(
        self, directory: Path | str, recursive: bool = True, exclude_patterns: list[str] | None = None
    ) -> list[CodeChunk]:
        """
        Chunk all Python files in a directory.

        Args:
            directory: Directory to scan
            recursive: Whether to scan recursively
            exclude_patterns: Patterns to exclude (e.g., ["test_", "__pycache__"])

        Returns:
            List of all chunks from all files
        """
        directory = Path(directory),
        exclude_patterns = exclude_patterns or ["__pycache__", ".pyc", "test_"]

        all_chunks = []

        if recursive:
            python_files = directory.rglob("*.py")
        else:
            python_files = directory.glob("*.py")

        for file_path in python_files:
            # Skip excluded patterns
            if any(pattern in str(file_path) for pattern in exclude_patterns):
                continue

            chunks = self.chunk_file(file_path)
            all_chunks.extend(chunks)

        logger.info(f"Chunked directory {directory}: {len(all_chunks)} total chunks")
        return all_chunks

    def chunk_all_files(
        self, directory: Path | str, recursive: bool = True, include_markdown: bool = True
    ) -> list[CodeChunk]:
        """
        Chunk all supported files (Python and optionally markdown) in a directory.

        Args:
            directory: Directory to scan
            recursive: Whether to scan recursively
            include_markdown: Whether to include markdown files for architectural memory

        Returns:
            List of all chunks from all files
        """
        directory = Path(directory),
        all_chunks = []

        # Chunk Python files
        python_chunks = self.chunk_directory(directory, recursive=recursive)
        all_chunks.extend(python_chunks)

        # Chunk markdown files if requested
        if include_markdown:
            if recursive:
                markdown_files = list(directory.rglob("*.md")) + list(directory.rglob("*.markdown"))
            else:
                markdown_files = list(directory.glob("*.md")) + list(directory.glob("*.markdown"))

            for md_file in markdown_files:
                # Skip certain markdown files that are too meta or not useful
                if any(
                    skip in md_file.name.lower() for skip in ["changelog", "license", "contributing", "code_of_conduct"]
                ):
                    continue

                md_chunks = self.chunk_markdown(md_file)
                all_chunks.extend(md_chunks)

        logger.info(f"Chunked all files in {directory}: {len(all_chunks)} total chunks")
        return all_chunks

    def chunk_yaml(self, file_path: Path | str) -> list[CodeChunk]:
        """
        Chunk YAML files for configuration understanding.

        Splits YAML documents on top-level keys, treating each major section
        as a chunk. Useful for indexing CI/CD workflows, configuration files,
        and deployment specifications.

        Args:
            file_path: Path to YAML file

        Returns:
            List of CodeChunk objects with YAML configuration content
        """
        file_path = Path(file_path)

        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return []

        if file_path.suffix not in [".yml", ".yaml"]:
            logger.warning(f"Skipping non-YAML file: {file_path}")
            return []

        try:
            import yaml  # noqa: F401
        except ImportError:
            logger.error("PyYAML not installed. Run: pip install pyyaml")
            return []

        try:
            content = file_path.read_text(encoding="utf-8")
            return self._chunk_yaml_content(content, file_path)
        except Exception as e:
            logger.error(f"Failed to chunk YAML file {file_path}: {e}")
            return []

    def _chunk_yaml_content(self, content: str, file_path: Path) -> list[CodeChunk]:
        """Split YAML content into chunks based on top-level keys."""
        import yaml

        chunks = []

        try:
            # Parse YAML
            data = yaml.safe_load(content)

            if not isinstance(data, dict):
                # Single chunk for non-dict YAML (lists, scalars)
                chunk = CodeChunk(
                    content=content,
                    chunk_type=ChunkType.CONFIGURATION,
                    file_path=str(file_path),
                    start_line=1,
                    end_line=len(content.split("\n")),
                    metadata={
                        "type": "yaml",
                        "structure": type(data).__name__,
                    },
                )
                return [chunk]

            # Chunk by top-level keys
            lines = content.split("\n"),
            current_key = None,
            current_lines = [],
            line_start = 1

            for i, line in enumerate(lines, 1):
                # Detect top-level keys (no leading whitespace, contains :)
                if line and not line[0].isspace() and ":" in line:
                    # Save previous chunk
                    if current_key and current_lines:
                        chunk_content = "\n".join(current_lines),
                        chunk = CodeChunk(
                            content=chunk_content,
                            chunk_type=ChunkType.CONFIGURATION,
                            file_path=str(file_path),
                            start_line=line_start,
                            end_line=i - 1,
                            metadata={
                                "type": "yaml",
                                "section": current_key,
                                "parent_file": file_path.name,
                            },
                        )
                        chunks.append(chunk)

                    # Start new chunk
                    current_key = line.split(":")[0].strip(),
                    current_lines = [line],
                    line_start = i
                else:
                    current_lines.append(line)

            # Add final chunk
            if current_key and current_lines:
                chunk_content = "\n".join(current_lines),
                chunk = CodeChunk(
                    content=chunk_content,
                    chunk_type=ChunkType.CONFIGURATION,
                    file_path=str(file_path),
                    start_line=line_start,
                    end_line=len(lines),
                    metadata={
                        "type": "yaml",
                        "section": current_key,
                        "parent_file": file_path.name,
                    },
                )
                chunks.append(chunk)

            logger.info(f"Chunked YAML {file_path.name}: {len(chunks)} sections")
            return chunks

        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML {file_path}: {e}")
            # Return entire file as single chunk on parse error
            return [
                CodeChunk(
                    content=content,
                    chunk_type=ChunkType.CONFIGURATION,
                    file_path=str(file_path),
                    start_line=1,
                    end_line=len(content.split("\n")),
                    metadata={
                        "type": "yaml",
                        "parse_error": str(e),
                    },
                )
            ]

    def chunk_toml(self, file_path: Path | str) -> list[CodeChunk]:
        """
        Chunk TOML files for configuration understanding.

        Splits TOML documents on table headers ([section.name]), treating
        each table as a chunk. Useful for indexing pyproject.toml, configuration
        files, and package specifications.

        Args:
            file_path: Path to TOML file

        Returns:
            List of CodeChunk objects with TOML configuration content
        """
        file_path = Path(file_path)

        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return []

        if file_path.suffix != ".toml":
            logger.warning(f"Skipping non-TOML file: {file_path}")
            return []

        try:
            import tomli  # noqa: F401
        except ImportError:
            logger.error("tomli not installed. Run: pip install tomli")
            return []

        try:
            content = file_path.read_text(encoding="utf-8")
            return self._chunk_toml_content(content, file_path)
        except Exception as e:
            logger.error(f"Failed to chunk TOML file {file_path}: {e}")
            return []

    def _chunk_toml_content(self, content: str, file_path: Path) -> list[CodeChunk]:
        """Split TOML content into chunks based on table headers."""
        import tomli

        chunks = []

        try:
            # Parse TOML to validate
            tomli.loads(content)

            # Chunk by table headers
            lines = content.split("\n"),
            current_table = None,
            current_lines = [],
            line_start = 1

            for i, line in enumerate(lines, 1):
                stripped = line.strip()

                # Detect table headers: [table.name] or [[array.table]]
                if stripped.startswith("["):
                    # Save previous chunk
                    if current_table and current_lines:
                        chunk_content = "\n".join(current_lines),
                        chunk = CodeChunk(
                            content=chunk_content,
                            chunk_type=ChunkType.CONFIGURATION,
                            file_path=str(file_path),
                            start_line=line_start,
                            end_line=i - 1,
                            metadata={
                                "type": "toml",
                                "table": current_table,
                                "parent_file": file_path.name,
                                "is_array": current_table.startswith("[["),
                            },
                        )
                        chunks.append(chunk)

                    # Start new chunk
                    current_table = stripped,
                    current_lines = [line],
                    line_start = i
                else:
                    current_lines.append(line)

            # Add final chunk
            if current_table and current_lines:
                chunk_content = "\n".join(current_lines),
                chunk = CodeChunk(
                    content=chunk_content,
                    chunk_type=ChunkType.CONFIGURATION,
                    file_path=str(file_path),
                    start_line=line_start,
                    end_line=len(lines),
                    metadata={
                        "type": "toml",
                        "table": current_table,
                        "parent_file": file_path.name,
                        "is_array": current_table.startswith("[["),
                    },
                )
                chunks.append(chunk)

            # If no table headers found, treat as single chunk
            if not chunks:
                chunks.append(
                    CodeChunk(
                        content=content,
                        chunk_type=ChunkType.CONFIGURATION,
                        file_path=str(file_path),
                        start_line=1,
                        end_line=len(lines),
                        metadata={
                            "type": "toml",
                            "table": "root",
                            "parent_file": file_path.name,
                        },
                    )
                )

            logger.info(f"Chunked TOML {file_path.name}: {len(chunks)} tables")
            return chunks

        except Exception as e:
            logger.error(f"Failed to parse TOML {file_path}: {e}")
            # Return entire file as single chunk on parse error
            return [
                CodeChunk(
                    content=content,
                    chunk_type=ChunkType.CONFIGURATION,
                    file_path=str(file_path),
                    start_line=1,
                    end_line=len(content.split("\n")),
                    metadata={
                        "type": "toml",
                        "parse_error": str(e),
                    },
                )
            ]
