import cvxpy as cp
from .component import Component


class SolarThermal(Component):
    def __init__(self, name, P_profile, n, P_max=None, economic=None, environmental=None):
        super().__init__(n, name, economic, environmental)
        self.type = "generation"
        self.medium = "heat"
        self.P_max = P_max
        self.flows["source"]["P_out"] = {"type": "heat", "value": cp.Variable(n, name="P_out")}
        self.constraints += [self.flows["source"]["P_out"]["value"] == P_profile * P_max]
