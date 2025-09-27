#!/usr/bin/env python3
"""Test script for minimal EcoSystemiser system."""

import sys
from pathlib import Path
import logging
import yaml
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_minimal_system():
    """Test the minimal energy system configuration."""

    print("\n" + "="*60)
    print("EcoSystemiser - Minimal System Test")
    print("="*60 + "\n")

    try:
        # Import required modules
        from src.EcoSystemiser.services.simulation_service import SimulationService, SimulationConfig
        from src.EcoSystemiser.analyser.kpi_calculator import KPICalculator

        print("✅ Modules imported successfully")

        # Load simulation configuration
        config_path = Path("config/simulations/example_simulation.yml")
        with open(config_path, 'r') as f:
            config_dict = yaml.safe_load(f)

        print(f"✅ Loaded simulation config: {config_path}")

        # Create simulation config
        sim_config = SimulationConfig(**config_dict)
        print(f"✅ Created simulation config for: {sim_config.simulation_id}")

        # Initialize simulation service
        service = SimulationService()
        print("✅ Initialized SimulationService")

        # Run simulation
        print("\n🚀 Running simulation...")
        result = service.run_simulation(sim_config)

        print(f"\n📊 Simulation Results:")
        print(f"   Status: {result.status}")

        if result.status == "error":
            print(f"   ❌ Error: {result.error}")
            return False

        if result.results_path:
            print(f"   Results saved to: {result.results_path}")

            # Load and display results summary
            with open(result.results_path, 'r') as f:
                results_data = json.load(f)

            print(f"\n   System Info:")
            print(f"   - System ID: {results_data.get('system_id')}")
            print(f"   - Timesteps: {results_data.get('timesteps')}")
            print(f"   - Components: {len(results_data.get('components', {}))}")
            print(f"   - Flows: {len(results_data.get('flows', {}))}")

        if result.kpis:
            print(f"\n   Key Performance Indicators:")
            for key, value in result.kpis.items():
                if isinstance(value, float):
                    print(f"   - {key}: {value:.2f}")
                else:
                    print(f"   - {key}: {value}")

        if result.solver_metrics:
            print(f"\n   Solver Metrics:")
            for key, value in result.solver_metrics.items():
                print(f"   - {key}: {value}")

        print("\n✅ Test completed successfully!")
        return True

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_component_repository():
    """Test the component repository functionality."""

    print("\n" + "="*60)
    print("Component Repository Test")
    print("="*60 + "\n")

    try:
        from src.EcoSystemiser.component_data.repository import ComponentRepository

        repo = ComponentRepository()

        # List available components
        energy_components = repo.list_available_components('energy')
        print(f"Available energy components: {energy_components}")

        # Load a specific component
        if 'sonnen_eco_10' in energy_components:
            component_data = repo.get_component_data('sonnen_eco_10')
            print(f"\nLoaded component: {component_data.get('manufacturer')} {component_data.get('model')}")
            print(f"  Class: {component_data.get('component_class')}")
            print(f"  Description: {component_data.get('description')}")

        print("\n✅ Component repository test passed!")
        return True

    except Exception as e:
        print(f"\n❌ Component repository test failed: {e}")
        return False

def test_system_builder():
    """Test the system builder functionality."""

    print("\n" + "="*60)
    print("System Builder Test")
    print("="*60 + "\n")

    try:
        from src.EcoSystemiser.utils.system_builder import SystemBuilder
        from src.EcoSystemiser.component_data.repository import ComponentRepository

        repo = ComponentRepository()
        config_path = Path("config/systems/schoonschip_energy_simple.yml")

        builder = SystemBuilder(config_path, repo)
        system = builder.build()

        print(f"✅ Built system: {system.system_id}")
        print(f"   Components: {list(system.components.keys())}")
        print(f"   Connections: {len(system.flows)}")

        # Validate connections
        issues = system.validate_connections()
        if issues:
            print(f"   ⚠️ Validation issues: {issues}")
        else:
            print(f"   ✅ All connections valid")

        return True

    except Exception as e:
        print(f"\n❌ System builder test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Run all tests
    all_passed = True

    # Test component repository
    if not test_component_repository():
        all_passed = False

    # Test system builder
    if not test_system_builder():
        all_passed = False

    # Test full simulation
    if not test_minimal_system():
        all_passed = False

    # Summary
    print("\n" + "="*60)
    if all_passed:
        print("✅ ALL TESTS PASSED - EcoSystemiser is ready!")
    else:
        print("❌ Some tests failed - please review the errors above")
    print("="*60 + "\n")

    sys.exit(0 if all_passed else 1)