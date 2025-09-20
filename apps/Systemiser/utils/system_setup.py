import cvxpy as cp
import numpy as np
import pandas as pd
from pathlib import Path
import sys, os, json
import logging

# Attempt to import Systemiser logger, otherwise use fallback
try:
    from Systemiser.utils.logger import setup_logging
    system_logger = setup_logging("SystemSetup", level=logging.INFO)
except ImportError:
    system_logger = logging.getLogger("SystemSetup_Fallback")
    system_logger.warning("Could not import Systemiser logger, using fallback.")
    if not system_logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        handler.setFormatter(formatter)
        system_logger.addHandler(handler)
        system_logger.setLevel(logging.INFO)

# Import components using relative paths within Systemiser package
try:
    from ..system.system import System
    from ..system.battery import Battery
    from ..system.grid import Grid
    from ..system.heat_buffer import HeatBuffer
    from ..system.heat_demand import HeatDemand
    from ..system.heat_pump import HeatPump
    from ..system.power_demand import PowerDemand
    from ..system.solar_pv import SolarPV
    from ..system.solar_thermal import SolarThermal
    from ..system.electric_boiler import ElectricBoiler
    from ..system.rainwater_source import RainwaterSource
    from ..system.water_storage import WaterStorage
    from ..system.water_pond import WaterPond
    from ..system.water_demand import WaterDemand
    from ..system.water_grid import WaterGrid
    from ..system.infiltration_demand import InfiltrationDemand
    from ..system.overflow_demand import OverflowDemand
    from ..system.evaporation_demand import EvaporationDemand
except ImportError as e:
    system_logger.error(f"Error importing system components: {e}")
    # Define dummy classes or raise error if components are essential
    # raise ImportError("Essential system components could not be imported.") from e

def load_profiles(N=24):
    """Load and normalize all profiles.
    
    Note: Paths are adjusted relative to the new file location.
    """
    try:
        # Determine base path relative to this file
        # Go up two levels (utils -> Systemiser -> workspace root)
        base_path = Path(__file__).parent.parent.parent 

        # Load data sources using adjusted paths
        csv_path = base_path / 'SankeyDiagram/data/schoonschip_sc1/schoonschip_sc1_house1_result_converted.csv'
        nasa_path = base_path / 'apps/WeatherMan/apis/NASA/output/light/nasa_power_light.json'

        if not csv_path.is_file():
             raise FileNotFoundError(f"CSV file not found at: {csv_path}")
        if not nasa_path.is_file():
             raise FileNotFoundError(f"NASA JSON file not found at: {nasa_path}")

        df = pd.read_csv(csv_path)
        with open(nasa_path, 'r') as f:
            nasa = json.load(f)['data']
        
        # Process all profiles
        profiles = {}
        
        # Energy profiles - normalize each
        for name, key in {
            'solar_pv': 'P_solar',
            'solar_thermal': 'P_solar_th',
            'base_load': 'P_base_el',
            'space_heating': 'P_base_th',
            'dhw': 'P_dhw'
        }.items():
            values = df[key].values
            # Ensure length matches N by repeating if needed
            if len(values) < N:
                repeats = N // len(values) + 1
                values = np.tile(values, repeats)[:N]
            else:
                values = values[:N]
            profiles[name] = {'data': values / max(abs(values).max(), 1e-6)}
        
        # Weather profiles
        temp_values = np.array([float(v) for v in nasa['temperature'].values()])
        rain_values = np.array([float(v) for v in nasa['rainfall'].values()])
        
        # Handle missing values and ensure length
        temp_values[temp_values == -999.0] = np.nan
        rain_values[rain_values == -999.0] = 0
        
        # Repeat values if needed
        if len(temp_values) < N:
            temp_values = np.tile(temp_values, N // len(temp_values) + 1)[:N]
            rain_values = np.tile(rain_values, N // len(rain_values) + 1)[:N]
        else:
            temp_values = temp_values[:N]
            rain_values = rain_values[:N]
        
        profiles['temperature'] = {'data': pd.Series(temp_values).interpolate().values}
        profiles['rainfall'] = {'data': rain_values / max(rain_values.max(), 1e-6)}
        
        # Add water demand profile
        profiles['water_demand'] = profiles['dhw']
        
        # Log analysis
        profile_summary_df = pd.DataFrame([{
            'Component': name.replace('_', ' ').title(),
            'Mean': f"{np.mean(p['data']):.2f}",
            'Total': f"{np.sum(p['data']):.2f}"
        } for name, p in profiles.items() if name != 'temperature'])
        system_logger.info(f"\nProfile Analysis:\n------------------\n{profile_summary_df.to_string()}\n------------------")
        
        return profiles
        
    except FileNotFoundError as fe:
         system_logger.error(f"Data file not found: {fe}")
         raise # Re-raise after logging
    except Exception as e:
        system_logger.exception("Error loading profiles")
        raise

def create_system(system_type, N=24):
    """Create system with components and connections."""
    try:
        # System class is imported using relative path
        system = System(f'schoonschip_{system_type}', N)
        profiles = load_profiles(N)
        
        # Create components with inline declarations
        # Component classes are imported using relative paths
        if system_type == 'energy':
            components = {
                'GRID': Grid('GRID', P_max=800, n=N),
                'BATTERIES': Battery('BATTERIES', P_max=150, E_max=300, E_init=150, eta=0.95, n=N),
                'SOLAR_PV': SolarPV('SOLAR_PV', P_profile=profiles['solar_pv']['data'], P_max=40, n=N),
                'SOLAR_THERMAL': SolarThermal('SOLAR_THERMAL', P_profile=profiles['solar_thermal']['data'], P_max=20, n=N),
                'BASE_LOAD': PowerDemand('BASE_LOAD', P_profile=profiles['base_load']['data'], P_max=15, n=N),
                'SPACE_HEATING': HeatDemand('SPACE_HEATING', P_profile=profiles['space_heating']['data'], P_max=15, n=N),
                'DHW': HeatDemand('DHW', P_profile=profiles['dhw']['data'], P_max=15, n=N),
                'HEAT_PUMPS': HeatPump('HEAT_PUMPS', cop=4.0, eta=0.95, P_max=300, n=N),
                'ELECTRIC_BOILERS': ElectricBoiler('ELECTRIC_BOILERS', eta=0.95, P_max=200, n=N),
                'TANK': HeatBuffer('TANK', P_max=50, E_max=200, E_init=100, eta=0.97, n=N)
            }
        else: # 'water'
            components = {
                'WATER_POND': WaterPond('WATER_POND', W_cha_max=20, E_max=200, E_init=100, 
                                       infiltration_rate=0.1, n=N),
                'WATER_STORAGE': WaterStorage('WATER_STORAGE', W_max=5.0, E_max=50, E_init=25, eta=0.99, n=N),
                'RAINWATER': RainwaterSource('RAINWATER', W_profile=profiles['rainfall']['data'], W_max=30, n=N),
                'WATER_GRID': WaterGrid('WATER_GRID', W_max=10, n=N),
                'DRINKING_WATER': WaterDemand('DRINKING_WATER', W_profile=profiles['water_demand']['data'], W_max=8, n=N),
                'EVAPORATION': EvaporationDemand('EVAPORATION', temp_profile=profiles['temperature']['data'], 
                                               W_max=3000*10/(1000*24), n=N), # Max rate needs clarification
                'OVERFLOW': OverflowDemand('OVERFLOW', W_max=None, n=N) # Assumes W_max=None implies unlimited
            }

        # Add components and create connections
        for component in components.values():
            system.add_component(component)
        
        # Setup connections
        if system_type == 'energy':
            system.connect('GRID', 'BATTERIES', 'electricity', True)
            for target in ['HEAT_PUMPS', 'BASE_LOAD', 'ELECTRIC_BOILERS']:
                system.connect('GRID', target, 'electricity')
                system.connect('SOLAR_PV', target, 'electricity')
                system.connect('BATTERIES', target, 'electricity')
            system.connect('SOLAR_PV', 'GRID', 'electricity')
            system.connect('SOLAR_PV', 'BATTERIES', 'electricity')
            system.connect('HEAT_PUMPS', 'TANK', 'heat')
            system.connect('HEAT_PUMPS', 'SPACE_HEATING', 'heat')
            system.connect('ELECTRIC_BOILERS', 'TANK', 'heat')
            system.connect('ELECTRIC_BOILERS', 'DHW', 'heat')
            system.connect('SOLAR_THERMAL', 'TANK', 'heat')
            system.connect('SOLAR_THERMAL', 'DHW', 'heat')
            system.connect('TANK', 'SPACE_HEATING', 'heat')
            system.connect('TANK', 'DHW', 'heat')
        else: # 'water'
            system.connect('RAINWATER', 'WATER_POND', 'water')
            system.connect('RAINWATER', 'OVERFLOW', 'water') # Potential overflow from rainwater source?
            system.connect('WATER_POND', 'EVAPORATION', 'water')
            # system.connect('WATER_POND', 'OVERFLOW', 'water') # Pond overflow connection might be needed
            system.connect('WATER_GRID', 'DRINKING_WATER', 'water')
            # system.connect('WATER_STORAGE', 'DRINKING_WATER', 'water') # Connection from storage? 
        
        return system, components
        
    except Exception as e:
        system_logger.exception(f"Error creating {system_type} system")
        raise

def create_objective(system, system_type):
    """Create optimization objective.
    
    This function currently only supports optimization mode, 
    not used by the rule-based solver in run.py.
    """
    try:
        if system_type == 'energy':
            # Find grid component based on type/name (more robust than assuming 'GRID')
            grid_comp = next((comp for comp in system.components.values() if comp.type == 'transmission' and comp.medium == 'electricity'), None)
            if not grid_comp:
                system_logger.warning("Could not find electricity grid component for objective.")
                return None # Or a default objective
                
            # Use flow names defined in the Grid component
            grid_input = cp.sum(grid_comp.flows['source']['P_draw']['value']) # Draw from grid
            grid_output = cp.sum(grid_comp.flows['sink']['P_feed']['value'])   # Feed into grid
            
            # Penalize grid input (draw) more than grid output (feed)
            return cp.Minimize(2 * grid_input + grid_output)
            
        elif system_type == 'water':
            water_grid_comp = next((comp for comp in system.components.values() if comp.type == 'transmission' and comp.medium == 'water'), None)
            overflow_comp = next((comp for comp in system.components.values() if comp.name == 'OVERFLOW'), None) # Assuming name

            grid_sum = 0
            if water_grid_comp:
                grid_sum = cp.sum(water_grid_comp.flows['source']['W_draw']['value']) # Draw from water grid
            else:
                system_logger.warning("Could not find water grid component for objective.")

            overflow_sum = 0
            if overflow_comp:
                overflow_sum = cp.sum(overflow_comp.flows['sink']['W_in']['value']) # Flow into overflow
            else:
                 system_logger.warning("Could not find overflow component for objective.")
            
            # Heavily penalize overflow, moderately penalize grid usage
            return cp.Minimize(5 * grid_sum + 20 * overflow_sum)
        else:
            system_logger.error(f"Unknown system type '{system_type}' for objective creation.")
            return None
            
    except KeyError as ke:
         system_logger.exception(f"Error creating objective due to missing flow key: {ke}")
         raise
    except Exception as e:
        system_logger.exception(f"Error creating objective for {system_type}")
        raise 