"""
Prompt optimization and improvement engine.

Provides AI-driven prompt enhancement, A/B testing,
and performance analysis for prompt effectiveness.
"""

import asyncio
import statistics
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from hive_cache import CacheManager
from hive_logging import get_logger

from ..core.exceptions import PromptError
from .template import PromptTemplate

logger = get_logger(__name__)


class OptimizationStrategy(Enum):
    """Optimization strategies for prompt improvement."""

    CLARITY = "clarity"  # Improve clarity and specificity
    BREVITY = "brevity"  # Reduce token usage while maintaining effectiveness
    CREATIVITY = "creativity"  # Enhance creative output
    ACCURACY = "accuracy"  # Improve factual accuracy and reasoning
    INSTRUCTION = "instruction"  # Better instruction following
    CONTEXT = "context"  # Better context utilization


@dataclass
class OptimizationResult:
    """Result from prompt optimization."""

    original_prompt: str
    optimized_prompt: str
    strategy: OptimizationStrategy
    improvements: list[str]
    estimated_improvement: float  # 0.0 to 1.0
    token_change: int  # Positive = more tokens, Negative = fewer tokens
    suggestions: list[str] = field(default_factory=list)


@dataclass
class PerformanceMetric:
    """Performance metric for prompt evaluation."""

    name: str
    value: float
    description: str
    higher_is_better: bool = True


@dataclass
class PromptTestResult:
    """Result from prompt A/B testing."""

    prompt_a: str
    prompt_b: str
    metrics_a: list[PerformanceMetric]
    metrics_b: list[PerformanceMetric]
    winner: str  # "A", "B", or "TIE"
    confidence: float  # 0.0 to 1.0
    sample_size: int


class PromptOptimizer:
    """
    AI-driven prompt optimization and testing engine.

    Provides systematic prompt improvement through analysis,
    optimization, and A/B testing capabilities.
    """

    def __init__(self, model_client: Any = None):  # ModelClient type
        self.model_client = model_client
        self.cache = CacheManager("prompt_optimizer")
        self._optimization_templates = self._load_optimization_templates()

    def _load_optimization_templates(self) -> dict[OptimizationStrategy, str]:
        """Load optimization prompt templates for different strategies."""
        return {
            OptimizationStrategy.CLARITY: """,
Analyze and improve this prompt for clarity and specificity:

Original prompt: {{ original_prompt }}

Please provide:
1. An improved version that is more clear and specific
2. List of specific improvements made
3. Explanation of why these changes improve clarity

Focus on:
- Removing ambiguity
- Adding specific instructions
- Clarifying expected output format
- Defining key terms

Improved prompt:""",
            OptimizationStrategy.BREVITY: """
Optimize this prompt to reduce token usage while maintaining effectiveness:

Original prompt: {{ original_prompt }}

Please provide:
1. A more concise version that maintains the same intent
2. List of reductions made
3. Token count estimate change

Focus on:
- Removing redundant words
- Combining similar instructions
- Using more efficient phrasing
- Eliminating unnecessary examples

Concise prompt:""",
            OptimizationStrategy.CREATIVITY: """
Enhance this prompt to encourage more creative and innovative responses:

Original prompt: {{ original_prompt }}

Please provide:
1. An enhanced version that promotes creativity
2. List of creative elements added
3. Explanation of how changes encourage innovation

Focus on:
- Adding open-ended elements
- Encouraging exploration
- Promoting novel approaches
- Including creative constraints

Creative prompt:""",
            OptimizationStrategy.ACCURACY: """
Improve this prompt to enhance factual accuracy and logical reasoning:

Original prompt: {{ original_prompt }}

Please provide:
1. An improved version focused on accuracy
2. List of accuracy improvements made
3. Explanation of reasoning enhancements

Focus on:
- Adding verification instructions
- Requesting sources or evidence
- Encouraging step-by-step reasoning
- Including accuracy checks

Accurate prompt:""",
            OptimizationStrategy.INSTRUCTION: """
Optimize this prompt for better instruction following and task completion:

Original prompt: {{ original_prompt }}

Please provide:
1. An improved version with clearer instructions
2. List of instruction improvements made
3. Explanation of task clarity enhancements

Focus on:
- Making instructions more explicit
- Adding step-by-step guidance
- Clarifying success criteria
- Including examples if helpful

Instructional prompt:""",
            OptimizationStrategy.CONTEXT: """
Improve this prompt to better utilize available context and information:

Original prompt: {{ original_prompt }}

Please provide:
1. An enhanced version that better uses context
2. List of context utilization improvements
3. Explanation of how changes leverage context

Focus on:
- Referencing relevant context
- Building on provided information
- Connecting to related concepts
- Utilizing background knowledge

Context-aware prompt:""",
        }

    async def optimize_prompt_async(
        self,
        prompt: str,
        strategy: OptimizationStrategy = OptimizationStrategy.CLARITY,
        context: dict[str, Any] | None = None,
    ) -> OptimizationResult:
        """
        Optimize a prompt using specified strategy.

        Args:
            prompt: Original prompt to optimize,
            strategy: Optimization strategy to use,
            context: Additional context for optimization

        Returns:
            OptimizationResult with improved prompt and analysis

        Raises:
            PromptError: Optimization failed,
        """
        if not self.model_client:
            raise PromptError("Model client required for prompt optimization")

        # Check cache first
        cache_key = f"optimize_{hash(prompt)}_{strategy.value}"
        cached_result = self.cache.get(cache_key)
        if cached_result:
            logger.debug("Using cached optimization result")
            return OptimizationResult(**cached_result)

        try:
            # Create optimization prompt
            optimization_template = PromptTemplate(template=self._optimization_templates[strategy], variables=[])

            optimization_prompt = optimization_template.render(original_prompt=prompt, **(context or {}))

            # Generate optimization
            response = await self.model_client.generate_async(
                optimization_prompt,
                temperature=0.3,  # Lower temperature for more consistent optimization
            )

            # Parse optimization result
            result = self._parse_optimization_response(response.content, prompt, strategy)

            # Cache result for 1 hour
            self.cache.set(cache_key, result.__dict__, ttl=3600)

            logger.info(f"Prompt optimization completed using {strategy.value} strategy")
            return result

        except Exception as e:
            raise PromptError(f"Prompt optimization failed: {str(e)}") from e

    def _parse_optimization_response(
        self, response: str, original_prompt: str, strategy: OptimizationStrategy
    ) -> OptimizationResult:
        """Parse AI response into optimization result."""
        # Simple parsing - in production, this would be more sophisticated
        lines = response.strip().split("\n")

        optimized_prompt = ""
        improvements = []
        suggestions = []

        # Extract optimized prompt (usually at the end)
        for i, line in enumerate(lines):
            if "prompt:" in line.lower() and i < len(lines) - 1:
                optimized_prompt = ("\n".join(lines[i + 1 :]).strip(),)
                break

        if not optimized_prompt:
            # Fallback: use the entire response as optimized prompt
            optimized_prompt = response.strip()

        # Extract improvements (look for numbered lists)
        for line in lines:
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-")):
                improvements.append(line)

        # Estimate improvement (simplified heuristic)
        estimated_improvement = self._estimate_improvement(original_prompt, optimized_prompt, strategy)

        # Calculate token change
        token_change = len(optimized_prompt.split()) - len(original_prompt.split())

        return OptimizationResult(
            original_prompt=original_prompt,
            optimized_prompt=optimized_prompt,
            strategy=strategy,
            improvements=improvements,
            estimated_improvement=estimated_improvement,
            token_change=token_change,
            suggestions=suggestions,
        )

    def _estimate_improvement(self, original: str, optimized: str, strategy: OptimizationStrategy) -> float:
        """Estimate improvement percentage (simplified heuristic)."""
        # Length-based heuristics for different strategies
        if strategy == OptimizationStrategy.BREVITY:
            reduction = (len(original) - len(optimized)) / len(original)
            return max(0.0, min(1.0, reduction))

        elif strategy == OptimizationStrategy.CLARITY:
            # More specific words indicate better clarity
            specific_indicators = ["specific", "clearly", "exactly", "must", "should"]
            original_score = sum(1 for word in specific_indicators if word in original.lower())
            optimized_score = sum(1 for word in specific_indicators if word in optimized.lower())
            return min(1.0, (optimized_score - original_score + 5) / 10)

        elif strategy == OptimizationStrategy.CREATIVITY:
            # Creative words indicate better creativity
            creative_indicators = [
                "creative",
                "innovative",
                "explore",
                "imagine",
                "unique",
            ]
            original_score = sum(1 for word in creative_indicators if word in original.lower())
            optimized_score = sum(1 for word in creative_indicators if word in optimized.lower())
            return min(1.0, (optimized_score - original_score + 5) / 10)

        # Default improvement estimate
        return 0.5

    async def ab_test_prompts_async(
        self,
        prompt_a: str,
        prompt_b: str,
        test_inputs: list[dict[str, Any]],
        evaluation_criteria: list[str],
        sample_size: int = 10,
    ) -> PromptTestResult:
        """
        A/B test two prompts for effectiveness.

        Args:
            prompt_a: First prompt to test,
            prompt_b: Second prompt to test,
            test_inputs: List of test input variables,
            evaluation_criteria: Criteria for evaluation,
            sample_size: Number of test cases to run

        Returns:
            PromptTestResult with comparison results

        Raises:
            PromptError: A/B testing failed,
        """
        if not self.model_client:
            raise PromptError("Model client required for A/B testing")

        if len(test_inputs) < sample_size:
            sample_size = len(test_inputs)

        try:
            logger.info(f"Starting A/B test with {sample_size} samples")

            # Test both prompts
            results_a = []
            results_b = []

            # Use a subset of test inputs
            test_sample = test_inputs[:sample_size]

            for i, inputs in enumerate(test_sample):
                # Test prompt A
                try:
                    template_a = PromptTemplate(template=prompt_a)
                    rendered_a = template_a.render(**inputs)
                    response_a = await self.model_client.generate_async(rendered_a)
                    results_a.append(response_a.content)
                except Exception as e:
                    (logger.warning(f"Prompt A failed for input {i}: {e}"),)
                    results_a.append("[ERROR]")

                # Test prompt B
                try:
                    template_b = PromptTemplate(template=prompt_b)
                    rendered_b = template_b.render(**inputs)
                    response_b = await self.model_client.generate_async(rendered_b)
                    results_b.append(response_b.content)
                except Exception as e:
                    (logger.warning(f"Prompt B failed for input {i}: {e}"),)
                    results_b.append("[ERROR]")

            # Evaluate results
            metrics_a = await self._evaluate_responses_async(results_a, evaluation_criteria)
            metrics_b = await self._evaluate_responses_async(results_b, evaluation_criteria)

            # Determine winner
            winner, confidence = self._determine_winner(metrics_a, metrics_b)

            result = PromptTestResult(
                prompt_a=prompt_a,
                prompt_b=prompt_b,
                metrics_a=metrics_a,
                metrics_b=metrics_b,
                winner=winner,
                confidence=confidence,
                sample_size=sample_size,
            )

            (logger.info(f"A/B test completed: Winner = {winner} (confidence: {confidence:.2f})"),)
            return result

        except Exception as e:
            raise PromptError(f"A/B testing failed: {str(e)}") from e

    async def _evaluate_responses_async(self, responses: list[str], criteria: list[str]) -> list[PerformanceMetric]:
        """Evaluate responses against criteria."""
        metrics = []

        # Basic metrics
        valid_responses = [r for r in responses if r != "[ERROR]"]
        success_rate = len(valid_responses) / len(responses) if responses else 0.0

        metrics.append(
            PerformanceMetric(
                name="success_rate",
                value=success_rate,
                description="Percentage of successful responses",
            )
        )

        if valid_responses:
            # Average response length
            avg_length = statistics.mean(len(r) for r in valid_responses)
            metrics.append(
                PerformanceMetric(
                    name="avg_response_length",
                    value=avg_length,
                    description="Average response length in characters",
                )
            )

            # Response variability (creativity indicator)
            if len(valid_responses) > 1:
                length_variance = statistics.variance([len(r) for r in valid_responses])
                metrics.append(
                    PerformanceMetric(
                        name="response_variability",
                        value=length_variance,
                        description="Variance in response lengths (creativity indicator)",
                    )
                )

        # Custom criteria evaluation would go here
        # For now, using basic metrics

        return metrics

    def _determine_winner(
        self, metrics_a: list[PerformanceMetric], metrics_b: list[PerformanceMetric]
    ) -> tuple[str, float]:
        """Determine winner and confidence level."""
        # Simple scoring based on success rate
        score_a = 0.0
        score_b = 0.0

        metrics_a_dict = ({m.name: m for m in metrics_a},)
        metrics_b_dict = {m.name: m for m in metrics_b}

        # Compare success rates
        if "success_rate" in metrics_a_dict and "success_rate" in metrics_b_dict:
            rate_a = metrics_a_dict["success_rate"].value
            rate_b = metrics_b_dict["success_rate"].value

            if rate_a > rate_b:
                score_a += 1
            elif rate_b > rate_a:
                score_b += 1

            # Calculate confidence based on difference
            difference = abs(rate_a - rate_b)
            confidence = min(1.0, difference * 2)  # Scale to 0-1
        else:
            confidence = 0.5

        # Determine winner
        if score_a > score_b:
            return "A", confidence
        elif score_b > score_a:
            return "B", confidence
        else:
            return "TIE", confidence

    async def batch_optimize_async(
        self,
        prompts: list[str],
        strategy: OptimizationStrategy = OptimizationStrategy.CLARITY,
    ) -> list[OptimizationResult]:
        """
        Optimize multiple prompts in batch.

        Args:
            prompts: List of prompts to optimize,
            strategy: Optimization strategy to use

        Returns:
            List of optimization results
        """
        logger.info(f"Starting batch optimization of {len(prompts)} prompts")

        tasks = [self.optimize_prompt_async(prompt, strategy) for prompt in prompts]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and log errors
        successful_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                (logger.error(f"Optimization failed for prompt {i}: {result}"),)
            else:
                successful_results.append(result)

        (logger.info(f"Batch optimization completed: {len(successful_results)}/{len(prompts)} successful"),)
        return successful_results

    def get_optimization_stats(self) -> dict[str, Any]:
        """Get optimization statistics and insights."""
        # This would track optimization history and effectiveness
        return {
            "cache_size": self.cache.size() if hasattr(self.cache, "size") else 0,
            "supported_strategies": [s.value for s in OptimizationStrategy],
            "optimization_count": "N/A",  # Would need tracking,
            "avg_improvement": "N/A",  # Would need tracking
        }
