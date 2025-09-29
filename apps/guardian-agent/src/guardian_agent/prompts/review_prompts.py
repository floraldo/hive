"""Prompt templates for code review generation."""

from pathlib import Path
from typing import Any, Dict, List, Optional

from hive_ai import PromptTemplate

from guardian_agent.core.interfaces import AnalysisResult, Severity


class ReviewPromptBuilder:
    """Builds optimized prompts for AI code review."""

    def __init__(self) -> None:
        """Initialize the prompt builder."""
        self.base_template = PromptTemplate(
            name="code_review",
            template="""You are an expert code reviewer for the Hive platform.
Review the following code and provide a comprehensive analysis.

File: {file_path}
Language: {language}

Code Content:
```{language}
{content}
```

{context_section}

{violations_section}

{patterns_section}

Please provide:
1. A concise summary of the code quality (2-3 sentences)
2. An overall score (0-100) based on:
   - Code quality and maintainability (40%)
   - Adherence to best practices (30%)
   - Performance and efficiency (20%)
   - Documentation and readability (10%)
3. Your confidence level (0-1) in this review
4. Up to 5 specific improvement suggestions not already covered by the analyzers

Format your response as JSON:
{{
    "summary": "...",
    "score": 85,
    "confidence": 0.9,
    "suggestions": [
        {{
            "message": "...",
            "line_range": [10, 20],
            "category": "performance|readability|maintainability|security",
            "example": "optional code example"
        }}
    ],
    "metadata": {{
        "strengths": ["..."],
        "areas_for_improvement": ["..."]
    }}
}}
""",
            variables=["file_path", "language", "content", "context_section", "violations_section", "patterns_section"],
        )

    def build_review_prompt(
        self,
        file_path: Path,
        content: str,
        analysis_results: List[AnalysisResult],
        similar_patterns: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """
        Build a comprehensive review prompt.

        Args:
            file_path: Path to the file being reviewed
            content: File content
            analysis_results: Results from other analyzers
            similar_patterns: Similar code patterns from vector search

        Returns:
            Formatted prompt string
        """
        # Determine language
        language = self._get_language(file_path)

        # Build context section
        context_section = self._build_context_section(analysis_results)

        # Build violations section
        violations_section = self._build_violations_section(analysis_results)

        # Build patterns section
        patterns_section = self._build_patterns_section(similar_patterns)

        # Format the prompt
        prompt = self.base_template.format(
            file_path=str(file_path),
            language=language,
            content=self._truncate_content(content),
            context_section=context_section,
            violations_section=violations_section,
            patterns_section=patterns_section,
        )

        return prompt

    def _get_language(self, file_path: Path) -> str:
        """Determine the programming language from file extension."""
        extension_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".jsx": "jsx",
            ".tsx": "tsx",
            ".java": "java",
            ".go": "go",
            ".rs": "rust",
            ".cpp": "cpp",
            ".c": "c",
            ".cs": "csharp",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
        }

        return extension_map.get(file_path.suffix.lower(), "text")

    def _truncate_content(self, content: str, max_lines: int = 500) -> str:
        """Truncate content if too long."""
        lines = content.split("\n")
        if len(lines) <= max_lines:
            return content

        # Include first and last portions
        truncated = lines[: max_lines // 2]
        truncated.append("\n... [truncated middle section] ...\n")
        truncated.extend(lines[-max_lines // 2 :])

        return "\n".join(truncated)

    def _build_context_section(self, analysis_results: List[AnalysisResult]) -> str:
        """Build context section from analysis results."""
        if not analysis_results:
            return ""

        lines = ["## Analysis Context", ""]

        # Aggregate metrics
        all_metrics = {}
        for result in analysis_results:
            all_metrics.update(result.metrics)

        if all_metrics:
            lines.append("### Code Metrics")
            for key, value in all_metrics.items():
                lines.append(f"- {key.replace('_', ' ').title()}: {value}")
            lines.append("")

        return "\n".join(lines)

    def _build_violations_section(self, analysis_results: List[AnalysisResult]) -> str:
        """Build violations section from analysis results."""
        all_violations = []
        for result in analysis_results:
            all_violations.extend(result.violations)

        if not all_violations:
            return "## Existing Issues\n\nNo violations detected by analyzers.\n"

        lines = ["## Existing Issues", "", f"The following {len(all_violations)} issues were already detected:", ""]

        # Group by severity
        by_severity = {
            Severity.CRITICAL: [],
            Severity.ERROR: [],
            Severity.WARNING: [],
            Severity.INFO: [],
        }

        for violation in all_violations:
            by_severity[violation.severity].append(violation)

        for severity in [Severity.CRITICAL, Severity.ERROR, Severity.WARNING, Severity.INFO]:
            violations = by_severity[severity]
            if violations:
                lines.append(f"### {severity.value.upper()} ({len(violations)})")
                for v in violations[:5]:  # Limit to 5 per severity
                    lines.append(f"- Line {v.line_number}: {v.message}")
                if len(violations) > 5:
                    lines.append(f"- ... and {len(violations) - 5} more")
                lines.append("")

        return "\n".join(lines)

    def _build_patterns_section(self, similar_patterns: Optional[List[Dict[str, Any]]]) -> str:
        """Build similar patterns section from vector search results."""
        if not similar_patterns:
            return ""

        lines = ["## Similar Code Patterns", "", "Found similar code in the codebase:", ""]

        for i, pattern in enumerate(similar_patterns[:3], 1):
            lines.append(f"{i}. {pattern.get('file', 'Unknown file')}")
            lines.append(f"   Similarity: {pattern.get('similarity', 0):.0%}")
            if pattern.get("description"):
                lines.append(f"   Context: {pattern['description']}")
            lines.append("")

        return "\n".join(lines)

    def build_fix_prompt(self, violation_description: str, code_snippet: str) -> str:
        """
        Build a prompt for generating fix suggestions.

        Args:
            violation_description: Description of the violation
            code_snippet: The problematic code

        Returns:
            Formatted fix prompt
        """
        prompt = f"""As an expert developer, provide a fix for the following issue:

Issue: {violation_description}

Problematic Code:
```python
{code_snippet}
```

Provide:
1. The corrected code
2. A brief explanation of the fix
3. Any potential side effects to watch for

Format as JSON:
{{
    "fixed_code": "...",
    "explanation": "...",
    "side_effects": ["..."]
}}
"""
        return prompt

    def build_explanation_prompt(self, code_snippet: str, question: str) -> str:
        """
        Build a prompt for explaining code.

        Args:
            code_snippet: Code to explain
            question: Specific question about the code

        Returns:
            Formatted explanation prompt
        """
        prompt = f"""Explain the following code, focusing on: {question}

Code:
```python
{code_snippet}
```

Provide a clear, concise explanation suitable for a code review comment.
Focus on practical implications and potential issues.
"""
        return prompt
