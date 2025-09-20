import cvxpy as cp
import numpy as np
import pandas as pd

# Use relative imports for models within the same package
from .economic_parameters import EconomicParameters 
from .environmental_parameters import EnvironmentalParameters

class Component:
    def __init__(self, N, name, economic: EconomicParameters, environmental: EnvironmentalParameters):
        self.type = ""
        self.N = N
        self.name = name
        self.flows = {'input': {}, 'output': {}, 'sink': {}, 'source': {}}
        self.bidirectional = False
        self.constraints = []
        # self.CO2 = None
        self.P_self = np.zeros(N)
        self.H_self = np.zeros(N)
        self.P_main = None
        self.economic = economic
        self.environmental = environmental
        # Initialize technical result attributes
        self.energy_generated = 0
        self.energy_stored = 0
        self.energy_consumed = 0
        self.energy_loss = 0
        self.energy_throughput = 0
        
        
    def get_technical_results(self):
        self.energy_generated       = np.sum(self.get_energy_generated())
        self.energy_stored          = np.sum(self.get_energy_stored())
        self.energy_consumed        = np.sum(self.get_energy_consumed())
        self.energy_loss            = np.sum(self.get_energy_loss())
        self.energy_throughput      = np.sum(self.get_energy_throughput())
        self.P_self                 = self.get_internal_energy_changes('electricity')
        self.H_self                 = self.get_internal_energy_changes('heat')
        
        self.technical_results = {
            'Energy Generated (kWh)': self.energy_generated,
            'Energy Stored (kWh)': self.energy_stored,
            'Energy Consumed (kWh)': self.energy_consumed,
            'Energy Loss (kWh)': self.energy_loss,
            'Energy Throughput (kWh)': self.energy_throughput,
            'Internal Electricity (kWh)': np.sum(self.P_self),
            'Internal Heat (kWh)': np.sum(self.H_self),
            # ... add any other relevant technical metrics here ...
        }
        
        technical_results_df = pd.DataFrame(list(self.technical_results.items()), columns=['Metric', 'Value']).round(2)
        return technical_results_df
    
    def get_economic_results(self):
        self.economic.capex             = self.economic.get_capex(self.P_max, max(self.E) if hasattr(self, 'E') else 0)
        self.economic.opex_per_year     = self.economic.get_opex(self.P_max, self.energy_throughput, self.N, years=1)
        self.economic.opex_lifetime     = self.economic.get_opex(self.P_max, self.energy_throughput, self.N, years=self.economic.lifetime)
        self.economic.revenue_per_year  = self.economic.get_revenue(self.energy_generated, self.N, years=1)
        self.economic.revenue_lifetime  = self.economic.get_revenue(self.energy_generated, self.N, years=self.economic.lifetime)
        self.economic.cash_flow         = self.economic.get_cash_flow()
        self.economic.lifecycle_cost    = self.economic.get_lifecycle_cost()
        self.economic.roi               = self.economic.get_roi()
        self.economic.pbp               = self.economic.get_pbp()
        self.economic.lcoe              = self.economic.get_levelised_cost(self.energy_generated, self.N)
        self.economic.lcos              = self.economic.get_levelised_cost(self.energy_stored, self.N)
        
        self.economical_results = {
            'CAPEX (€)': self.economic.capex,
            'OPEX per Year (€)': self.economic.opex_per_year,
            'OPEX over Lifetime (€)': self.economic.opex_lifetime,
            'Revenue per Year (€)': self.economic.revenue_per_year,
            'Revenue over Lifetime (€)': self.economic.revenue_lifetime,
            'Cash Flow (€)': self.economic.cash_flow,
            'Lifecycle Cost (€)': self.economic.lifecycle_cost,
            'Annual ROI (%)': self.economic.roi,
            'Payback Period (years)': self.economic.pbp,
            'Levelized Cost of Electricity (LCOE) (€/kWh)': self.economic.lcoe,
            'Levelized Cost of Storage (LCOS) (€/kWh)': self.economic.lcos,
            # ... add any other relevant economic metrics here ...
        }
        economical_results_df = pd.DataFrame(list(self.economical_results.items()), columns=['Metric', 'Value']).round(2)
        return economical_results_df
    
    
    def get_environmental_results(self):
        if not hasattr(self, 'environmental'):
            raise AttributeError("Environmental parameters are not set for this component.")
        
        relevant_size = np.max(np.abs(self.P_self))
        total_energy = np.sum(self.P_self)
        lifetime = int(self.economic.lifetime)
    
        # Calculate and set environmental attributes
        self.environmental.co2_embedded = self.environmental.get_emissions_embedded(relevant_size)
        self.environmental.co2_annual = self.environmental.get_emissions_annual(total_energy, N=self.N)
        self.environmental.co2_emissions_lifetime = self.environmental.calculate_emissions_over_time(relevant_size, total_energy, lifetime, years=lifetime, distribute_embedded=True, N=self.N)['Yearly CO2 Emissions (kg)'].sum()
        self.environmental.co2_emissions_30years = self.environmental.calculate_emissions_over_time(relevant_size, total_energy, lifetime, years=30, distribute_embedded=True, N=self.N)['Yearly CO2 Emissions (kg)'].sum()
        self.environmental.material_usage = self.environmental.get_total_material_use(relevant_size)
        self.environmental.water_usage = self.environmental.get_total_water_use(total_energy, N=self.N)
        self.environmental.land_usage = self.environmental.get_total_land_use(relevant_size)
    
        # Construct the environmental results DataFrame
        self.environmental_results = {
            'Total CO2 Emissions over Lifetime (kgCO2)': self.environmental.co2_emissions_lifetime,
            'Total CO2 Emissions over 30 Years (kgCO2)': self.environmental.co2_emissions_30years,
            'CO2 Embedded (kgCO2)': self.environmental.co2_embedded,
            'Annual CO2 Emissions (kgCO2/year)': self.environmental.co2_annual,
            'Total Material Usage (units)': self.environmental.material_usage,
            'Total Water Usage (L)': self.environmental.water_usage,
            'Total Land Usage (m²)': self.environmental.land_usage
            # ... additional metrics ...
        }
    
        environmental_results_df = pd.DataFrame(list(self.environmental_results.items()), columns=['Metric', 'Value']).round(2)
        return environmental_results_df

    # def calculate_CO2_emissions(self):
    #     if self.CO2 is not None:
    #         total_CO2 = 0
    #         CO2_per_timestep = np.zeros(self.N)
    #         for direction, flows in self.flows.items():
    #             for flow_name, flow in flows.items():
    #                 if flow['type'] == 'electricity' and direction == 'input':
    #                     if isinstance(flow['value'], cp.Variable):
    #                         CO2_per_timestep += flow['value'].value * self.CO2
    #                     else:
    #                         CO2_per_timestep += flow['value'] * self.CO2
    #         total_CO2 = cp.sum(CO2_per_timestep)
    #         return total_CO2, CO2_per_timestep
    #     else:
    #         return 0, np.zeros(self.N)

    def set_constraints(self):
        for t in range(self.N):
            input_flows = cp.sum([-flow['value'][t] for flow_name, flow in self.flows['input'].items() if
                                  isinstance(flow['value'], cp.Variable)])
            output_flows = cp.sum([flow['value'][t] for flow_name, flow in self.flows['output'].items() if
                                   isinstance(flow['value'], cp.Variable)])
            source_flows = cp.sum([flow['value'][t] for flow_name, flow in self.flows['source'].items() if
                                   isinstance(flow['value'], cp.Variable)])
            sink_flows = cp.sum([-flow['value'][t] for flow_name, flow in self.flows['sink'].items() if
                                 isinstance(flow['value'], cp.Variable)])
            # ENERGY BALANCE
            self.constraints += [
                output_flows + input_flows == source_flows + sink_flows
            ]
        return self.constraints

    def print_constraints(self):
        print(f"\nConstraints for {self.name}")
        for constraint in self.constraints:
            print(constraint)

    def print_flows(self):
        print(f"\nFlows to and from {self.name}")
        for direction, outer_dict in self.flows.items():
            for flow_name, flow in outer_dict.items():
                print(f"{flow_name}: {direction} ({flow['value']})")

    def get_result(self):
        result = {}
        for direction, flows in self.flows.items():
            for flow_name, flow in flows.items():
                if isinstance(flow['value'], cp.Variable):
                    result[flow_name] = flow['value'].value
        return result

    def get_energy_generated(self):
        if self.type == "generation" or self.type == "transmission":
            return np.array([flow['value'] for flow in self.flows['source'].values()]) / 1e3
        else:
            return 0

    def get_energy_stored(self):
        if self.type == "storage":
            P_dis = np.array(self.flows['source']['P_dis']['value'])
            P_cha = np.array(self.flows['sink']['P_cha']['value'])
            return (P_dis + P_cha) / 2 / 1e3
        else:
            return 0

    def get_energy_consumed(self):
        return np.array([flow['value'] for flow in self.flows['input'].values()]) / 1e3

    def get_energy_loss(self):
        return np.array([flow['value'] for flow in self.flows['sink'].values() if flow['type'] == 'loss']) / 1e3

    def get_energy_throughput(self):
        # Assuming energy throughput is the sum of all input energy over time
        energy_throughput = sum([np.sum(flow['value']) for flow_name, flow in self.flows['input'].items()]) / 1e3
        return energy_throughput
    
    def get_internal_energy_changes(self, energy_type):
        if energy_type not in ['electricity', 'heat']:
            raise ValueError("Invalid energy type. Must be 'electricity' or 'heat'.")

        energy_change = 0

        # Sum up source and sink values based on the energy type
        for flow_type in ['source', 'sink']:
            for flow in self.flows.get(flow_type, {}).values():
                if flow['type'] == energy_type:
                    flow_value = np.array(flow['value'].value if isinstance(flow['value'], cp.Variable) else flow['value']) /1e3
                    energy_change += flow_value if flow_type == 'source' else -flow_value

        return energy_change
    
    def print_results(self):
        # Helper function to format the floats with rounding
        def format_currency(value):
            return f"€{value:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    
        def format_energy(value):
            return f"{value:,.1f} kWh".replace(',', 'X').replace('.', ',').replace('X', '.')
    
        def format_percentage(value):
            return f"{value * 100:.0f}%"
    
        def format_years(value):
            return f"{value:.1f} years"
        
        def format_emissions(value):
            return f"{value:.1f} kg CO2"
    
        print(f"{self.name.upper()}")
        print("  Technical Results:")
        print(f"    Energy Generated: {format_energy(self.energy_generated)}")
        print(f"    Energy Stored:    {format_energy(self.energy_stored)}")
        print(f"    Energy Consumed:  {format_energy(self.energy_consumed)}")
        print(f"    Energy Loss:      {format_energy(self.energy_loss)}")
        print(f"    Energy Throughput:{format_energy(self.energy_throughput)}")
        print()
    
        print("  Economic Results:")
        print(f"    CAPEX:                {format_currency(self.economic.capex)}")
        print(f"    OPEX per Year:        {format_currency(self.economic.opex_per_year)}")
        print(f"    OPEX over Lifetime:   {format_currency(self.economic.opex_lifetime)}")
        print(f"    Revenue per Year:     {format_currency(self.economic.revenue_per_year)}")
        print(f"    Revenue over Lifetime:{format_currency(self.economic.revenue_lifetime)}")
        print(f"    Cash Flow:            {format_currency(self.economic.cash_flow)}")
        print(f"    Lifecycle Cost:       {format_currency(self.economic.lifecycle_cost)}")
        print(f"    ROI:                  {format_percentage(self.economic.roi)}")
        print(f"    PBP:                  {format_years(self.economic.pbp)}")
        print(f"    LCOE:                 {format_currency(self.economic.lcoe)}/kWh")
        print(f"    LCOS:                 {format_currency(self.economic.lcos)}/kWh")
        print()

        print("  Environmental Results:")
        print(f"    Emissions Lifetime:   {format_emissions(self.environmental.co2_emissions_lifetime)}")