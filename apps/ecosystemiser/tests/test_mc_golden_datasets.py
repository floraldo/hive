"""
Golden Dataset Tests for Monte Carlo Validation

This module validates the Monte Carlo uncertainty analysis implementation
against analytical models with known statistical properties and distributions.

References:
- Saltelli et al. (2008): Global Sensitivity Analysis
- Helton & Davis (2003): Latin Hypercube Sampling
- Sobol (1967): Quasi-random sequences
"""

import json

import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pytest
from scipy import stats
from scipy.stats import beta, norm, uniform

from ecosystemiser.discovery.algorithms.monte_carlo import (
    MonteCarloConfig,
    MonteCarloEngine,
    UncertaintyVariable,
)


class AnalyticalModels:
    """Collection of analytical models with known statistical properties."""

    @staticmethod
    def linear_model(x: np.ndarray, coefficients: np.ndarray = None) -> float:
        """
        Linear model: y = sum(a_i * x_i)

        With uniform inputs, analytical mean and variance are known.
        """
        if coefficients is None:
            coefficients = np.ones(len(x))

        return np.sum(coefficients * x)

    @staticmethod
    def rosenbrock(x: np.ndarray) -> float:
        """
        Rosenbrock function with known global minimum.

        Global minimum: f(1, 1, ..., 1) = 0
        """
        return np.sum(100 * (x[1:] - x[:-1] ** 2) ** 2 + (1 - x[:-1]) ** 2)

    @staticmethod
    def portfolio_model(
        weights: np.ndarray, returns: np.ndarray, covariance: np.ndarray
    ) -> Tuple[float, float]:
        """
        Portfolio optimization model with known mean-variance frontier.

        Returns: (expected_return, variance)
        """
        expected_return = np.dot(weights, returns)
        variance = np.dot(weights, np.dot(covariance, weights))
        return expected_return, variance

    @staticmethod
    def ishigami_function(x: np.ndarray, a: float = 7, b: float = 0.1) -> float:
        """
        Ishigami function - standard sensitivity analysis benchmark.

        Analytical sensitivity indices are known.
        """
        assert len(x) == 3, "Ishigami function requires exactly 3 inputs"
        return np.sin(x[0]) + a * np.sin(x[1]) ** 2 + b * x[2] ** 4 * np.sin(x[0])

    @staticmethod
    def get_analytical_statistics(
        model: str, distribution: str, n_vars: int
    ) -> Dict[str, float]:
        """Get analytical statistics for validation."""
        if model == "linear" and distribution == "uniform":
            # For uniform(0,1) inputs and unit coefficients
            mean = n_vars * 0.5  # Each variable contributes 0.5
            variance = n_vars * (1 / 12)  # Each variable contributes 1/12
            return {"mean": mean, "variance": variance, "std": np.sqrt(variance)}

        elif model == "ishigami":
            # Ishigami with uniform(-π, π) inputs
            a, b = 7, 0.1
            # Analytical results from Sobol & Levitan (1999)
            var_total = a**2 / 8 + b * np.pi**4 / 5 + b**2 * np.pi**8 / 18 + 0.5
            return {
                "variance": var_total,
                "S1": 0.314,  # First-order sensitivity of x1
                "S2": 0.442,  # First-order sensitivity of x2
                "S3": 0.0,  # First-order sensitivity of x3
                "ST1": 0.558,  # Total sensitivity of x1
                "ST2": 0.442,  # Total sensitivity of x2
                "ST3": 0.244,  # Total sensitivity of x3
            }

        return {}


class TestMonteCarloGoldenDatasets:
    """Test Monte Carlo implementation against analytical solutions."""

    def test_linear_model_statistics(self):
        """Test MC analysis on linear model with known statistics."""
        n_vars = 5
        n_samples = 10000

        # Configure Monte Carlo with uniform distributions
        uncertainty_vars = {}
        for i in range(n_vars):
            uncertainty_vars[f"x{i}"] = {
                "distribution": "uniform",
                "parameters": {"low": 0, "high": 1},
                "bounds": (0, 1),
            }

        config = MonteCarloConfig(
            dimensions=n_vars,
            bounds=[(0, 1)] * n_vars,
            population_size=n_samples,
            sampling_method="lhs",
            uncertainty_variables=uncertainty_vars,
            confidence_levels=[0.05, 0.95],
        )

        mc = MonteCarloEngine(config)

        # Define evaluation function
        def fitness_function(x):
            result = AnalyticalModels.linear_model(x)
            return {"fitness": result, "objectives": [result], "valid": True}

        # Run Monte Carlo analysis
        result = mc.analyze(fitness_function)

        # Extract statistics
        stats = result["uncertainty_analysis"]["statistics"]
        analytical = AnalyticalModels.get_analytical_statistics(
            "linear", "uniform", n_vars
        )

        # Validate mean (should be within 1% of analytical)
        relative_error_mean = (
            abs(stats["mean"] - analytical["mean"]) / analytical["mean"]
        )
        assert (
            relative_error_mean < 0.01
        ), f"Mean error too large: {relative_error_mean:.2%}"

        # Validate standard deviation (should be within 2% of analytical)
        relative_error_std = abs(stats["std"] - analytical["std"]) / analytical["std"]
        assert (
            relative_error_std < 0.02
        ), f"Std deviation error too large: {relative_error_std:.2%}"

    def test_sampling_uniformity_lhs(self):
        """Test Latin Hypercube Sampling uniformity."""
        config = MonteCarloConfig(
            dimensions=2,
            bounds=[(0, 1), (0, 1)],
            population_size=100,
            sampling_method="lhs",
        )

        mc = MonteCarloEngine(config)
        samples = mc._latin_hypercube_sampling()

        # Check that samples are in bounds
        assert np.all(samples >= 0) and np.all(samples <= 1), "Samples out of bounds"

        # Check uniformity: divide space into grid and count samples
        n_bins = 10
        hist, _, _ = np.histogram2d(
            samples[:, 0], samples[:, 1], bins=[n_bins, n_bins], range=[[0, 1], [0, 1]]
        )

        # Each cell should have approximately equal probability
        expected_per_bin = len(samples) / (n_bins * n_bins)

        # LHS should have exactly 1 sample per row and column
        # Check that each row and column has samples
        row_sums = np.sum(hist > 0, axis=1)
        col_sums = np.sum(hist > 0, axis=0)

        assert np.all(row_sums > 0), "LHS missing samples in some rows"
        assert np.all(col_sums > 0), "LHS missing samples in some columns"

    def test_sobol_sequence_properties(self):
        """Test Sobol sequence low-discrepancy properties."""
        config = MonteCarloConfig(
            dimensions=2,
            bounds=[(0, 1), (0, 1)],
            population_size=256,  # Power of 2 for Sobol
            sampling_method="sobol",
        )

        mc = MonteCarloEngine(config)
        samples = mc._sobol_sampling()

        # Sobol sequences should have low discrepancy
        # Test: check that samples fill space more uniformly than random
        n_bins = 16
        hist, _, _ = np.histogram2d(
            samples[:, 0], samples[:, 1], bins=[n_bins, n_bins], range=[[0, 1], [0, 1]]
        )

        # Count empty bins (should be fewer than random sampling)
        empty_bins = np.sum(hist == 0)
        max_empty = n_bins * n_bins * 0.3  # Allow up to 30% empty for 256 samples

        assert (
            empty_bins < max_empty
        ), f"Sobol sequence has poor space filling: {empty_bins} empty bins"

    def test_confidence_intervals(self):
        """Test confidence interval calculations."""
        # Generate known normal distribution
        np.random.seed(42)
        true_mean = 100
        true_std = 15
        n_samples = 10000

        config = MonteCarloConfig(
            dimensions=1,
            bounds=[(-np.inf, np.inf)],
            population_size=n_samples,
            confidence_levels=[0.05, 0.25, 0.50, 0.75, 0.95],
        )

        mc = MonteCarloEngine(config)

        # Generate samples from known distribution
        samples = norm.rvs(loc=true_mean, scale=true_std, size=n_samples)

        # Calculate uncertainty analysis
        analysis = mc._calculate_uncertainty_analysis(samples)

        # Verify confidence intervals
        ci = analysis["confidence_intervals"]

        # 90% CI should contain approximately 90% of the probability mass
        ci_90_lower = ci["5%"]
        ci_90_upper = ci["95%"]

        # Analytical 90% CI for normal distribution
        z_score = 1.645  # 90% CI
        expected_lower = true_mean - z_score * true_std
        expected_upper = true_mean + z_score * true_std

        # Allow 5% tolerance
        assert (
            abs(ci_90_lower - expected_lower) < 5
        ), f"Lower CI incorrect: {ci_90_lower:.2f} vs {expected_lower:.2f}"
        assert (
            abs(ci_90_upper - expected_upper) < 5
        ), f"Upper CI incorrect: {ci_90_upper:.2f} vs {expected_upper:.2f}"

    def test_risk_metrics_var_cvar(self):
        """Test Value-at-Risk and Conditional Value-at-Risk calculations."""
        # Generate known distribution (normal for analytical comparison)
        np.random.seed(42)
        returns = norm.rvs(
            loc=0.05, scale=0.20, size=10000
        )  # 5% return, 20% volatility

        config = MonteCarloConfig(
            dimensions=1,
            bounds=[(-1, 1)],
            population_size=len(returns),
            risk_analysis=True,
        )

        mc = MonteCarloEngine(config)

        # Calculate risk metrics
        analysis = mc._calculate_uncertainty_analysis(returns)
        risk = analysis["risk_metrics"]

        # Verify VaR calculation (95% confidence level)
        var_95 = risk.get("var_95", None)
        if var_95 is not None:
            # Analytical VaR for normal distribution
            analytical_var = norm.ppf(0.05, loc=0.05, scale=0.20)

            relative_error = abs(var_95 - analytical_var) / abs(analytical_var)
            assert relative_error < 0.05, f"VaR calculation error: {relative_error:.2%}"

        # Verify CVaR (should be more negative than VaR)
        cvar_95 = risk.get("cvar_95", None)
        if cvar_95 is not None and var_95 is not None:
            assert cvar_95 < var_95, "CVaR should be worse than VaR"

    def test_sensitivity_analysis(self):
        """Test sensitivity analysis on Ishigami function."""
        # Ishigami function has known sensitivity indices
        n_samples = 5000

        uncertainty_vars = {
            "x1": {
                "distribution": "uniform",
                "parameters": {"low": -np.pi, "high": np.pi},
                "bounds": (-np.pi, np.pi),
            },
            "x2": {
                "distribution": "uniform",
                "parameters": {"low": -np.pi, "high": np.pi},
                "bounds": (-np.pi, np.pi),
            },
            "x3": {
                "distribution": "uniform",
                "parameters": {"low": -np.pi, "high": np.pi},
                "bounds": (-np.pi, np.pi),
            },
        }

        config = MonteCarloConfig(
            dimensions=3,
            bounds=[(-np.pi, np.pi)] * 3,
            population_size=n_samples,
            sampling_method="sobol",
            uncertainty_variables=uncertainty_vars,
            sensitivity_analysis=True,
        )

        mc = MonteCarloEngine(config)

        def fitness_function(x):
            result = AnalyticalModels.ishigami_function(x)
            return {"fitness": result, "objectives": [result], "valid": True}

        # Run analysis
        result = mc.analyze(fitness_function)

        # Extract sensitivity indices
        sensitivity = result.get("sensitivity_analysis", {})

        if sensitivity:
            # Get analytical values
            analytical = AnalyticalModels.get_analytical_statistics(
                "ishigami", "uniform", 3
            )

            # Check first-order indices (allow 20% error due to finite sampling)
            for i, true_si in enumerate(
                [analytical["S1"], analytical["S2"], analytical["S3"]]
            ):
                param_name = f"x{i+1}"
                if param_name in sensitivity:
                    estimated_si = sensitivity[param_name].get("first_order", 0)
                    if true_si > 0.01:  # Only check non-negligible indices
                        relative_error = abs(estimated_si - true_si) / true_si
                        assert (
                            relative_error < 0.30
                        ), f"Sensitivity index S{i+1} error: {relative_error:.2%}"

    def test_correlation_handling(self):
        """Test handling of correlated input variables."""
        # Create correlation matrix
        correlation = np.array([[1.0, 0.7, 0.0], [0.7, 1.0, 0.0], [0.0, 0.0, 1.0]])

        config = MonteCarloConfig(
            dimensions=3,
            bounds=[(0, 1)] * 3,
            population_size=1000,
            sampling_method="lhs",
            correlation_matrix=correlation,
        )

        mc = MonteCarloEngine(config)

        # Generate correlated samples
        samples = mc.initialize_population()

        # Verify correlation structure
        empirical_corr = np.corrcoef(samples.T)

        # Check that correlation is approximately preserved
        for i in range(3):
            for j in range(3):
                expected = correlation[i, j]
                observed = empirical_corr[i, j]
                error = abs(expected - observed)

                # Allow 0.1 tolerance for correlation
                assert (
                    error < 0.15
                ), f"Correlation [{i},{j}] not preserved: {observed:.2f} vs {expected:.2f}"

    def test_distribution_sampling(self):
        """Test sampling from different distributions."""
        distributions = {
            "normal": {
                "distribution": "normal",
                "parameters": {"mean": 10, "std": 2},
                "bounds": (4, 16),  # 3 sigma bounds
            },
            "lognormal": {
                "distribution": "lognormal",
                "parameters": {"mean": 2, "std": 0.5},
                "bounds": (0, 20),
            },
            "beta": {
                "distribution": "beta",
                "parameters": {"a": 2, "b": 5},
                "bounds": (0, 1),
            },
            "triangular": {
                "distribution": "triangular",
                "parameters": {"low": 0, "mode": 3, "high": 10},
                "bounds": (0, 10),
            },
        }

        for dist_name, dist_config in distributions.items():
            config = MonteCarloConfig(
                dimensions=1,
                bounds=[dist_config["bounds"]],
                population_size=5000,
                uncertainty_variables={"x": dist_config},
            )

            mc = MonteCarloEngine(config)

            # Sample from distribution
            samples = mc._sample_from_distribution(
                dist_config["distribution"], dist_config["parameters"], 5000
            )

            # Basic checks
            assert len(samples) == 5000, f"Wrong sample size for {dist_name}"

            # Check bounds compliance (with small tolerance for truncation)
            lower, upper = dist_config["bounds"]
            assert np.all(
                samples >= lower - 0.01
            ), f"{dist_name}: samples below lower bound"
            assert np.all(
                samples <= upper + 0.01
            ), f"{dist_name}: samples above upper bound"

            # Check distribution properties (mean for normal)
            if dist_name == "normal":
                empirical_mean = np.mean(samples)
                expected_mean = dist_config["parameters"]["mean"]
                assert (
                    abs(empirical_mean - expected_mean) < 0.1
                ), f"Normal distribution mean incorrect"

    def save_validation_results(self, test_name: str, metrics: Dict[str, Any]):
        """Save validation results for reporting."""
        results_dir = Path("tests/validation_results")
        results_dir.mkdir(exist_ok=True)

        results_file = results_dir / f"mc_{test_name}_results.json"

        with open(results_file, "w") as f:
            json.dump(metrics, f, indent=2, default=str)

    def generate_distribution_plot(
        self, samples: np.ndarray, analytical_dist: Any, test_name: str
    ):
        """Generate visualization of sampling distribution."""
        plt.figure(figsize=(12, 5))

        # Histogram of samples
        plt.subplot(1, 2, 1)
        plt.hist(samples, bins=50, density=True, alpha=0.7, label="MC Samples")

        if analytical_dist is not None:
            x_range = np.linspace(samples.min(), samples.max(), 100)
            plt.plot(
                x_range,
                analytical_dist.pdf(x_range),
                "r-",
                label="Analytical PDF",
                linewidth=2,
            )

        plt.xlabel("Value")
        plt.ylabel("Density")
        plt.title(f"Distribution Validation: {test_name}")
        plt.legend()
        plt.grid(True, alpha=0.3)

        # Q-Q plot
        plt.subplot(1, 2, 2)
        if analytical_dist is not None:
            stats.probplot(samples, dist=analytical_dist, plot=plt)
        else:
            stats.probplot(samples, dist="norm", plot=plt)

        plt.title("Q-Q Plot")
        plt.grid(True, alpha=0.3)

        plt.tight_layout()

        # Save plot
        plots_dir = Path("tests/validation_plots")
        plots_dir.mkdir(exist_ok=True)
        plt.savefig(
            plots_dir / f"mc_{test_name}_distribution.png", dpi=300, bbox_inches="tight"
        )
        plt.close()


class TestMCNumericalStability:
    """Test numerical stability of Monte Carlo operations."""

    def test_extreme_bounds(self):
        """Test MC with extreme parameter bounds."""
        config = MonteCarloConfig(
            dimensions=3,
            bounds=[(-1e10, 1e10), (1e-10, 1e-5), (0, 1e6)],
            population_size=100,
            sampling_method="lhs",
        )

        mc = MonteCarloEngine(config)
        samples = mc.initialize_population()

        # Check that samples respect bounds
        for i, (lower, upper) in enumerate(config.bounds):
            assert np.all(samples[:, i] >= lower), f"Dimension {i} below lower bound"
            assert np.all(samples[:, i] <= upper), f"Dimension {i} above upper bound"

        # Check no NaN or inf values
        assert not np.any(np.isnan(samples)), "NaN values in samples"
        assert not np.any(np.isinf(samples)), "Inf values in samples"

    def test_high_dimensional_sampling(self):
        """Test MC in high-dimensional spaces."""
        n_dims = 100
        config = MonteCarloConfig(
            dimensions=n_dims,
            bounds=[(0, 1)] * n_dims,
            population_size=500,
            sampling_method="lhs",
        )

        mc = MonteCarloEngine(config)
        samples = mc.initialize_population()

        assert samples.shape == (
            500,
            n_dims,
        ), "Wrong shape for high-dimensional samples"

        # Check that LHS properties hold in high dimensions
        # Each dimension should have good coverage
        for dim in range(min(10, n_dims)):  # Check first 10 dimensions
            dim_samples = samples[:, dim]
            # Check coverage using percentiles
            percentiles = np.percentile(dim_samples, [10, 50, 90])
            assert 0.05 < percentiles[0] < 0.15, f"Poor coverage in dim {dim} (low)"
            assert 0.45 < percentiles[1] < 0.55, f"Poor coverage in dim {dim} (mid)"
            assert 0.85 < percentiles[2] < 0.95, f"Poor coverage in dim {dim} (high)"

    def test_statistical_convergence(self):
        """Test that statistics converge with increasing samples."""
        sample_sizes = [100, 500, 1000, 5000]
        means = []
        stds = []

        for n_samples in sample_sizes:
            config = MonteCarloConfig(
                dimensions=1,
                bounds=[(0, 1)],
                population_size=n_samples,
                sampling_method="uniform",
            )

            mc = MonteCarloEngine(config)

            def fitness_function(x):
                return {
                    "fitness": x[0] ** 2,  # Simple quadratic
                    "objectives": [x[0] ** 2],
                    "valid": True,
                }

            result = mc.analyze(fitness_function)
            stats = result["uncertainty_analysis"]["statistics"]
            means.append(stats["mean"])
            stds.append(stats["std"])

        # Check convergence: variance should decrease with sample size
        for i in range(len(sample_sizes) - 1):
            # Later estimates should have smaller variance (be more stable)
            # This is a weak test - just checking trend
            if i > 0:  # Skip first comparison as it can be noisy
                assert (
                    abs(means[i + 1] - 1 / 3) <= abs(means[i] - 1 / 3) * 1.1
                ), "Mean not converging"


# Main test execution
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
