#!/usr/bin/env python3
"""CLI interface for Guardian RAG-enhanced code review.

This module provides a command-line interface for running Guardian's RAG-enhanced
code review on specified files, outputting results in JSON format compatible with
GitHub's PR comment API.

Usage:
    python -m guardian_agent.cli_review --files file1.py file2.py --output review.json
    python -m guardian_agent.cli_review --pr-number 123 --output review.json

Features:
    - RAG-enhanced pattern detection
    - Golden rules validation
    - Confidence scoring (only outputs comments >80% confidence)
    - GitHub-compatible JSON output
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from hive_logging import get_logger

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Guardian RAG-enhanced code review CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Review specific files
  python -m guardian_agent.cli_review --files src/foo.py src/bar.py --output review.json

  # Review files changed in PR #123
  python -m guardian_agent.cli_review --pr-number 123 --output review.json

  # Review with custom confidence threshold
  python -m guardian_agent.cli_review --files src/foo.py --confidence 0.90 --output review.json
        """,
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--files",
        nargs="+",
        help="Python files to review",
    )
    input_group.add_argument(
        "--pr-number",
        type=int,
        help="Pull request number (fetches changed files via git)",
    )

    parser.add_argument(
        "--output",
        required=True,
        help="Output JSON file path",
    )

    parser.add_argument(
        "--confidence",
        type=float,
        default=0.80,
        help="Minimum confidence threshold (default: 0.80)",
    )

    parser.add_argument(
        "--max-comments",
        type=int,
        default=5,
        help="Maximum comments to output (default: 5)",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    return parser.parse_args()


def get_changed_files_from_pr(pr_number: int) -> list[str]:
    """Get list of changed Python files from a PR.

    Args:
        pr_number: GitHub PR number

    Returns:
        List of changed Python file paths

    Note:
        This is a placeholder. Real implementation would use GitHub API
        or git diff to detect changed files.
    """
    logger.info(f"Fetching changed files from PR #{pr_number}")
    # Placeholder - in real implementation, use GitHub API or git diff
    return []


async def review_files_with_rag(
    files: list[str],
    confidence_threshold: float = 0.80,
) -> list[dict[str, Any]]:
    """Review files using RAG-enhanced Guardian engine.

    Args:
        files: List of Python file paths to review
        confidence_threshold: Minimum confidence for including a comment

    Returns:
        List of review comments with metadata

    Note:
        This connects to the RAGCommentEngine from
        apps/guardian-agent/src/guardian_agent/review/rag_comment_engine.py
    """
    try:
        from guardian_agent.review.rag_comment_engine import RAGCommentEngine

        logger.info(f"Initializing RAG engine for {len(files)} files")

        engine = RAGCommentEngine()
        all_comments = []

        # Prepare PR files format: list of (file_path, content) tuples
        pr_files = []
        for file_path in files:
            if not Path(file_path).exists():
                logger.warning(f"File not found: {file_path}")
                continue

            logger.info(f"Reviewing {file_path}")

            # Read file content
            with open(file_path, encoding="utf-8") as f:
                code_content = f.read()

            # Add to PR files list (treat full content as diff for analysis)
            pr_files.append((file_path, code_content))

        # Run RAG-enhanced review
        comment_batch = await engine.analyze_pr_for_comments(
            pr_files=pr_files,
            pr_number=0,  # CLI mode, no actual PR number
        )

        # Convert PRComment objects to GitHub API format
        for pr_comment in comment_batch.comments:
            # Filter by confidence threshold
            if pr_comment.confidence_score >= confidence_threshold:
                all_comments.append(
                    {
                        "path": pr_comment.file_path,
                        "line": pr_comment.line_number,
                        "body": pr_comment.to_github_comment(),
                        "confidence": pr_comment.confidence_score,
                        "pattern_type": pr_comment.comment_type,
                    }
                )

        logger.info(
            f"Generated {len(all_comments)} comments from {len(comment_batch.comments)} total "
            f"(threshold: {confidence_threshold})"
        )

        return all_comments

    except ImportError as e:
        logger.error(f"Failed to import RAGCommentEngine: {e}")
        logger.info("Falling back to placeholder comments")
        return generate_placeholder_comments(files)


def generate_placeholder_comments(files: list[str]) -> list[dict[str, Any]]:
    """Generate placeholder comments when RAG engine is unavailable.

    Args:
        files: List of file paths

    Returns:
        List of placeholder review comments
    """
    comments = []

    for file_path in files:
        if not Path(file_path).exists():
            continue

        # Simple placeholder comment
        comments.append(
            {
                "path": file_path,
                "line": 1,
                "body": f"""## 🤖 Guardian AI Review (Placeholder Mode)

**File**: {file_path}

This file has been queued for RAG-enhanced review. Full analysis will be available once the RAG index is built.

**Next Steps**:
1. Build RAG index: `python scripts/rag/index_hive_codebase_fixed.py`
2. Re-run review for detailed feedback

---
*Guardian is currently in placeholder mode. RAG engine integration pending.*
""",
                "confidence": 1.0,
                "pattern_type": "placeholder",
            }
        )

    return comments


def format_for_github_api(
    comments: list[dict[str, Any]],
    max_comments: int = 5,
) -> list[dict[str, Any]]:
    """Format review comments for GitHub Pull Request API.

    Args:
        comments: Raw review comments from Guardian
        max_comments: Maximum number of comments to include

    Returns:
        List of comments formatted for GitHub API

    GitHub PR Comment API Format:
        {
            "path": "file/path.py",
            "line": 42,
            "body": "Markdown comment body",
            "side": "RIGHT"
        }
    """
    # Sort by confidence (highest first)
    sorted_comments = sorted(
        comments,
        key=lambda c: c.get("confidence", 0),
        reverse=True,
    )

    # Limit to max_comments
    limited_comments = sorted_comments[:max_comments]

    # Format for GitHub API
    github_comments = []
    for comment in limited_comments:
        # Add feedback footer to comment body
        body_with_feedback = f"""{comment["body"]}

---
**Was this helpful?** 👍 useful | 👎 not useful | 🤔 unclear

*This review powered by Guardian AI + RAG system | Confidence: {comment.get("confidence", 0):.0%}*"""

        github_comments.append(
            {
                "path": comment["path"],
                "line": comment.get("line", 1),
                "body": body_with_feedback,
                "side": "RIGHT",  # Comment on the new version
            }
        )

    return github_comments


async def main_async() -> int:
    """Main CLI entrypoint (async version)."""
    args = parse_args()

    # Configure logging
    if args.verbose:
        import logging

        logging.getLogger("guardian_agent").setLevel(logging.DEBUG)
        logging.getLogger("hive_ai.rag").setLevel(logging.DEBUG)

    logger.info("Guardian CLI Review starting")
    logger.info(f"Confidence threshold: {args.confidence}, Max comments: {args.max_comments}")

    try:
        # Get files to review
        if args.files:
            files_to_review = args.files
            logger.info(f"Reviewing {len(files_to_review)} specified files")
        else:
            files_to_review = get_changed_files_from_pr(args.pr_number)
            if not files_to_review:
                logger.warning(f"No Python files changed in PR #{args.pr_number}")
                # Write empty result
                with open(args.output, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=2)
                return 0

        # Run RAG-enhanced review (async)
        raw_comments = await review_files_with_rag(
            files=files_to_review,
            confidence_threshold=args.confidence,
        )

        logger.info(f"Generated {len(raw_comments)} total comments")

        # Format for GitHub API
        github_comments = format_for_github_api(
            comments=raw_comments,
            max_comments=args.max_comments,
        )

        logger.info(f"Formatted {len(github_comments)} comments for GitHub (limit: {args.max_comments})")

        # Write output
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(github_comments, f, indent=2)

        logger.info(f"Review complete. Output written to {args.output}")
        logger.info(f"Summary: {len(github_comments)} comments (from {len(raw_comments)} candidates)")

        return 0

    except Exception as e:
        logger.error(f"Review failed: {e}", exc_info=True)
        return 1


def main() -> int:
    """Main CLI entrypoint (sync wrapper)."""
    return asyncio.run(main_async())


if __name__ == "__main__":
    sys.exit(main())
