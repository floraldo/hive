import cvxpy as cp
import numpy as np


class Component:
    """Base component class for energy and water systems."""

    def __init__(self, name, **kwargs):
        # Core attributes
        self.name = name
        self.type = kwargs.get("component_type", "")
        self.medium = kwargs.get("medium", "")

        # Operating parameters
        self.F_max = kwargs.get("F_max", kwargs.get("P_max", None))
        self.E_max = kwargs.get("E_max", None)
        self.E_init = kwargs.get("E_init", None)
        self.eta = kwargs.get("eta", 1.0)
        self.cop = kwargs.get("cop", None)
        self.profile = kwargs.get("profile", None)
        self.bidirectional = kwargs.get("bidirectional", False)

        # Flow and state tracking
        self.flows = {"input": {}, "output": {}, "sink": {}, "source": {}}
        self.variables = {}
        self.N = None
        self.current_supply = None
        self.demand = None

    def initialize_variables(self, method="optimization", N=None):
        """Initialize variables including supply tracking."""
        if N is None:
            raise ValueError("Number of time steps 'N' must be provided")
        self.N = N

        # Initialize tracking arrays
        self.current_supply = np.zeros(N)
        if self.type == "consumption" and self.profile is not None:
            self.demand = self.profile * self.F_max

        # Initialize flow variables based on method
        for flow_direction in self.flows:
            for flow_name in self.flows[flow_direction]:
                self.flows[flow_direction][flow_name]["value"] = (
                    cp.Variable(N, nonneg=True, name=f"{self.name}_{flow_name}")
                    if method == "optimization"
                    else np.zeros(N)
                )

        # Initialize storage variables if applicable
        if self.type == "storage":
            self.variables["E"] = cp.Variable(N, name=f"{self.name}_E") if method == "optimization" else np.zeros(N)
            if method == "rule_based" and self.E_init is not None:
                self.variables["E"][0] = self.E_init

    def get_current_supply(self, t):
        """Get current supply at timestep t."""
        return self.current_supply[t]

    def get_remaining_demand(self, t):
        """Get remaining unmet demand at timestep t."""
        if self.type != "consumption":
            return 0
        return max(0, self.demand[t] - self.current_supply[t])

    def set_constraints(self):
        """Set up component constraints."""
        constraints = []

        # Energy balance constraints
        for t in range(self.N):
            flows = {
                "in": sum(f["value"][t] for f in self.flows["input"].values()),
                "out": sum(f["value"][t] for f in self.flows["output"].values()),
                "source": sum(f["value"][t] for f in self.flows["source"].values()),
                "sink": sum(f["value"][t] for f in self.flows["sink"].values()),
            }
            constraints.append(flows["in"] + flows["sink"] == flows["out"] + flows["source"])

        # Type-specific constraints
        if self.type == "storage":
            self._add_storage_constraints(constraints)
        elif self.type == "generation" and self.profile is not None:
            self._add_generation_constraints(constraints)
        elif self.type == "consumption" and self.profile is not None:
            self._add_consumption_constraints(constraints)

        self.constraints = constraints
        return constraints

    def _add_storage_constraints(self, constraints):
        """Add storage-specific constraints."""
        E = self.variables.get("E")
        if E is not None:
            P_charge = next(iter(self.flows["sink"].values()))["value"]
            P_discharge = next(iter(self.flows["source"].values()))["value"]

            constraints.extend(
                [E[0] == self.E_init, E >= 0, E <= self.E_max, P_charge <= self.F_max, P_discharge <= self.F_max]
            )

            for t in range(1, self.N):
                constraints.append(E[t] == E[t - 1] + self.eta * (P_charge[t - 1] - P_discharge[t - 1]))

    def _add_generation_constraints(self, constraints):
        """Add generation-specific constraints."""
        output_flow = next(iter(self.flows["output"].values()))["value"]
        constraints.append(output_flow == self.profile * self.F_max)

    def _add_consumption_constraints(self, constraints):
        """Add consumption-specific constraints."""
        input_flow = next(iter(self.flows["input"].values()))["value"]
        constraints.append(input_flow == self.profile * self.F_max)

    def __repr__(self):
        return f"{self.name} ({self.type}, {self.medium})"


# Specialized Components
class StorageComponent(Component):
    """Base class for storage components."""

    def __init__(self, name, medium, **kwargs):
        super().__init__(name, component_type="storage", medium=medium, **kwargs)
        self.bidirectional = True
        flow_prefix = "P" if medium == "electricity" else "Q" if medium == "heat" else "W"
        self.flows["sink"][f"{flow_prefix}_charge"] = {"type": medium, "value": None}
        self.flows["source"][f"{flow_prefix}_discharge"] = {"type": medium, "value": None}


class Battery(StorageComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, medium="electricity", **kwargs)


class HeatBuffer(StorageComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, medium="heat", **kwargs)


class WaterStorage(StorageComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, medium="water", **kwargs)


class ConversionComponent(Component):
    """Base class for conversion components."""

    def __init__(self, name, input_medium, output_medium, **kwargs):
        super().__init__(name, component_type="conversion", medium=output_medium, **kwargs)
        self.flows["input"]["P_in"] = {"type": input_medium, "value": None}
        self.flows["output"][f'{"Q" if output_medium == "heat" else "P"}_out'] = {"type": output_medium, "value": None}


class ElectricBoiler(ConversionComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, input_medium="electricity", output_medium="heat", **kwargs)

    def set_constraints(self):
        constraints = super().set_constraints()
        P_in = self.flows["input"]["P_in"]["value"]
        Q_out = self.flows["output"]["Q_out"]["value"]
        constraints.extend([Q_out == self.eta * P_in, P_in <= self.F_max])
        return constraints


class HeatPump(ConversionComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, input_medium="electricity", output_medium="heat", **kwargs)
        self.flows["source"]["Q_source"] = {"type": "heat", "value": None}
        self.flows["sink"]["P_loss"] = {"type": "electricity", "value": None}

    def set_constraints(self):
        constraints = super().set_constraints()
        flows = {
            "P_in": self.flows["input"]["P_in"]["value"],
            "Q_out": self.flows["output"]["Q_out"]["value"],
            "Q_source": self.flows["source"]["Q_source"]["value"],
            "P_loss": self.flows["sink"]["P_loss"]["value"],
        }
        constraints.extend(
            [
                flows["Q_out"] == self.eta * self.cop * flows["P_in"],
                flows["Q_source"] == (self.cop - 1) * flows["P_in"],
                flows["P_loss"] == flows["P_in"] * (1 - self.eta),
                flows["P_in"] <= self.F_max,
            ]
        )
        return constraints


# Simple components with standard configurations
class Grid(Component):
    def __init__(self, name, **kwargs):
        super().__init__(name, component_type="grid", **kwargs)
        self.bidirectional = True
        prefix = "P" if self.medium == "electricity" else "Q" if self.medium == "heat" else "W"
        self.flows["input"][f"{prefix}_feed"] = {"type": self.medium, "value": None}
        self.flows["output"][f"{prefix}_draw"] = {"type": self.medium, "value": None}


class WaterGrid(Grid):
    """Grid component for water supply."""

    def __init__(self, name, **kwargs):
        super().__init__(name, medium="water", **kwargs)
        # Any water-specific initialization can go here


class DemandComponent(Component):
    def __init__(self, name, medium, **kwargs):
        super().__init__(name, component_type="consumption", medium=medium, **kwargs)
        prefix = "P" if medium == "electricity" else "Q" if medium == "heat" else "W"
        self.flows["input"][f"{prefix}_in"] = {"type": medium, "value": None}


class GenerationComponent(Component):
    def __init__(self, name, medium, **kwargs):
        super().__init__(name, component_type="generation", medium=medium, **kwargs)
        prefix = "P" if medium == "electricity" else "Q" if medium == "heat" else "W"
        self.flows["output"][f"{prefix}_out"] = {"type": medium, "value": None}


# Concrete demand and generation components
class PowerDemand(DemandComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, medium="electricity", **kwargs)


class HeatDemand(DemandComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, medium="heat", **kwargs)


class WaterDemand(DemandComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, medium="water", **kwargs)


class SolarPV(GenerationComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, medium="electricity", **kwargs)


class SolarThermal(GenerationComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, medium="heat", **kwargs)


class RainwaterSource(GenerationComponent):
    def __init__(self, name, **kwargs):
        super().__init__(name, medium="water", **kwargs)


class OverflowDemand(DemandComponent):
    """Overflow component for excess water."""

    def __init__(self, name, **kwargs):
        super().__init__(name, medium="water", **kwargs)


class InfiltrationDemand(DemandComponent):
    """Infiltration component to model infiltration losses."""

    def __init__(self, name, **kwargs):
        super().__init__(name, medium="water", **kwargs)
        self.infiltration_rate = kwargs.get("infiltration_rate", 0.1)


class EvaporationDemand(DemandComponent):
    """Evaporation demand component representing evaporation losses."""

    def __init__(self, name, **kwargs):
        super().__init__(name, medium="water", **kwargs)
        self.temp_profile = kwargs.get("temp_profile", None)
        self.evap_profile = None

    def initialize_variables(self, method="optimization", N=None):
        super().initialize_variables(method, N)
        if self.temp_profile is not None:
            # Calculate evaporation profile based on temperature
            T = np.maximum(0, self.temp_profile)  # Only positive temperatures
            self.evap_profile = 0.85 * (T / 30) + 0.15 * (T / 30) ** 2  # Normalized evaporation rate
            self.evap_profile = np.maximum(0.1, self.evap_profile)  # Minimum evaporation rate


class WaterPond(StorageComponent):
    """Water pond component with infiltration losses."""

    def __init__(self, name, **kwargs):
        super().__init__(name, medium="water", **kwargs)
        self.infiltration_rate = kwargs.get("infiltration_rate", 0.1)
        self.flows["sink"]["W_infiltration"] = {"type": "water", "value": None}

    def set_constraints(self):
        """Add pond-specific constraints including infiltration."""
        constraints = super().set_constraints()
        E = self.variables.get("E")
        if E is not None:
            W_infiltration = self.flows["sink"]["W_infiltration"]["value"]
            constraints.extend([W_infiltration == self.infiltration_rate * E])
        return constraints
