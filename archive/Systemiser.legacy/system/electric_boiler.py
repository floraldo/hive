import cvxpy as cp
import numpy as np
from .component import Component


class ElectricBoiler(Component):
    def __init__(self, name, eta=0.95, n=8760, P_max=None, economic=None, environmental=None):
        super().__init__(n, name, economic, environmental)
        self.type = "generation"
        self.P_max = P_max
        self.eta = eta
        self.medium = "heat"
        self.flows["source"]["P_heat"] = {"type": "heat", "value": cp.Variable(n, nonneg=True, name=f"{name}_P_heat")}
        self.flows["sink"]["P_elec"] = {
            "type": "electricity",
            "value": cp.Variable(n, nonneg=True, name=f"{name}_P_elec"),
        }

    def set_constraints(self):
        for t in range(self.N):
            # The heat output is eta times the electrical input
            self.constraints += [
                self.flows["source"]["P_heat"]["value"][t] == self.eta * self.flows["sink"]["P_elec"]["value"][t]
            ]

            if self.P_max is not None:
                self.constraints += [
                    self.flows["sink"]["P_elec"]["value"][t] <= self.P_max,
                ]

        super().set_constraints()
        return self.constraints
