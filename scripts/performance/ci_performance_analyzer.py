#!/usr/bin/env python3
"""CI/CD Performance & Cost Analyzer

Analyzes GitHub Actions performance metrics and identifies optimization opportunities:
- Pipeline runtime analysis
- Job bottleneck identification
- Dockerfile efficiency audit
- Cost optimization recommendations

Part of the Automated Guardian Campaign for CI/CD excellence.
"""

import argparse
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import requests


class CIPerfomanceAnalyzer:
    def __init__(self, repo_owner: str, repo_name: str, github_token: str):
        self.repo_owner = repo_owner
        self.repo_name = repo_name
        self.github_token = github_token
        self.base_url = "https://api.github.com"
        self.headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
        self.analysis_results = {
            "workflow_performance": [],
            "job_bottlenecks": [],
            "dockerfile_issues": [],
            "optimization_recommendations": [],
        }

    def get_workflow_runs(self, days_back: int = 30) -> list[dict]:
        """Get workflow runs from the last N days"""
        since_date = (datetime.now() - timedelta(days=days_back)).isoformat()

        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/actions/runs"
        params = {"created": f">={since_date}", "per_page": 100, "status": "completed"}

        all_runs = []
        page = 1

        while True:
            params["page"] = page
            response = requests.get(url, headers=self.headers, params=params, timeout=30)

            if response.status_code != 200:
                print(f"Error fetching workflow runs: {response.status_code}")
                break

            data = response.json()
            runs = data.get("workflow_runs", [])

            if not runs:
                break

            all_runs.extend(runs)

            if len(runs) < 100:  # Last page
                break

            page += 1

        return all_runs

    def get_workflow_jobs(self, run_id: int) -> list[dict]:
        """Get jobs for a specific workflow run"""
        url = f"{self.base_url}/repos/{self.repo_owner}/{self.repo_name}/actions/runs/{run_id}/jobs"

        response = requests.get(url, headers=self.headers, timeout=30)

        if response.status_code == 200:
            return response.json().get("jobs", [])

        return []

    def analyze_workflow_performance(self, days_back: int = 30) -> None:
        """Analyze workflow performance metrics"""
        print(f"Analyzing workflow performance over the last {days_back} days...")

        runs = self.get_workflow_runs(days_back)

        if not runs:
            print("No workflow runs found")
            return

        # Group runs by workflow
        workflows = {}

        for run in runs:
            workflow_name = run["name"]

            if workflow_name not in workflows:
                workflows[workflow_name] = {
                    "runs": [],
                    "total_duration": 0,
                    "avg_duration": 0,
                    "success_rate": 0,
                    "failure_count": 0,
                }

            # Calculate duration
            if run["created_at"] and run["updated_at"]:
                created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
                updated = datetime.fromisoformat(run["updated_at"].replace("Z", "+00:00"))
                duration = (updated - created).total_seconds()

                workflows[workflow_name]["runs"].append(
                    {
                        "id": run["id"],
                        "duration": duration,
                        "status": run["status"],
                        "conclusion": run["conclusion"],
                        "created_at": run["created_at"],
                    },
                )

                workflows[workflow_name]["total_duration"] += duration

                if run["conclusion"] != "success":
                    workflows[workflow_name]["failure_count"] += 1

        # Calculate statistics
        for workflow_name, data in workflows.items():
            run_count = len(data["runs"])
            if run_count > 0:
                data["avg_duration"] = data["total_duration"] / run_count
                data["success_rate"] = ((run_count - data["failure_count"]) / run_count) * 100

                # Find slowest runs
                data["runs"].sort(key=lambda x: x["duration"], reverse=True)
                data["slowest_runs"] = data["runs"][:5]

                self.analysis_results["workflow_performance"].append(
                    {
                        "name": workflow_name,
                        "run_count": run_count,
                        "avg_duration_minutes": data["avg_duration"] / 60,
                        "success_rate": data["success_rate"],
                        "failure_count": data["failure_count"],
                        "slowest_duration_minutes": data["runs"][0]["duration"] / 60 if data["runs"] else 0,
                    },
                )

    def analyze_job_bottlenecks(self, sample_runs: int = 20) -> None:
        """Analyze individual job performance to identify bottlenecks"""
        print(f"Analyzing job bottlenecks from {sample_runs} recent runs...")

        runs = self.get_workflow_runs(days_back=7)[:sample_runs]

        job_stats = {}

        for run in runs:
            jobs = self.get_workflow_jobs(run["id"])

            for job in jobs:
                job_name = job["name"]

                if job_name not in job_stats:
                    job_stats[job_name] = {"durations": [], "failure_count": 0, "total_runs": 0}

                job_stats[job_name]["total_runs"] += 1

                if job["started_at"] and job["completed_at"]:
                    started = datetime.fromisoformat(job["started_at"].replace("Z", "+00:00"))
                    completed = datetime.fromisoformat(job["completed_at"].replace("Z", "+00:00"))
                    duration = (completed - started).total_seconds()

                    job_stats[job_name]["durations"].append(duration)

                if job["conclusion"] != "success":
                    job_stats[job_name]["failure_count"] += 1

        # Calculate job statistics and identify bottlenecks
        for job_name, stats in job_stats.items():
            if stats["durations"]:
                avg_duration = sum(stats["durations"]) / len(stats["durations"])
                max_duration = max(stats["durations"])
                failure_rate = (stats["failure_count"] / stats["total_runs"]) * 100

                self.analysis_results["job_bottlenecks"].append(
                    {
                        "name": job_name,
                        "avg_duration_minutes": avg_duration / 60,
                        "max_duration_minutes": max_duration / 60,
                        "failure_rate": failure_rate,
                        "total_runs": stats["total_runs"],
                        "is_bottleneck": avg_duration > 300,  # 5+ minutes
                    },
                )

        # Sort by average duration
        self.analysis_results["job_bottlenecks"].sort(key=lambda x: x["avg_duration_minutes"], reverse=True)

    def analyze_dockerfiles(self) -> None:
        """Analyze Dockerfiles for efficiency issues"""
        print("Analyzing Dockerfiles for optimization opportunities...")

        dockerfile_paths = []

        # Find all Dockerfiles
        for dockerfile in Path.cwd().rglob("*Dockerfile*"):
            if dockerfile.is_file():
                dockerfile_paths.append(dockerfile)

        for dockerfile_path in dockerfile_paths:
            try:
                with open(dockerfile_path, encoding="utf-8") as f:
                    content = f.read()

                issues = self._analyze_dockerfile_content(content, dockerfile_path)

                if issues:
                    self.analysis_results["dockerfile_issues"].append(
                        {"file": str(dockerfile_path.relative_to(Path.cwd())), "issues": issues},
                    )

            except Exception as e:
                print(f"Error analyzing {dockerfile_path}: {e}")

    def _analyze_dockerfile_content(self, content: str, filepath: Path) -> list[dict]:
        """Analyze Dockerfile content for common issues"""
        issues = []
        lines = content.split("\n")

        # Check for common anti-patterns
        deps_installed = False

        for i, line in enumerate(lines, 1):
            line = line.strip()

            # Check for COPY . . before dependency installation
            if line.startswith("COPY . .") and not deps_installed:
                issues.append(
                    {
                        "line": i,
                        "issue": "COPY . . before dependency installation breaks layer caching",
                        "severity": "high",
                        "recommendation": "Copy dependency files first, install deps, then copy source code",
                    },
                )

            # Check for dependency installation
            if any(cmd in line.lower() for cmd in ["pip install", "npm install", "apt-get install"]):
                deps_installed = True

            # Check for missing --no-cache-dir with pip
            if "pip install" in line and "--no-cache-dir" not in line:
                issues.append(
                    {
                        "line": i,
                        "issue": "pip install without --no-cache-dir increases image size",
                        "severity": "medium",
                        "recommendation": "Add --no-cache-dir flag to pip install commands",
                    },
                )

            # Check for apt-get without cleanup
            if "apt-get install" in line and i < len(lines) - 1:
                next_lines = "\n".join(lines[i : i + 3])
                if "apt-get clean" not in next_lines and "rm -rf /var/lib/apt" not in next_lines:
                    issues.append(
                        {
                            "line": i,
                            "issue": "apt-get install without cleanup increases image size",
                            "severity": "medium",
                            "recommendation": "Add apt-get clean && rm -rf /var/lib/apt/lists/* after apt-get install",
                        },
                    )

            # Check for multiple RUN commands that could be combined
            if line.startswith("RUN ") and i < len(lines) - 1:
                next_line = lines[i].strip()
                if next_line.startswith("RUN "):
                    issues.append(
                        {
                            "line": i,
                            "issue": "Multiple consecutive RUN commands create unnecessary layers",
                            "severity": "low",
                            "recommendation": "Combine RUN commands with && to reduce layers",
                        },
                    )

        return issues

    def generate_optimization_recommendations(self) -> None:
        """Generate specific optimization recommendations based on analysis"""
        recommendations = []

        # Workflow-level recommendations
        slow_workflows = [w for w in self.analysis_results["workflow_performance"] if w["avg_duration_minutes"] > 10]

        for workflow in slow_workflows:
            recommendations.append(
                {
                    "type": "workflow",
                    "target": workflow["name"],
                    "issue": f"Workflow averages {workflow['avg_duration_minutes']:.1f} minutes",
                    "recommendation": "Consider parallelizing jobs or optimizing slow steps",
                    "priority": "high" if workflow["avg_duration_minutes"] > 20 else "medium",
                },
            )

        # Job-level recommendations
        bottleneck_jobs = [j for j in self.analysis_results["job_bottlenecks"] if j["is_bottleneck"]]

        for job in bottleneck_jobs[:5]:  # Top 5 bottlenecks
            if "test" in job["name"].lower():
                recommendation = "Split tests into parallel jobs or optimize test execution"
            elif "build" in job["name"].lower():
                recommendation = "Optimize build process, use caching, or upgrade runner"
            else:
                recommendation = "Analyze job steps and optimize slow operations"

            recommendations.append(
                {
                    "type": "job",
                    "target": job["name"],
                    "issue": f"Job averages {job['avg_duration_minutes']:.1f} minutes",
                    "recommendation": recommendation,
                    "priority": "high" if job["avg_duration_minutes"] > 15 else "medium",
                },
            )

        # Dockerfile recommendations
        for dockerfile in self.analysis_results["dockerfile_issues"]:
            high_severity_issues = [i for i in dockerfile["issues"] if i["severity"] == "high"]

            if high_severity_issues:
                recommendations.append(
                    {
                        "type": "dockerfile",
                        "target": dockerfile["file"],
                        "issue": f"{len(high_severity_issues)} high-severity optimization issues",
                        "recommendation": "Fix layer caching and dependency installation order",
                        "priority": "high",
                    },
                )

        self.analysis_results["optimization_recommendations"] = recommendations

    def generate_report(self) -> str:
        """Generate comprehensive CI/CD performance report"""
        report_lines = []

        # Executive Summary
        total_workflows = len(self.analysis_results["workflow_performance"])
        slow_workflows = len(
            [w for w in self.analysis_results["workflow_performance"] if w["avg_duration_minutes"] > 10],
        )
        bottleneck_jobs = len([j for j in self.analysis_results["job_bottlenecks"] if j["is_bottleneck"]])
        dockerfile_issues = sum(len(d["issues"]) for d in self.analysis_results["dockerfile_issues"])

        report_lines.extend(
            [
                "# 🚀 CI/CD Performance Analysis Report",
                "",
                f"**Analysis Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}",
                f"**Repository**: {self.repo_owner}/{self.repo_name}",
                "",
                "## 📊 Executive Summary",
                "",
                f"- **Workflows Analyzed**: {total_workflows}",
                f"- **Slow Workflows (>10min)**: {slow_workflows}",
                f"- **Job Bottlenecks (>5min)**: {bottleneck_jobs}",
                f"- **Dockerfile Issues**: {dockerfile_issues}",
                f"- **Optimization Opportunities**: {len(self.analysis_results['optimization_recommendations'])}",
                "",
            ],
        )

        # Workflow Performance
        if self.analysis_results["workflow_performance"]:
            report_lines.extend(["## ⚡ Workflow Performance", ""])

            # Top 5 slowest workflows
            slowest = sorted(
                self.analysis_results["workflow_performance"],
                key=lambda x: x["avg_duration_minutes"],
                reverse=True,
            )[:5]

            report_lines.extend(["### Slowest Workflows", ""])

            for workflow in slowest:
                status_emoji = (
                    "🔴"
                    if workflow["avg_duration_minutes"] > 20
                    else "🟡" if workflow["avg_duration_minutes"] > 10 else "🟢"
                )
                report_lines.append(
                    f"{status_emoji} **{workflow['name']}**: {workflow['avg_duration_minutes']:.1f}min avg "
                    f"({workflow['success_rate']:.1f}% success rate, {workflow['run_count']} runs)",
                )

            report_lines.append("")

        # Job Bottlenecks
        if self.analysis_results["job_bottlenecks"]:
            report_lines.extend(["## 🐌 Job Bottlenecks", "", "### Top 5 Slowest Jobs", ""])

            for job in self.analysis_results["job_bottlenecks"][:5]:
                status_emoji = (
                    "🔴" if job["avg_duration_minutes"] > 15 else "🟡" if job["avg_duration_minutes"] > 5 else "🟢"
                )
                report_lines.append(
                    f"{status_emoji} **{job['name']}**: {job['avg_duration_minutes']:.1f}min avg "
                    f"(max: {job['max_duration_minutes']:.1f}min, {job['failure_rate']:.1f}% failure rate)",
                )

            report_lines.append("")

        # Dockerfile Issues
        if self.analysis_results["dockerfile_issues"]:
            report_lines.extend(["## 🐳 Dockerfile Optimization", ""])

            for dockerfile in self.analysis_results["dockerfile_issues"]:
                report_lines.append(f"### {dockerfile['file']}")

                for issue in dockerfile["issues"]:
                    severity_emoji = (
                        "🔴" if issue["severity"] == "high" else "🟡" if issue["severity"] == "medium" else "🔵"
                    )
                    report_lines.append(f"{severity_emoji} **Line {issue['line']}**: {issue['issue']}")
                    report_lines.append(f"   *Recommendation*: {issue['recommendation']}")

                report_lines.append("")

        # Optimization Recommendations
        if self.analysis_results["optimization_recommendations"]:
            report_lines.extend(["## 🎯 Optimization Recommendations", ""])

            # Group by priority
            high_priority = [
                r for r in self.analysis_results["optimization_recommendations"] if r["priority"] == "high"
            ]
            medium_priority = [
                r for r in self.analysis_results["optimization_recommendations"] if r["priority"] == "medium"
            ]

            if high_priority:
                report_lines.extend(["### 🔴 High Priority", ""])

                for rec in high_priority:
                    report_lines.append(f"- **{rec['target']}**: {rec['issue']}")
                    report_lines.append(f"  *Action*: {rec['recommendation']}")

                report_lines.append("")

            if medium_priority:
                report_lines.extend(["### 🟡 Medium Priority", ""])

                for rec in medium_priority:
                    report_lines.append(f"- **{rec['target']}**: {rec['issue']}")
                    report_lines.append(f"  *Action*: {rec['recommendation']}")

                report_lines.append("")

        # Cost Estimation
        total_minutes = sum(
            w["avg_duration_minutes"] * w["run_count"] for w in self.analysis_results["workflow_performance"]
        )

        # GitHub Actions pricing: ~$0.008 per minute for Linux runners
        estimated_cost = total_minutes * 0.008

        report_lines.extend(
            [
                "## 💰 Cost Analysis",
                "",
                f"- **Total CI/CD Minutes (30 days)**: {total_minutes:.0f} minutes",
                f"- **Estimated Monthly Cost**: ${estimated_cost:.2f}",
                "",
            ],
        )

        if slow_workflows > 0 or bottleneck_jobs > 0:
            potential_savings = (slow_workflows * 5 + bottleneck_jobs * 3) * 30 * 0.008  # Rough estimate
            report_lines.extend([f"- **Potential Monthly Savings**: ${potential_savings:.2f} (with optimizations)", ""])

        # Next Steps
        report_lines.extend(
            [
                "## 📋 Next Steps",
                "",
                "1. **Address high-priority optimizations** to reduce build times",
                "2. **Implement Dockerfile improvements** for faster image builds",
                "3. **Consider parallel job execution** for slow workflows",
                "4. **Monitor performance trends** with regular analysis",
                "",
                "---",
                "",
                "*This analysis helps optimize CI/CD performance and reduce costs while maintaining quality.*",
            ],
        )

        return "\n".join(report_lines)

    def save_report(self, report_content: str) -> None:
        """Save the performance analysis report"""
        report_path = Path.cwd() / "ci_performance_analysis_report.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        print(f"Report saved to: {report_path}")


def main():
    """Main execution function"""
    parser = argparse.ArgumentParser(description="CI/CD Performance Analyzer")
    parser.add_argument("--repo-owner", required=True, help="GitHub repository owner")
    parser.add_argument("--repo-name", required=True, help="GitHub repository name")
    parser.add_argument("--github-token", help="GitHub API token (or set GITHUB_TOKEN env var)")
    parser.add_argument("--days", type=int, default=30, help="Days of history to analyze")

    args = parser.parse_args()

    github_token = args.github_token or os.getenv("GITHUB_TOKEN")
    if not github_token:
        print("Error: GitHub token required. Use --github-token or set GITHUB_TOKEN environment variable.")
        return 1

    analyzer = CIPerfomanceAnalyzer(args.repo_owner, args.repo_name, github_token)

    print("🚀 CI/CD PERFORMANCE ANALYZER")
    print("=" * 60)

    try:
        # Run analysis
        analyzer.analyze_workflow_performance(args.days)
        analyzer.analyze_job_bottlenecks()
        analyzer.analyze_dockerfiles()
        analyzer.generate_optimization_recommendations()

        # Generate and save report
        report = analyzer.generate_report()
        analyzer.save_report(report)

        print("\nCI/CD performance analysis complete!")
        return 0

    except Exception as e:
        print(f"Analysis failed: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
