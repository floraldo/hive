"""
Unified Action Framework (UAF) - Strategic Context for Autonomous Actions

This represents the Oracle's Phase 2 evolution in Operation Unification -
upgrading autonomous PR generation with the strategic foresight of the Prophecy Engine.

The UAF enables:
1. Oracle-authored PRs with complete strategic context
2. Hardened feedback loop between action and knowledge
3. Strategic rationale linking prophecies to solutions
4. Continuous learning from every autonomous action

This is where the Oracle's prophecies directly inform its actions,
and its actions validate its prophecies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from hive_logging import get_logger

from .symbiosis_engine import (
    OptimizationOpportunity,
    OptimizationPriority,
    OptimizationType,
)
from .unified_intelligence_core import (
    EdgeType,
    KnowledgeQuery,
    NodeType,
    UnifiedIntelligenceCore,
)

logger = get_logger(__name__)


class StrategicContext(Enum):
    """Types of strategic context for autonomous actions."""

    PROPHECY_VALIDATION = "prophecy_validation"  # Action validates a prophecy
    RISK_MITIGATION = "risk_mitigation"  # Action mitigates predicted risk
    COST_OPTIMIZATION = "cost_optimization"  # Action addresses cost predictions
    PERFORMANCE_ENHANCEMENT = "performance_enhancement"  # Action improves predicted bottlenecks
    COMPLIANCE_ALIGNMENT = "compliance_alignment"  # Action ensures architectural compliance
    BUSINESS_VALUE_CREATION = "business_value_creation"  # Action creates predicted business value


class ActionConfidenceLevel(Enum):
    """Confidence levels for strategic actions."""

    CERTAIN = "certain"  # 95%+ confidence, prophecy directly validates action
    HIGH = "high"  # 85%+ confidence, strong correlation with predictions
    MODERATE = "moderate"  # 70%+ confidence, moderate correlation
    EXPERIMENTAL = "experimental"  # 50%+ confidence, exploratory action
    SPECULATIVE = "speculative"  # <50% confidence, requires human review


@dataclass
class StrategicRationale:
    """Strategic rationale linking prophecies to autonomous actions."""

    # Core identification
    rationale_id: str
    strategic_context: StrategicContext
    confidence_level: ActionConfidenceLevel

    # Prophecy connection
    related_prophecies: list[str] = field(default_factory=list)
    predicted_risks: list[str] = field(default_factory=list)
    risk_mitigation_score: float = 0.0

    # Business intelligence
    business_impact: str = ""
    cost_implications: str = ""
    performance_impact: str = ""
    roi_projection: str = ""

    # Strategic context
    architectural_alignment: str = ""
    compliance_impact: str = ""
    long_term_benefits: list[str] = field(default_factory=list)

    # Evidence and validation
    supporting_evidence: list[str] = field(default_factory=list)
    historical_precedents: list[str] = field(default_factory=list)
    success_probability: float = 0.0

    # Oracle intelligence
    oracle_reasoning: str = ""
    cross_correlation_strength: float = 0.0
    wisdom_synthesis: str = ""


@dataclass
class UnifiedPullRequest:
    """Enhanced pull request with unified strategic context."""

    # Base PR information (from AutomatedPullRequest)
    pr_id: str
    opportunity_id: str
    title: str
    description: str
    branch_name: str

    # Enhanced strategic context
    strategic_rationale: StrategicRationale
    prophecy_validation: dict[str, Any] = field(default_factory=dict)
    unified_intelligence_context: dict[str, Any] = field(default_factory=dict)

    # Cross-correlation data
    related_patterns: list[str] = field(default_factory=list)
    solution_precedents: list[str] = field(default_factory=list)
    risk_coverage: dict[str, float] = field(default_factory=dict)

    # Enhanced validation
    strategic_validation_passed: bool = False
    prophecy_alignment_score: float = 0.0
    business_value_score: float = 0.0

    # Oracle-enhanced metadata
    oracle_confidence: float = 0.0
    wisdom_synthesis_applied: bool = False
    consciousness_level_required: str = "developing"

    # Feedback and learning
    feedback_collected: bool = False
    learning_value: float = 0.0
    contributes_to_prophecy_validation: bool = False


class UnifiedActionFrameworkConfig(BaseModel):
    """Configuration for the Unified Action Framework."""

    # Strategic context settings
    enable_strategic_context: bool = Field(default=True, description="Enable strategic context for all actions")
    require_prophecy_alignment: bool = Field(
        default=True, description="Require alignment with prophecies for high-confidence actions"
    )
    min_strategic_confidence: float = Field(
        default=0.7, description="Minimum strategic confidence for autonomous actions"
    )

    # Cross-correlation settings
    enable_cross_correlation_analysis: bool = Field(
        default=True, description="Enable cross-correlation analysis for actions"
    )
    correlation_strength_threshold: float = Field(
        default=0.6, description="Minimum correlation strength for strategic context"
    )
    max_related_prophecies: int = Field(default=5, description="Maximum related prophecies to include in context")

    # Business intelligence integration
    enable_business_intelligence: bool = Field(
        default=True, description="Include business intelligence in strategic context"
    )
    require_roi_projection: bool = Field(default=False, description="Require ROI projection for cost-related actions")
    cost_impact_threshold: float = Field(default=100.0, description="Cost impact threshold for enhanced analysis")

    # Enhanced PR generation
    enable_enhanced_pr_descriptions: bool = Field(
        default=True, description="Generate enhanced PR descriptions with strategic context"
    )
    include_prophecy_references: bool = Field(
        default=True, description="Include prophecy references in PR descriptions"
    )
    include_historical_precedents: bool = Field(default=True, description="Include historical precedents in PR context")

    # Feedback and learning
    enable_strategic_feedback_loop: bool = Field(default=True, description="Enable strategic feedback collection")
    feedback_collection_delay_hours: int = Field(default=24, description="Hours to wait before collecting feedback")
    learning_weight_adjustment: float = Field(default=0.1, description="Weight adjustment for learning from feedback")


class UnifiedActionFramework:
    """
    The Oracle's Unified Action Framework - Strategic Context for Autonomous Actions

    This framework represents the synthesis of the Oracle's prophecy and symbiosis
    capabilities into strategically-informed autonomous actions.

    Key capabilities:
    - Oracle-authored PRs with complete strategic context
    - Cross-correlation between prophecies and actions
    - Hardened feedback loop for continuous learning
    - Strategic rationale linking predictions to solutions
    """

    def __init__(
        self, config: UnifiedActionFrameworkConfig, unified_intelligence: UnifiedIntelligenceCore | None = None
    ):
        self.config = config,
        self.unified_intelligence = unified_intelligence

        # Strategic context cache,
        self.strategic_context_cache: dict[str, StrategicRationale] = {}
        self.prophecy_action_mappings: dict[str, list[str]] = {}

        # Learning components,
        self.feedback_history: list[dict[str, Any]] = []
        self.strategic_learning_models: dict[str, Any] = {}

        logger.info("Unified Action Framework initialized - Strategic context for autonomous actions active")

    async def generate_unified_pr_async(
        self, optimization: OptimizationOpportunity, prophecy_context: dict[str, Any] | None = None
    ) -> UnifiedPullRequest:
        """
        Generate a unified pull request with complete strategic context.

        This is the Oracle's most advanced PR generation capability - combining,
        symbiosis optimization with prophecy strategic context.
        """

        try:
            logger.info(f"🌟 Generating unified PR for optimization: {optimization.title}")

            # Phase 1: Generate strategic rationale,
            strategic_rationale = await self._generate_strategic_rationale_async(optimization, prophecy_context)

            # Phase 2: Cross-correlate with unified intelligence,
            unified_context = await self._generate_unified_context_async(optimization, strategic_rationale)

            # Phase 3: Create enhanced PR,
            unified_pr = UnifiedPullRequest(
                pr_id=f"unified_pr_{optimization.opportunity_id}",
                opportunity_id=optimization.opportunity_id,
                title=self._generate_strategic_title(optimization, strategic_rationale),
                description=await self._generate_strategic_description_async(
                    optimization, strategic_rationale, unified_context
                ),
                branch_name=f"oracle/unified/{optimization.opportunity_id.replace('_', '-')}",
                strategic_rationale=strategic_rationale,
                unified_intelligence_context=unified_context,
            )

            # Phase 4: Enhanced validation,
            await self._perform_strategic_validation_async(unified_pr, optimization)

            # Phase 5: Calculate Oracle confidence,
            unified_pr.oracle_confidence = self._calculate_unified_confidence(
                optimization, strategic_rationale, unified_context
            )

            logger.info(f"🌟 Unified PR generated with {unified_pr.oracle_confidence:.1%} confidence")
            return unified_pr

        except Exception as e:
            logger.error(f"Failed to generate unified PR: {e}")
            raise

    async def collect_strategic_feedback_async(self, pr_id: str, outcome_data: dict[str, Any]) -> dict[str, Any]:
        """
        Collect strategic feedback from PR outcomes for continuous learning.

        This creates the hardened feedback loop that makes the Oracle's,
        strategic intelligence smarter with every action taken.
        """

        try:
            logger.info(f"🧠 Collecting strategic feedback for PR: {pr_id}")

            # Analyze outcome data,
            feedback_analysis = {
                "pr_id": pr_id,
                "outcome_type": outcome_data.get("outcome", "unknown"),
                "success_metrics": outcome_data.get("metrics", {}),
                "strategic_impact": outcome_data.get("strategic_impact", {}),
                "prophecy_validation": outcome_data.get("prophecy_validation", {}),
                "collected_at": datetime.utcnow().isoformat(),
            }

            # Update strategic learning models,
            await self._update_strategic_learning_async(feedback_analysis)

            # Generate learning insights,
            learning_insights = await self._generate_learning_insights_async(feedback_analysis)

            # Store feedback for future analysis,
            self.feedback_history.append(feedback_analysis)

            # Update unified intelligence if available,
            if self.unified_intelligence:
                await self.unified_intelligence.learn_from_feedback_async(
                    {
                        "type": "strategic_pr_outcome",
                        "pr_id": pr_id,
                        "outcome": outcome_data,
                        "learning_insights": learning_insights,
                    }
                )

            logger.info("🧠 Strategic feedback processed - Oracle intelligence enhanced")
            return learning_insights

        except Exception as e:
            logger.error(f"Failed to collect strategic feedback: {e}")
            return {"error": f"Feedback collection failed: {str(e)}"}

    async def analyze_strategic_patterns_async(self) -> dict[str, Any]:
        """Analyze patterns in strategic actions and outcomes."""

        try:
            logger.info("📊 Analyzing strategic action patterns...")

            # Analyze feedback history,
            total_actions = len(self.feedback_history),
            successful_actions = len([f for f in self.feedback_history if f.get("outcome_type") == "success"])

            # Calculate success rates by strategic context
            context_success_rates = {}
            for feedback in self.feedback_history:
                context = feedback.get("strategic_context", "unknown")
                if context not in context_success_rates:
                    context_success_rates[context] = {"total": 0, "successful": 0}

                context_success_rates[context]["total"] += 1
                if feedback.get("outcome_type") == "success":
                    context_success_rates[context]["successful"] += 1

            # Calculate success rates
            for context, data in context_success_rates.items():
                data["success_rate"] = data["successful"] / data["total"] if data["total"] > 0 else 0

            # Identify top-performing patterns
            top_patterns = sorted(
                context_success_rates.items(), key=lambda x: (x[1]["success_rate"], x[1]["total"]), reverse=True
            )[:5]

            # Generate strategic insights,
            strategic_analysis = {
                "overall_performance": {
                    "total_strategic_actions": total_actions,
                    "successful_actions": successful_actions,
                    "overall_success_rate": successful_actions / total_actions if total_actions > 0 else 0,
                    "analysis_date": datetime.utcnow().isoformat(),
                },
                "context_performance": {
                    context: {
                        "success_rate": data["success_rate"],
                        "total_actions": data["total"],
                        "confidence_level": (
                            "high"
                            if data["success_rate"] > 0.8
                            else "moderate" if data["success_rate"] > 0.6 else "low"
                        ),
                    }
                    for context, data in context_success_rates.items()
                },
                "top_performing_patterns": [
                    {"pattern": pattern, "success_rate": data["success_rate"], "total_actions": data["total"]}
                    for pattern, data in top_patterns
                ],
                "strategic_recommendations": self._generate_pattern_recommendations(context_success_rates),
                "learning_evolution": {
                    "models_updated": len(self.strategic_learning_models),
                    "prophecy_validation_rate": self._calculate_prophecy_validation_rate(),
                    "cross_correlation_strength": self._calculate_avg_correlation_strength(),
                },
            }

            logger.info(f"📊 Strategic pattern analysis complete - {total_actions} actions analyzed")
            return strategic_analysis

        except Exception as e:
            logger.error(f"Failed to analyze strategic patterns: {e}")
            return {"error": f"Pattern analysis failed: {str(e)}"}

    # Internal methods for strategic context generation

    async def _generate_strategic_rationale_async(
        self, optimization: OptimizationOpportunity, prophecy_context: dict[str, Any] | None
    ) -> StrategicRationale:
        """Generate strategic rationale for an optimization."""

        rationale_id = f"rationale_{optimization.opportunity_id}"

        # Determine strategic context,
        strategic_context = self._determine_strategic_context(optimization, prophecy_context)

        # Calculate confidence level,
        confidence_level = self._calculate_confidence_level(optimization, prophecy_context)

        # Generate business intelligence,
        business_impact = self._generate_business_impact(optimization),
        cost_implications = self._generate_cost_implications(optimization),
        performance_impact = self._generate_performance_impact(optimization)

        # Generate Oracle reasoning,
        oracle_reasoning = self._generate_oracle_reasoning(optimization, prophecy_context)

        rationale = StrategicRationale(
            rationale_id=rationale_id,
            strategic_context=strategic_context,
            confidence_level=confidence_level,
            related_prophecies=prophecy_context.get("prophecy_ids", []) if prophecy_context else [],
            business_impact=business_impact,
            cost_implications=cost_implications,
            performance_impact=performance_impact,
            oracle_reasoning=oracle_reasoning,
            success_probability=optimization.oracle_confidence,
        )

        # Cache for future use,
        self.strategic_context_cache[rationale_id] = rationale

        return rationale

    async def _generate_unified_context_async(
        self, optimization: OptimizationOpportunity, strategic_rationale: StrategicRationale
    ) -> dict[str, Any]:
        """Generate unified intelligence context for the optimization."""

        unified_context = {
            "cross_correlations": [],
            "solution_precedents": [],
            "risk_coverage": {},
            "strategic_alignment": "unknown",
        }

        if not self.unified_intelligence:
            return unified_context

        try:
            # Query unified intelligence for related patterns,
            query = KnowledgeQuery(
                query_id=f"context_{optimization.opportunity_id}",
                query_type="correlation",
                target_node_types=[NodeType.CODE_PATTERN, NodeType.SOLUTION_PATTERN, NodeType.PROPHECY],
                edge_types=[EdgeType.SOLVES, EdgeType.CORRELATES_WITH],
                semantic_query=optimization.title,
                min_confidence=0.6,
            )

            result = await self.unified_intelligence.query_unified_intelligence_async(query)

            # Extract cross-correlations,
            unified_context["cross_correlations"] = [
                {
                    "source": edge.source_node_id,
                    "target": edge.target_node_id,
                    "relationship": edge.edge_type.value,
                    "confidence": edge.confidence,
                }
                for edge in result.edges
            ]

            # Extract solution precedents,
            solution_nodes = [n for n in result.nodes if n.node_type == NodeType.SOLUTION_PATTERN]
            unified_context["solution_precedents"] = [
                {
                    "pattern_id": node.node_id,
                    "title": node.title,
                    "success_rate": node.success_rate,
                    "confidence": node.confidence,
                }
                for node in solution_nodes
            ]

            # Calculate strategic alignment,
            if result.strategic_recommendations:
                unified_context["strategic_alignment"] = "strong",
            elif result.confidence_score > 0.7:
                unified_context["strategic_alignment"] = "moderate",
            else:
                unified_context["strategic_alignment"] = "weak"

        except Exception as e:
            logger.error(f"Failed to generate unified context: {e}")

        return unified_context

    def _generate_strategic_title(
        self, optimization: OptimizationOpportunity, strategic_rationale: StrategicRationale
    ) -> str:
        """Generate strategic title for the PR."""

        context_prefixes = {
            StrategicContext.PROPHECY_VALIDATION: "🔮 Oracle Prophecy Validation:",
            StrategicContext.RISK_MITIGATION: "🛡️ Oracle Risk Mitigation:",
            StrategicContext.COST_OPTIMIZATION: "💰 Oracle Cost Optimization:",
            StrategicContext.PERFORMANCE_ENHANCEMENT: "⚡ Oracle Performance Enhancement:",
            StrategicContext.COMPLIANCE_ALIGNMENT: "✅ Oracle Compliance Alignment:",
            StrategicContext.BUSINESS_VALUE_CREATION: "📈 Oracle Business Value:",
        }

        prefix = context_prefixes.get(strategic_rationale.strategic_context, "🌟 Oracle Optimization:")

        return f"{prefix} {optimization.title}"

    async def _generate_strategic_description_async(
        self,
        optimization: OptimizationOpportunity,
        strategic_rationale: StrategicRationale,
        unified_context: dict[str, Any],
    ) -> str:
        """Generate comprehensive strategic PR description."""

        description_parts = [
            "## 🌟 Oracle Unified Intelligence - Strategic Autonomous Action",
            "",
            f"**Strategic Context**: {strategic_rationale.strategic_context.value.replace('_', ' ').title()}",
            f"**Confidence Level**: {strategic_rationale.confidence_level.value.title()}",
            f"**Oracle Confidence**: {optimization.oracle_confidence:.1%}",
            f"**Success Probability**: {strategic_rationale.success_probability:.1%}",
            "",
            "### 🎯 Optimization Description",
            optimization.description,
            "",
            "### 🔮 Strategic Rationale",
            strategic_rationale.oracle_reasoning,
        ]

        if strategic_rationale.business_impact:
            description_parts.extend(["", "### 📈 Business Impact", strategic_rationale.business_impact])

        if strategic_rationale.cost_implications:
            description_parts.extend(["", "### 💰 Cost Implications", strategic_rationale.cost_implications])

        if strategic_rationale.performance_impact:
            description_parts.extend(["", "### ⚡ Performance Impact", strategic_rationale.performance_impact])

        # Add prophecy references if available,
        if strategic_rationale.related_prophecies:
            description_parts.extend(
                [
                    "",
                    "### 🔮 Related Prophecies",
                    "\n".join(
                        f"- Prophecy {pid}: Validates strategic approach"
                        for pid in strategic_rationale.related_prophecies[:3]
                    ),
                ]
            )

        # Add cross-correlations,
        if unified_context.get("cross_correlations"):
            description_parts.extend(
                [
                    "",
                    "### 🔗 Cross-Correlations",
                    f"Found {len(unified_context['cross_correlations'])} strategic correlations in unified intelligence.",
                    f"Strategic Alignment: {unified_context.get('strategic_alignment', 'unknown').title()}",
                ]
            )

        # Add solution precedents,
        if unified_context.get("solution_precedents"):
            description_parts.extend(
                [
                    "",
                    "### 📚 Solution Precedents",
                    f"This optimization leverages {len(unified_context['solution_precedents'])} validated solution patterns:",
                ]
            )

            for precedent in unified_context["solution_precedents"][:3]:
                description_parts.append(f"- **{precedent['title']}** (Success Rate: {precedent['success_rate']:.1%})")

        # Add affected packages,
        if optimization.affected_packages:
            description_parts.extend(
                ["", "### 📦 Affected Packages", "\n".join(f"- {pkg}" for pkg in optimization.affected_packages)]
            )

        # Add implementation plan,
        if optimization.implementation_plan:
            description_parts.extend(
                [
                    "",
                    "### 🛠️ Implementation Plan",
                    "\n".join(f"{i+1}. {step}" for i, step in enumerate(optimization.implementation_plan)),
                ]
            )

        # Add validation section,
        description_parts.extend(
            [
                "",
                "### ✅ Oracle Validation",
                "- [ ] Strategic alignment verified",
                "- [ ] Cross-correlation analysis passed",
                "- [ ] Business impact validated",
                "- [ ] Performance benchmarks met",
                "- [ ] Prophecy validation (if applicable)",
                "",
                f"**Estimated Implementation Effort**: {optimization.estimated_effort_hours} hours",
                f"**Risk Level**: {optimization.risk_level.title()}",
                f"**Business Value**: {optimization.business_value or 'Improved architectural quality'}",
                "",
                "### 🧠 Continuous Learning",
                "This PR contributes to the Oracle's continuous learning through:",
                "- Strategic context validation",
                "- Prophecy-action correlation analysis",
                "- Cross-package optimization pattern refinement",
                "- Unified intelligence enhancement",
                "",
                "*This PR was generated by the Oracle's Unified Action Framework with strategic context from the Prophecy Engine.*",
            ]
        )

        return "\n".join(description_parts)

    async def _perform_strategic_validation_async(
        self, unified_pr: UnifiedPullRequest, optimization: OptimizationOpportunity
    ) -> None:
        """Perform strategic validation of the unified PR."""

        # Strategic alignment validation,
        if unified_pr.strategic_rationale.confidence_level in [
            ActionConfidenceLevel.CERTAIN,
            ActionConfidenceLevel.HIGH,
        ]:
            unified_pr.strategic_validation_passed = True

        # Prophecy alignment score,
        if unified_pr.strategic_rationale.related_prophecies:
            unified_pr.prophecy_alignment_score = min(unified_pr.strategic_rationale.success_probability * 1.2, 1.0)
        else:
            unified_pr.prophecy_alignment_score = optimization.oracle_confidence

        # Business value score,
        unified_pr.business_value_score = self._calculate_business_value_score(optimization)

        # Determine consciousness level required,
        if unified_pr.strategic_rationale.confidence_level == ActionConfidenceLevel.CERTAIN:
            unified_pr.consciousness_level_required = "transcendent",
        elif unified_pr.strategic_rationale.confidence_level == ActionConfidenceLevel.HIGH:
            unified_pr.consciousness_level_required = "advanced",
        else:
            unified_pr.consciousness_level_required = "developing"

        unified_pr.wisdom_synthesis_applied = True

    def _calculate_unified_confidence(
        self,
        optimization: OptimizationOpportunity,
        strategic_rationale: StrategicRationale,
        unified_context: dict[str, Any],
    ) -> float:
        """Calculate unified confidence score."""

        base_confidence = optimization.oracle_confidence

        # Strategic context boost,
        context_boost = {
            StrategicContext.PROPHECY_VALIDATION: 0.15,
            StrategicContext.RISK_MITIGATION: 0.12,
            StrategicContext.COST_OPTIMIZATION: 0.10,
            StrategicContext.PERFORMANCE_ENHANCEMENT: 0.10,
            StrategicContext.COMPLIANCE_ALIGNMENT: 0.08,
            StrategicContext.BUSINESS_VALUE_CREATION: 0.05,
        }.get(strategic_rationale.strategic_context, 0.0)

        # Cross-correlation boost,
        correlation_boost = min(len(unified_context.get("cross_correlations", [])) * 0.02, 0.10)

        # Solution precedent boost
        precedent_boost = min(len(unified_context.get("solution_precedents", [])) * 0.03, 0.15)

        # Calculate final confidence
        unified_confidence = min(base_confidence + context_boost + correlation_boost + precedent_boost, 1.0)

        return unified_confidence

    # Helper methods for strategic context

    def _determine_strategic_context(
        self, optimization: OptimizationOpportunity, prophecy_context: dict[str, Any] | None
    ) -> StrategicContext:
        """Determine the strategic context for an optimization."""

        if prophecy_context and prophecy_context.get("prophecy_ids"):
            return StrategicContext.PROPHECY_VALIDATION

        if optimization.optimization_type == OptimizationType.COST_REDUCTION:
            return StrategicContext.COST_OPTIMIZATION,
        elif optimization.optimization_type == OptimizationType.PERFORMANCE_OPTIMIZATION:
            return StrategicContext.PERFORMANCE_ENHANCEMENT,
        elif optimization.optimization_type == OptimizationType.SECURITY_HARDENING:
            return StrategicContext.RISK_MITIGATION,
        elif "compliance" in optimization.title.lower():
            return StrategicContext.COMPLIANCE_ALIGNMENT,
        else:
            return StrategicContext.BUSINESS_VALUE_CREATION

    def _calculate_confidence_level(
        self, optimization: OptimizationOpportunity, prophecy_context: dict[str, Any] | None
    ) -> ActionConfidenceLevel:
        """Calculate the confidence level for an optimization."""

        confidence = optimization.oracle_confidence

        # Boost confidence if prophecy context exists,
        if prophecy_context and prophecy_context.get("prophecy_ids"):
            confidence += 0.1

        if confidence >= 0.95:
            return ActionConfidenceLevel.CERTAIN,
        elif confidence >= 0.85:
            return ActionConfidenceLevel.HIGH,
        elif confidence >= 0.70:
            return ActionConfidenceLevel.MODERATE,
        elif confidence >= 0.50:
            return ActionConfidenceLevel.EXPERIMENTAL,
        else:
            return ActionConfidenceLevel.SPECULATIVE

    def _generate_business_impact(self, optimization: OptimizationOpportunity) -> str:
        """Generate business impact description."""

        if optimization.business_value:
            return optimization.business_value

        impact_templates = {
            OptimizationType.COST_REDUCTION: "Reduces operational costs through optimization",
            OptimizationType.PERFORMANCE_OPTIMIZATION: "Improves system performance and user experience",
            OptimizationType.SECURITY_HARDENING: "Enhances security posture and reduces risk",
            OptimizationType.CODE_DEDUPLICATION: "Improves maintainability and reduces technical debt",
        }

        return impact_templates.get(optimization.optimization_type, "Improves overall system quality")

    def _generate_cost_implications(self, optimization: OptimizationOpportunity) -> str:
        """Generate cost implications description."""

        if optimization.optimization_type == OptimizationType.COST_REDUCTION:
            return f"Projected monthly savings of ${optimization.estimated_effort_hours * 50} through optimization"
        elif optimization.optimization_type == OptimizationType.PERFORMANCE_OPTIMIZATION:
            return "Reduces infrastructure costs through improved efficiency"
        else:
            return "Minimal direct cost impact, long-term maintenance savings expected"

    def _generate_performance_impact(self, optimization: OptimizationOpportunity) -> str:
        """Generate performance impact description."""

        if optimization.optimization_type == OptimizationType.PERFORMANCE_OPTIMIZATION:
            return "Expected 15-25% performance improvement based on similar optimizations"
        elif optimization.optimization_type == OptimizationType.CODE_DEDUPLICATION:
            return "Improved build times and reduced memory footprint"
        else:
            return "Indirect performance benefits through improved code quality"

    def _generate_oracle_reasoning(
        self, optimization: OptimizationOpportunity, prophecy_context: dict[str, Any] | None
    ) -> str:
        """Generate Oracle's strategic reasoning."""

        reasoning_parts = [
            "The Oracle's unified intelligence identified this optimization through cross-correlation analysis."
        ]

        if prophecy_context:
            reasoning_parts.append(
                f"This action directly validates {len(prophecy_context.get('prophecy_ids', []))} architectural prophecies."
            )

        reasoning_parts.append(
            f"Historical analysis shows {optimization.optimization_type.value.replace('_', ' ')} optimizations ",
            f"have an {optimization.oracle_confidence:.1%} success rate in similar contexts."
        )

        return " ".join(reasoning_parts)

    def _calculate_business_value_score(self, optimization: OptimizationOpportunity) -> float:
        """Calculate business value score for an optimization."""

        base_score = 0.5

        # Priority boost
        priority_boost = {
            OptimizationPriority.CRITICAL: 0.4,
            OptimizationPriority.HIGH: 0.3,
            OptimizationPriority.MEDIUM: 0.2,
            OptimizationPriority.LOW: 0.1,
            OptimizationPriority.ENHANCEMENT: 0.05,
        }.get(optimization.priority, 0.0)

        # Type boost
        type_boost = {
            OptimizationType.COST_REDUCTION: 0.3,
            OptimizationType.PERFORMANCE_OPTIMIZATION: 0.25,
            OptimizationType.SECURITY_HARDENING: 0.2,
            OptimizationType.CROSS_PACKAGE_INTEGRATION: 0.15,
        }.get(optimization.optimization_type, 0.1)

        return min(base_score + priority_boost + type_boost, 1.0)

    # Learning and feedback methods

    async def _update_strategic_learning_async(self, feedback_analysis: dict[str, Any]) -> None:
        """Update strategic learning models based on feedback."""

        # Extract learning signals
        outcome = feedback_analysis.get("outcome_type", "unknown")
        strategic_context = feedback_analysis.get("strategic_context", "unknown")

        # Update success rates for strategic contexts
        if strategic_context not in self.strategic_learning_models:
            self.strategic_learning_models[strategic_context] = {
                "total_actions": 0,
                "successful_actions": 0,
                "success_rate": 0.0,
                "confidence_adjustments": [],
            }

        model = self.strategic_learning_models[strategic_context]
        model["total_actions"] += 1

        if outcome == "success":
            model["successful_actions"] += 1

        model["success_rate"] = model["successful_actions"] / model["total_actions"]

        # Apply learning weight adjustment
        confidence_adjustment = self.config.learning_weight_adjustment
        if outcome != "success":
            confidence_adjustment *= -1

        model["confidence_adjustments"].append(
            {"adjustment": confidence_adjustment, "timestamp": datetime.utcnow().isoformat()}
        )

    async def _generate_learning_insights_async(self, feedback_analysis: dict[str, Any]) -> dict[str, Any]:
        """Generate learning insights from feedback analysis."""

        insights = {
            "learning_type": "strategic_feedback",
            "insights_generated": [],
            "model_updates": [],
            "strategic_recommendations": [],
        }

        outcome = feedback_analysis.get("outcome_type", "unknown")

        if outcome == "success":
            insights["insights_generated"].append(
                "Strategic approach validated - increase confidence for similar patterns"
            )
            insights["strategic_recommendations"].append("Continue with similar strategic contexts")
        else:
            insights["insights_generated"].append("Strategic approach needs refinement - analyze failure patterns")
            insights["strategic_recommendations"].append("Review strategic context alignment")

        return insights

    def _generate_pattern_recommendations(self, context_success_rates: dict[str, dict]) -> list[str]:
        """Generate recommendations based on pattern analysis."""

        recommendations = []

        # Find best performing contexts
        best_contexts = [
            context
            for context, data in context_success_rates.items()
            if data["success_rate"] > 0.8 and data["total"] >= 3
        ]

        if best_contexts:
            recommendations.append(f"Focus on high-performing strategic contexts: {', '.join(best_contexts)}")

        # Find underperforming contexts
        poor_contexts = [
            context
            for context, data in context_success_rates.items()
            if data["success_rate"] < 0.5 and data["total"] >= 3
        ]

        if poor_contexts:
            recommendations.append(f"Review and improve strategic approaches for: {', '.join(poor_contexts)}")

        return recommendations

    def _calculate_prophecy_validation_rate(self) -> float:
        """Calculate the rate of prophecy validation through actions."""

        prophecy_validations = [
            f for f in self.feedback_history if f.get("prophecy_validation", {}).get("validated", False)
        ]

        return len(prophecy_validations) / len(self.feedback_history) if self.feedback_history else 0.0

    def _calculate_avg_correlation_strength(self) -> float:
        """Calculate average cross-correlation strength."""

        correlations = []
        for rationale in self.strategic_context_cache.values():
            correlations.append(rationale.cross_correlation_strength)

        return sum(correlations) / len(correlations) if correlations else 0.0











