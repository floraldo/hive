import cvxpy as cp
import numpy as np
from .component import Component


class HeatPump(Component):
    def __init__(self, name, cop, eta, n, P_max=None, economic=None, environmental=None):
        super().__init__(n, name, economic, environmental)
        self.type = "generation"
        self.P_max = P_max
        self.COP = cop
        self.eta = eta
        self.medium = "heat"
        self.flows["source"]["P_heatsource"] = {
            "type": "heat",
            "value": cp.Variable(n, nonneg=True, name=f"{name}_P_heatsource"),
        }
        self.flows["sink"]["P_loss"] = {
            "type": "electricity",
            "value": cp.Variable(n, nonneg=True, name=f"{name}_P_loss"),
        }
        self.flows["sink"]["P_pump"] = {
            "type": "electricity",
            "value": cp.Variable(n, nonneg=True, name=f"{name}_P_pump"),
        }

    def set_constraints(self):
        for t in range(self.N):
            input_flows = cp.sum(
                [
                    flow["value"][t]
                    for direction in self.flows
                    for flow_name, flow in self.flows[direction].items()
                    if direction == "input"
                ]
            )

            # Heat pump produces COP times more heat than electricity input
            self.constraints += [
                self.flows["source"]["P_heatsource"]["value"][t] == (self.COP - 1) * input_flows,
                self.flows["sink"]["P_loss"]["value"][t] == input_flows * (1 - self.eta),
                self.flows["sink"]["P_pump"]["value"][t] == input_flows * self.eta,
            ]

            if self.P_max is not None:
                self.constraints += [
                    input_flows <= self.P_max,
                ]

        super().set_constraints()
        return self.constraints
