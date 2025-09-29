"""Enhanced Results I/O service for optimal hybrid persistence."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from hive_logging import get_logger

logger = get_logger(__name__)


class EnhancedResultsIO:
    """Enhanced service for hybrid simulation results persistence."""

    def __init__(self) -> None:
        """Initialize enhanced results I/O service."""
        self.supported_formats = ["json", "parquet", "csv", "pickle"]

    def save_results_structured(
        self,
        system,
        simulation_id: str,
        output_dir: Path,
        study_id: str | None = None,
        metadata: dict | None = None,
    ) -> Path:
        """Save simulation results in structured directory format.

        Creates directory structure:
        output_dir/
        ├── simulation_runs/{study_id}/{run_id}/
        │   ├── flows.parquet              # High-res time-series flows
        │   ├── components.parquet         # Component states
        │   ├── simulation_config.json     # Full simulation configuration
        │   └── kpis.json                  # Calculated KPIs and summary

        Args:
            system: Solved system object
            simulation_id: Unique simulation identifier
            output_dir: Base directory for structured storage
            study_id: Optional study identifier for grouping runs
            metadata: Additional metadata to save

        Returns:
            Path to created run directory
        """
        output_dir = Path(output_dir)
        study_id = study_id or "default_study"

        # Create structured directory
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"{simulation_id}_{timestamp}"
        run_dir = output_dir / "simulation_runs" / study_id / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Extract results from system
        results = self._extract_system_results_enhanced(system)

        # Save flows as Parquet (efficient for time-series)
        flows_data = self._prepare_flows_dataframe(results["flows"])
        flows_path = run_dir / "flows.parquet"
        flows_data.to_parquet(flows_path, engine="pyarrow", compression="snappy")

        # Save components as Parquet (efficient for time-series states)
        components_data = self._prepare_components_dataframe(results["components"], system.N)
        components_path = run_dir / "components.parquet"
        components_data.to_parquet(components_path, engine="pyarrow", compression="snappy")

        # Save simulation configuration
        config_data = {
            "system_id": system.system_id,
            "run_id": run_id,
            "study_id": study_id,
            "timesteps": system.N,
            "timestamp": datetime.now().isoformat(),
            "solver_type": getattr(system, "solver_type", "unknown"),
            "metadata": metadata or {},
            # Add system configuration if available
            "system_config": getattr(system, "config", {}),
        }

        config_path = run_dir / "simulation_config.json"
        with open(config_path, "w") as f:
            json.dump(config_data, f, indent=2, default=str)

        # Calculate and save KPIs
        try:
            from ecosystemiser.analyser.kpi_calculator import KPICalculator

            kpi_calc = KPICalculator()
            kpis = kpi_calc.calculate_from_system(system)

            kpi_data = {
                "run_id": run_id,
                "calculation_timestamp": datetime.now().isoformat(),
                "kpis": kpis,
                "summary": {
                    "total_flows": len(results["flows"]),
                    "total_components": len(results["components"]),
                    "simulation_status": "completed",
                },
            }

            kpis_path = run_dir / "kpis.json"
            with open(kpis_path, "w") as f:
                json.dump(kpi_data, f, indent=2, default=str)

        except Exception as e:
            logger.warning(f"Failed to calculate KPIs: {e}")
            # Save minimal KPI data
            kpi_data = {
                "run_id": run_id,
                "calculation_timestamp": datetime.now().isoformat(),
                "kpis": {},
                "error": str(e),
                "summary": {
                    "total_flows": len(results["flows"]),
                    "total_components": len(results["components"]),
                    "simulation_status": "completed_with_kpi_errors",
                },
            }

            kpis_path = run_dir / "kpis.json"
            with open(kpis_path, "w") as f:
                json.dump(kpi_data, f, indent=2, default=str)

        logger.info(f"Structured results saved to {run_dir}")
        logger.info(f"  - Flows: {flows_path} ({flows_data.shape[0]} records)")
        logger.info(f"  - Components: {components_path} ({components_data.shape[0]} records)")
        logger.info(f"  - Config: {config_path}")
        logger.info(f"  - KPIs: {kpis_path}")

        return run_dir

    def _extract_system_results_enhanced(self, system) -> dict[str, Any]:
        """Extract results from system with enhanced CVXPY handling."""
        results = {
            "system_id": system.system_id,
            "timesteps": system.N,
            "components": {},
            "flows": {},
            "timestamp": datetime.now().isoformat(),
        }

        # Extract component states with enhanced CVXPY handling
        for comp_name, component in system.components.items():
            comp_data = {"type": component.type, "medium": component.medium}

            # Extract storage levels
            if component.type == "storage" and hasattr(component, "E"):
                if isinstance(component.E, np.ndarray):
                    comp_data["E"] = component.E.tolist()
                elif hasattr(component.E, "value") and component.E.value is not None:
                    cvxpy_value = component.E.value
                    if isinstance(cvxpy_value, np.ndarray):
                        comp_data["E"] = cvxpy_value.tolist()
                    else:
                        comp_data["E"] = [float(cvxpy_value)] * system.N
                else:
                    comp_data["E"] = [0.0] * system.N

                comp_data["E_max"] = float(component.E_max) if hasattr(component, "E_max") else None

            # Extract generation profiles
            if component.type == "generation" and hasattr(component, "profile"):
                if isinstance(component.profile, np.ndarray):
                    comp_data["profile"] = component.profile.tolist()
                elif hasattr(component.profile, "value") and component.profile.value is not None:
                    cvxpy_value = component.profile.value
                    if isinstance(cvxpy_value, np.ndarray):
                        comp_data["profile"] = cvxpy_value.tolist()
                    else:
                        comp_data["profile"] = [float(cvxpy_value)] * system.N
                else:
                    comp_data["profile"] = [0.0] * system.N

            results["components"][comp_name] = comp_data

        # Extract flows with enhanced CVXPY handling
        for flow_name, flow_data in system.flows.items():
            flow_result = {
                "source": flow_data["source"],
                "target": flow_data["target"],
                "type": flow_data["type"],
            }

            # Enhanced flow value extraction
            if "value" in flow_data:
                flow_value = flow_data["value"]

                if isinstance(flow_value, np.ndarray):
                    flow_result["value"] = flow_value.tolist()
                elif hasattr(flow_value, "value"):  # CVXPY variable
                    if flow_value.value is not None:
                        cvxpy_value = flow_value.value
                        if isinstance(cvxpy_value, np.ndarray):
                            flow_result["value"] = cvxpy_value.tolist()
                        else:
                            flow_result["value"] = [float(cvxpy_value)] * system.N
                    else:
                        logger.warning(f"CVXPY variable {flow_name} has None value, using zeros")
                        flow_result["value"] = [0.0] * system.N
                elif hasattr(flow_value, "__iter__") and not isinstance(flow_value, str):
                    flow_result["value"] = list(flow_value)
                else:
                    flow_result["value"] = [float(flow_value)] * system.N

            results["flows"][flow_name] = flow_result

        return results

    def _prepare_flows_dataframe(self, flows: dict) -> pd.DataFrame:
        """Convert flows to efficient DataFrame format for Parquet storage."""
        data = []

        for flow_name, flow_info in flows.items():
            if "value" in flow_info and isinstance(flow_info["value"], list):
                for t, value in enumerate(flow_info["value"]):
                    data.append(
                        {
                            "timestep": t,
                            "flow_name": flow_name,
                            "source": flow_info["source"],
                            "target": flow_info["target"],
                            "type": flow_info["type"],
                            "value": value,
                        }
                    )

        df = pd.DataFrame(data)

        # Optimize data types for storage efficiency
        if not df.empty:
            df["timestep"] = df["timestep"].astype("uint16")  # Max 65535 timesteps
            df["value"] = df["value"].astype("float32")  # Sufficient precision for energy flows
            df["flow_name"] = df["flow_name"].astype("category")
            df["source"] = df["source"].astype("category")
            df["target"] = df["target"].astype("category")
            df["type"] = df["type"].astype("category")

        return df

    def _prepare_components_dataframe(self, components: dict, timesteps: int) -> pd.DataFrame:
        """Convert components to efficient DataFrame format for Parquet storage."""
        data = []

        for comp_name, comp_data in components.items():
            # Storage levels
            if "E" in comp_data and comp_data["E"]:
                for t, energy in enumerate(comp_data["E"]):
                    data.append(
                        {
                            "timestep": t,
                            "component_name": comp_name,
                            "type": comp_data["type"],
                            "medium": comp_data["medium"],
                            "variable": "energy_level",
                            "value": energy,
                            "unit": "kWh",
                        }
                    )

            # Generation profiles
            if "profile" in comp_data and comp_data["profile"]:
                for t, generation in enumerate(comp_data["profile"]):
                    data.append(
                        {
                            "timestep": t,
                            "component_name": comp_name,
                            "type": comp_data["type"],
                            "medium": comp_data["medium"],
                            "variable": "generation",
                            "value": generation,
                            "unit": "kW",
                        }
                    )

        df = pd.DataFrame(data)

        # Optimize data types for storage efficiency
        if not df.empty:
            df["timestep"] = df["timestep"].astype("uint16")
            df["value"] = df["value"].astype("float32")
            df["component_name"] = df["component_name"].astype("category")
            df["type"] = df["type"].astype("category")
            df["medium"] = df["medium"].astype("category")
            df["variable"] = df["variable"].astype("category")
            df["unit"] = df["unit"].astype("category")

        return df

    def load_structured_results(self, run_dir: Path) -> dict[str, Any]:
        """Load results from structured directory format.

        Args:
            run_dir: Path to run directory

        Returns:
            Dictionary containing all results and metadata
        """
        run_dir = Path(run_dir)

        if not run_dir.exists():
            raise FileNotFoundError(f"Run directory not found: {run_dir}")

        results = {}

        # Load configuration
        config_path = run_dir / "simulation_config.json"
        if config_path.exists():
            with open(config_path) as f:
                results["config"] = json.load(f)

        # Load KPIs
        kpis_path = run_dir / "kpis.json"
        if kpis_path.exists():
            with open(kpis_path) as f:
                results["kpis"] = json.load(f)

        # Load flows
        flows_path = run_dir / "flows.parquet"
        if flows_path.exists():
            flows_df = pd.read_parquet(flows_path)
            results["flows_df"] = flows_df
            results["flows"] = self._dataframe_to_flows(flows_df)

        # Load components
        components_path = run_dir / "components.parquet"
        if components_path.exists():
            components_df = pd.read_parquet(components_path)
            results["components_df"] = components_df
            results["components"] = self._dataframe_to_components(components_df)

        logger.info(f"Loaded structured results from {run_dir}")
        return results

    def _dataframe_to_flows(self, df: pd.DataFrame) -> dict:
        """Convert flows DataFrame back to dictionary format."""
        flows = {}

        for flow_name in df["flow_name"].unique():
            flow_df = df[df["flow_name"] == flow_name].sort_values("timestep")

            flows[flow_name] = {
                "source": flow_df["source"].iloc[0],
                "target": flow_df["target"].iloc[0],
                "type": flow_df["type"].iloc[0],
                "value": flow_df["value"].tolist(),
            }

        return flows

    def _dataframe_to_components(self, df: pd.DataFrame) -> dict:
        """Convert components DataFrame back to dictionary format."""
        components = {}

        for comp_name in df["component_name"].unique():
            comp_df = df[df["component_name"] == comp_name]

            comp_data = {
                "type": comp_df["type"].iloc[0],
                "medium": comp_df["medium"].iloc[0],
            }

            # Extract energy levels
            energy_df = comp_df[comp_df["variable"] == "energy_level"].sort_values("timestep")
            if not energy_df.empty:
                comp_data["E"] = energy_df["value"].tolist()

            # Extract generation profiles
            gen_df = comp_df[comp_df["variable"] == "generation"].sort_values("timestep")
            if not gen_df.empty:
                comp_data["profile"] = gen_df["value"].tolist()

            components[comp_name] = comp_data

        return components

    def create_run_summary(self, run_dir: Path) -> dict[str, Any]:
        """Create a summary of a simulation run for database indexing.

        Args:
            run_dir: Path to run directory

        Returns:
            Summary dictionary suitable for database storage
        """
        run_dir = Path(run_dir)
        summary = {}

        try:
            # Load basic config
            config_path = run_dir / "simulation_config.json"
            if config_path.exists():
                with open(config_path) as f:
                    config = json.load(f)
                    summary.update(
                        {
                            "run_id": config.get("run_id"),
                            "study_id": config.get("study_id"),
                            "system_id": config.get("system_id"),
                            "timesteps": config.get("timesteps"),
                            "timestamp": config.get("timestamp"),
                            "solver_type": config.get("solver_type", "unknown"),
                        }
                    )

            # Load key KPIs
            kpis_path = run_dir / "kpis.json"
            if kpis_path.exists():
                with open(kpis_path) as f:
                    kpi_data = json.load(f)
                    kpis = kpi_data.get("kpis", {})

                    # Extract key metrics for database indexing
                    summary.update(
                        {
                            "total_cost": kpis.get("total_cost"),
                            "total_co2": kpis.get("total_co2"),
                            "self_consumption_rate": kpis.get("self_consumption_rate"),
                            "self_sufficiency_rate": kpis.get("self_sufficiency_rate"),
                            "renewable_fraction": kpis.get("renewable_fraction"),
                            "total_generation_kwh": kpis.get("total_generation_kwh"),
                            "total_demand_kwh": kpis.get("total_demand_kwh"),
                            "net_grid_usage_kwh": kpis.get("net_grid_usage_kwh"),
                            "simulation_status": kpi_data.get("summary", {}).get("simulation_status", "unknown"),
                        }
                    )

            # Add file paths for reference
            summary["results_path"] = str(run_dir)
            summary["flows_path"] = str(run_dir / "flows.parquet")
            summary["components_path"] = str(run_dir / "components.parquet")

        except Exception as e:
            logger.warning(f"Error creating run summary: {e}")
            summary["error"] = str(e)

        return summary
