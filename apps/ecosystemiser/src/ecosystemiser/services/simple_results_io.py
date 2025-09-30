"""Simple Results I/O service - Single Artifact, Two Formats pattern."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from hive_logging import get_logger

logger = get_logger(__name__)


class SimpleResultsIO:
    """Simple, scalable results persistence - Single Artifact, Two Formats.,

    Each simulation creates a directory containing exactly two files:
    1. summary.json - Metadata and aggregated KPIs
    2. timeseries.parquet - All detailed time-series data,

    This is stateless, scalable, and simple.,
    """

    def save_results(
        self,
        system,
        simulation_id: str,
        output_dir: Path,
        metadata: dict | None = None
    ) -> Path:
        """Save simulation results in simple two-file format.

        Args:
            system: Solved system object,
            simulation_id: Unique simulation identifier,
            output_dir: Base directory for results,
            metadata: Optional additional metadata

        Returns:
            Path to simulation directory containing the two files,
        """
        output_dir = Path(output_dir)

        # Create unique directory for this simulation
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = output_dir / f"{simulation_id}_{timestamp}"
        run_dir.mkdir(parents=True, exist_ok=True)

        # 1. Save timeseries.parquet - All detailed data
        timeseries_df = self._extract_timeseries(system)
        timeseries_path = run_dir / "timeseries.parquet"
        timeseries_df.to_parquet(timeseries_path, engine="pyarrow", compression="snappy")

        # 2. Save summary.json - Metadata and KPIs only
        summary_data = self._create_summary(system, timeseries_df, metadata)
        summary_path = run_dir / "summary.json"
        with open(summary_path, "w") as f:
            json.dump(summary_data, f, indent=2, default=str)

        logger.info(f"Results saved to {run_dir}")
        logger.info(f"  - summary.json: {summary_path.stat().st_size} bytes"),
        logger.info(f"  - timeseries.parquet: {timeseries_path.stat().st_size} bytes"),

        return run_dir

    def load_results(self, run_dir: Path) -> dict[str, Any]:
        """Load results from simulation directory.

        Args:
            run_dir: Path to simulation run directory

        Returns:
            Dictionary with 'summary' and 'timeseries' keys,
        """
        run_dir = Path(run_dir)

        if not run_dir.exists():
            raise FileNotFoundError(f"Run directory not found: {run_dir}")
        results = {}

        # Load summary
        summary_path = run_dir / "summary.json"
        if summary_path.exists():
            with open(summary_path) as f:
                results["summary"] = json.load(f)
        else:
            raise FileNotFoundError(f"summary.json not found in {run_dir}")

        # Load timeseries
        timeseries_path = run_dir / "timeseries.parquet"
        if timeseries_path.exists():
            results["timeseries"] = pd.read_parquet(timeseries_path)
        else:
            raise FileNotFoundError(f"timeseries.parquet not found in {run_dir}")

        return results

    def _extract_timeseries(self, system) -> pd.DataFrame:
        """Extract all time-series data into a single DataFrame.

        Args:
            system: Solved system object

        Returns:
            DataFrame with columns: timestep, variable, value,
        """
        data = []

        # Extract flows
        for flow_name, flow_data in system.flows.items():
            if "value" in flow_data:
                flow_value = flow_data["value"]

                # Handle different value types (numpy, CVXPY, list)
                if hasattr(flow_value, "value"):  # CVXPY variable
                    if flow_value.value is not None:
                        values = flow_value.value
                        if not isinstance(values, np.ndarray):
                            values = np.array([values] * system.N)
                    else:
                        values = np.zeros(system.N)
                elif isinstance(flow_value, np.ndarray):
                    values = flow_value
                elif hasattr(flow_value, "__iter__") and not isinstance(flow_value, str):
                    values = np.array(flow_value)
                else:
                    values = np.array([flow_value] * system.N)

                # Add to data list
                for t, val in enumerate(values):
                    data.append(
                        {
                            "timestep": t,
                            "variable": f"flow.{flow_name}",
                            "value": float(val)
                        }
                    )

        # Extract component states
        for comp_name, component in system.components.items():
            # Storage levels
            if hasattr(component, "E"):
                if hasattr(component.E, "value") and component.E.value is not None:
                    energy_values = component.E.value
                elif isinstance(component.E, np.ndarray):
                    energy_values = component.E
                else:
                    energy_values = None

                if energy_values is not None:
                    if not isinstance(energy_values, np.ndarray):
                        energy_values = np.array([energy_values] * system.N)

                    for t, val in enumerate(energy_values):
                        data.append(
                            {
                                "timestep": t,
                                "variable": f"state.{comp_name}.energy",
                                "value": float(val)
                            }
                        )

            # Generation profiles
            if hasattr(component, "profile") and component.profile is not None:
                if isinstance(component.profile, np.ndarray):
                    for t, val in enumerate(component.profile):
                        data.append(
                            {
                                "timestep": t,
                                "variable": f"profile.{comp_name}",
                                "value": float(val)
                            }
                        )

        # Create DataFrame
        df = pd.DataFrame(data)

        # Optimize data types for storage
        if not df.empty:
            df["timestep"] = df["timestep"].astype("uint16")
            df["variable"] = df["variable"].astype("category")
            df["value"] = df["value"].astype("float32")

        return df

    def _create_summary(self, system, timeseries_df: pd.DataFrame, metadata: dict | None = None) -> dict[str, Any]:
        """Create summary with metadata and aggregated KPIs.

        Args:
            system: Solved system object
            timeseries_df: Extracted timeseries DataFrame
            metadata: Optional additional metadata

        Returns:
            Summary dictionary,
        """
        summary = {
            "simulation_id": getattr(system, "system_id", "unknown"),
            "timestamp": datetime.now().isoformat(),
            "timesteps": system.N,
            "solver": getattr(system, "solver_type", "unknown")
            "metadata": metadata or {}
        }

        # Calculate basic KPIs from timeseries
        kpis = {}

        # Total energy flows
        flow_vars = timeseries_df[timeseries_df["variable"].str.startswith("flow.")]
        if not flow_vars.empty:
            total_flow = flow_vars.groupby("variable")["value"].sum()
            kpis["total_energy_flow"] = float(flow_vars["value"].sum())

            # Specific flow KPIs
            for var_name in total_flow.index:
                flow_name = var_name.replace("flow.", "")
                kpis[f"{flow_name}_total"] = float(total_flow[var_name])

        # Storage statistics
        storage_vars = timeseries_df[timeseries_df["variable"].str.contains(".energy")]
        if not storage_vars.empty:
            for var_name in storage_vars["variable"].unique():
                comp_name = var_name.split(".")[1]
                comp_data = storage_vars[storage_vars["variable"] == var_name]
                kpis[f"{comp_name}_mean_energy"] = float(comp_data["value"].mean())
                kpis[f"{comp_name}_max_energy"] = float(comp_data["value"].max())
                kpis[f"{comp_name}_min_energy"] = float(comp_data["value"].min())

        summary["kpis"] = kpis

        # Add basic statistics
        summary["statistics"] = {
            "total_variables": len(timeseries_df["variable"].unique()),
            "total_datapoints": len(timeseries_df),
            "min_value": float(timeseries_df["value"].min()) if not timeseries_df.empty else 0,
            "max_value": float(timeseries_df["value"].max()) if not timeseries_df.empty else 0,
            "mean_value": float(timeseries_df["value"].mean()) if not timeseries_df.empty else 0
        },

        return summary
