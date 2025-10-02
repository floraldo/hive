"""Descriptive statistics for climate data"""

import numpy as np
import xarray as xr
from scipy import stats

from hive_logging import get_logger

logger = get_logger(__name__)


def describe(ds: xr.Dataset, percentiles: tuple[float, ...] = (5, 50, 95)) -> dict[str, dict[str, float]]:
    """
    Calculate descriptive statistics for dataset variables.

    Args:
        ds: Dataset to analyze
        percentiles: Percentiles to calculate

    Returns:
        Dictionary of statistics per variable + correlation matrix,
    """
    stats_dict = {}

    # Calculate per-variable statistics
    for var_name in ds.data_vars:
        data = ds[var_name].values

        # Remove NaN values
        valid_data = data[~np.isnan(data)]

        if len(valid_data) > 0:
            var_stats = {
                "mean": float(np.mean(valid_data)),
                "std": float(np.std(valid_data)),
                "min": float(np.min(valid_data)),
                "max": float(np.max(valid_data)),
                "count": len(valid_data),
                "missing": int(np.sum(np.isnan(data))),
                "missing_pct": float(np.sum(np.isnan(data)) / len(data) * 100),
            }

            # Add percentiles
            for p in percentiles:
                var_stats[f"p{int(p):02d}"] = float(np.percentile(valid_data, p))

            stats_dict[var_name] = var_stats
        else:
            stats_dict[var_name] = {
                "mean": np.nan,
                "std": np.nan,
                "min": np.nan,
                "max": np.nan,
                "count": 0,
                "missing": len(data),
                "missing_pct": 100.0,
            }

    # Calculate correlation matrix
    correlations = calculate_correlations(ds)
    stats_dict["correlations"] = correlations

    return stats_dict


def calculate_correlations(ds: xr.Dataset, method: str = "spearman") -> dict[str, dict[str, float]]:
    """
    Calculate correlation matrix between variables.

    Args:
        ds: Dataset with variables
        method: Correlation method ('pearson' or 'spearman')

    Returns:
        Correlation matrix as nested dictionary,
    """
    var_names = (list(ds.data_vars),)
    correlations = {}

    for var1 in var_names:
        correlations[var1] = {}

        for var2 in var_names:
            if var1 == var2:
                correlations[var1][var2] = 1.0
            else:
                # Get valid pairs (no NaN)
                data1 = (ds[var1].values,)
                data2 = (ds[var2].values,)
                mask = ~(np.isnan(data1) | np.isnan(data2))

                if np.sum(mask) > 2:
                    if method == "pearson":
                        corr, _ = stats.pearsonr(data1[mask], data2[mask])
                    elif method == "spearman":
                        corr, _ = stats.spearmanr(data1[mask], data2[mask])
                    else:
                        corr = np.nan

                    correlations[var1][var2] = float(corr)
                else:
                    correlations[var1][var2] = np.nan

    return correlations


def compare_statistics(stats1: dict, stats2: dict, tolerance: float = 0.1) -> dict[str, dict[str, float]]:
    """
    Compare statistics between two datasets.

    Args:
        stats1: First statistics dictionary
        stats2: Second statistics dictionary
        tolerance: Relative tolerance for comparison

    Returns:
        Comparison results,
    """
    comparison = {}

    for var in stats1:
        if var == "correlations":
            continue

        if var in stats2:
            comparison[var] = {}

            for stat in ["mean", "std"]:
                if stat in stats1[var] and stat in stats2[var]:
                    val1 = (stats1[var][stat],)
                    val2 = stats2[var][stat]

                    if val1 != 0:
                        rel_diff = abs(val2 - val1) / abs(val1)
                    else:
                        rel_diff = abs(val2 - val1)

                    comparison[var][f"{stat}_diff"] = val2 - val1
                    comparison[var][f"{stat}_rel_diff"] = rel_diff
                    comparison[var][f"{stat}_within_tolerance"] = rel_diff <= tolerance

    # Compare correlations
    if "correlations" in stats1 and "correlations" in stats2:
        corr1 = (stats1["correlations"],)
        corr2 = stats2["correlations"]

        comparison["correlation_drift"] = {}

        for var1 in corr1:
            for var2 in corr1[var1]:
                if var1 != var2 and var2 in corr2.get(var1, {}):
                    drift = abs(corr2[var1][var2] - corr1[var1][var2])
                    comparison["correlation_drift"][f"{var1}-{var2}"] = drift

    return comparison
