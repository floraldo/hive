import pytest
import json
from pathlib import Path
import numpy as np

# Import the function to test
from Systemiser.io.results import save_system_results
# Import System and a component class for creating a dummy system
from Systemiser.system.system import System
from Systemiser.system.battery import Battery # Example component

@pytest.fixture
def dummy_system(tmp_path): # Use pytest's tmp_path fixture for temporary directory
    """Creates a simple dummy System object for testing saving."""
    N = 5 # Short time horizon for testing
    system = System("dummy_test_system", N)
    
    # Add a simple storage component with some data
    battery = Battery('BATT1', P_max=10, E_max=20, E_init=5, eta=0.9, n=N)
    # Simulate some results (e.g., storage level over time)
    battery.E = np.array([5.0, 7.0, 6.0, 8.0, 7.5])
    system.add_component(battery)
    
    # Add a simple flow
    # Note: In a real run, flows are added via system.connect and populated by solver
    system.flows["SOURCE_to_BATT1"] = {
        'source': 'SOURCE',
        'target': 'BATT1',
        'type': 'electricity',
        'value': np.array([2.0, 0.0, 2.0, 0.0, 1.0]) * battery.eta # Simulate charging
    }
    system.flows["BATT1_to_SINK"] = {
        'source': 'BATT1',
        'target': 'SINK',
        'type': 'electricity',
        'value': np.array([0.0, 1.0, 0.0, 1.5, 0.0]) / battery.eta # Simulate discharging
    }
    system.flow_types['electricity'] = {'unit': 'kW', 'color': '#FFFF00'}
    
    # Define the output directory within the temp path
    output_dir = tmp_path / "test_output"
    output_dir.mkdir()
    
    return system, output_dir

def test_save_system_results_creates_file(dummy_system):
    """Test that save_system_results creates an output JSON file."""
    system, output_dir = dummy_system
    output_filename = "solved_system_flows_hourly.json"
    output_file = output_dir / output_filename
    
    assert not output_file.exists() # Ensure file doesn't exist initially
    
    success = save_system_results(system, output_dir)
    
    assert success is True
    assert output_file.exists()
    assert output_file.is_file()

def test_save_system_results_creates_file_with_suffix(dummy_system):
    """Test save_system_results with a filename suffix."""
    system, output_dir = dummy_system
    suffix = "_test_suffix"
    output_filename = f"solved_system_flows_hourly{suffix}.json"
    output_file = output_dir / output_filename
    
    assert not output_file.exists()
    success = save_system_results(system, output_dir, suffix=suffix)
    assert success is True
    assert output_file.exists()

def test_save_system_results_file_content(dummy_system):
    """Test the structure and basic content of the saved JSON file."""
    system, output_dir = dummy_system
    output_filename = "solved_system_flows_hourly.json"
    output_file = output_dir / output_filename
    
    save_system_results(system, output_dir)
    
    assert output_file.exists()
    
    with open(output_file, 'r') as f:
        data = json.load(f)
        
    assert isinstance(data, dict)
    assert 'flows' in data
    assert 'storage_levels' in data
    
    assert isinstance(data['flows'], list)
    assert len(data['flows']) == 2 # Based on dummy_system setup
    
    # Check structure of the first flow
    flow1 = data['flows'][0]
    assert 'from' in flow1
    assert 'to' in flow1
    assert 'type' in flow1
    assert 'values' in flow1
    assert 'mean' in flow1
    assert 'max' in flow1
    assert 'total' in flow1
    assert 'unit' in flow1
    assert 'color' in flow1
    assert len(flow1['values']) == system.N
    
    assert isinstance(data['storage_levels'], dict)
    assert 'BATT1' in data['storage_levels']
    
    # Check structure of storage level data
    storage1 = data['storage_levels']['BATT1']
    assert 'current' in storage1
    assert 'max' in storage1
    assert 'average' in storage1
    assert 'initial' in storage1
    assert 'values' in storage1
    assert len(storage1['values']) == system.N

# Potential future tests:
# - Test handling of missing flow data (None values)
# - Test handling of missing storage data (None values)
# - Test handling of systems with no storage components
# - Test handling of systems with no flows 