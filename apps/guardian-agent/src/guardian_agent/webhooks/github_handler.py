"""GitHub webhook handler for PR reviews."""

import hmac
import json
from pathlib import Path
from typing import Any

from guardian_agent.core.config import GuardianConfig
from guardian_agent.review.engine import ReviewEngine
from hive_async import AsyncExecutor
from hive_logging import get_logger

logger = get_logger(__name__)


class GitHubWebhookHandler:
    """
    Handles GitHub webhooks for automated PR reviews.

    Processes pull request events and posts review comments
    back to GitHub using the Guardian Agent.
    """

    def __init__(
        self, config: GuardianConfig | None = None, github_token: str | None = None, webhook_secret: str | None = None
    ) -> None:
        """Initialize the webhook handler."""
        self.config = config or GuardianConfig()
        self.github_token = github_token
        self.webhook_secret = webhook_secret

        self.review_engine = ReviewEngine(self.config)
        self.async_executor = AsyncExecutor(max_workers=2)

        logger.info("GitHubWebhookHandler initialized")

    async def handle_webhook(self, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        """
        Handle incoming GitHub webhook.

        Args:
            payload: Webhook payload
            headers: Request headers

        Returns:
            Response data
        """
        # Verify webhook signature if secret is configured
        if self.webhook_secret and not self._verify_signature(payload, headers):
            logger.warning("Invalid webhook signature")
            return {"error": "Invalid signature"}, 403

        # Get event type
        event_type = headers.get("X-GitHub-Event", "")

        if event_type == "pull_request":
            return await self._handle_pull_request(payload)
        elif event_type == "pull_request_review_comment":
            return await self._handle_review_comment(payload)
        elif event_type == "issue_comment":
            return await self._handle_issue_comment(payload)
        else:
            logger.info("Ignoring event type: %s", event_type)
            return {"message": f"Event type {event_type} not handled"}, 200

    async def _handle_pull_request(self, payload: dict[str, Any]) -> Tuple[dict[str, Any], int]:
        """Handle pull request events."""
        action = payload.get("action", "")
        pr = payload.get("pull_request", {})

        # Only review on opened or synchronize (new commits)
        if action not in ["opened", "synchronize"]:
            return {"message": f"Action {action} not handled"}, 200

        # Extract PR information
        pr_number = pr.get("number")
        repo_full_name = payload.get("repository", {}).get("full_name")
        base_branch = pr.get("base", {}).get("ref")
        head_branch = pr.get("head", {}).get("ref")
        head_sha = pr.get("head", {}).get("sha")

        logger.info("Processing PR #%d in %s (%s -> %s)", pr_number, repo_full_name, head_branch, base_branch)

        # Get changed files
        changed_files = await self._get_changed_files(repo_full_name, pr_number)

        # Review each file
        review_results = []
        for file_info in changed_files:
            if self._should_review_file(file_info["filename"]):
                result = await self._review_pr_file(repo_full_name, pr_number, file_info)
                review_results.append(result)

        # Post review comment
        await self._post_review_comment(repo_full_name, pr_number, head_sha, review_results)

        return {"message": f"Reviewed {len(review_results)} files"}, 200

    async def _handle_review_comment(self, payload: dict[str, Any]) -> Tuple[dict[str, Any], int]:
        """Handle review comment events for learning."""
        action = payload.get("action", "")
        if action != "created":
            return {"message": "Only handling new comments"}, 200

        comment = payload.get("comment", {})

        # Check if this is feedback on our review
        if "@guardian-agent" in comment.get("body", ""):
            # Extract feedback for learning system
            feedback = self._extract_feedback(comment)
            if feedback:
                await self._process_feedback(feedback)

        return {"message": "Feedback processed"}, 200

    async def _handle_issue_comment(self, payload: dict[str, Any]) -> Tuple[dict[str, Any], int]:
        """Handle issue comments that might trigger reviews."""
        comment = payload.get("comment", {})
        issue = payload.get("issue", {})

        # Check if this is a PR and comment mentions us
        if issue.get("pull_request") and "@guardian-agent review" in comment.get("body", ""):
            # Trigger a review
            pr_url = issue["pull_request"]["url"]
            # Would fetch PR details and trigger review
            logger.info("Manual review requested via comment")

        return {"message": "Comment processed"}, 200

    def _verify_signature(self, payload: dict[str, Any], headers: dict[str, str]) -> bool:
        """Verify webhook signature."""
        signature = headers.get("X-Hub-Signature-256", "")
        if not signature:
            return False

        expected = (
            "sha256=",
            +hmac.new(self.webhook_secret.encode(), json.dumps(payload).encode(), "sha256").hexdigest(),
        )

        return hmac.compare_digest(expected, signature)

    async def _get_changed_files(self, repo: str, pr_number: int) -> list[dict[str, Any]]:
        """Get list of changed files in PR."""
        # In real implementation, would use GitHub API
        # For now, return mock data
        return [
            {
                "filename": "src/example.py",
                "status": "modified",
                "additions": 10,
                "deletions": 5,
                "patch": "@@ -1,5 +1,10 @@\n+def new_function():\n+    pass\n",
            }
        ]

    def _should_review_file(self, filename: str) -> bool:
        """Check if file should be reviewed."""
        path = Path(filename)

        # Check include patterns
        for pattern in self.config.include_patterns:
            if path.match(pattern):
                # Check exclude patterns
                for exclude in self.config.exclude_patterns:
                    if path.match(exclude):
                        return False
                return True

        return False

    async def _review_pr_file(self, repo: str, pr_number: int, file_info: dict[str, Any]) -> dict[str, Any]:
        """Review a single file in the PR."""
        filename = file_info["filename"]

        # Get file content (would use GitHub API)
        content = await self._get_file_content(repo, filename)

        # Run review
        file_path = Path(filename)
        result = await self.review_engine.review_file(file_path)

        # Format for PR comment
        return {"path": filename, "review": result, "line_comments": self._generate_line_comments(result, file_info)}

    async def _get_file_content(self, repo: str, filename: str) -> str:
        """Get file content from GitHub."""
        # In real implementation, would use GitHub API
        return "# Mock file content\ndef example():\n    pass"

    def _generate_line_comments(self, review_result, file_info: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate line-specific comments from review."""
        comments = []

        for violation in review_result.all_violations:
            comments.append(
                {
                    "path": file_info["filename"],
                    "line": violation.line_number,
                    "side": "RIGHT",
                    "body": f"**{violation.severity.value.upper()}**: {violation.message}",
                }
            )

        for suggestion in review_result.all_suggestions[:3]:  # Limit suggestions
            comments.append(
                {
                    "path": file_info["filename"],
                    "line": suggestion.line_range[0],
                    "side": "RIGHT",
                    "body": f"💡 **Suggestion**: {suggestion.message}",
                }
            )

        return comments

    async def _post_review_comment(
        self, repo: str, pr_number: int, commit_sha: str, review_results: list[dict[str, Any]]
    ) -> None:
        """Post review comment to PR."""
        # Format overall review
        body = self._format_review_body(review_results)

        # Collect all line comments
        comments = []
        for result in review_results:
            comments.extend(result.get("line_comments", []))

        # Would use GitHub API to post review
        logger.info("Would post review to PR #%d with %d comments", pr_number, len(comments))

    def _format_review_body(self, review_results: list[dict[str, Any]]) -> str:
        """Format the main review comment body."""
        lines = ["## 🤖 Guardian Agent Review", ""]

        # Overall summary
        total_violations = sum(sum(r["review"].violations_count.values()) for r in review_results)
        avg_score = sum(r["review"].overall_score for r in review_results) / len(review_results)

        lines.extend(
            [
                f"**Overall Score**: {avg_score:.0f}/100",
                f"**Files Reviewed**: {len(review_results)}",
                f"**Total Issues**: {total_violations}",
                "",
            ]
        )

        # File summaries
        if review_results:
            lines.append("### File Reviews")
            for result in review_results:
                review = result["review"]
                status = "✅" if not review.has_blocking_issues else "❌"
                lines.append(f"- {status} **{result['path']}** (Score: {review.overall_score:.0f}/100)")
            lines.append("")

        # Footer
        lines.extend(["---", "*Generated by Guardian Agent | [Documentation](https://github.com/hive/guardian-agent)*"])

        return "\n".join(lines)

    def _extract_feedback(self, comment: dict[str, Any]) -> dict[str, Any] | None:
        """Extract feedback from comment for learning."""
        body = comment.get("body", "")

        # Look for feedback patterns
        if "correct" in body.lower() or "agree" in body.lower():
            return {"type": "positive", "comment_id": comment.get("id"), "body": body}
        elif "incorrect" in body.lower() or "disagree" in body.lower():
            return {"type": "negative", "comment_id": comment.get("id"), "body": body}

        return None

    async def _process_feedback(self, feedback: dict[str, Any]) -> None:
        """Process feedback for learning system."""
        # Would integrate with learning system
        logger.info("Processing %s feedback: %s", feedback["type"], feedback["comment_id"])
