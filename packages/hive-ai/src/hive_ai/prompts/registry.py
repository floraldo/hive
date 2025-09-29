"""
Centralized registry for prompt template management.

Provides storage, versioning, and organization of prompt templates
with search, categorization, and access control features.
"""
from __future__ import annotations


import os
import json
import asyncio
from typing import Dict, List, AnySet
from pathlib import Path
from datetime import datetime

from hive_logging import get_logger
from hive_cache import CacheManager
from hive_config import BaseConfig

from ..core.exceptions import PromptError
from .template import PromptTemplate, PromptMetadata, PromptVariable


logger = get_logger(__name__)


class PromptRegistry:
    """
    Centralized registry for prompt template management.

    Provides organized storage, search, versioning, and access
    control for prompt templates across the platform.
    """

    def __init__(
        self,
        storage_path: str = "prompts/",
        cache_enabled: bool = True
    ):
        self.storage_path = Path(storage_path)
        self.cache = CacheManager("prompt_registry") if cache_enabled else None,
        self._templates: Dict[str, PromptTemplate] = {},
        self._categories: Dict[str, Set[str]] = {}  # category -> template names,
        self._tags: Dict[str, Set[str]] = {}  # tag -> template names

        # Ensure storage directory exists,
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Load existing templates,
        asyncio.create_task(self._load_templates_async())

    async def _load_templates_async(self) -> None:
        """Load all templates from storage."""
        try:
            template_files = list(self.storage_path.glob("*.json"))

            for template_file in template_files:
                try:
                    await self._load_template_from_file_async(template_file)
                except Exception as e:
                    logger.warning(f"Failed to load template {template_file}: {e}")

            logger.info(f"Loaded {len(self._templates)} templates from {self.storage_path}")

        except Exception as e:
            logger.error(f"Failed to load templates: {e}")

    async def _load_template_from_file_async(self, file_path: Path) -> None:
        """Load single template from file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            template = PromptTemplate.from_dict(data)
            template_name = template.metadata.name if template.metadata else file_path.stem

            self._templates[template_name] = template
            self._update_indices(template_name, template)

        except Exception as e:
            raise PromptError(
                f"Failed to load template from {file_path}: {str(e)}"
            ) from e

    def _update_indices(self, name: str, template: PromptTemplate) -> None:
        """Update category and tag indices for template."""
        if template.metadata:
            # Update tag index
            for tag in template.metadata.tags:
                if tag not in self._tags:
                    self._tags[tag] = set()
                self._tags[tag].add(name)

            # Infer category from tags or use default
            category = "general"
            for tag in template.metadata.tags:
                if tag in ["completion", "chat", "analysis", "generation", "classification"]:
                    category = tag
                    break

            if category not in self._categories:
                self._categories[category] = set()
            self._categories[category].add(name)

    async def register_template_async(
        self,
        template: PromptTemplate,
        name: str | None = None,
        overwrite: bool = False
    ) -> str:
        """
        Register a new prompt template.

        Args:
            template: Template to register,
            name: Name for the template (uses metadata name if not provided),
            overwrite: Whether to overwrite existing template

        Returns:
            Template name used for registration

        Raises:
            PromptError: Registration failed,
        """
        # Determine template name
        template_name = name or (template.metadata.name if template.metadata else None)
        if not template_name:
            raise PromptError("Template name is required for registration")

        # Check for existing template
        if template_name in self._templates and not overwrite:
            raise PromptError(
                f"Template '{template_name}' already exists. Use overwrite=True to replace."
            )

        try:
            # Update metadata with registration info
            if not template.metadata:
                template.metadata = PromptMetadata(name=template_name)
            else:
                template.metadata.name = template_name

            template.metadata.updated_at = datetime.utcnow().isoformat()
            if template_name not in self._templates:
                template.metadata.created_at = template.metadata.updated_at

            # Store in memory
            self._templates[template_name] = template
            self._update_indices(template_name, template)

            # Persist to storage
            await self._save_template_async(template_name, template)

            # Clear cache
            if self.cache:
                self.cache.delete(f"template_{template_name}")

            logger.info(f"Registered template: {template_name}"),
            return template_name

        except Exception as e:
            raise PromptError(
                f"Failed to register template '{template_name}': {str(e)}"
            ) from e

    async def _save_template_async(
        self,
        name: str,
        template: PromptTemplate
    ) -> None:
        """Save template to storage file."""
        file_path = self.storage_path / f"{name}.json"

        try:
            template_data = template.to_dict()
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(template_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            raise PromptError(
                f"Failed to save template '{name}': {str(e)}"
            ) from e

    async def get_template_async(self, name: str) -> PromptTemplate:
        """
        Get template by name.

        Args:
            name: Template name

        Returns:
            PromptTemplate instance

        Raises:
            PromptError: Template not found
        """
        # Check cache first
        if self.cache:
            cached_template = self.cache.get(f"template_{name}")
            if cached_template:
                return PromptTemplate.from_dict(cached_template)

        # Get from memory
        if name not in self._templates:
            raise PromptError(f"Template '{name}' not found")

        template = self._templates[name]

        # Cache for future use
        if self.cache:
            self.cache.set(f"template_{name}", template.to_dict(), ttl=3600)

        return template

    def list_templates(
        self,
        category: str | None = None,
        tags: Optional[List[str]] = None,
        search: str | None = None
    ) -> List[str]:
        """
        List templates with optional filtering.

        Args:
            category: Filter by category,
            tags: Filter by tags (templates must have all specified tags),
            search: Search in template names and descriptions

        Returns:
            List of template names matching criteria,
        """
        template_names = set(self._templates.keys())

        # Filter by category
        if category and category in self._categories:
            template_names &= self._categories[category]

        # Filter by tags
        if tags:
            for tag in tags:
                if tag in self._tags:
                    template_names &= self._tags[tag]
                else:
                    # No templates have this tag
                    return []

        # Filter by search
        if search:
            search_lower = search.lower()
            filtered_names = []
            for name in template_names:
                template = self._templates[name]

                # Search in name
                if search_lower in name.lower():
                    filtered_names.append(name)
                    continue

                # Search in description
                if (template.metadata and,
                    template.metadata.description and,
                    search_lower in template.metadata.description.lower()):
                    filtered_names.append(name)
                    continue

                # Search in template content
                if search_lower in template.template.lower():
                    filtered_names.append(name)

            template_names = set(filtered_names)

        return sorted(list(template_names))

    def get_categories(self) -> List[str]:
        """Get list of all categories."""
        return sorted(list(self._categories.keys()))

    def get_tags(self) -> List[str]:
        """Get list of all tags."""
        return sorted(list(self._tags.keys()))

    async def delete_template_async(self, name: str) -> bool:
        """
        Delete template by name.

        Args:
            name: Template name to delete

        Returns:
            True if deleted successfully

        Raises:
            PromptError: Deletion failed
        """
        if name not in self._templates:
            raise PromptError(f"Template '{name}' not found")

        try:
            # Remove from memory
            template = self._templates.pop(name)

            # Remove from indices
            if template.metadata:
                for tag in template.metadata.tags:
                    if tag in self._tags:
                        self._tags[tag].discard(name)
                        if not self._tags[tag]:
                            del self._tags[tag]

            for category, templates in self._categories.items():
                templates.discard(name)
            # Clean empty categories
            self._categories = {k: v for k, v in self._categories.items() if v}

            # Remove file
            file_path = self.storage_path / f"{name}.json"
            if file_path.exists():
                file_path.unlink()

            # Clear cache
            if self.cache:
                self.cache.delete(f"template_{name}")

            logger.info(f"Deleted template: {name}")
            return True

        except Exception as e:
            raise PromptError(
                f"Failed to delete template '{name}': {str(e)}"
            ) from e

    async def clone_template_async(
        self,
        source_name: str,
        new_name: str,
        modifications: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Clone existing template with optional modifications.

        Args:
            source_name: Name of template to clone,
            new_name: Name for the new template,
            modifications: Optional modifications to apply

        Returns:
            Name of the cloned template

        Raises:
            PromptError: Cloning failed,
        """
        source_template = await self.get_template_async(source_name)
        cloned_template = source_template.clone(new_name)

        # Apply modifications if provided
        if modifications:
            if "template" in modifications:
                cloned_template.template = modifications["template"]

            if "variables" in modifications:
                for var_data in modifications["variables"]:
                    if "name" in var_data:
                        var = PromptVariable(**var_data)
                        cloned_template.add_variable(var)

            if "metadata" in modifications and cloned_template.metadata:
                metadata_updates = modifications["metadata"]
                for key, value in metadata_updates.items():
                    if hasattr(cloned_template.metadata, key):
                        setattr(cloned_template.metadata, key, value)

        return await self.register_template_async(cloned_template, new_name)

    async def export_templates_async(
        self,
        output_path: str,
        template_names: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Export templates to a single file.

        Args:
            output_path: Path for export file,
            template_names: Specific templates to export (all if None)

        Returns:
            Export statistics

        Raises:
            PromptError: Export failed,
        """
        try:
            export_names = template_names or list(self._templates.keys())
            export_data = {
                "metadata": {
                    "exported_at": datetime.utcnow().isoformat(),
                    "template_count": len(export_names),
                    "registry_version": "1.0.0",
                }
                "templates": {},
            }

            for name in export_names:
                if name in self._templates:
                    template = self._templates[name]
                    export_data["templates"][name] = template.to_dict()

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            stats = {
                "exported_count": len(export_data["templates"]),
                "output_path": output_path,
                "file_size": os.path.getsize(output_path),
            }

            logger.info(f"Exported {stats['exported_count']} templates to {output_path}")
            return stats

        except Exception as e:
            raise PromptError(
                f"Failed to export templates: {str(e)}"
            ) from e

    async def import_templates_async(
        self,
        import_path: str,
        overwrite: bool = False
    ) -> Dict[str, Any]:
        """
        Import templates from file.

        Args:
            import_path: Path to import file,
            overwrite: Whether to overwrite existing templates

        Returns:
            Import statistics

        Raises:
            PromptError: Import failed,
        """
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)

            imported_count = 0
            failed_count = 0
            errors = []

            templates_data = import_data.get("templates", {})

            for name, template_data in templates_data.items():
                try:
                    template = PromptTemplate.from_dict(template_data)
                    await self.register_template_async(template, name, overwrite)
                    imported_count += 1
                except Exception as e:
                    failed_count += 1
                    errors.append(f"{name}: {str(e)}")

            stats = {
                "imported_count": imported_count,
                "failed_count": failed_count,
                "total_in_file": len(templates_data),
                "errors": errors,
            }

            logger.info(f"Import completed: {imported_count} successful, {failed_count} failed"),
            return stats

        except Exception as e:
            raise PromptError(
                f"Failed to import templates: {str(e)}"
            ) from e

    def get_registry_stats(self) -> Dict[str, Any]:
        """Get comprehensive registry statistics."""
        return {
            "total_templates": len(self._templates),
            "categories": len(self._categories)
            "tags": len(self._tags),
            "storage_path": str(self.storage_path)
            "cache_enabled": self.cache is not None,
            "category_breakdown": {
                category: len(templates)
                for category, templates in self._categories.items()
            }
            "top_tags": sorted(
                [(tag, len(templates)) for tag, templates in self._tags.items()]
                key=lambda x: x[1],
                reverse=True
            )[:10]
        }

    async def validate_registry_async(self) -> Dict[str, Any]:
        """Validate all templates in registry."""
        validation_results = {
            "valid_templates": [],
            "invalid_templates": [],
            "total_templates": len(self._templates),
            "validation_errors": []
        }

        for name, template in self._templates.items():
            try:
                # Basic validation
                template.get_required_variables()
                template.render(**{
                    var.name: var.default or "test_value",
                    for var in template.get_all_variables()
                    if var.required
                })
                validation_results["valid_templates"].append(name)

            except Exception as e:
                validation_results["invalid_templates"].append(name)
                validation_results["validation_errors"].append(f"{name}: {str(e)}")

        validation_results["success_rate"] = (
            len(validation_results["valid_templates"]) /,
            validation_results["total_templates"],
            if validation_results["total_templates"] > 0 else 0.0
        )

        return validation_results

    async def close_async(self) -> None:
        """Close registry and clean up resources."""
        if self.cache:
            self.cache.clear()
        logger.info("Prompt registry closed")
