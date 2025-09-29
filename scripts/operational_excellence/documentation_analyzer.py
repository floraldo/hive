#!/usr/bin/env python3
"""
Documentation Analyzer - Operational Excellence Tool

Analyzes repository documentation to identify:
- Dead links (internal and external)
- TODO/FIXME/HACK comments in code
- Redundant or outdated documentation
- Documentation organization opportunities

Part of the Operational Excellence Campaign for platform hardening.
"""

import re
import sys
import time
from pathlib import Path

import requests


def find_all_markdown_files(root_dir: Path = None) -> list[Path]:
    """Find all markdown files in the repository"""
    if root_dir is None:
        root_dir = Path.cwd()

    md_files = []
    for md_file in root_dir.rglob("*.md"):
        # Skip hidden directories and files
        if any(part.startswith(".") for part in md_file.parts):
            continue
        md_files.append(md_file)

    return sorted(md_files)


def find_all_python_files(root_dir: Path = None) -> list[Path]:
    """Find all Python files in the repository"""
    if root_dir is None:
        root_dir = Path.cwd()

    py_files = []
    for py_file in root_dir.rglob("*.py"):
        # Skip hidden directories, __pycache__, .venv, etc.
        if any(part.startswith(".") or part == "__pycache__" for part in py_file.parts):
            continue
        py_files.append(py_file)

    return sorted(py_files)


def extract_links_from_markdown(file_path: Path) -> dict[str, list[tuple[str, int]]]:
    """Extract all links from a markdown file"""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return {"error": [f"Could not read file: {e}"]}

    links = {
        "internal": [],  # Links to other files in the repo
        "external": [],  # HTTP/HTTPS links
        "relative": [],  # Relative file paths
    }

    # Regex patterns for different link types
    markdown_link_pattern = r"\[([^\]]*)\]\(([^)]+)\)"

    for line_num, line in enumerate(content.split("\n"), 1):
        matches = re.findall(markdown_link_pattern, line)

        for link_text, link_url in matches:
            link_url = link_url.strip()

            if link_url.startswith(("http://", "https://")):
                links["external"].append((link_url, line_num))
            elif link_url.startswith("/") or "../" in link_url or "./" in link_url:
                links["relative"].append((link_url, line_num))
            elif link_url.endswith(".md") or "/" in link_url:
                links["internal"].append((link_url, line_num))

    return links


def check_internal_link(link: str, base_file: Path) -> bool:
    """Check if an internal link exists"""
    try:
        if link.startswith("/"):
            # Absolute path from repo root
            target_path = Path.cwd() / link.lstrip("/")
        else:
            # Relative path from current file
            target_path = (base_file.parent / link).resolve()

        return target_path.exists()
    except:
        return False


def check_external_link(url: str, timeout: int = 5) -> tuple[bool, str]:
    """Check if an external link is accessible"""
    try:
        response = requests.head(url, timeout=timeout, allow_redirects=True)
        if response.status_code < 400:
            return True, f"OK ({response.status_code})"
        else:
            return False, f"HTTP {response.status_code}"
    except requests.exceptions.Timeout:
        return False, "Timeout"
    except requests.exceptions.RequestException as e:
        return False, f"Error: {str(e)[:100]}"


def find_todo_comments(file_path: Path) -> list[tuple[str, int, str]]:
    """Find TODO/FIXME/HACK comments in a Python file"""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return []

    todos = []
    patterns = [
        (r"#\s*(TODO[:\s].*)", "TODO"),
        (r"#\s*(FIXME[:\s].*)", "FIXME"),
        (r"#\s*(XXX[:\s].*)", "XXX"),
        (r"#\s*(HACK[:\s].*)", "HACK"),
        (r"#\s*(BUG[:\s].*)", "BUG"),
        (r"#\s*(NOTE[:\s].*)", "NOTE"),
    ]

    for line_num, line in enumerate(content.split("\n"), 1):
        for pattern, comment_type in patterns:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                todos.append((comment_type, line_num, match.group(1).strip()))

    return todos


def analyze_documentation_redundancy(md_files: list[Path]) -> dict[str, list[Path]]:
    """Analyze documentation for potential redundancy"""
    categories = {
        "certification": [],
        "phase_reports": [],
        "architecture": [],
        "cleanup": [],
        "testing": [],
        "other": [],
    }

    for md_file in md_files:
        filename = md_file.name.lower()

        if "certification" in filename or "cert" in filename:
            categories["certification"].append(md_file)
        elif "phase" in filename or "v3" in filename:
            categories["phase_reports"].append(md_file)
        elif "architecture" in filename or "arch" in filename:
            categories["architecture"].append(md_file)
        elif "cleanup" in filename or "clean" in filename:
            categories["cleanup"].append(md_file)
        elif "test" in filename or "integration" in filename:
            categories["testing"].append(md_file)
        else:
            categories["other"].append(md_file)

    return categories


def generate_documentation_analysis_report() -> str:
    """Generate comprehensive documentation analysis report"""
    print("OPERATIONAL EXCELLENCE: Documentation Analysis")
    print("=" * 60)

    # Find all files
    md_files = find_all_markdown_files()
    py_files = find_all_python_files()

    # Analyze links
    dead_internal_links = []
    dead_external_links = []
    all_todos = []

    print(f"Analyzing {len(md_files)} markdown files for dead links...")

    for md_file in md_files[:20]:  # Limit to first 20 for performance
        links = extract_links_from_markdown(md_file)

        # Check internal links
        for link, line_num in links.get("internal", []) + links.get("relative", []):
            if not check_internal_link(link, md_file):
                dead_internal_links.append((md_file, link, line_num))

        # Check external links (sample only to avoid rate limiting)
        for link, line_num in links.get("external", [])[:3]:
            time.sleep(0.1)  # Rate limiting
            is_alive, status = check_external_link(link)
            if not is_alive:
                dead_external_links.append((md_file, link, line_num, status))

    print(f"Analyzing {len(py_files)} Python files for TODO comments...")

    # Analyze TODO comments (sample for performance)
    for py_file in py_files[:50]:  # Limit to first 50 for performance
        todos = find_todo_comments(py_file)
        for todo_type, line_num, comment in todos:
            all_todos.append((py_file, todo_type, line_num, comment))

    # Analyze documentation redundancy
    doc_categories = analyze_documentation_redundancy(md_files)

    # Generate report
    report = []
    report.append("# Documentation Analysis Report")
    report.append("")
    report.append("## Executive Summary")
    report.append(f"- **Markdown files analyzed**: {len(md_files)}")
    report.append(f"- **Python files analyzed**: {min(50, len(py_files))} of {len(py_files)}")
    report.append(f"- **Dead internal links**: {len(dead_internal_links)}")
    report.append(f"- **Dead external links**: {len(dead_external_links)}")
    report.append(f"- **TODO comments found**: {len(all_todos)}")
    report.append("")

    # Dead internal links
    if dead_internal_links:
        report.append("## Dead Internal Links")
        report.append("These links point to files that don't exist:")
        report.append("")
        for md_file, link, line_num in dead_internal_links[:20]:
            report.append(f"- `{md_file.relative_to(Path.cwd())}:{line_num}` -> `{link}`")
        if len(dead_internal_links) > 20:
            report.append(f"- ... and {len(dead_internal_links) - 20} more")
        report.append("")

    # Dead external links
    if dead_external_links:
        report.append("## Dead External Links")
        report.append("These external URLs are not accessible:")
        report.append("")
        for md_file, link, line_num, status in dead_external_links[:10]:
            report.append(f"- `{md_file.relative_to(Path.cwd())}:{line_num}` -> `{link}` ({status})")
        if len(dead_external_links) > 10:
            report.append(f"- ... and {len(dead_external_links) - 10} more")
        report.append("")

    # TODO comments analysis
    if all_todos:
        report.append("## TODO Comments Analysis")
        report.append("Technical debt and action items found in code:")
        report.append("")

        # Group by type
        todo_by_type = {}
        for py_file, todo_type, line_num, comment in all_todos:
            if todo_type not in todo_by_type:
                todo_by_type[todo_type] = []
            todo_by_type[todo_type].append((py_file, line_num, comment))

        for todo_type, todos in todo_by_type.items():
            report.append(f"### {todo_type} Comments ({len(todos)})")
            for py_file, line_num, comment in todos[:10]:
                report.append(f"- `{py_file.relative_to(Path.cwd())}:{line_num}` - {comment[:100]}")
            if len(todos) > 10:
                report.append(f"- ... and {len(todos) - 10} more")
            report.append("")

    # Documentation organization analysis
    report.append("## Documentation Organization Analysis")
    report.append("")

    for category, files in doc_categories.items():
        if files:
            report.append(f"### {category.replace('_', ' ').title()} ({len(files)} files)")
            for doc_file in files[:10]:
                report.append(f"- `{doc_file.relative_to(Path.cwd())}`")
            if len(files) > 10:
                report.append(f"- ... and {len(files) - 10} more")
            report.append("")

    # Recommendations
    report.append("## Recommendations")
    report.append("")

    if dead_internal_links:
        report.append("### Fix Dead Internal Links")
        report.append("1. Update or remove broken internal links")
        report.append("2. Consider using relative paths for better portability")
        report.append("")

    if dead_external_links:
        report.append("### Fix Dead External Links")
        report.append("1. Update URLs that have moved")
        report.append("2. Remove links to discontinued services")
        report.append("3. Consider archiving important external content")
        report.append("")

    if all_todos:
        report.append("### Address TODO Comments")
        report.append("1. Review and prioritize TODO items")
        report.append("2. Convert important TODOs to proper issues/tickets")
        report.append("3. Remove completed or obsolete TODO comments")
        report.append("")

    # Documentation cleanup recommendations
    phase_reports = doc_categories["phase_reports"]
    if len(phase_reports) > 5:
        report.append("### Documentation Cleanup")
        report.append(f"1. **Archive old phase reports** - {len(phase_reports)} phase reports can be consolidated")
        report.append("2. **Keep only current documentation** - Archive superseded reports")
        report.append("3. **Create documentation index** - Improve navigation")
        report.append("")

    return "\n".join(report)


def main():
    """Main execution function"""
    try:
        report = generate_documentation_analysis_report()

        # Write report to file
        report_path = Path("DOCUMENTATION_ANALYSIS_REPORT.md")
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)

        print("Documentation analysis complete!")
        print(f"Report saved to: {report_path}")

        return True

    except Exception as e:
        print(f"Documentation analysis failed: {e}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
