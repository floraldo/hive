"""Results I/O service for saving and loading simulation results."""

import json
import pickle  # golden-rule-ignore: rule-17 - Required for legacy scientific data compatibility
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from hive_logging import get_logger

logger = get_logger(__name__)


class ResultsIO:
    """Service for handling simulation results persistence."""

    def __init__(self):
        """Initialize results I/O service."""
        self.supported_formats = ["json", "parquet", "csv", "pickle"]

    def save_results(
        self,
        system,
        simulation_id: str,
        output_dir: Path,
        format: str = "json",
        metadata: Optional[Dict] = None,
    ) -> Path:
        """Save simulation results to file.

        Args:
            system: Solved system object
            simulation_id: Unique simulation identifier
            output_dir: Directory for output files
            format: Output format ('json', 'parquet', 'csv', 'pickle')
            metadata: Additional metadata to save

        Returns:
            Path to saved results file
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{simulation_id}_{timestamp}.{format}"
        output_path = output_dir / filename

        # Extract results from system
        results = self._extract_system_results(system)

        # Add metadata
        if metadata:
            results["metadata"] = metadata

        # Save based on format
        if format == "json":
            self._save_json(results, output_path)
        elif format == "parquet":
            self._save_parquet(results, output_path)
        elif format == "csv":
            self._save_csv(results, output_path)
        elif format == "pickle":
            self._save_pickle(results, output_path)
        else:
            raise ValueError(f"Unsupported format: {format}")

        logger.info(f"Results saved to {output_path}")
        return output_path

    def load_results(self, file_path: Path) -> Dict[str, Any]:
        """Load simulation results from file.

        Args:
            file_path: Path to results file

        Returns:
            Dictionary containing results
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"Results file not found: {file_path}")

        # Load based on extension
        ext = file_path.suffix.lower()

        if ext == ".json":
            return self._load_json(file_path)
        elif ext == ".parquet":
            return self._load_parquet(file_path)
        elif ext == ".csv":
            return self._load_csv(file_path)
        elif ext in [".pkl", ".pickle"]:
            return self._load_pickle(file_path)
        else:
            raise ValueError(f"Unsupported file format: {ext}")

    def _extract_system_results(self, system) -> Dict[str, Any]:
        """Extract results from system object.

        Args:
            system: Solved system object

        Returns:
            Dictionary containing all results
        """
        results = {
            "system_id": system.system_id,
            "timesteps": system.N,
            "components": {},
            "flows": {},
            "timestamp": datetime.now().isoformat(),
        }

        # Extract component states
        for comp_name, component in system.components.items():
            comp_data = {"type": component.type, "medium": component.medium}

            # Extract storage levels
            if component.type == "storage" and hasattr(component, "E"):
                if isinstance(component.E, np.ndarray):
                    comp_data["E"] = component.E.tolist()
                    comp_data["E_max"] = float(component.E_max) if hasattr(component, "E_max") else None

            # Extract generation profiles
            if component.type == "generation" and hasattr(component, "profile"):
                if isinstance(component.profile, np.ndarray):
                    comp_data["profile"] = component.profile.tolist()

            # Extract economic parameters if available
            if hasattr(component, "economic") and component.economic:
                comp_data["economic"] = {
                    "capex": component.economic.capex,
                    "opex_fix": component.economic.opex_fix,
                    "opex_var": component.economic.opex_var,
                }

            results["components"][comp_name] = comp_data

        # Extract flows
        for flow_name, flow_data in system.flows.items():
            flow_result = {
                "source": flow_data["source"],
                "target": flow_data["target"],
                "type": flow_data["type"],
            }

            # Convert flow values
            if "value" in flow_data:
                if isinstance(flow_data["value"], np.ndarray):
                    flow_result["value"] = flow_data["value"].tolist()
                elif hasattr(flow_data["value"], "value"):  # CVXPY variable
                    if flow_data["value"].value is not None:
                        flow_result["value"] = flow_data["value"].value.tolist()

            results["flows"][flow_name] = flow_result

        return results

    def _save_json(self, results: Dict, path: Path):
        """Save results as JSON."""
        with open(path, "w") as f:
            json.dump(results, f, indent=2, default=str)

    def _save_parquet(self, results: Dict, path: Path):
        """Save results as Parquet."""
        # Convert to DataFrame format
        flows_df = self._flows_to_dataframe(results["flows"])

        # Save using pandas/pyarrow
        flows_df.to_parquet(path, engine="pyarrow", compression="snappy")

        # Save metadata separately
        metadata_path = path.with_suffix(".meta.json")
        metadata = {k: v for k, v in results.items() if k != "flows"}
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2, default=str)

    def _save_csv(self, results: Dict, path: Path):
        """Save results as CSV."""
        # Convert to DataFrame format
        flows_df = self._flows_to_dataframe(results["flows"])
        flows_df.to_csv(path, index=False)

        # Save metadata separately
        metadata_path = path.with_suffix(".meta.json")
        metadata = {k: v for k, v in results.items() if k != "flows"}
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2, default=str)

    def _save_pickle(self, results: Dict, path: Path):
        """Save results as pickle."""
        with open(path, "wb") as f:
            pickle.dump(results, f)

    def _load_json(self, path: Path) -> Dict:
        """Load results from JSON."""
        with open(path, "r") as f:
            return json.load(f)

    def _load_parquet(self, path: Path) -> Dict:
        """Load results from Parquet."""
        # Load flows
        flows_df = pd.read_parquet(path)
        results = {"flows": self._dataframe_to_flows(flows_df)}

        # Load metadata if exists
        metadata_path = path.with_suffix(".meta.json")
        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
                results.update(metadata)

        return results

    def _load_csv(self, path: Path) -> Dict:
        """Load results from CSV."""
        # Load flows
        flows_df = pd.read_csv(path)
        results = {"flows": self._dataframe_to_flows(flows_df)}

        # Load metadata if exists
        metadata_path = path.with_suffix(".meta.json")
        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                metadata = json.load(f)
                results.update(metadata)

        return results

    def _load_pickle(self, path: Path) -> Dict:
        """Load results from pickle."""
        with open(path, "rb") as f:
            return pickle.load(f)

    def _flows_to_dataframe(self, flows: Dict) -> pd.DataFrame:
        """Convert flows dictionary to DataFrame format.

        Args:
            flows: Dictionary of flow data

        Returns:
            DataFrame with flow time series
        """
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

        return pd.DataFrame(data)

    def _dataframe_to_flows(self, df: pd.DataFrame) -> Dict:
        """Convert DataFrame back to flows dictionary.

        Args:
            df: DataFrame with flow data

        Returns:
            Dictionary of flows
        """
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

    def create_results_summary(self, results: Dict) -> pd.DataFrame:
        """Create a summary DataFrame from results.

        Args:
            results: Results dictionary

        Returns:
            Summary DataFrame
        """
        summary_data = []

        # Summarize flows
        if "flows" in results:
            for flow_name, flow_info in results["flows"].items():
                if "value" in flow_info and isinstance(flow_info["value"], list):
                    values = np.array(flow_info["value"])
                    summary_data.append(
                        {
                            "category": "Flow",
                            "name": flow_name,
                            "source": flow_info["source"],
                            "target": flow_info["target"],
                            "mean": np.mean(values),
                            "max": np.max(values),
                            "total": np.sum(values),
                        }
                    )

        # Summarize components
        if "components" in results:
            for comp_name, comp_data in results["components"].items():
                if "E" in comp_data:
                    levels = np.array(comp_data["E"])
                    summary_data.append(
                        {
                            "category": "Storage",
                            "name": comp_name,
                            "source": "-",
                            "target": "-",
                            "mean": np.mean(levels),
                            "max": np.max(levels),
                            "total": "-",
                        }
                    )

        return pd.DataFrame(summary_data)
