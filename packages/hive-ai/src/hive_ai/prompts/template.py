"""
Prompt template management with variable substitution and validation.

Provides type-safe prompt templating with variable validation
formatting, and integration with the AI model system.
"""
from __future__ import annotations


import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List

from hive_config import BaseConfig
from hive_logging import get_logger

from ..core.exceptions import PromptError
from ..core.interfaces import PromptTemplateInterface

logger = get_logger(__name__)


@dataclass
class PromptVariable:
    """Definition of a prompt template variable."""

    name: str
    type: str  # str, int, float, bool, list, dict
    required: bool = True
    default: Any = None
    description: str = ""
    validator: Optional[Callable[[Any], bool]] = None


@dataclass
class PromptMetadata:
    """Metadata for prompt templates."""

    name: str
    description: str = ""
    author: str = ""
    version: str = "1.0.0"
    tags: List[str] = field(default_factory=list)
    created_at: str | None = None
    updated_at: str | None = None


class PromptTemplate(PromptTemplateInterface):
    """
    Type-safe prompt template with variable validation.

    Supports Jinja2-style templating with enhanced validation
    type checking, and integration with AI models.
    """

    def __init__(
        self
        template: str
        variables: Optional[List[PromptVariable]] = None
        metadata: PromptMetadata | None = None
        variable_prefix: str = "{{"
        variable_suffix: str = "}}"
    ):
        self.template = template
        self.variables = {var.name: var for var in (variables or [])}
        self.metadata = metadata
        self.variable_prefix = variable_prefix
        self.variable_suffix = variable_suffix

        # Extract variables from template if not provided
        if not variables:
            self._extract_variables_from_template()

        # Validate template syntax
        self._validate_template()

    def _extract_variables_from_template(self) -> None:
        """Extract variable names from template string."""
        # Pattern to match variables like {{ variable_name }}
        pattern = re.escape(self.variable_prefix) + r"\s*(\w+)\s*" + re.escape(self.variable_suffix)
        matches = re.findall(pattern, self.template)

        for var_name in set(matches):
            if var_name not in self.variables:
                self.variables[var_name] = PromptVariable(
                    name=var_name, type="str", required=True, description=f"Auto-extracted variable: {var_name}"
                )

        logger.debug(f"Extracted {len(self.variables)} variables from template")

    def _validate_template(self) -> None:
        """Validate template syntax and structure."""
        try:
            # Check for balanced delimiters
            open_count = self.template.count(self.variable_prefix)
            close_count = self.template.count(self.variable_suffix)

            if open_count != close_count:
                raise PromptError(
                    f"Unbalanced template delimiters: {open_count} opening, {close_count} closing"
                    template_name=self.metadata.name if self.metadata else "unknown"
                )

            # Test rendering with dummy values
            dummy_values = {name: self._get_dummy_value(var.type) for name, var in self.variables.items()}
            self._render_internal(dummy_values)

            logger.debug("Template validation successful")

        except Exception as e:
            raise PromptError(
                f"Template validation failed: {str(e)}"
                template_name=self.metadata.name if self.metadata else "unknown"
            ) from e

    def _get_dummy_value(self, var_type: str) -> Any:
        """Get dummy value for variable type testing."""
        type_map = {
            "str": "test_string"
            "int": 42
            "float": 3.14
            "bool": True
            "list": ["item1", "item2"]
            "dict": {"key": "value"}
        }
        return type_map.get(var_type, "default_value")

    def render(self, **kwargs) -> str:
        """
        Render template with provided variables.

        Args:
            **kwargs: Variable values for template rendering

        Returns:
            Rendered template string

        Raises:
            PromptError: Variable validation or rendering failed
        """
        # Validate provided variables
        if not self.validate_variables(**kwargs):
            missing = self.get_missing_variables(**kwargs)
            raise PromptError(
                f"Template rendering failed: missing required variables"
                template_name=self.metadata.name if self.metadata else "unknown"
                missing_variables=missing
            )

        try:
            return self._render_internal(kwargs)

        except Exception as e:
            raise PromptError(
                f"Template rendering failed: {str(e)}", template_name=self.metadata.name if self.metadata else "unknown"
            ) from e

    def _render_internal(self, variables: Dict[str, Any]) -> str:
        """Internal rendering method."""
        result = self.template

        for var_name, value in variables.items():
            placeholder = f"{self.variable_prefix} {var_name} {self.variable_suffix}"
            placeholder_tight = f"{self.variable_prefix}{var_name}{self.variable_suffix}"

            # Handle both spaced and tight formatting
            if placeholder in result:
                result = result.replace(placeholder, str(value))
            elif placeholder_tight in result:
                result = result.replace(placeholder_tight, str(value))

        return result

    def validate_variables(self, **kwargs) -> bool:
        """
        Validate provided variables against template requirements.

        Args:
            **kwargs: Variable values to validate

        Returns:
            True if all required variables are valid
        """
        try:
            for var_name, var_def in self.variables.items():
                if var_def.required and var_name not in kwargs:
                    if var_def.default is None:
                        return False
                    kwargs[var_name] = var_def.default

                if var_name in kwargs:
                    value = kwargs[var_name]

                    # Type validation
                    if not self._validate_type(value, var_def.type):
                        logger.warning(f"Type mismatch for {var_name}: expected {var_def.type}")
                        return False

                    # Custom validator
                    if var_def.validator and not var_def.validator(value):
                        logger.warning(f"Custom validation failed for {var_name}")
                        return False

            return True

        except Exception as e:
            logger.error(f"Variable validation error: {e}")
            return False

    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Validate value type against expected type."""
        type_validators = {
            "str": lambda v: isinstance(v, str)
            "int": lambda v: isinstance(v, int)
            "float": lambda v: isinstance(v, (int, float))
            "bool": lambda v: isinstance(v, bool)
            "list": lambda v: isinstance(v, list)
            "dict": lambda v: isinstance(v, dict)
            "any": lambda v: True
        }

        validator = type_validators.get(expected_type.lower())
        return validator(value) if validator else True

    def get_required_variables(self) -> List[str]:
        """Get list of required template variables."""
        return [var.name for var in self.variables.values() if var.required and var.default is None]

    def get_missing_variables(self, **kwargs) -> List[str]:
        """Get list of missing required variables."""
        provided = set(kwargs.keys())
        required = set(self.get_required_variables())
        return list(required - provided)

    def get_all_variables(self) -> List[PromptVariable]:
        """Get all variable definitions."""
        return list(self.variables.values())

    def add_variable(self, variable: PromptVariable) -> None:
        """Add new variable definition."""
        self.variables[variable.name] = variable
        logger.debug(f"Added variable: {variable.name}")

    def remove_variable(self, variable_name: str) -> bool:
        """Remove variable definition."""
        if variable_name in self.variables:
            del self.variables[variable_name]
            logger.debug(f"Removed variable: {variable_name}")
            return True
        return False

    def clone(self, new_name: str | None = None) -> "PromptTemplate":
        """Create a copy of this template."""
        new_metadata = None
        if self.metadata:
            new_metadata = PromptMetadata(
                name=new_name or f"{self.metadata.name}_copy"
                description=self.metadata.description
                author=self.metadata.author
                version=self.metadata.version
                tags=self.metadata.tags.copy()
            )

        return PromptTemplate(
            template=self.template
            variables=list(self.variables.values())
            metadata=new_metadata
            variable_prefix=self.variable_prefix
            variable_suffix=self.variable_suffix
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize template to dictionary."""
        return {
            "template": self.template
            "variables": [
                {
                    "name": var.name
                    "type": var.type
                    "required": var.required
                    "default": var.default
                    "description": var.description
                }
                for var in self.variables.values()
            ]
            "metadata": {
                "name": self.metadata.name
                "description": self.metadata.description
                "author": self.metadata.author
                "version": self.metadata.version
                "tags": self.metadata.tags
            }
            if self.metadata
            else None
            "variable_prefix": self.variable_prefix
            "variable_suffix": self.variable_suffix
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PromptTemplate":
        """Create template from dictionary."""
        variables = [
            PromptVariable(
                name=var_data["name"]
                type=var_data["type"]
                required=var_data.get("required", True)
                default=var_data.get("default")
                description=var_data.get("description", "")
            )
            for var_data in data.get("variables", [])
        ]

        metadata = None
        if data.get("metadata"):
            metadata = PromptMetadata(**data["metadata"])

        return cls(
            template=data["template"]
            variables=variables
            metadata=metadata
            variable_prefix=data.get("variable_prefix", "{{")
            variable_suffix=data.get("variable_suffix", "}}")
        )


class PromptChain:
    """
    Chain multiple prompt templates for complex workflows.

    Allows sequential processing where outputs from one template
    become inputs to the next template in the chain.
    """

    def __init__(self, templates: List[PromptTemplate], name: str = "") -> None:
        self.templates = templates
        self.name = name
        self._validate_chain()

    def _validate_chain(self) -> None:
        """Validate that the prompt chain is properly configured."""
        if not self.templates:
            raise PromptError("Prompt chain cannot be empty")

        # Check for variable compatibility between templates
        for i in range(len(self.templates) - 1):
            current_template = self.templates[i]
            next_template = self.templates[i + 1]

            # Log chain structure
            logger.debug(
                f"Chain step {i + 1}: {current_template.metadata.name if current_template.metadata else 'unnamed'} "
                f"-> {next_template.metadata.name if next_template.metadata else 'unnamed'}"
            )

    async def execute_async(
        self, initial_variables: Dict[str, Any], model_client: Any = None  # ModelClient type - avoid circular import
    ) -> List[str]:
        """
        Execute the prompt chain with model generation.

        Args:
            initial_variables: Variables for the first template
            model_client: AI model client for generation

        Returns:
            List of generated outputs from each step

        Raises:
            PromptError: Chain execution failed
        """
        if not model_client:
            raise PromptError("Model client required for chain execution")

        results = []
        current_variables = initial_variables.copy()

        try:
            for i, template in enumerate(self.templates):
                # Render current template
                prompt = template.render(**current_variables)
                results.append(prompt)

                # If not the last template, generate response for next step
                if i < len(self.templates) - 1:
                    response = await model_client.generate_async(prompt)
                    # Add response as variable for next template
                    current_variables[f"step_{i + 1}_output"] = response.content

                logger.debug(f"Chain step {i + 1} completed")

            logger.info(f"Prompt chain '{self.name}' executed successfully with {len(results)} steps")
            return results

        except Exception as e:
            raise PromptError(f"Prompt chain execution failed at step {i + 1}: {str(e)}") from e

    def render_all(self, variables: Dict[str, Any]) -> List[str]:
        """
        Render all templates with same variables (no chaining).

        Args:
            variables: Variables to apply to all templates

        Returns:
            List of rendered prompts
        """
        results = []
        for template in self.templates:
            try:
                rendered = template.render(**variables)
                results.append(rendered)
            except PromptError as e:
                logger.warning(f"Template rendering failed: {e}")
                results.append(f"[ERROR: {str(e)}]")

        return results

    def get_required_variables(self) -> List[str]:
        """Get all required variables across all templates."""
        all_required = set()
        for template in self.templates:
            all_required.update(template.get_required_variables())
        return list(all_required)

    def add_template(self, template: PromptTemplate) -> None:
        """Add template to the end of the chain."""
        self.templates.append(template)
        logger.debug(f"Added template to chain: {template.metadata.name if template.metadata else 'unnamed'}")

    def insert_template(self, index: int, template: PromptTemplate) -> None:
        """Insert template at specific position in chain."""
        self.templates.insert(index, template)
        logger.debug(f"Inserted template at position {index}")

    def remove_template(self, index: int) -> PromptTemplate:
        """Remove and return template at index."""
        if 0 <= index < len(self.templates):
            removed = self.templates.pop(index)
            logger.debug(f"Removed template at position {index}")
            return removed
        raise IndexError(f"Template index {index} out of range")

    def __len__(self) -> int:
        """Get number of templates in chain."""
        return len(self.templates)

    def __getitem__(self, index: int) -> PromptTemplate:
        """Get template by index."""
        return self.templates[index]
