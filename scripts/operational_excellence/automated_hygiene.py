#!/usr/bin/env python3
"""
Automated Repository Hygiene Scanner

Proactive maintenance automation for repository health:
- Stale branch detection and reporting
- Documentation link validation
- TODO comment tracking
- Documentation linting

Part of the Automated Guardian Campaign for proactive operational excellence.
"""

import argparse
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

import requests


class RepositoryHygieneScanner:
    def __init__(self, repo_root: Path = None):
        self.repo_root = repo_root or Path.cwd()
        self.findings = {
            "stale_branches": [],
            "merged_branches": [],
            "dead_links": [],
            "new_todos": [],
            "markdown_issues": [],
        }
        self.stats = {"branches_analyzed": 0, "links_checked": 0, "files_scanned": 0, "todos_found": 0}

    def run_git_command(self, cmd: list[str]) -> str:
        """Run a git command and return output"""
        try:
            result = subprocess.run(["git"] + cmd, capture_output=True, text=True, check=True, cwd=self.repo_root)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            print(f"Git command failed: git {' '.join(cmd)}")
            print(f"Error: {e.stderr}")
            return ""

    def analyze_stale_branches(self) -> None:
        """Analyze branches for staleness and merge status"""
        print("Analyzing repository branches...")

        # Get all branches
        branches_output = self.run_git_command(["branch", "-a"])
        if not branches_output:
            return

        # Get merged branches
        merged_output = self.run_git_command(["branch", "--merged", "main"])
        merged_branches = set()
        for line in merged_output.split("\n"):
            line = line.strip()
            if line and not line.startswith("*") and line != "main":
                merged_branches.add(line)

        # Analyze each branch
        for line in branches_output.split("\n"):
            line = line.strip()
            if not line or line.startswith("*") or "HEAD ->" in line:
                continue

            # Clean branch name
            branch_name = line.replace("remotes/origin/", "")
            if branch_name == "main":
                continue

            self.stats["branches_analyzed"] += 1

            # Check if merged
            if branch_name in merged_branches:
                self.findings["merged_branches"].append(
                    {"name": branch_name, "type": "merged", "action": "Can be safely deleted"},
                )
                continue

            # Check staleness
            try:
                last_commit = self.run_git_command(["log", "-1", "--format=%ci", f"origin/{branch_name}"])
                if last_commit:
                    commit_date = datetime.fromisoformat(last_commit.split(" ")[0] + " " + last_commit.split(" ")[1])
                    days_old = (datetime.now() - commit_date).days

                    if days_old > 90:
                        self.findings["stale_branches"].append(
                            {
                                "name": branch_name,
                                "days_old": days_old,
                                "last_commit": last_commit,
                                "action": "Review for deletion",
                            },
                        )
            except Exception as e:
                print(f"Could not analyze branch {branch_name}: {e}")

    def check_documentation_links(self) -> None:
        """Check all documentation for dead links"""
        print("Checking documentation links...")

        md_files = list(self.repo_root.rglob("*.md"))
        # Filter out hidden directories and common ignore patterns
        md_files = [f for f in md_files if not any(part.startswith(".") for part in f.parts)]

        link_pattern = r"\[([^\]]*)\]\(([^)]+)\)"

        for md_file in md_files:
            try:
                with open(md_file, encoding="utf-8") as f:
                    content = f.read()

                self.stats["files_scanned"] += 1

                for line_num, line in enumerate(content.split("\n"), 1):
                    matches = re.findall(link_pattern, line)

                    for link_text, link_url in matches:
                        link_url = link_url.strip()
                        self.stats["links_checked"] += 1

                        # Check different types of links
                        if link_url.startswith(("http://", "https://")):
                            # External link - check if accessible
                            if not self._check_external_link(link_url):
                                self.findings["dead_links"].append(
                                    {
                                        "file": str(md_file.relative_to(self.repo_root)),
                                        "line": line_num,
                                        "url": link_url,
                                        "text": link_text,
                                        "type": "external",
                                    },
                                )

                        elif link_url.startswith("/") or "../" in link_url or "./" in link_url:
                            # Internal link - check if file exists
                            if not self._check_internal_link(link_url, md_file):
                                self.findings["dead_links"].append(
                                    {
                                        "file": str(md_file.relative_to(self.repo_root)),
                                        "line": line_num,
                                        "url": link_url,
                                        "text": link_text,
                                        "type": "internal",
                                    },
                                )

            except Exception as e:
                print(f"Error processing {md_file}: {e}")

    def _check_external_link(self, url: str, timeout: int = 5) -> bool:
        """Check if external link is accessible"""
        try:
            response = requests.head(url, timeout=timeout, allow_redirects=True)
            return response.status_code < 400
        except:
            return False

    def _check_internal_link(self, link: str, base_file: Path) -> bool:
        """Check if internal link exists"""
        try:
            if link.startswith("/"):
                # Absolute path from repo root
                target_path = self.repo_root / link.lstrip("/")
            else:
                # Relative path from current file
                target_path = (base_file.parent / link).resolve()

            return target_path.exists()
        except:
            return False

    def scan_todo_comments(self) -> None:
        """Scan for TODO/FIXME comments in code"""
        print("Scanning for TODO comments...")

        py_files = list(self.repo_root.rglob("*.py"))
        # Filter out hidden directories and common ignore patterns
        py_files = [f for f in py_files if not any(part.startswith(".") or part == "__pycache__" for part in f.parts)]

        todo_patterns = [
            (r"#\s*(TODO[:\s].*)", "TODO"),
            (r"#\s*(FIXME[:\s].*)", "FIXME"),
            (r"#\s*(XXX[:\s].*)", "XXX"),
            (r"#\s*(HACK[:\s].*)", "HACK"),
            (r"#\s*(BUG[:\s].*)", "BUG"),
        ]

        for py_file in py_files:
            try:
                with open(py_file, encoding="utf-8") as f:
                    content = f.read()

                self.stats["files_scanned"] += 1

                for line_num, line in enumerate(content.split("\n"), 1):
                    for pattern, comment_type in todo_patterns:
                        match = re.search(pattern, line, re.IGNORECASE)
                        if match:
                            self.stats["todos_found"] += 1

                            # Get git blame info for the line
                            author = self._get_line_author(py_file, line_num)

                            self.findings["new_todos"].append(
                                {
                                    "file": str(py_file.relative_to(self.repo_root)),
                                    "line": line_num,
                                    "type": comment_type,
                                    "comment": match.group(1).strip(),
                                    "author": author,
                                    "full_line": line.strip(),
                                },
                            )

            except Exception as e:
                print(f"Error processing {py_file}: {e}")

    def _get_line_author(self, file_path: Path, line_num: int) -> str:
        """Get the author of a specific line using git blame"""
        try:
            result = subprocess.run(
                ["git", "blame", "-L", f"{line_num},{line_num}", str(file_path)],
                capture_output=True,
                text=True,
                cwd=self.repo_root,
            )

            if result.returncode == 0 and result.stdout:
                # Parse git blame output to extract author
                blame_line = result.stdout.strip()
                # Format: commit (Author Name YYYY-MM-DD HH:MM:SS +0000 line_num) content
                match = re.search(r"\(([^)]+)\s+\d{4}-\d{2}-\d{2}", blame_line)
                if match:
                    return match.group(1).strip()
        except:
            pass

        return "Unknown"

    def lint_documentation(self) -> None:
        """Lint markdown documentation for style and formatting issues"""
        print("Linting documentation...")

        # This is a placeholder for markdown linting
        # In a real implementation, you'd integrate with markdownlint or similar
        md_files = list(self.repo_root.rglob("*.md"))
        md_files = [f for f in md_files if not any(part.startswith(".") for part in f.parts)]

        for md_file in md_files:
            try:
                with open(md_file, encoding="utf-8") as f:
                    content = f.read()

                # Basic checks
                lines = content.split("\n")

                # Check for trailing whitespace
                for line_num, line in enumerate(lines, 1):
                    if line.rstrip() != line:
                        self.findings["markdown_issues"].append(
                            {
                                "file": str(md_file.relative_to(self.repo_root)),
                                "line": line_num,
                                "issue": "Trailing whitespace",
                                "severity": "minor",
                            },
                        )

                # Check for missing title
                if not content.strip().startswith("#"):
                    self.findings["markdown_issues"].append(
                        {
                            "file": str(md_file.relative_to(self.repo_root)),
                            "line": 1,
                            "issue": "Missing document title (should start with #)",
                            "severity": "major",
                        },
                    )

            except Exception as e:
                print(f"Error linting {md_file}: {e}")

    def generate_report(self) -> str:
        """Generate comprehensive hygiene report"""
        report_lines = []

        # Executive Summary
        total_issues = (
            len(self.findings["stale_branches"])
            + len(self.findings["merged_branches"])
            + len(self.findings["dead_links"])
            + len(self.findings["new_todos"])
            + len(self.findings["markdown_issues"])
        )

        report_lines.extend(
            [
                "## 📊 Executive Summary",
                "",
                f"**Scan Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                f"**Total Issues Found**: {total_issues}",
                f"**Branches Analyzed**: {self.stats['branches_analyzed']}",
                f"**Links Checked**: {self.stats['links_checked']}",
                f"**Files Scanned**: {self.stats['files_scanned']}",
                f"**TODO Comments**: {self.stats['todos_found']}",
                "",
            ],
        )

        # Stale Branches
        if self.findings["merged_branches"] or self.findings["stale_branches"]:
            report_lines.extend(["## 🌿 Branch Hygiene", ""])

            if self.findings["merged_branches"]:
                report_lines.extend(
                    [
                        f"### ✅ Merged Branches ({len(self.findings['merged_branches'])})",
                        "These branches have been merged and can be safely deleted:",
                        "",
                    ],
                )

                for branch in self.findings["merged_branches"][:10]:
                    report_lines.append(f"- `{branch['name']}` - {branch['action']}")

                if len(self.findings["merged_branches"]) > 10:
                    report_lines.append(f"- ... and {len(self.findings['merged_branches']) - 10} more")

                report_lines.extend(["", "**Action Required**: Review and delete merged branches", ""])

            if self.findings["stale_branches"]:
                report_lines.extend(
                    [
                        f"### ⚠️ Stale Branches ({len(self.findings['stale_branches'])})",
                        "These branches haven't been updated in 90+ days:",
                        "",
                    ],
                )

                for branch in self.findings["stale_branches"][:10]:
                    report_lines.append(f"- `{branch['name']}` - {branch['days_old']} days old")

                if len(self.findings["stale_branches"]) > 10:
                    report_lines.append(f"- ... and {len(self.findings['stale_branches']) - 10} more")

                report_lines.extend(["", "**Action Required**: Review stale branches for deletion or reactivation", ""])

        # Dead Links
        if self.findings["dead_links"]:
            report_lines.extend(
                [
                    f"## 🔗 Dead Links ({len(self.findings['dead_links'])})",
                    "Documentation links that are no longer accessible:",
                    "",
                ],
            )

            for link in self.findings["dead_links"][:10]:
                report_lines.append(
                    f"- `{link['file']}:{link['line']}` - [{link['text']}]({link['url']}) ({link['type']})",
                )

            if len(self.findings["dead_links"]) > 10:
                report_lines.append(f"- ... and {len(self.findings['dead_links']) - 10} more")

            report_lines.extend(["", "**Action Required**: Update or remove broken links", ""])

        # TODO Comments
        if self.findings["new_todos"]:
            report_lines.extend(
                [f"## 📝 TODO Comments ({len(self.findings['new_todos'])})", "Technical debt items found in code:", ""],
            )

            # Group by type
            todos_by_type = {}
            for todo in self.findings["new_todos"]:
                todo_type = todo["type"]
                if todo_type not in todos_by_type:
                    todos_by_type[todo_type] = []
                todos_by_type[todo_type].append(todo)

            for todo_type, todos in todos_by_type.items():
                report_lines.append(f"### {todo_type} ({len(todos)})")
                for todo in todos[:5]:
                    report_lines.append(f"- `{todo['file']}:{todo['line']}` - {todo['comment']} (by {todo['author']})")
                if len(todos) > 5:
                    report_lines.append(f"- ... and {len(todos) - 5} more")
                report_lines.append("")

            report_lines.extend(["**Action Required**: Review TODO comments and create issues for important items", ""])

        # Markdown Issues
        if self.findings["markdown_issues"]:
            report_lines.extend(
                [
                    f"## 📄 Documentation Issues ({len(self.findings['markdown_issues'])})",
                    "Formatting and style issues in documentation:",
                    "",
                ],
            )

            for issue in self.findings["markdown_issues"][:10]:
                report_lines.append(f"- `{issue['file']}:{issue['line']}` - {issue['issue']} ({issue['severity']})")

            if len(self.findings["markdown_issues"]) > 10:
                report_lines.append(f"- ... and {len(self.findings['markdown_issues']) - 10} more")

            report_lines.extend(["", "**Action Required**: Fix documentation formatting issues", ""])

        # No Issues Found
        if total_issues == 0:
            report_lines.extend(
                ["## ✅ All Clear!", "", "No hygiene issues found. Repository is in excellent condition!", ""],
            )

        # Next Steps
        if total_issues > 0:
            report_lines.extend(
                [
                    "## 🎯 Recommended Actions",
                    "",
                    "1. **High Priority**: Address merged branches and dead links",
                    "2. **Medium Priority**: Review stale branches and TODO comments",
                    "3. **Low Priority**: Fix documentation formatting issues",
                    "",
                    "**Automation Note**: This report will be regenerated weekly. Address items above to keep the repository clean.",
                    "",
                ],
            )

        return "\n".join(report_lines)

    def save_report(self, report_content: str) -> None:
        """Save the hygiene report to file"""
        report_path = self.repo_root / "repository_hygiene_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        print(f"Report saved to: {report_path}")

        # Set GitHub Actions output
        has_findings = any(len(findings) > 0 for findings in self.findings.values())
        if os.getenv("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"has_findings={'true' if has_findings else 'false'}\n")


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="Automated Repository Hygiene Scanner")
    parser.add_argument("--analyze-branches", action="store_true", help="Analyze branch staleness")
    parser.add_argument("--check-links", action="store_true", help="Check documentation links")
    parser.add_argument("--scan-todos", action="store_true", help="Scan for TODO comments")
    parser.add_argument("--lint-docs", action="store_true", help="Lint documentation")
    parser.add_argument("--generate-report", action="store_true", help="Generate hygiene report")
    parser.add_argument("--all", action="store_true", help="Run all checks")

    args = parser.parse_args()

    if not any(
        [args.analyze_branches, args.check_links, args.scan_todos, args.lint_docs, args.generate_report, args.all],
    ):
        parser.print_help()
        return

    scanner = RepositoryHygieneScanner()

    print("🧹 AUTOMATED REPOSITORY HYGIENE SCANNER")
    print("=" * 60)

    if args.all or args.analyze_branches:
        scanner.analyze_stale_branches()

    if args.all or args.check_links:
        scanner.check_documentation_links()

    if args.all or args.scan_todos:
        scanner.scan_todo_comments()

    if args.all or args.lint_docs:
        scanner.lint_documentation()

    if args.all or args.generate_report:
        report = scanner.generate_report()
        scanner.save_report(report)
        print("\nHygiene scan complete!")


if __name__ == "__main__":
    main()
