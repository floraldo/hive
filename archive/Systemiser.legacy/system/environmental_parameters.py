from hive_logging import get_logger

logger = get_logger(__name__)
# -*- coding: utf-8 -*-

# environmental_parameters.py

# class EnvironmentalParameters:
#     def __init__(self, CO2_emissions=None, CO2_production=None, CO2_operation=None, footprint=None, LCA=None):
#         self.CO2_emissions = CO2_emissions
#         self.CO2_production = CO2_production
#         self.CO2_operation = CO2_operation
#         self.footprint = footprint
#         self.LCA = LCA

#     def calculate_total_emissions(self, total_energy_generated, total_energy_operated):
#         self.total_emissions = self.CO2_production + self.CO2_operation * (total_energy_generated + total_energy_operated)
#         return self.total_emissions

#     def calculate_total_footprint(self, total_energy_generated):
#         self.total_footprint = self.footprint * total_energy_generated
#         return self.total_footprint

#     # Assume the LCA is a fixed value per component and does not depend on the energy generated/operated

import pandas as pd

class EnvironmentalParameters:
    def __init__(self, **kwargs):
        # Initialization with various environmental parameters
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_emissions_annual(self, relevant_energy, year=0, co2_change_rate=0.0, N=8760):
        # Merged functionality of get_operational_emissions and get_emissions_annual
        adjusted_co2_operation = self.CO2_operation * ((1 + co2_change_rate) ** year)
        return adjusted_co2_operation / 1e3 * relevant_energy * (8760 / N)

    def get_emissions_embedded(self, relevant_size):
        return self.CO2_embedded * relevant_size

    def calculate_emissions_over_time(self, relevant_size, relevant_energy, lifetime, N=8760, years=30, distribute_embedded=True, co2_change_rate=0.0):
        emissions_df = pd.DataFrame(index=range(years), columns=['Yearly CO2 Emissions (kg)'])
        total_embedded_emissions = self.get_emissions_embedded(relevant_size)

        for year in range(years):
            yearly_embedded_emissions = total_embedded_emissions / lifetime if distribute_embedded and year < lifetime else total_embedded_emissions if year == 0 else 0
            yearly_operational_emissions = self.get_emissions_annual(relevant_energy, year, co2_change_rate, N)
            emissions_df.loc[year] = yearly_embedded_emissions + yearly_operational_emissions

        return emissions_df

    def get_lifetime_emissions(self, relevant_size, relevant_energy, lifetime, co2_change_rate=0.0, N=8760):
        emissions_df = self.calculate_emissions_over_time(relevant_size, relevant_energy, lifetime, years=lifetime, distribute_embedded=True, co2_change_rate=co2_change_rate, N=N)
        return emissions_df['Yearly CO2 Emissions (kg)'].sum()
    
    def get_total_material_use(self, relevant_size):
        # Assuming 'critical_materials', 'recyclable_materials', 'non-recyclable_materials' are the parameters
        material_use_total = (self.critical_materials + self.recyclable_materials + self.non_recyclable_materials) * relevant_size
        return material_use_total

    def get_total_water_use(self, relevant_quantity, N=8760):
        # Assuming 'water_use' parameter is defined in liters per unit size
        water_use_total = self.water_use * relevant_quantity * (8760 / N)
        return water_use_total

    def get_total_land_use(self, relevant_size):
        # Assuming 'land_use' parameter is defined in square meters per unit size
        land_use_total = self.land_use * relevant_size
        return land_use_total
    

    # def get_lifetime_emissions(self, component):
    #     if not all(hasattr(self, attr) for attr in ['CO2_operation', 'CO2_embedded']):
    #         raise AttributeError("Required environmental attributes are not set.")

    #     if component.type == 'storage':
    #         relevant_energy = component.energy_loss  # For a battery, use energy lost due to inefficiency.
    #     elif component.type == 'generation':
    #         relevant_energy = component.energy_generated  # For generators, use energy generated.
    #     elif component.type == 'consumption':
    #         relevant_energy = component.energy_consumed  # For generators, use energy consumed.
    #     else:
    #         relevant_energy = component.energy_throughput  # For other types of components, use energy throughput.

    #     # Assuming 'CO2_operation' is per kWh and 'CO2_embedded' is a fixed amount.
    #     total_emissions = (self.CO2_operation * relevant_energy) + self.CO2_embedded
    #     return total_emissions

    # def get_water_usage(self, energy_generated_kWh):
    #     """Calculate the total water usage based on energy generated."""
    #     if hasattr(self, 'water_use'):
    #         return self.water_use * energy_generated_kWh
    #     else:
    #         raise AttributeError("Water usage rate ('water_use') is not set.")

    # def get_materials_usage(self, component_size):
    #     """Calculate the materials usage based on the component size."""
    #     materials_usage = {}
    #     if hasattr(self, 'critical_materials'):
    #         materials_usage['critical'] = self.critical_materials * component_size
    #     if hasattr(self, 'recyclable_materials'):
    #         materials_usage['recyclable'] = self.recyclable_materials * component_size
    #     if hasattr(self, 'non_recyclable_materials'):
    #         materials_usage['non_recyclable'] = self.non_recyclable_materials * component_size
    #     return materials_usage