#!/usr/bin/env python3
"""
Systemiser Energy System Simulation Demo

This script demonstrates how to run the Systemiser energy system simulation.
It sets up the environment, checks dependencies, and runs a complete simulation
of both energy and water systems.

Author: Smart Hoods Optimization Tool
Date: 2025
"""

import sys
import subprocess
import os
from pathlib import Path
import importlib
import logging


def check_and_install_packages():
    """Check if required packages are installed and install if missing."""
    required_packages = ["numpy>=1.21.0", "pandas>=1.3.0", "cvxpy>=1.3.0", "matplotlib>=3.5.0"]

    print("🔍 Checking required packages...")

    missing_packages = []

    for package in required_packages:
        package_name = package.split(">=")[0]
        try:
            importlib.import_module(package_name)
            print(f"✅ {package_name} - Already installed")
        except ImportError:
            print(f"❌ {package_name} - Missing")
            missing_packages.append(package)

    if missing_packages:
        print(f"\n📦 Installing missing packages: {', '.join(missing_packages)}")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade"] + missing_packages)
            print("✅ All packages installed successfully!")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install packages: {e}")
            print("Please install manually: pip install " + " ".join(missing_packages))
            return False
    else:
        print("✅ All required packages are already installed!")

    return True


def verify_data_files():
    """Verify that required data files exist."""
    print("\n🔍 Checking required data files...")

    # Go up one level from Systemiser to workspace root
    workspace_root = Path(__file__).parent.parent

    required_files = [
        workspace_root / "SankeyDiagram/data/schoonschip_sc1/schoonschip_sc1_house1_result_converted.csv",
        workspace_root / "apps/WeatherMan/apis/NASA/output/light/nasa_power_light.json",
    ]

    missing_files = []
    for file_path in required_files:
        if file_path.exists():
            print(f"✅ {file_path.relative_to(workspace_root)} - Found")
        else:
            print(f"❌ {file_path.relative_to(workspace_root)} - Missing")
            missing_files.append(str(file_path.relative_to(workspace_root)))

    if missing_files:
        print("\n⚠️  Missing data files. The simulation may fail.")
        print("Please ensure the following files exist:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        return False

    print("✅ All required data files found!")
    return True


def setup_logging():
    """Setup logging for the demo."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(Path(__file__).parent / "systemiser_demo.log"),
        ],
    )
    return logging.getLogger("SystemiserDemo")


def run_simulation():
    """Run the Systemiser simulation."""
    print("\n🚀 Starting Systemiser Energy System Simulation...")
    print("=" * 60)

    try:
        # Import and run the simulation using Poetry workspace imports
        import Systemiser.run as systemiser_run

        # Create output directory in the Systemiser folder
        output_dir = Path(__file__).parent / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        print(f"📁 Output directory: {output_dir.absolute()}")
        print("🔄 Running simulation (this may take a few moments)...")

        # Run the simulation
        systemiser_run.run_simulation(output_dir)

        print("\n🎉 Simulation completed successfully!")
        print(f"📊 Results saved to: {output_dir.absolute()}")

        # List output files
        if output_dir.exists():
            output_files = list(output_dir.glob("*"))
            if output_files:
                print("\n📋 Generated files:")
                for file in output_files:
                    print(f"   - {file.name}")
            else:
                print("\n⚠️  No output files found (check logs for issues)")

        return True

    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("Make sure you're running this script from the Systemiser directory.")
        return False
    except Exception as e:
        print(f"❌ Simulation error: {e}")
        print("Check the logs for more details.")
        return False


def show_demo_results():
    """Show information about the simulation results."""
    print("\n" + "=" * 60)
    print("📊 SIMULATION RESULTS OVERVIEW")
    print("=" * 60)

    print(
        """
🔋 ENERGY SYSTEM SIMULATION:
   • Simulated 24-hour energy system operation
   • Components: Solar PV, Battery, Grid, Heat Pump, etc.
   • Rule-based energy flow optimization
   • Energy balance verification performed
   
💧 WATER SYSTEM SIMULATION:
   • Simulated 24-hour water system operation  
   • Components: Rainwater, Storage, Pond, Grid, etc.
   • Water flow optimization and balance verification
   
📈 ANALYSIS PERFORMED:
   • Timestep-by-timestep energy flow calculation
   • Storage level tracking and optimization
   • Grid import/export analysis
   • Conservation law verification
   
📁 OUTPUT FILES:
   • System flow data in JSON format
   • Component state information
   • Balance verification reports
   • Detailed logging information
    """
    )


def main():
    """Main demo function."""
    print("🌟 SYSTEMISER ENERGY SYSTEM SIMULATION DEMO")
    print("=" * 60)
    print(
        """
Welcome to the Systemiser Demo!

This demonstration will:
1. Check and install required Python packages
2. Verify required data files exist  
3. Run a complete 24-hour energy and water system simulation
4. Generate detailed results and analysis

The simulation models a smart energy community with:
- Solar PV generation and battery storage
- Heat pumps and thermal storage
- Grid connections and demand profiles
- Rainwater harvesting and water management
    """
    )

    # Setup logging
    logger = setup_logging()
    logger.info("Starting Systemiser demo")

    # Check working directory
    expected_dir = Path(__file__).parent.name
    if expected_dir != "Systemiser":
        print("❌ Error: Please run this script from the Systemiser directory")
        return 1

    # Step 1: Check and install packages
    if not check_and_install_packages():
        print("❌ Failed to setup required packages. Exiting.")
        return 1

    # Step 2: Verify data files
    data_ok = verify_data_files()
    if not data_ok:
        print("\n⚠️  Continuing anyway, but simulation may fail...")
        input("Press Enter to continue or Ctrl+C to exit...")

    # Step 3: Run simulation
    if run_simulation():
        show_demo_results()
        print("\n✨ Demo completed successfully!")
        print("Check 'systemiser_demo.log' for detailed execution logs.")

        # Offer to run visualization
        try:
            choice = input("\n🎨 Would you like to generate visualizations? (y/n): ").lower().strip()
            if choice in ["y", "yes"]:
                import Systemiser.visualizer as viz

                viz.run_visualization()
        except ImportError:
            print("Visualization tool not yet available. Run 'python visualizer.py' separately.")
        except KeyboardInterrupt:
            print("\nVisualization skipped.")

        return 0
    else:
        print("\n❌ Demo failed. Check logs for details.")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
