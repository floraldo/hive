"""Context formatting with instructional priming for LLM agents.

Implements Design Decision 2 (Option C): Structured sections with
explicit instructions on how to use retrieved context.

Provides multiple output formats optimized for different agent needs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .models import PatternContext, RuleContext, StructuredContext


class FormatStyle(Enum):
    """Output format styles for different use cases."""

    INSTRUCTIONAL = "instructional"  # Full instructional priming (recommended)
    STRUCTURED = "structured"  # Organized sections without instructions
    MINIMAL = "minimal"  # Compact format for token efficiency
    MARKDOWN = "markdown"  # Pretty markdown for humans


@dataclass
class FormattingConfig:
    """Configuration for context formatting."""

    style: FormatStyle = FormatStyle.INSTRUCTIONAL
    include_metadata: bool = True
    include_relevance_scores: bool = True
    include_line_numbers: bool = False
    max_code_lines: int = 50  # Truncate long code snippets
    show_deprecation_warnings_first: bool = True  # Show warnings prominently


class ContextFormatter:
    """Format StructuredContext for LLM consumption with instructional priming.

    Implements multiple output formats optimized for different agent workflows:
    - Instructional: Full guidance on how to use context (best for code review)
    - Structured: Clean sections without heavy instructions (good for general use)
    - Minimal: Token-efficient format (for high-throughput scenarios)
    - Markdown: Human-readable pretty-printed format (for debugging/docs)
    """

    def __init__(self, config: FormattingConfig | None = None):
        """Initialize context formatter.

        Args:
            config: Formatting configuration

        """
        self.config = config or FormattingConfig()

    def format_context(self, context: StructuredContext) -> str:
        """Format StructuredContext based on configured style.

        Args:
            context: Structured context from RAG retrieval

        Returns:
            Formatted string ready for LLM prompt injection

        """
        if self.config.style == FormatStyle.INSTRUCTIONAL:
            return self._format_instructional(context)
        if self.config.style == FormatStyle.STRUCTURED:
            return self._format_structured(context)
        if self.config.style == FormatStyle.MINIMAL:
            return self._format_minimal(context)
        if self.config.style == FormatStyle.MARKDOWN:
            return self._format_markdown(context)
        return self._format_instructional(context)  # Default

    def _format_instructional(self, context: StructuredContext) -> str:
        """Format with full instructional priming (Option C).

        Provides explicit instructions on how to use each piece of context.
        """
        sections = ["Here is relevant context from the Hive codebase to help you complete your task.", ""]

        # Deprecation warnings FIRST (if configured)
        if self.config.show_deprecation_warnings_first and context.deprecation_warnings:
            sections.extend(self._format_deprecation_warnings_instructional(context.deprecation_warnings))

        # Code patterns with instructions
        if context.code_patterns:
            sections.extend(self._format_code_patterns_instructional(context.code_patterns))

        # Golden rules with instructions
        if context.golden_rules:
            sections.extend(self._format_golden_rules_instructional(context.golden_rules))

        # Metadata footer
        if self.config.include_metadata:
            sections.extend(self._format_metadata_footer(context))

        return "\n".join(sections)

    def _format_code_patterns_instructional(self, patterns: list[PatternContext]) -> list[str]:
        """Format code patterns with instructional priming."""
        sections = [
            "---",
            "### RELEVANT CODE PATTERN(S)",
            (
                "I have found existing code that is conceptually similar to your task. "
                "Use this as a **style and structural reference** for your implementation."
            ),
            "",
        ]

        for i, pattern in enumerate(patterns, 1):
            sections.append(f"**PATTERN {i}** (from `{pattern.source}`)")

            if pattern.purpose:
                sections.append(f"*Purpose*: {pattern.purpose}")

            if pattern.usage_context:
                sections.append(f"*Context*: {pattern.usage_context}")

            if self.config.include_relevance_scores:
                sections.append(f"*Relevance*: {pattern.relevance_score:.2f}")

            # Code block
            code = self._truncate_code(pattern.code)
            sections.append(f"```python\n{code}\n```")
            sections.append("")

        return sections

    def _format_golden_rules_instructional(self, rules: list[RuleContext]) -> list[str]:
        """Format golden rules with instructional priming."""
        sections = [
            "---",
            "### APPLICABLE GOLDEN RULE(S)",
            (
                "You **MUST** follow these architectural rules. "
                "If your generated code violates them, the task will fail validation."
            ),
            "",
        ]

        for rule in rules:
            sections.append(f"**Rule #{rule.rule_number}** ({rule.severity}): {rule.rule_text}")
            sections.append(f"*Why this matters*: {rule.relevance_reason}")

            if rule.examples:
                sections.append("*Examples*:")
                for example in rule.examples:
                    sections.append(f"  - {example}")

            sections.append("")

        return sections

    def _format_deprecation_warnings_instructional(self, warnings: list[str]) -> list[str]:
        """Format deprecation warnings with instructional priming."""
        sections = [
            "---",
            "### DEPRECATION WARNING(S)",
            ("The following patterns are **DEPRECATED** in the Hive codebase. Do NOT use them in your solution."),
            "",
        ]

        for warning in warnings:
            sections.append(f"- {warning}")

        sections.append("")

        return sections

    def _format_structured(self, context: StructuredContext) -> str:
        """Format with clean structure but minimal instructions."""
        sections = ["## Context from Hive Codebase", ""]

        # Deprecation warnings
        if context.deprecation_warnings:
            sections.append("### Deprecated Patterns")
            for warning in context.deprecation_warnings:
                sections.append(f"- {warning}")
            sections.append("")

        # Code patterns
        if context.code_patterns:
            sections.append("### Similar Code Patterns")
            for i, pattern in enumerate(context.code_patterns, 1):
                sections.append(f"**{i}. {pattern.source}**")
                if pattern.purpose:
                    sections.append(f"{pattern.purpose}")

                code = self._truncate_code(pattern.code)
                sections.append(f"```python\n{code}\n```")
                sections.append("")

        # Golden rules
        if context.golden_rules:
            sections.append("### Applicable Golden Rules")
            for rule in context.golden_rules:
                sections.append(f"- **Rule #{rule.rule_number}**: {rule.rule_text}")
            sections.append("")

        return "\n".join(sections)

    def _format_minimal(self, context: StructuredContext) -> str:
        """Format in token-efficient compact style."""
        sections = []

        # Deprecation
        if context.deprecation_warnings:
            sections.append(f"DEPRECATED: {'; '.join(context.deprecation_warnings)}")

        # Patterns
        if context.code_patterns:
            sections.append(f"PATTERNS ({len(context.code_patterns)}):")
            for pattern in context.code_patterns:
                code = self._truncate_code(pattern.code, max_lines=20)
                sections.append(f"  {pattern.source}: {code[:200]}")

        # Rules
        if context.golden_rules:
            sections.append(f"RULES: {', '.join(f'#{r.rule_number}' for r in context.golden_rules)}")

        return "\n".join(sections)

    def _format_markdown(self, context: StructuredContext) -> str:
        """Format as pretty markdown for human consumption."""
        sections = ["# RAG Context", ""]

        # Summary
        sections.append("## Summary")
        sections.append(f"- Code Patterns: {len(context.code_patterns)}")
        sections.append(f"- Golden Rules: {len(context.golden_rules)}")
        sections.append(f"- Deprecation Warnings: {len(context.deprecation_warnings)}")
        sections.append(f"- Retrieval Time: {context.retrieval_time_ms:.1f}ms")
        sections.append("")

        # Deprecation warnings
        if context.deprecation_warnings:
            sections.append("## Deprecation Warnings")
            for warning in context.deprecation_warnings:
                sections.append(f"> {warning}")
            sections.append("")

        # Code patterns
        if context.code_patterns:
            sections.append("## Code Patterns")
            for i, pattern in enumerate(context.code_patterns, 1):
                sections.append(f"### Pattern {i}: {pattern.source}")
                sections.append(f"**Relevance**: {pattern.relevance_score:.2%}")

                if pattern.purpose:
                    sections.append(f"**Purpose**: {pattern.purpose}")

                if pattern.usage_context:
                    sections.append(f"**Context**: {pattern.usage_context}")

                code = self._truncate_code(pattern.code)
                sections.append(f"```python\n{code}\n```")
                sections.append("")

        # Golden rules
        if context.golden_rules:
            sections.append("## Golden Rules")
            for rule in context.golden_rules:
                sections.append(f"### Rule #{rule.rule_number} ({rule.severity})")
                sections.append(f"{rule.rule_text}")
                sections.append(f"*{rule.relevance_reason}*")
                sections.append("")

        return "\n".join(sections)

    def _format_metadata_footer(self, context: StructuredContext) -> list[str]:
        """Format metadata footer for context."""
        sections = [
            "---",
            "*RAG Retrieval Metadata*",
            f"- Retrieved: {len(context.code_patterns)} patterns, {len(context.golden_rules)} rules",
            f"- Retrieval Time: {context.retrieval_time_ms:.1f}ms",
        ]

        if context.filters_applied:
            filters_str = ", ".join(f"{k}={v}" for k, v in context.filters_applied.items())
            sections.append(f"- Filters: {filters_str}")

        sections.append("")

        return sections

    def _truncate_code(self, code: str, max_lines: int | None = None) -> str:
        """Truncate long code snippets for token efficiency.

        Args:
            code: Code to truncate
            max_lines: Maximum lines (uses config default if None)

        Returns:
            Truncated code with ellipsis if needed

        """
        max_lines = max_lines or self.config.max_code_lines,
        lines = code.split("\n")

        if len(lines) <= max_lines:
            return code

        # Truncate and add ellipsis
        truncated = "\n".join(lines[:max_lines])
        truncated += f"\n... ({len(lines) - max_lines} more lines)"

        return truncated


# Convenience functions for common formatting patterns


def format_for_code_review(context: StructuredContext) -> str:
    """Format context for code review use case.

    Uses instructional priming with deprecation warnings first.
    """
    formatter = ContextFormatter(
        config=FormattingConfig(
            style=FormatStyle.INSTRUCTIONAL,
            show_deprecation_warnings_first=True,
            include_relevance_scores=True,
        ),
    )
    return formatter.format_context(context)


def format_for_implementation(context: StructuredContext) -> str:
    """Format context for implementation use case.

    Uses instructional priming focused on patterns and rules.
    """
    formatter = ContextFormatter(
        config=FormattingConfig(
            style=FormatStyle.INSTRUCTIONAL,
            show_deprecation_warnings_first=False,
            max_code_lines=80,  # More code for implementation
        ),
    )
    return formatter.format_context(context)


def format_for_documentation(context: StructuredContext) -> str:
    """Format context for human documentation.

    Uses markdown format for readability.
    """
    formatter = ContextFormatter(
        config=FormattingConfig(
            style=FormatStyle.MARKDOWN,
            include_metadata=True,
        ),
    )
    return formatter.format_context(context)


def format_minimal(context: StructuredContext) -> str:
    """Format context in minimal token-efficient style.

    Good for high-throughput scenarios or token budget constraints.
    """
    formatter = ContextFormatter(
        config=FormattingConfig(
            style=FormatStyle.MINIMAL,
            include_metadata=False,
        ),
    )
    return formatter.format_context(context)
