import cvxpy as cp
import numpy as np
from .component import Component


class SolarPV(Component):
    def __init__(self, name, P_profile, n, P_max=None, economic=None, environmental=None):
        super().__init__(n, name, economic, environmental)
        self.type = "generation"
        self.medium = "electricity"
        self.P_max = P_max
        self.profile = P_profile
        self.flows["source"]["P_out"] = {
            "type": "electricity",
            "value": cp.Variable(n, name="P_out"),
            "profile": P_profile,
        }
        self.constraints += [self.flows["source"]["P_out"]["value"] == P_profile * P_max]
