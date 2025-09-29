"""
Scenario management system for EcoSystemiser results storage and retrieval.
"""
from __future__ import annotations


import json
import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List
import pandas as pd
import numpy as np

from ecosystemiser.db import get_ecosystemiser_connection
from ecosystemiser.services.results_io import ResultsIO
from hive_logging import get_logger

logger = get_logger(__name__)


class ScenarioManager:
    """Manages scenario storage, organization, and retrieval."""

    def __init__(self, base_path: Path | None = None):
        """Initialize scenario manager.

        Args:
            base_path: Base directory for scenario storage
        """
        self.base_path = base_path or Path(__file__).parent.parent.parent.parent / "data"
        self.results_io = ResultsIO()
        self._ensure_directory_structure()
        self._ensure_database_schema()

    def _ensure_directory_structure(self) -> None:
        """Create the scenario directory structure."""
        directories = [
            "scenarios/baseline"
            "scenarios/parametric"
            "scenarios/temporal"
            "scenarios/optimization"
            "scenarios/validation"
            "profiles/climate"
            "profiles/demand"
            "profiles/generation"
            "results"
            "cache/preprocessed_profiles"
            "cache/kpi_aggregations"
            "cache/visualization_data"
        ]

        for directory in directories:
            (self.base_path / directory).mkdir(parents=True, exist_ok=True)

    def _ensure_database_schema(self) -> None:
        """Ensure scenario management tables exist."""
        with get_ecosystemiser_connection() as conn:
            # Scenarios table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scenarios (
                    scenario_id TEXT PRIMARY KEY
                    scenario_type TEXT NOT NULL
                    scenario_name TEXT NOT NULL
                    config_hash TEXT NOT NULL
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    metadata JSON
                )
            """)

            # Simulation runs table (extends base schema)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS simulation_runs_enhanced (
                    run_id TEXT PRIMARY KEY
                    scenario_id TEXT NOT NULL
                    solver_type TEXT NOT NULL
                    status TEXT NOT NULL
                    started_at TIMESTAMP NOT NULL
                    completed_at TIMESTAMP
                    duration_seconds REAL
                    results_path TEXT
                    config_snapshot JSON
                    error_message TEXT
                    FOREIGN KEY (scenario_id) REFERENCES scenarios (scenario_id)
                )
            """)

            # KPI results table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS kpi_results (
                    run_id TEXT
                    kpi_name TEXT NOT NULL
                    kpi_value REAL NOT NULL
                    unit TEXT
                    category TEXT
                    PRIMARY KEY (run_id, kpi_name)
                    FOREIGN KEY (run_id) REFERENCES simulation_runs_enhanced (run_id)
                )
            """)

            # Profile files table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS profile_files (
                    run_id TEXT
                    profile_type TEXT NOT NULL
                    file_path TEXT NOT NULL
                    timesteps INTEGER
                    start_time TEXT
                    resolution_minutes INTEGER
                    PRIMARY KEY (run_id, profile_type)
                    FOREIGN KEY (run_id) REFERENCES simulation_runs_enhanced (run_id)
                )
            """)

            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_scenarios_type ON scenarios(scenario_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_scenario ON simulation_runs_enhanced(scenario_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_solver ON simulation_runs_enhanced(solver_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_kpi_name ON kpi_results(kpi_name)")

            conn.commit()

    def register_scenario(self, scenario_id: str, scenario_type: str
                         scenario_name: str, config: Dict[str, Any]
                         metadata: Dict | None = None) -> None:
        """Register a new scenario configuration.

        Args:
            scenario_id: Unique scenario identifier
            scenario_type: Type category (baseline, parametric, etc.)
            scenario_name: Human-readable name
            config: Scenario configuration dictionary
            metadata: Additional metadata
        """
        config_hash = hashlib.md5(json.dumps(config, sort_keys=True).encode()).hexdigest()

        with get_ecosystemiser_connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO scenarios
                (scenario_id, scenario_type, scenario_name, config_hash, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (scenario_id, scenario_type, scenario_name, config_hash
                  json.dumps(metadata or {})))
            conn.commit()

        logger.info(f"Registered scenario: {scenario_id}")

    def store_result(self, scenario_id: str, solver_type: str, system
                    metadata: Dict | None = None) -> str:
        """Store complete simulation result with profiles.

        Args:
            scenario_id: Scenario identifier
            solver_type: Solver used (rule_based, milp, etc.)
            system: Solved system object
            metadata: Additional run metadata

        Returns:
            Generated run_id
        """
        run_id = f"{scenario_id}_{solver_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        started_at = datetime.now().isoformat()

        try:
            # Create results directory structure
            result_dir = self.base_path / "results" / scenario_id / solver_type / run_id
            result_dir.mkdir(parents=True, exist_ok=True)

            # Store metadata and KPIs
            kpis = self._extract_kpis(system)
            metadata_file = result_dir / "metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump({
                    "run_id": run_id,
                    "scenario_id": scenario_id,
                    "solver_type": solver_type,
                    "started_at": started_at,
                    "completed_at": datetime.now().isoformat(),
                    "kpis": kpis,
                    "metadata": metadata or {}
                }, f, indent=2)

            # Store individual profiles
            profile_paths = self._store_profiles(system, result_dir)

            # Store in database
            with get_ecosystemiser_connection() as conn:
                # Insert run record
                conn.execute("""
                    INSERT INTO simulation_runs_enhanced
                    (run_id, scenario_id, solver_type, status, started_at
                     completed_at, results_path, config_snapshot)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (run_id, scenario_id, solver_type, "completed", started_at
                      datetime.now().isoformat(), str(result_dir)
                      json.dumps(metadata or {})))

                # Insert KPI records
                for kpi_name, kpi_data in kpis.items():
                    conn.execute("""
                        INSERT INTO kpi_results
                        (run_id, kpi_name, kpi_value, unit, category)
                        VALUES (?, ?, ?, ?, ?)
                    """, (run_id, kpi_name, kpi_data["value"]
                          kpi_data.get("unit"), kpi_data.get("category")))

                # Insert profile file records
                for profile_type, file_path in profile_paths.items():
                    conn.execute("""
                        INSERT INTO profile_files
                        (run_id, profile_type, file_path, timesteps)
                        VALUES (?, ?, ?, ?)
                    """, (run_id, profile_type, str(file_path), system.N))

                conn.commit()

            # Create 'latest' symlink
            latest_link = result_dir.parent / "latest"
            if latest_link.exists():
                latest_link.unlink()
            latest_link.symlink_to(run_id, target_is_directory=True)

            logger.info(f"Stored simulation result: {run_id}")
            return run_id

        except Exception as e:
            logger.error(f"Failed to store result for {run_id}: {e}")
            # Store error in database
            with get_ecosystemiser_connection() as conn:
                conn.execute("""
                    INSERT INTO simulation_runs_enhanced
                    (run_id, scenario_id, solver_type, status, started_at, error_message)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (run_id, scenario_id, solver_type, "failed", started_at, str(e)))
                conn.commit()
            raise

    def _extract_kpis(self, system) -> Dict[str, Dict[str, Any]]:
        """Extract KPIs from solved system.

        Args:
            system: Solved system object

        Returns:
            Dictionary of KPI values with metadata
        """
        kpis = {}

        # Energy balance KPIs
        solar_total = demand_total = grid_import_total = grid_export_total = 0.0

        for flow_key, flow_data in system.flows.items():
            if flow_data["value"] is None:
                continue

            flow_total = np.sum(flow_data["value"])
            if flow_total is None:
                continue

            if "SolarPV" in flow_data["source"]:
                solar_total += flow_total
            elif flow_data["target"] == "PowerDemand":
                demand_total += flow_total
            elif flow_data["source"] == "Grid" and flow_data["target"] != "Grid":
                grid_import_total += flow_total
            elif flow_data["target"] == "Grid" and flow_data["source"] != "Grid":
                grid_export_total += flow_total

        # Battery analysis
        battery_cycles = battery_avg_soc = battery_range_kwh = 0.0
        battery_comp = system.components.get("Battery")
        if battery_comp and hasattr(battery_comp, "E"):
            yearly_range = np.max(battery_comp.E) - np.min(battery_comp.E)
            battery_cycles = yearly_range / battery_comp.E_max
            battery_avg_soc = np.mean(battery_comp.E) / battery_comp.E_max
            battery_range_kwh = yearly_range

        # Calculate derived KPIs
        kpis.update({
            "solar_generation_mwh": {,
                "value": solar_total / 1000, "unit": "MWh", "category": "energy"
            }
            "total_demand_mwh": {,
                "value": demand_total / 1000, "unit": "MWh", "category": "energy"
            }
            "grid_import_mwh": {,
                "value": grid_import_total / 1000, "unit": "MWh", "category": "energy"
            }
            "grid_export_mwh": {,
                "value": grid_export_total / 1000, "unit": "MWh", "category": "energy"
            }
            "net_grid_mwh": {,
                "value": (grid_import_total - grid_export_total) / 1000,
                "unit": "MWh", "category": "energy"
            }
            "self_consumption_ratio": {,
                "value": min(1.0, demand_total / solar_total) if solar_total > 0 else 0,
                "unit": "ratio", "category": "performance"
            }
            "self_sufficiency_ratio": {,
                "value": min(1.0, (solar_total - grid_export_total) / demand_total) if demand_total > 0 else 0,
                "unit": "ratio", "category": "performance"
            }
            "battery_cycles": {,
                "value": battery_cycles, "unit": "cycles", "category": "storage"
            }
            "battery_avg_soc": {,
                "value": battery_avg_soc, "unit": "ratio", "category": "storage"
            }
            "battery_range_kwh": {,
                "value": battery_range_kwh, "unit": "kWh", "category": "storage"
            }
        })

        return kpis

    def _store_profiles(self, system, result_dir: Path) -> Dict[str, Path]:
        """Store individual component and flow profiles.

        Args:
            system: Solved system object
            result_dir: Directory for storing profile files

        Returns:
            Dictionary mapping profile types to file paths
        """
        profile_paths = {}

        # Store flows as Parquet
        flows_data = []
        for flow_key, flow_data in system.flows.items():
            if flow_data["value"] is not None:
                values = np.array(flow_data["value"])
                for t, value in enumerate(values):
                    flows_data.append({
                        "timestep": t,
                        "flow_name": flow_key,
                        "source": flow_data["source"],
                        "target": flow_data["target"],
                        "type": flow_data["type"],
                        "value": value
                    })

        if flows_data:
            flows_df = pd.DataFrame(flows_data)
            flows_path = result_dir / "flows.parquet"
            flows_df.to_parquet(flows_path, engine="pyarrow", compression="snappy")
            profile_paths["flows"] = flows_path

        # Store component states as Parquet
        components_data = []
        for comp_name, component in system.components.items():
            # Storage levels
            if component.type == "storage" and hasattr(component, "E"):
                if isinstance(component.E, np.ndarray):
                    for t, energy in enumerate(component.E):
                        components_data.append({
                            "timestep": t,
                            "component": comp_name,
                            "type": component.type,
                            "medium": component.medium,
                            "variable": "E",
                            "value": energy,
                            "unit": "kWh"
                        })

            # Generation profiles
            if component.type == "generation" and hasattr(component, "profile"):
                if isinstance(component.profile, np.ndarray):
                    for t, power in enumerate(component.profile):
                        components_data.append({
                            "timestep": t,
                            "component": comp_name,
                            "type": component.type,
                            "medium": component.medium,
                            "variable": "profile",
                            "value": power,
                            "unit": "kW"
                        })

        if components_data:
            components_df = pd.DataFrame(components_data)
            components_path = result_dir / "components.parquet"
            components_df.to_parquet(components_path, engine="pyarrow", compression="snappy")
            profile_paths["components"] = components_path

        return profile_paths

    def load_latest_result(self, scenario_id: str, solver_type: str) -> Dict | None:
        """Load the most recent result for a scenario/solver combination.

        Args:
            scenario_id: Scenario identifier
            solver_type: Solver type

        Returns:
            Result dictionary or None if not found
        """
        with get_ecosystemiser_connection() as conn:
            cursor = conn.execute("""
                SELECT run_id, results_path FROM simulation_runs_enhanced
                WHERE scenario_id = ? AND solver_type = ? AND status = 'completed'
                ORDER BY completed_at DESC LIMIT 1
            """, (scenario_id, solver_type))

            row = cursor.fetchone()
            if not row:
                return None

            run_id, results_path = row

            # Load metadata
            metadata_file = Path(results_path) / "metadata.json"
            if metadata_file.exists():
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)

                # Add profile loading methods
                metadata["_load_flows"] = lambda: self._load_profile(results_path, "flows")
                metadata["_load_components"] = lambda: self._load_profile(results_path, "components")

                return metadata

        return None

    def _load_profile(self, results_path: str, profile_type: str) -> pd.DataFrame | None:
        """Load a specific profile type from results.

        Args:
            results_path: Path to results directory
            profile_type: Type of profile to load

        Returns:
            DataFrame with profile data or None
        """
        profile_file = Path(results_path) / f"{profile_type}.parquet"
        if profile_file.exists():
            return pd.read_parquet(profile_file)
        return None

    def compare_scenarios(self, scenario_ids: List[str]
                         solver_type: str | None = None) -> pd.DataFrame:
        """Compare KPIs across multiple scenarios.

        Args:
            scenario_ids: List of scenario identifiers
            solver_type: Optional solver filter

        Returns:
            DataFrame with comparison results
        """
        with get_ecosystemiser_connection() as conn:
            placeholders = ",".join(["?"] * len(scenario_ids))
            query = f"""
                SELECT sr.scenario_id, sr.solver_type, kr.kpi_name, kr.kpi_value, kr.unit
                FROM simulation_runs_enhanced sr
                JOIN kpi_results kr ON sr.run_id = kr.run_id
                WHERE sr.scenario_id IN ({placeholders}) AND sr.status = 'completed'
            """

            params = scenario_ids
            if solver_type:
                query += " AND sr.solver_type = ?"
                params.append(solver_type)

            return pd.read_sql_query(query, conn, params=params)
