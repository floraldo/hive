import pytest
import numpy as np
from pathlib import Path

# Import the functions to test (adjust path if needed)
from Systemiser.utils.system_setup import load_profiles, create_system
from Systemiser.system.system import System # To check return type

# Constants for tests
TEST_TIMESTEPS = 24 # Use a standard N for tests

@pytest.fixture(scope="module")
def loaded_profiles():
    """Fixture to load profiles once for all tests in this module."""
    try:
        return load_profiles(N=TEST_TIMESTEPS)
    except FileNotFoundError as e:
        pytest.fail(f"Failed to load profiles needed for tests: {e}")
    except Exception as e:
         pytest.fail(f"Exception during profile loading: {e}")

def test_load_profiles_structure(loaded_profiles):
    """Test that load_profiles returns a dictionary with expected keys."""
    profiles = loaded_profiles
    assert isinstance(profiles, dict)
    expected_keys = ['solar_pv', 'solar_thermal', 'base_load', 'space_heating', 'dhw', 'temperature', 'rainfall', 'water_demand']
    for key in expected_keys:
        assert key in profiles
        assert 'data' in profiles[key]
        assert isinstance(profiles[key]['data'], np.ndarray)
        assert len(profiles[key]['data']) == TEST_TIMESTEPS

def test_load_profiles_no_nan_except_temp(loaded_profiles):
    """Test that loaded profiles (except temperature) do not contain NaN."""
    profiles = loaded_profiles
    for key, profile_data in profiles.items():
        if key != 'temperature': # Temperature might have NaNs interpolated
             assert not np.isnan(profile_data['data']).any(), f"NaN found in profile: {key}"

def test_create_energy_system():
    """Test creating the energy system."""
    try:
        system, components = create_system('energy', N=TEST_TIMESTEPS)
        assert isinstance(system, System)
        assert system.system_id == 'schoonschip_energy'
        assert system.N == TEST_TIMESTEPS
        assert len(system.components) > 0
        assert len(system.flows) > 0 # Check if connections were made
        # Check for a specific expected component
        assert 'GRID' in system.components
        assert 'BATTERIES' in system.components
    except Exception as e:
        pytest.fail(f"create_system('energy') raised an exception: {e}")

def test_create_water_system():
    """Test creating the water system."""
    try:
        system, components = create_system('water', N=TEST_TIMESTEPS)
        assert isinstance(system, System)
        assert system.system_id == 'schoonschip_water'
        assert system.N == TEST_TIMESTEPS
        assert len(system.components) > 0
        assert len(system.flows) > 0
        # Check for specific expected components
        assert 'WATER_POND' in system.components
        assert 'RAINWATER' in system.components
    except Exception as e:
        pytest.fail(f"create_system('water') raised an exception: {e}")

# TODO: Add test for create_objective if needed (currently only used in optimization mode) 