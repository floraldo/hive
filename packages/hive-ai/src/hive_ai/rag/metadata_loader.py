"""
Metadata loader for operational context and architectural memory.

Loads and parses metadata from:
- scripts_metadata.json (script purposes, dependencies, execution types)
- USAGE_MATRIX.md (usage patterns, contexts)
- Archive directory (deprecation reasons, migration notes)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


class MetadataLoader:
    """
    Load operational metadata and architectural memory for code chunks.

    Provides context about script purposes, usage patterns, deprecation
    reasons, and migration notes to enrich RAG retrieval results.
    """

    def __init__(self, project_root: Path | None = None):
        """
        Initialize metadata loader.

        Args:
            project_root: Root directory of Hive project.
                         Defaults to auto-detection.
        """
        self.project_root = project_root or self._find_project_root()
        self.scripts_metadata: dict[str, Any] = {}
        self.usage_matrix: dict[str, Any] = {}
        self.archive_notes: dict[str, Any] = {}

        # Load metadata on init
        self._load_metadata()

    def _find_project_root(self) -> Path:
        """Find Hive project root directory."""
        current = Path(__file__).resolve()

        # Walk up until we find pyproject.toml or .git
        while current.parent != current:
            if (current / "pyproject.toml").exists() or (current / ".git").exists():
                return current
            current = current.parent

        # Fallback to current directory
        return Path.cwd()

    def _load_metadata(self) -> None:
        """Load all metadata sources."""
        try:
            self._load_scripts_metadata()
            self._load_usage_matrix()
            self._load_archive_notes()
            logger.info("Metadata loaded successfully")
        except Exception as e:
            logger.warning(f"Failed to load some metadata: {e}")

    def _load_scripts_metadata(self) -> None:
        """Load scripts_metadata.json if it exists."""
        metadata_path = (
            self.project_root / "scripts" / "archive" / "cleanup_project" / "cleanup" / "scripts_metadata.json"
        )

        if metadata_path.exists():
            try:
                with open(metadata_path, encoding="utf-8") as f:
                    data = json.load(f)
                    # Index by script path for O(1) lookup
                    self.scripts_metadata = {script["script_path"]: script for script in data.get("scripts", [])}
                logger.info(f"Loaded {len(self.scripts_metadata)} script metadata entries")
            except Exception as e:
                logger.error(f"Failed to load scripts_metadata.json: {e}")

    def _load_usage_matrix(self) -> None:
        """Load USAGE_MATRIX.md and parse usage contexts."""
        matrix_path = self.project_root / "scripts" / "USAGE_MATRIX.md"

        if matrix_path.exists():
            try:
                content = matrix_path.read_text(encoding="utf-8")
                self.usage_matrix = self._parse_usage_matrix(content)
                logger.info(f"Loaded usage matrix with {len(self.usage_matrix)} entries")
            except Exception as e:
                logger.error(f"Failed to load USAGE_MATRIX.md: {e}")

    def _parse_usage_matrix(self, content: str) -> dict[str, Any]:
        """
        Parse USAGE_MATRIX.md to extract usage contexts.

        Returns:
            Dictionary mapping script paths to usage contexts.
        """
        usage_data = {}
        current_section = None

        for line in content.split("\n"):
            line = line.strip()

            # Detect section headers (e.g., "## CI/CD Scripts")
            if line.startswith("##"):
                current_section = line.replace("##", "").strip()
                continue

            # Extract script paths from markdown (e.g., "- `scripts/foo.py`")
            if line.startswith("-") and "`" in line:
                # Extract path between backticks
                start = line.find("`") + 1
                end = line.find("`", start)
                if start > 0 and end > start:
                    script_path = line[start:end]
                    usage_data[script_path] = {
                        "usage_context": current_section,
                        "description": line[end + 1 :].strip(" -"),
                    }

        return usage_data

    def _load_archive_notes(self) -> None:
        """Load deprecation and migration notes from archive directory."""
        archive_dir = self.project_root / "scripts" / "archive"

        if not archive_dir.exists():
            return

        # Look for README.md or other documentation files
        readme_path = archive_dir / "README.md"
        if readme_path.exists():
            try:
                content = readme_path.read_text(encoding="utf-8")
                self.archive_notes = self._parse_archive_readme(content)
                logger.info(f"Loaded archive notes for {len(self.archive_notes)} scripts")
            except Exception as e:
                logger.error(f"Failed to load archive README: {e}")

    def _parse_archive_readme(self, content: str) -> dict[str, Any]:
        """
        Parse archive README to extract deprecation reasons.

        Returns:
            Dictionary mapping script paths to deprecation info.
        """
        deprecation_data = {}

        # Simple parsing - look for patterns like:
        # - `scripts/old_script.py` - Deprecated: reason here
        for line in content.split("\n"):
            if "Deprecated" in line or "deprecated" in line:
                if "`" in line:
                    start = line.find("`") + 1
                    end = line.find("`", start)
                    if start > 0 and end > start:
                        script_path = line[start:end]
                        reason = line[end:].split(":", 1)[-1].strip()
                        deprecation_data[script_path] = {
                            "deprecation_reason": reason,
                            "is_archived": True,
                        }

        return deprecation_data

    def get_file_metadata(self, file_path: Path | str) -> dict[str, Any]:
        """
        Get comprehensive metadata for a file.

        Args:
            file_path: Path to the file (absolute or relative to project root)

        Returns:
            Dictionary with operational and architectural metadata
        """
        file_path_str = str(file_path)

        # Normalize path to be relative to project root
        if Path(file_path).is_absolute():
            try:
                rel_path = str(Path(file_path).relative_to(self.project_root))
            except ValueError:
                rel_path = file_path_str
        else:
            rel_path = file_path_str

        metadata = {
            "file_path": rel_path,
            "is_archived": "archive" in rel_path.lower(),
        }

        # Check scripts_metadata.json
        if rel_path in self.scripts_metadata:
            script_meta = self.scripts_metadata[rel_path]
            metadata.update(
                {
                    "purpose": script_meta.get("purpose"),
                    "execution_type": script_meta.get("execution_type"),
                    "dependencies": script_meta.get("dependencies", []),
                }
            )

        # Check usage matrix
        if rel_path in self.usage_matrix:
            usage_meta = self.usage_matrix[rel_path]
            metadata.update(
                {
                    "usage_context": usage_meta.get("usage_context"),
                    "description": usage_meta.get("description"),
                }
            )

        # Check archive notes
        if rel_path in self.archive_notes:
            archive_meta = self.archive_notes[rel_path]
            metadata.update(
                {
                    "deprecation_reason": archive_meta.get("deprecation_reason"),
                    "is_archived": True,
                }
            )

        return metadata

    def is_archived(self, file_path: Path | str) -> bool:
        """Check if a file is archived/deprecated."""
        metadata = self.get_file_metadata(file_path)
        return metadata.get("is_archived", False)

    def get_usage_context(self, file_path: Path | str) -> str | None:
        """Get usage context for a file (CI/CD, Manual, Testing, etc.)."""
        metadata = self.get_file_metadata(file_path)
        return metadata.get("usage_context")

    def get_deprecation_info(self, file_path: Path | str) -> dict[str, Any] | None:
        """Get deprecation information for a file if it exists."""
        metadata = self.get_file_metadata(file_path)

        if metadata.get("is_archived"):
            return {
                "is_deprecated": True,
                "reason": metadata.get("deprecation_reason"),
                "replacement": metadata.get("replacement_pattern"),
            }

        return None
