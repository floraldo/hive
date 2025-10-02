"""
Write-Capable Guardian Engine.

Extends RAGEnhancedCommentEngine with the ability to propose and apply
safe code changes. Integrates with RAG for context-aware improvements.

Progressive deployment:
1. Start with Level 1 (typos) in dry-run mode
2. Validate proposals through safety gates
3. Require approval for all changes
4. Progressively enable higher levels based on success rate
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from .rag_comment_engine import RAGEnhancedCommentEngine
from .write_mode import (
    STANDARD_SAFETY_GATES,
    ChangeCategory,
    ChangeProposal,
    SafetyGate,
    WriteModeConfig,
)

logger = logging.getLogger(__name__)


class WriteCapableEngine(RAGEnhancedCommentEngine):
    """
    Guardian engine capable of proposing and applying code changes.

    Extends read-only RAG engine with write capabilities, implementing
    progressive safety levels and comprehensive validation.
    """

    def __init__(
        self,
        rag_index_dir: str | Path,
        write_config: WriteModeConfig | None = None,
        safety_gates: list[SafetyGate] | None = None,
        proposals_dir: str | Path | None = None,
    ):
        """
        Initialize write-capable engine.

        Args:
            rag_index_dir: RAG index directory
            write_config: Write mode configuration
            safety_gates: Custom safety gates (uses standard if None)
            proposals_dir: Directory to store change proposals
        """
        super().__init__(rag_index_dir=rag_index_dir)

        # Write mode configuration
        self.write_config = write_config or WriteModeConfig(dry_run=True)
        self.safety_gates = safety_gates or STANDARD_SAFETY_GATES

        # Proposal storage
        self.proposals_dir = Path(proposals_dir or "data/guardian_proposals")
        self.proposals_dir.mkdir(parents=True, exist_ok=True)

        # Metrics
        self.proposals_created = 0
        self.proposals_approved = 0
        self.proposals_applied = 0
        self.proposals_rejected = 0

        logger.info(f"Write mode initialized: dry_run={self.write_config.dry_run}")
        logger.info(f"Enabled levels: {[l.name for l in self.write_config.enabled_levels]}")

    async def analyze_pr_with_proposals(
        self,
        pr_number: int,
        pr_files: list[dict[str, Any]],
        pr_title: str,
        pr_description: str,
    ) -> dict[str, Any]:
        """
        Analyze PR and generate both comments and change proposals.

        Returns:
            {
                "comments": [...],  # Traditional read-only comments
                "proposals": [...],  # Change proposals for safe fixes
                "metrics": {...}
            }
        """
        # Get traditional comments
        result = await self.analyze_pr(
            pr_number=pr_number,
            pr_files=pr_files,
            pr_title=pr_title,
            pr_description=pr_description,
        )

        # Generate change proposals for detected issues
        proposals = []
        for comment in result["comments"]:
            # Check if this issue can be auto-fixed
            proposal = await self._generate_proposal_from_comment(
                comment=comment,
                pr_number=pr_number,
            )
            if proposal:
                proposals.append(proposal)

        # Validate proposals through safety gates
        validated_proposals = []
        for proposal in proposals:
            if await self._validate_proposal(proposal):
                validated_proposals.append(proposal)
                self._save_proposal(proposal)

        self.proposals_created += len(validated_proposals)

        return {
            "comments": result["comments"],
            "proposals": [p.to_dict() for p in validated_proposals],
            "metrics": {
                "total_comments": len(result["comments"]),
                "proposals_created": len(validated_proposals),
                "proposals_by_level": self._count_by_level(validated_proposals),
                "proposals_created_lifetime": self.proposals_created,
                "proposals_approved_lifetime": self.proposals_approved,
                "proposals_applied_lifetime": self.proposals_applied,
            },
        }

    async def _generate_proposal_from_comment(
        self,
        comment: dict[str, Any],
        pr_number: int,
    ) -> ChangeProposal | None:
        """
        Generate change proposal from detected issue.

        Uses RAG to find similar patterns and generate safe fix.
        """
        violation_type = comment.get("violation_type"),
        file_path = comment.get("file_path"),
        line_number = comment.get("line_number")

        if not all([violation_type, file_path, line_number]):
            return None

        # Determine if this is a fixable issue
        category = self._get_fix_category(violation_type)
        if not category:
            return None

        # Check if level is enabled
        if not self.write_config.is_level_enabled(category.level):
            logger.debug(f"Level {category.level.name} not enabled, skipping proposal")
            return None

        # Get context from RAG
        rag_context = await self._get_fix_context(
            violation_type=violation_type,
            file_path=file_path,
        )

        # Generate fix
        old_code, new_code = await self._generate_fix(
            category=category,
            file_path=Path(file_path),
            line_number=line_number,
            rag_context=rag_context,
        )

        if not new_code or old_code == new_code:
            return None

        # Create proposal
        proposal_id = self._generate_proposal_id(file_path, line_number, category)

        proposal = ChangeProposal(
            proposal_id=proposal_id,
            file_path=Path(file_path),
            category=category,
            level=category.level,
            description=self._generate_description(category, violation_type),
            old_code=old_code,
            new_code=new_code,
            rag_context=rag_context,
            related_patterns=comment.get("related_patterns", []),
            confidence_score=comment.get("confidence", 0.8),
            risk_assessment=f"Risk level: {category.level.risk_level}",
            requires_tests=category.level.requires_tests,
            requires_review=category.level.requires_review,
            created_at=datetime.now(),
        )

        return proposal

    async def _validate_proposal(self, proposal: ChangeProposal) -> bool:
        """
        Validate proposal through all applicable safety gates.

        Returns:
            True if proposal passes all gates
        """
        for gate in self.safety_gates:
            if not gate.applies_to(proposal):
                continue

            passed, message = await gate.validate(proposal)
            if not passed:
                logger.warning(f"Proposal {proposal.proposal_id} failed gate {gate.name}: {message}")
                return False

            logger.debug(f"Proposal {proposal.proposal_id} passed gate {gate.name}")

        # Mark as validated
        proposal.syntax_validated = True
        return True

    async def approve_proposal(
        self,
        proposal_id: str,
        approved_by: str,
    ) -> bool:
        """
        Approve a change proposal.

        Args:
            proposal_id: Proposal identifier
            approved_by: Approver identifier (username, email, etc.)

        Returns:
            True if approved successfully
        """
        proposal = self._load_proposal(proposal_id)
        if not proposal:
            logger.error(f"Proposal {proposal_id} not found")
            return False

        proposal.approved_by = approved_by
        proposal.review_status = "approved"
        self._save_proposal(proposal)
        self.proposals_approved += 1

        logger.info(f"Proposal {proposal_id} approved by {approved_by}")

        # Auto-apply if configured
        if self.write_config.can_auto_apply(proposal):
            return await self.apply_proposal(proposal_id)

        return True

    async def reject_proposal(
        self,
        proposal_id: str,
        reason: str,
    ) -> bool:
        """Reject a change proposal."""
        proposal = self._load_proposal(proposal_id)
        if not proposal:
            return False

        proposal.review_status = "rejected"
        proposal.risk_assessment += f"\nRejected: {reason}"
        self._save_proposal(proposal)
        self.proposals_rejected += 1

        logger.info(f"Proposal {proposal_id} rejected: {reason}")
        return True

    async def apply_proposal(
        self,
        proposal_id: str,
    ) -> bool:
        """
        Apply an approved change proposal.

        Creates git commit for rollback capability.
        """
        proposal = self._load_proposal(proposal_id)
        if not proposal:
            return False

        if self.write_config.dry_run:
            logger.info(f"DRY RUN: Would apply proposal {proposal_id}")
            return True

        if proposal.review_status != "approved":
            logger.error(f"Cannot apply unapproved proposal {proposal_id}")
            return False

        try:
            # Read current file
            current_content = proposal.file_path.read_text()

            # Apply change
            new_content = current_content.replace(proposal.old_code, proposal.new_code, 1)

            if new_content == current_content:
                logger.error(f"Change not applied - old code not found in {proposal.file_path}")
                return False

            # Write change
            proposal.file_path.write_text(new_content)

            # Create git commit for rollback
            if self.write_config.auto_commit:
                commit_hash = await self._create_commit(proposal)
                proposal.git_commit = commit_hash

            proposal.applied_at = datetime.now()
            self._save_proposal(proposal)
            self.proposals_applied += 1

            logger.info(f"Applied proposal {proposal_id} to {proposal.file_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to apply proposal {proposal_id}: {e}")
            return False

    async def _create_commit(self, proposal: ChangeProposal) -> str:
        """Create git commit for applied change."""
        try:
            # Stage file
            subprocess.run(
                ["git", "add", str(proposal.file_path)],
                check=True,
                capture_output=True,
            )

            # Create commit
            commit_msg = f"""Guardian auto-fix: {proposal.category.value}

{proposal.description}

File: {proposal.file_path}
Level: {proposal.level.name}
Risk: {proposal.level.risk_level}
Approved by: {proposal.approved_by}

Generated with Guardian Write Mode
Proposal ID: {proposal.proposal_id}
"""

            result = subprocess.run(
                ["git", "commit", "-m", commit_msg],
                check=True,
                capture_output=True,
                text=True,
            )

            # Get commit hash
            commit_hash = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

            logger.info(f"Created commit {commit_hash[:8]} for proposal {proposal.proposal_id}")
            return commit_hash

        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to create commit: {e}")
            return ""

    def _get_fix_category(self, violation_type: str) -> ChangeCategory | None:
        """Map violation type to fix category."""
        category_map = {
            "missing_trailing_comma": ChangeCategory.MISSING_TRAILING_COMMA,
            "no_print_statements": ChangeCategory.GOLDEN_RULE_VIOLATION,
            "use_hive_logging": ChangeCategory.GOLDEN_RULE_VIOLATION,
            "missing_docstring": ChangeCategory.MISSING_DOCSTRING,
            "missing_type_hints": ChangeCategory.TYPE_HINT_MISSING,
        }
        return category_map.get(violation_type)

    async def _get_fix_context(
        self,
        violation_type: str,
        file_path: str,
    ) -> str:
        """Get RAG context for generating fix."""
        # Query RAG for similar fixes
        query = f"How to fix {violation_type} in Python code?"

        if self.query_engine:
            try:
                result = await self.query_engine.query(query_text=query, max_results=3)
                return self.context_formatter.format(
                    chunks=result["chunks"],
                    query=query,
                    style=self.context_formatter.FormattingStyle.MINIMAL,
                )
            except Exception as e:
                logger.error(f"Failed to get RAG context: {e}")

        return f"Fix {violation_type} following project patterns"

    async def _generate_fix(
        self,
        category: ChangeCategory,
        file_path: Path,
        line_number: int,
        rag_context: str,
    ) -> tuple[str, str]:
        """
        Generate code fix based on category and context.

        Returns:
            (old_code, new_code) tuple
        """
        # Read file
        try:
            lines = file_path.read_text().split("\n")
            if line_number < 1 or line_number > len(lines):
                return "", ""

            old_line = lines[line_number - 1]

            # Apply category-specific fixes
            if category == ChangeCategory.MISSING_TRAILING_COMMA:
                new_line = self._fix_trailing_comma(old_line)
            elif category == ChangeCategory.GOLDEN_RULE_VIOLATION:
                new_line = self._fix_golden_rule(old_line, rag_context)
            else:
                # Generic fix (for now)
                new_line = old_line

            return old_line, new_line

        except Exception as e:
            logger.error(f"Failed to generate fix: {e}")
            return "", ""

    def _fix_trailing_comma(self, line: str) -> str:
        """Add trailing comma to line if appropriate."""
        stripped = line.rstrip()
        if stripped.endswith(")") or stripped.endswith("]") or stripped.endswith("}"):
            return line  # Don't add comma to closing brackets
        if not stripped.endswith(",") and not stripped.endswith(":"):
            return stripped + ","
        return line

    def _fix_golden_rule(self, line: str, context: str) -> str:
        """Fix golden rule violation based on context."""
        # Example: Replace print() with logger
        if "print(" in line:
            return line.replace("print(", "logger.info(")
        return line

    def _generate_description(self, category: ChangeCategory, violation_type: str) -> str:
        """Generate human-readable description."""
        descriptions = {
            ChangeCategory.MISSING_TRAILING_COMMA: "Add missing trailing comma for consistency",
            ChangeCategory.GOLDEN_RULE_VIOLATION: f"Fix golden rule violation: {violation_type}",
            ChangeCategory.MISSING_DOCSTRING: "Add missing docstring",
            ChangeCategory.TYPE_HINT_MISSING: "Add missing type hints",
        }
        return descriptions.get(category, f"Fix {violation_type}")

    def _generate_proposal_id(
        self,
        file_path: str,
        line_number: int,
        category: ChangeCategory,
    ) -> str:
        """Generate unique proposal ID."""
        content = f"{file_path}:{line_number}:{category.value}:{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:12]

    def _save_proposal(self, proposal: ChangeProposal) -> None:
        """Save proposal to disk."""
        proposal_file = self.proposals_dir / f"{proposal.proposal_id}.json"
        proposal_file.write_text(json.dumps(proposal.to_dict(), indent=2))

    def _load_proposal(self, proposal_id: str) -> ChangeProposal | None:
        """Load proposal from disk."""
        proposal_file = self.proposals_dir / f"{proposal_id}.json"
        if not proposal_file.exists():
            return None

        try:
            data = json.loads(proposal_file.read_text())
            return ChangeProposal.from_dict(data)
        except Exception as e:
            logger.error(f"Failed to load proposal {proposal_id}: {e}")
            return None

    def _count_by_level(self, proposals: list[ChangeProposal]) -> dict[str, int]:
        """Count proposals by level."""
        counts = {}
        for proposal in proposals:
            level_name = proposal.level.name
            counts[level_name] = counts.get(level_name, 0) + 1
        return counts

    def get_metrics(self) -> dict[str, Any]:
        """Get Write Mode metrics."""
        return {
            "proposals_created": self.proposals_created,
            "proposals_approved": self.proposals_approved,
            "proposals_applied": self.proposals_applied,
            "proposals_rejected": self.proposals_rejected,
            "approval_rate": (self.proposals_approved / self.proposals_created if self.proposals_created > 0 else 0.0),
            "success_rate": (self.proposals_applied / self.proposals_approved if self.proposals_approved > 0 else 0.0),
        }
