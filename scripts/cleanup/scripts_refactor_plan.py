#!/usr/bin/env python3
"""
Scripts Directory Refactoring Tool - Phase 1: Analysis and Planning

This script implements the systematic refactoring plan for the scripts directory,
following the guiding principles of consolidation, clarity, and safety.
"""

import ast
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class ScriptMetadata:
    """Metadata for a single script file"""

    path: str
    name: str
    purpose: str
    dependencies: list[str]
    execution_type: str  # python, shell, batch
    size_lines: int
    last_modified: str
    has_main: bool
    has_argparse: bool
    todo_count: int
    is_executable: bool


@dataclass
class RedundancyGroup:
    """Group of scripts with overlapping functionality"""

    group_name: str
    primary_script: str  # The best one to keep as base
    redundant_scripts: list[str]
    consolidation_strategy: str


class ScriptsAnalyzer:
    """Comprehensive analyzer for the scripts directory"""

    def __init__(self, scripts_root: Path):
        self.scripts_root = scripts_root
        self.project_root = scripts_root.parent
        self.metadata_map: dict[str, ScriptMetadata] = {}
        self.redundancy_groups: list[RedundancyGroup] = []

    def analyze_script(self, script_path: Path) -> ScriptMetadata:
        """Analyze a single script file and extract metadata"""
        try:
            content = script_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")

            # Extract purpose from docstring or comments
            purpose = self._extract_purpose(content, lines)

            # Extract dependencies
            dependencies = self._extract_dependencies(content, script_path.suffix)

            # Determine execution type
            execution_type = self._determine_execution_type(script_path, content)

            # Check for main function and argparse
            has_main = "def main(" in content or 'if __name__ == "__main__"' in content
            has_argparse = "argparse" in content or "ArgumentParser" in content

            # Count TODOs
            todo_count = len(
                [line for line in lines if any(marker in line.upper() for marker in ["TODO", "FIXME", "XXX", "HACK"])],
            )

            # Check if executable
            is_executable = script_path.suffix in [".sh", ".py"] and content.startswith("#!")

            return ScriptMetadata(
                path=str(script_path.relative_to(self.project_root)),
                name=script_path.name,
                purpose=purpose,
                dependencies=dependencies,
                execution_type=execution_type,
                size_lines=len(lines),
                last_modified=datetime.fromtimestamp(script_path.stat().st_mtime).isoformat(),
                has_main=has_main,
                has_argparse=has_argparse,
                todo_count=todo_count,
                is_executable=is_executable,
            )

        except Exception as e:
            # Return minimal metadata for problematic files
            return ScriptMetadata(
                path=str(script_path.relative_to(self.project_root)),
                name=script_path.name,
                purpose=f"Error analyzing: {e}",
                dependencies=[],
                execution_type="unknown",
                size_lines=0,
                last_modified="unknown",
                has_main=False,
                has_argparse=False,
                todo_count=0,
                is_executable=False,
            )

    def _extract_purpose(self, content: str, lines: list[str]) -> str:
        """Extract purpose from docstring or initial comments"""
        # Try to extract from module docstring
        try:
            tree = ast.parse(content)
            if (
                isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant)
                and isinstance(tree.body[0].value.value, str)
            ):
                return tree.body[0].value.value.strip().split("\n")[0]
        except:
            pass

        # Fall back to initial comments
        for line in lines[:10]:
            line = line.strip()
            if line.startswith('"""') or line.startswith("'''"):
                return line.strip('"""\'').strip()
            elif line.startswith("#") and not line.startswith("#!"):
                comment = line.lstrip("#").strip()
                if len(comment) > 10:  # Ignore short comments
                    return comment

        return "No clear purpose found"

    def _extract_dependencies(self, content: str, file_ext: str) -> list[str]:
        """Extract import dependencies"""
        dependencies = []

        if file_ext == ".py":
            # Extract Python imports
            import_pattern = r"^(?:from\s+(\S+)\s+import|import\s+(\S+))"
            for match in re.finditer(import_pattern, content, re.MULTILINE):
                module = match.group(1) or match.group(2)
                if module and not module.startswith("."):
                    dependencies.append(module.split(".")[0])

        elif file_ext in [".sh", ".bat"]:
            # Extract shell command dependencies
            command_pattern = r"\b(python|pip|poetry|docker|git|curl|wget)\b"
            dependencies.extend(set(re.findall(command_pattern, content)))

        return list(set(dependencies))

    def _determine_execution_type(self, script_path: Path, content: str) -> str:
        """Determine how the script is executed"""
        if script_path.suffix == ".py":
            return "python"
        elif script_path.suffix == ".sh":
            return "shell"
        elif script_path.suffix == ".bat":
            return "batch"
        elif content.startswith("#!/usr/bin/env python"):
            return "python"
        elif content.startswith("#!/bin/bash") or content.startswith("#!/bin/sh"):
            return "shell"
        else:
            return "unknown"

    def full_audit(self) -> dict[str, ScriptMetadata]:
        """Perform full audit of all scripts"""
        print("Phase 1: Full Script Audit")
        print("=" * 50)

        script_files = []
        for pattern in ["*.py", "*.sh", "*.bat"]:
            script_files.extend(self.scripts_root.rglob(pattern))

        total_files = len(script_files)
        print(f"Found {total_files} script files to analyze...")

        for i, script_path in enumerate(script_files, 1):
            print(f"[{i:2d}/{total_files}] Analyzing {script_path.name}...")
            metadata = self.analyze_script(script_path)
            self.metadata_map[metadata.path] = metadata

        print(f"\n[OK] Analyzed {len(self.metadata_map)} scripts")
        return self.metadata_map

    def identify_redundancy_groups(self) -> list[RedundancyGroup]:
        """Identify groups of scripts with overlapping functionality"""
        print("\nPhase 1b: Identifying Redundancy Groups")
        print("=" * 50)

        # Define redundancy groups based on analysis and user guidance
        group_definitions = [
            {
                "group_name": "cleanup_scripts",
                "keywords": ["cleanup", "clean", "comprehensive_cleanup", "targeted_cleanup"],
                "primary_strategy": "Keep most comprehensive, merge unique features",
            },
            {
                "group_name": "testing_scripts",
                "keywords": ["test", "integration", "validate", "cert"],
                "primary_strategy": "Keep comprehensive test runner",
            },
            {
                "group_name": "security_scripts",
                "keywords": ["security", "audit"],
                "primary_strategy": "Keep most comprehensive security audit",
            },
            {
                "group_name": "database_scripts",
                "keywords": ["database", "db", "optimize", "seed", "init"],
                "primary_strategy": "Merge into database toolkit",
            },
            {
                "group_name": "fixer_scripts",
                "keywords": ["fix_", "modernize", "add_type"],
                "primary_strategy": "Consolidate into maintenance toolkit",
            },
            {
                "group_name": "async_refactor_scripts",
                "keywords": ["async", "queen_async", "worker_async", "enhance_async"],
                "primary_strategy": "Archive - refactoring complete",
            },
            {
                "group_name": "type_hint_scripts",
                "keywords": ["type_hint", "modernize_type", "add_type"],
                "primary_strategy": "Keep best type hint fixer",
            },
        ]

        for group_def in group_definitions:
            matching_scripts = []

            for path, metadata in self.metadata_map.items():
                script_name_lower = metadata.name.lower()
                purpose_lower = metadata.purpose.lower()

                # Check if script matches this group
                if any(keyword in script_name_lower or keyword in purpose_lower for keyword in group_def["keywords"]):
                    matching_scripts.append(path)

            if len(matching_scripts) > 1:
                # Determine primary script (largest, most recent, or most comprehensive)
                primary = self._select_primary_script(matching_scripts)
                redundant = [s for s in matching_scripts if s != primary]

                group = RedundancyGroup(
                    group_name=group_def["group_name"],
                    primary_script=primary,
                    redundant_scripts=redundant,
                    consolidation_strategy=group_def["primary_strategy"],
                )
                self.redundancy_groups.append(group)

                print(f"[GROUP] {group_def['group_name']}: {len(matching_scripts)} scripts")
                print(f"   Primary: {Path(primary).name}")
                print(f"   Redundant: {[Path(s).name for s in redundant]}")

        print(f"\n[OK] Identified {len(self.redundancy_groups)} redundancy groups")
        return self.redundancy_groups

    def _select_primary_script(self, script_paths: list[str]) -> str:
        """Select the best script to keep as primary from a group"""
        scripts_data = [(path, self.metadata_map[path]) for path in script_paths]

        # Scoring criteria (higher is better)
        def score_script(path: str, metadata: ScriptMetadata) -> int:
            score = 0

            # Size (more comprehensive)
            score += metadata.size_lines // 10

            # Has proper main function
            if metadata.has_main:
                score += 20

            # Has argument parsing (more mature)
            if metadata.has_argparse:
                score += 15

            # Fewer TODOs (more complete)
            score -= metadata.todo_count * 5

            # Prefer "comprehensive" in name
            if "comprehensive" in metadata.name.lower():
                score += 30

            # Prefer operational_excellence (usually more mature)
            if "operational_excellence" in path:
                score += 25

            return score

        # Return the highest scoring script
        scored_scripts = [(path, score_script(path, meta)) for path, meta in scripts_data]
        return max(scored_scripts, key=lambda x: x[1])[0]

    def generate_audit_report(self) -> str:
        """Generate comprehensive audit report"""
        report = f"""# Scripts Directory Audit Report

**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Total Scripts Analyzed**: {len(self.metadata_map)}

## Executive Summary

### Current State Analysis
- **Total Files**: {len(self.metadata_map)}
- **Python Scripts**: {len([m for m in self.metadata_map.values() if m.execution_type == "python"])}
- **Shell Scripts**: {len([m for m in self.metadata_map.values() if m.execution_type == "shell"])}
- **Batch Scripts**: {len([m for m in self.metadata_map.values() if m.execution_type == "batch"])}

### Quality Metrics
- **Scripts with Main Functions**: {len([m for m in self.metadata_map.values() if m.has_main])}
- **Scripts with Argument Parsing**: {len([m for m in self.metadata_map.values() if m.has_argparse])}
- **Scripts with TODOs**: {len([m for m in self.metadata_map.values() if m.todo_count > 0])}
- **Total TODO Count**: {sum(m.todo_count for m in self.metadata_map.values())}

### Size Distribution
- **Large Scripts (>200 lines)**: {len([m for m in self.metadata_map.values() if m.size_lines > 200])}
- **Medium Scripts (50-200 lines)**: {len([m for m in self.metadata_map.values() if 50 <= m.size_lines <= 200])}
- **Small Scripts (<50 lines)**: {len([m for m in self.metadata_map.values() if m.size_lines < 50])}

## Redundancy Analysis

### Identified Groups
{chr(10).join(f"- **{group.group_name}**: {len(group.redundant_scripts) + 1} scripts (Primary: {Path(group.primary_script).name})" for group in self.redundancy_groups)}

### Consolidation Opportunities
Total scripts that can be consolidated or archived: {sum(len(group.redundant_scripts) for group in self.redundancy_groups)}

## Detailed Script Inventory

| Script | Type | Lines | Purpose | Dependencies |
|--------|------|-------|---------|--------------|
"""

        # Add detailed inventory
        for path in sorted(self.metadata_map.keys()):
            meta = self.metadata_map[path]
            deps_str = ", ".join(meta.dependencies[:3])  # Show first 3 deps
            if len(meta.dependencies) > 3:
                deps_str += f" (+{len(meta.dependencies) - 3} more)"

            report += (
                f"| {meta.name} | {meta.execution_type} | {meta.size_lines} | {meta.purpose[:50]}... | {deps_str} |\n"
            )

        return report

    def save_metadata(self, output_path: Path):
        """Save metadata map to JSON file"""
        metadata_dict = {path: asdict(meta) for path, meta in self.metadata_map.items()}

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(metadata_dict, f, indent=2, ensure_ascii=False)

        print(f"[SAVE] Metadata saved to {output_path}")


def main():
    """Main execution function"""
    print("Scripts Directory Refactoring - Phase 1: Analysis")
    print("=" * 60)

    scripts_root = Path(__file__).parent.parent
    analyzer = ScriptsAnalyzer(scripts_root)

    # Phase 1: Full audit
    metadata_map = analyzer.full_audit()

    # Phase 1b: Identify redundancy groups
    redundancy_groups = analyzer.identify_redundancy_groups()

    # Generate outputs
    output_dir = scripts_root / "cleanup"
    output_dir.mkdir(exist_ok=True)

    # Save metadata
    analyzer.save_metadata(output_dir / "scripts_metadata.json")

    # Generate audit report
    report = analyzer.generate_audit_report()
    report_path = output_dir / "scripts_audit_report.md"
    report_path.write_text(report, encoding="utf-8")

    print(f"\n[SAVE] Audit report saved to {report_path}")

    # Summary
    print("\nAnalysis Complete!")
    print(f"   - {len(metadata_map)} scripts analyzed")
    print(f"   - {len(redundancy_groups)} redundancy groups identified")
    print(f"   - {sum(len(g.redundant_scripts) for g in redundancy_groups)} scripts can be consolidated")
    print(
        f"   - Potential reduction: {sum(len(g.redundant_scripts) for g in redundancy_groups) / len(metadata_map) * 100:.1f}%",
    )

    print("\nNext Steps:")
    print(f"   1. Review audit report: {report_path}")
    print("   2. Run Phase 2: Consolidation planning")
    print("   3. Execute dry-run before making changes")


if __name__ == "__main__":
    main()
