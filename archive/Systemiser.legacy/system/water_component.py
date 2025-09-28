import numpy as np
import cvxpy as cp
import pandas as pd

# Assuming component.py and other related files are in the same directory
from .component import Component
from .economic_parameters import EconomicParameters  # Updated relative import
from .environmental_parameters import EnvironmentalParameters  # Updated relative import
from hive_logging import get_logger

logger = get_logger(__name__)


class WaterComponent(Component):
    def __init__(self, N, name, economic: EconomicParameters, environmental: EnvironmentalParameters):
        super().__init__(N, name, economic, environmental)  # Pass params to super
        self.type = ""
        self.flows = {"input": {}, "output": {}, "sink": {}, "source": {}}
        self.bidirectional = False
        self.constraints = []
        self.W_self = np.zeros(N)
        self.W_main = None
        # Initialize technical result attributes
        self.water_collected = 0
        self.water_stored = 0
        self.water_consumed = 0
        self.water_loss = 0
        self.water_throughput = 0

    def get_technical_results(self):
        self.water_collected = np.sum(self.get_water_collected())
        self.water_stored = np.sum(self.get_water_stored())
        self.water_consumed = np.sum(self.get_water_consumed())
        self.water_loss = np.sum(self.get_water_loss())
        self.water_throughput = np.sum(self.get_water_throughput())
        self.W_self = self.get_internal_water_changes()

        self.technical_results = {
            "Water Collected (m³)": self.water_collected,
            "Water Stored (m³)": self.water_stored,
            "Water Consumed (m³)": self.water_consumed,
            "Water Loss (m³)": self.water_loss,
            "Water Throughput (m³)": self.water_throughput,
            "Internal Water (m³)": np.sum(self.W_self),
        }

        technical_results_df = pd.DataFrame(list(self.technical_results.items()), columns=["Metric", "Value"]).round(2)
        return technical_results_df

    def get_water_collected(self):
        if self.type == "generation":
            return np.array([flow["value"] for flow in self.flows["source"].values()]) / 1e3
        return 0

    def get_water_stored(self):
        if self.type == "storage":
            W_out = np.array(self.flows["source"]["W_out"]["value"])
            W_in = np.array(self.flows["sink"]["W_in"]["value"])
            return (W_out + W_in) / 2 / 1e3
        return 0

    def get_water_consumed(self):
        return np.array([flow["value"] for flow in self.flows["input"].values()]) / 1e3

    def get_water_loss(self):
        return np.array([flow["value"] for flow in self.flows["sink"].values() if "loss" in flow["name"]]) / 1e3

    def get_water_throughput(self):
        return sum([np.sum(flow["value"]) for flow in self.flows["input"].values()]) / 1e3

    def get_internal_water_changes(self):
        water_change = 0
        for flow_type in ["source", "sink"]:
            for flow in self.flows.get(flow_type, {}).values():
                if flow["type"] == "water":
                    flow_value = (
                        np.array(flow["value"].value if isinstance(flow["value"], cp.Variable) else flow["value"]) / 1e3
                    )
                    water_change += flow_value if flow_type == "source" else -flow_value
        return water_change

    def set_constraints(self):
        for t in range(self.N):
            # Get flows that are optimization variables
            input_flows = cp.sum(
                [-flow["value"][t] for flow in self.flows["input"].values() if isinstance(flow["value"], cp.Variable)]
            )
            output_flows = cp.sum(
                [flow["value"][t] for flow in self.flows["output"].values() if isinstance(flow["value"], cp.Variable)]
            )
            source_flows = cp.sum(
                [flow["value"][t] for flow in self.flows["source"].values() if isinstance(flow["value"], cp.Variable)]
            )
            sink_flows = cp.sum(
                [-flow["value"][t] for flow in self.flows["sink"].values() if isinstance(flow["value"], cp.Variable)]
            )

            # Mass balance constraint
            self.constraints += [output_flows + input_flows == source_flows + sink_flows]
        return self.constraints

    def print_constraints(self):
        logger.info(f"\nConstraints for {self.name}")
        for constraint in self.constraints:
            logger.info(constraint)

    def print_flows(self):
        logger.info(f"\nFlows to and from {self.name}")
        for direction, outer_dict in self.flows.items():
            for flow_name, flow in outer_dict.items():
                logger.info(f"{flow_name}: {direction} ({flow['value']})")

    def get_result(self):
        result = {}
        for direction, flows in self.flows.items():
            for flow_name, flow in flows.items():
                if isinstance(flow["value"], cp.Variable):
                    result[flow_name] = flow["value"].value
        return result
