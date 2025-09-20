import cvxpy as cp
import numpy as np
from .water_component import WaterComponent

class WaterPond(WaterComponent):
    def __init__(self, name, W_cha_max, E_max, E_init, infiltration_rate, n, economic=None, environmental=None):
        super().__init__(n, name, economic, environmental)
        self.type = "storage"
        self.medium = "water"
        self.W_cha_max = W_cha_max
        self.E_max = E_max
        self.E_init = E_init
        self.infiltration_rate = infiltration_rate
        
        self.E = cp.Variable(n, name=f'{name}_E')
        self.flows['sink']['W_cha'] = {'type': 'water', 'value': cp.Variable(n, nonneg=True, name=f'{name}_W_cha')}
        self.flows['source']['W_dis'] = {'type': 'water', 'value': cp.Variable(n, nonneg=True, name=f'{name}_W_dis')}
        self.flows['sink']['W_inf'] = {'type': 'water', 'value': cp.Variable(n, nonneg=True, name=f'{name}_W_inf')}
        
        self.constraints += [
            self.E[0] == self.E_init,
            self.E >= 0,
            self.E <= self.E_max,
            self.flows['sink']['W_cha']['value'] <= self.W_cha_max,
            self.flows['source']['W_dis']['value'] <= self.W_cha_max,
            self.flows['sink']['W_inf']['value'] == cp.multiply(self.infiltration_rate, self.E)
        ]

    def set_constraints(self):
        super().set_constraints()
        for t in range(1, self.N):
            self.constraints += [
                self.E[t] == self.E[t-1] + (
                    self.flows['sink']['W_cha']['value'][t] -
                    self.flows['source']['W_dis']['value'][t] -
                    self.flows['sink']['W_inf']['value'][t]
                )
            ]
        return self.constraints

    def debug_flows(self, timestep):
        """Debug helper to check flow constraints."""
        print(f"\n=== Water Pond Flow Analysis at t={timestep} ===")
        
        # Get actual values after solving
        input_sum = sum(flow['value'][timestep] for flow in self.flows['input'].values())
        output_sum = sum(flow['value'][timestep] for flow in self.flows['output'].values())
        charging = self.flows['sink']['W_cha']['value'][timestep]
        discharging = self.flows['source']['W_dis']['value'][timestep]
        
        print(f"Sum of input flows: {input_sum}")
        print(f"Sum of output flows: {output_sum}")
        print(f"Charging rate (W_cha): {charging}")
        print(f"Discharging rate (W_dis): {discharging}")
        print(f"Maximum charging rate: {self.W_cha_max}")
        print(f"Storage level: {self.E[timestep]}")
        print(f"Mass balance check: input_flows = {input_sum} ?= W_cha + output - W_dis = {charging + output_sum - discharging}")
        
        if charging > self.W_cha_max:
            print("WARNING: Charging rate exceeds maximum!")