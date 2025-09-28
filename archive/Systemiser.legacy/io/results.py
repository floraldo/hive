import cvxpy as cp
import numpy as np
from pathlib import Path
import json
from hive_logging import get_logger

# Attempt to import Systemiser logger, otherwise use fallback
try:
    from Systemiser.utils.logger import setup_logging

    system_logger = setup_logging("ResultsIO", level=logging.INFO)
except ImportError:
    system_logger = get_logger("ResultsIO_Fallback")
    system_logger.warning("Could not import Systemiser logger, using fallback.")
    if not system_logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(levelname)s: %(message)s")
        handler.setFormatter(formatter)
        system_logger.addHandler(handler)
        system_logger.setLevel(logging.INFO)


def save_system_results(system, output_dir: Path, suffix=""):
    """Save system results (flows, storage levels) to JSON in a specified directory.

    Args:
        system: The solved System object.
        output_dir (Path): The directory where the results file will be saved.
        suffix (str): Optional suffix for the filename (e.g., "_water").
    """
    try:
        flows = []

        # Process all flows defined in the system's connections
        # This is more robust than iterating through components' internal flow dicts
        for flow_key, flow_data in system.flows.items():
            # Ensure flow has results (might not if optimization failed or rule-based didn't run)
            if "value" in flow_data and isinstance(flow_data["value"], (cp.Variable, np.ndarray)):
                flow_values = flow_data["value"].value if hasattr(flow_data["value"], "value") else flow_data["value"]

                # Handle potential None values if optimization was infeasible
                if flow_values is None:
                    system_logger.warning(f"Flow '{flow_key}' has no value. Skipping.")
                    flow_values = np.zeros(system.N)  # Use zeros as placeholder

                # Ensure flow_values is a numpy array for calculations
                if not isinstance(flow_values, np.ndarray):
                    flow_values = np.array(flow_values)

                # Determine from and to based on flow key or data
                source = flow_data.get("source", "Unknown")
                target = flow_data.get("target", "Unknown")
                flow_type = flow_data.get("type", "Unknown")

                flows.append(
                    {
                        "from": source,
                        "to": target,
                        "type": flow_type,
                        "flow_type": "connection",  # Indicate this comes from system.flows
                        "values": flow_values.tolist(),
                        "mean": float(np.mean(flow_values)),
                        "max": float(np.max(flow_values)),
                        "total": float(np.sum(flow_values)),
                        # Safely get unit and color from system flow types
                        "unit": system.flow_types.get(flow_type, {}).get("unit", "N/A"),
                        "color": system.flow_types.get(flow_type, {}).get("color", "#808080"),  # Default grey
                    }
                )
            else:
                system_logger.debug(f"Skipping flow '{flow_key}' - no 'value' or not Variable/ndarray.")

        # Process storage levels
        storage_levels = {}
        for name, component in system.components.items():
            if component.type == "storage":
                # Check if storage level variable E exists and has a value
                if hasattr(component, "E") and isinstance(component.E, (cp.Variable, np.ndarray)):
                    E_values = component.E.value if hasattr(component.E, "value") else component.E

                    if E_values is None:
                        system_logger.warning(f"Storage component '{name}' level (E) has no value. Using E_init.")
                        # Create placeholder based on E_init if needed
                        E_values = np.full(system.N, component.E_init)

                    # Ensure E_values is a numpy array
                    if not isinstance(E_values, np.ndarray):
                        E_values = np.array(E_values)

                    storage_levels[name] = {
                        "current": float(E_values[-1]),
                        "max": float(component.E_max),
                        "average": float(np.mean(E_values)),
                        "initial": float(E_values[0]),
                        "values": E_values.tolist(),
                    }
                else:
                    system_logger.warning(
                        f"Storage component '{name}' missing 'E' attribute or it's not Variable/ndarray."
                    )

        # Construct output path
        output_dir.mkdir(parents=True, exist_ok=True)  # Ensure directory exists
        output_filename = f"solved_system_flows_hourly{suffix}.json"
        output_path = output_dir / output_filename

        system_logger.info(f"Saving data to: {output_path}")
        with open(output_path, "w") as f:
            json.dump({"flows": flows, "storage_levels": storage_levels}, f, indent=2)
        return True

    except AttributeError as ae:
        system_logger.exception(f"Error saving results - likely missing attribute in component or system: {ae}")
        return False
    except KeyError as ke:
        system_logger.exception(f"Error saving results - likely missing key in flow data: {ke}")
        return False
    except Exception as e:
        system_logger.exception(f"Error saving results: {e}")
        return False
