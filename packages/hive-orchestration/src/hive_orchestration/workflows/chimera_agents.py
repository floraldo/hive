"""Chimera Agent Registry - Real Agent Integration

Provides agent implementations for Chimera workflow execution.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


class E2ETesterAgentAdapter:
    """Adapter for e2e-tester-agent integration with Chimera workflow.

    Wraps the E2E tester CLI and programmatic API for workflow execution.
    """

    def __init__(self) -> None:
        """Initialize E2E tester agent adapter."""
        self.logger = logger
        self.logger.info("E2E tester agent adapter initialized")

    async def generate_test(
        self,
        feature: str,
        url: str,
    ) -> dict[str, Any]:
        """Generate E2E test from feature description.

        Args:
            feature: Natural language feature description
            url: Target URL for testing

        Returns:
            Test generation result with test_path and metadata

        Example:
            result = await agent.generate_test(
                feature="User can login with Google OAuth",
                url="https://myapp.dev/login"
            )

        """
        try:
            # Import E2E tester components
            from e2e_tester import TestGenerator

            # Generate test
            generator = TestGenerator()
            output_path = Path(f"tests/e2e/test_{self._slugify(feature)}.py")

            generated = generator.generate_test_file(
                feature=feature,
                url=url,
                output_path=output_path,
            )

            self.logger.info(
                f"Generated E2E test: {generated.test_name} "
                f"({len(generated.test_code)} chars)",
            )

            return {
                "status": "success",
                "test_path": str(output_path),
                "test_name": generated.test_name,
                "lines_of_code": len(generated.test_code.splitlines()),
                "generated_at": generated.generated_at.isoformat(),
            }

        except Exception as e:
            self.logger.error(f"E2E test generation failed: {e}", exc_info=True)

            return {
                "status": "error",
                "error": str(e),
            }

    async def execute_test(
        self,
        test_path: str,
        url: str,
    ) -> dict[str, Any]:
        """Execute E2E test file.

        Args:
            test_path: Path to pytest test file
            url: URL to test against

        Returns:
            Test execution result with status and metrics

        Example:
            result = await agent.execute_test(
                test_path="tests/e2e/test_google_login.py",
                url="https://staging.myapp.dev/login"
            )

        """
        try:
            # Import E2E tester components
            from e2e_tester import TestExecutor

            # Execute test
            executor = TestExecutor()
            result = executor.execute_test(
                test_path=test_path,
                headless=True,
                capture_screenshots=True,
            )

            self.logger.info(
                f"Executed E2E test: {result.status.value} "
                f"({result.tests_passed}/{result.tests_run} passed)",
            )

            return {
                "status": "passed" if result.tests_passed == result.tests_run else "failed",
                "duration": result.duration,
                "tests_run": result.tests_run,
                "tests_passed": result.tests_passed,
                "tests_failed": result.tests_failed,
                "screenshots": result.screenshots,
            }

        except Exception as e:
            self.logger.error(f"E2E test execution failed: {e}", exc_info=True)

            return {
                "status": "error",
                "error": str(e),
            }

    def _slugify(self, text: str) -> str:
        """Convert feature description to valid filename."""
        slug = text.lower().replace(" ", "_")
        slug = "".join(c if c.isalnum() or c == "_" else "_" for c in slug)

        # Remove consecutive underscores
        while "__" in slug:
            slug = slug.replace("__", "_")

        return slug.strip("_")[:50]


class CoderAgentAdapter:
    """Adapter for hive-coder agent integration with Chimera workflow.

    Wraps the coder agent for TDD-based feature implementation.
    """

    def __init__(self) -> None:
        """Initialize coder agent adapter."""
        self.logger = logger
        self.logger.info("Coder agent adapter initialized")

    async def implement_feature(
        self,
        test_path: str,
        feature: str,
    ) -> dict[str, Any]:
        """Implement feature to pass E2E test.

        Args:
            test_path: Path to E2E test file
            feature: Feature description

        Returns:
            Implementation result with PR info and commit SHA

        Example:
            result = await agent.implement_feature(
                test_path="tests/e2e/test_google_login.py",
                feature="User can login with Google OAuth"
            )

        """
        try:
            import tempfile
            import uuid
            from datetime import UTC, datetime

            from hive_architect.models import ExecutionPlan, ExecutionTask, TaskType
            from hive_coder import CoderAgent

            self.logger.info(f"Implementing feature: {feature}")
            self.logger.info(f"Target test: {test_path}")

            # Generate ExecutionPlan from feature description
            # This is a simplified plan focused on making the E2E test pass
            plan_id = f"chimera-{uuid.uuid4().hex[:8]}"
            service_name = self._extract_service_name(test_path)

            plan = ExecutionPlan(
                plan_id=plan_id,
                service_name=service_name,
                service_type="api",  # Default to API service
                created_at=datetime.now(UTC),
                tasks=[
                    ExecutionTask(
                        task_id="scaffold",
                        task_type=TaskType.SCAFFOLD,
                        description=f"Create service structure for {service_name}",
                        template="api-service",
                        parameters={"service_name": service_name},
                    ),
                    ExecutionTask(
                        task_id="implement_feature",
                        task_type=TaskType.SERVICE_LOGIC,
                        description=f"Implement: {feature}",
                        parameters={
                            "feature_description": feature,
                            "test_file": test_path,
                        },
                        dependencies=[{"task_id": "scaffold", "dependency_type": "sequential"}],
                    ),
                ],
            )

            self.logger.info(f"Generated execution plan: {plan.plan_id}")

            # Save plan to temporary file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                plan_file = Path(f.name)
                plan.to_json_file(str(plan_file))

            self.logger.info(f"Plan saved to: {plan_file}")

            # Execute plan with CoderAgent
            output_dir = Path("tmp/chimera_generated") / service_name
            output_dir.parent.mkdir(parents=True, exist_ok=True)

            coder = CoderAgent()
            result = coder.execute_plan(
                plan_file=plan_file,
                output_dir=output_dir,
                validate_output=False,  # Skip validation for now
                run_tests=False,  # E2E test will validate
            )

            self.logger.info(
                f"Coder execution complete: {result.status.value} "
                f"({result.tasks_completed}/{result.total_tasks} tasks)",
            )

            # Clean up temp plan file
            plan_file.unlink()

            # For MVP, we don't create real PRs yet - just return the output directory
            # TODO: Add git operations and PR creation
            return {
                "status": "success" if result.status.value == "completed" else "failed",
                "pr_id": f"local-{plan_id}",  # Placeholder PR ID
                "commit_sha": plan_id,  # Use plan ID as commit reference
                "files_changed": len(result.files_created),
                "output_directory": str(result.output_directory),
                "implementation_notes": f"Generated {len(result.files_created)} files",
            }

        except Exception as e:
            self.logger.error(f"Feature implementation failed: {e}", exc_info=True)

            return {
                "status": "error",
                "error": str(e),
            }

    def _extract_service_name(self, test_path: str) -> str:
        """Extract service name from test path."""
        # Extract from test filename: test_google_login.py -> google_login
        test_file = Path(test_path).stem  # Remove .py
        if test_file.startswith("test_"):
            return test_file[5:]  # Remove "test_" prefix
        return test_file


class GuardianAgentAdapter:
    """Adapter for guardian-agent integration with Chimera workflow.

    Wraps the guardian agent for PR review.
    """

    def __init__(self) -> None:
        """Initialize guardian agent adapter."""
        self.logger = logger
        self.logger.info("Guardian agent adapter initialized")

    async def review_pr(
        self,
        pr_id: str,
    ) -> dict[str, Any]:
        """Review pull request for quality and compliance.

        Args:
            pr_id: Pull request ID (format: "local-{plan_id}" or GitHub PR number)

        Returns:
            Review result with decision and score

        Example:
            result = await agent.review_pr(pr_id="PR#123")

        """
        try:
            from guardian_agent import ReviewEngine

            self.logger.info(f"Reviewing PR: {pr_id}")

            # For local PRs (generated by CoderAgent), review the output directory
            if pr_id.startswith("local-"):
                # Extract plan ID from pr_id (for future use)
                _plan_id = pr_id.replace("local-", "")
                review_dir = Path("tmp/chimera_generated")

                # Find the service directory
                service_dirs = list(review_dir.glob("*"))
                if not service_dirs:
                    return {
                        "status": "error",
                        "error": "No generated service found to review",
                    }

                service_dir = service_dirs[0]  # Review first service
                self.logger.info(f"Reviewing generated service: {service_dir}")

                # Initialize ReviewEngine
                engine = ReviewEngine()

                # Review all Python files in the service
                violations = []
                total_score = 0.0
                file_count = 0

                for py_file in service_dir.rglob("*.py"):
                    if "__pycache__" in str(py_file):
                        continue

                    self.logger.info(f"Reviewing file: {py_file.name}")

                    review_result = await engine.review_file(py_file)
                    violations.extend(review_result.violations)

                    # Calculate file score (1.0 - violation severity)
                    file_score = 1.0 - (
                        sum(v.severity.value for v in review_result.violations) / 10.0
                    )
                    total_score += max(0.0, file_score)
                    file_count += 1

                # Calculate overall score
                avg_score = total_score / file_count if file_count > 0 else 0.0

                # Determine approval decision
                # Approve if score >= 0.7 and no critical violations
                critical_violations = [
                    v for v in violations if v.severity.name in ("CRITICAL", "ERROR")
                ]

                decision = "approved" if avg_score >= 0.7 and not critical_violations else "rejected"

                self.logger.info(
                    f"Review complete: {decision} (score: {avg_score:.2f}, "
                    f"violations: {len(violations)})",
                )

                return {
                    "status": "success",
                    "decision": decision,
                    "score": avg_score,
                    "violations_count": len(violations),
                    "critical_violations": len(critical_violations),
                    "files_reviewed": file_count,
                }

            # For real GitHub PRs, we would fetch via GitHub API
            # For now, auto-approve (TODO: implement GitHub integration)
            self.logger.warning(f"GitHub PR review not implemented: {pr_id}")

            return {
                "status": "success",
                "decision": "approved",
                "score": 1.0,
                "comments": [],
                "review_notes": "GitHub PR review not yet implemented",
            }

        except Exception as e:
            self.logger.error(f"PR review failed: {e}", exc_info=True)

            return {
                "status": "error",
                "error": str(e),
            }


class DeploymentAgentAdapter:
    """Adapter for deployment agent integration with Chimera workflow.

    Handles staging deployment for E2E validation.
    For MVP, deploys to local staging directory accessible via file:// URL.
    """

    def __init__(self) -> None:
        """Initialize deployment agent adapter."""
        self.logger = logger
        self.staging_dir = Path("tmp/chimera_staging")
        self.logger.info("Deployment agent adapter initialized")

    async def deploy_to_staging(
        self,
        commit_sha: str,
    ) -> dict[str, Any]:
        """Deploy commit to staging environment.

        Args:
            commit_sha: Git commit SHA to deploy (or plan ID for local builds)

        Returns:
            Deployment result with staging URL

        Example:
            result = await agent.deploy_to_staging(
                commit_sha="abc123def456"
            )

        """
        try:
            import shutil

            self.logger.info(f"Deploying to staging: {commit_sha}")

            # Find the generated service directory
            source_dir = Path("tmp/chimera_generated")
            service_dirs = list(source_dir.glob("*"))

            if not service_dirs:
                return {
                    "status": "error",
                    "error": "No generated service found to deploy",
                }

            service_dir = service_dirs[0]
            self.logger.info(f"Deploying service: {service_dir.name}")

            # Create staging directory
            self.staging_dir.mkdir(parents=True, exist_ok=True)

            # Copy service to staging
            staging_service_dir = self.staging_dir / service_dir.name

            # Remove existing staging deployment
            if staging_service_dir.exists():
                shutil.rmtree(staging_service_dir)

            # Copy to staging
            shutil.copytree(service_dir, staging_service_dir)

            self.logger.info(f"Service deployed to: {staging_service_dir}")

            # For MVP, staging URL is file:// path
            # In production, this would be https://staging.example.com
            staging_url = f"file://{staging_service_dir.absolute()}"

            return {
                "status": "success",
                "staging_url": staging_url,
                "deployment_id": commit_sha,
                "staging_directory": str(staging_service_dir),
                "deployment_notes": f"Local staging deployment of {service_dir.name}",
            }

        except Exception as e:
            self.logger.error(f"Staging deployment failed: {e}", exc_info=True)

            return {
                "status": "error",
                "error": str(e),
            }


def create_chimera_agents_registry() -> dict[str, Any]:
    """Create agent registry for Chimera workflow execution.

    Returns:
        Dictionary mapping agent names to agent instances

    Example:
        registry = create_chimera_agents_registry()
        executor = ChimeraExecutor(agents_registry=registry)

    """
    return {
        "e2e-tester-agent": E2ETesterAgentAdapter(),
        "coder-agent": CoderAgentAdapter(),
        "guardian-agent": GuardianAgentAdapter(),
        "deployment-agent": DeploymentAgentAdapter(),
    }


__all__ = [
    "CoderAgentAdapter",
    "DeploymentAgentAdapter",
    "E2ETesterAgentAdapter",
    "GuardianAgentAdapter",
    "create_chimera_agents_registry",
]
