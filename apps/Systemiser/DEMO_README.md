# 🌟 Systemiser Demo & Visualization Guide

## Quick Start

### 🚀 Run the Demo
```bash
# From the Systemiser directory
cd Systemiser
python run_demo.py
```

### 🎨 Generate Visualizations  
```bash
# After running the demo, generate charts and graphs
python visualizer.py
```

Or run both together:
```bash
cd Systemiser
python run_demo.py
# The demo will offer to run visualizations automatically at the end
```

## What You'll Get

### 📊 Simulation Results
- **Energy System**: 24-hour simulation of solar PV, battery storage, grid interaction, heat pumps
- **Water System**: Rainwater harvesting, storage tanks, water demand management
- **JSON Output**: Detailed flow data saved to `output/` directory

### 🎨 Visualizations
Three comprehensive chart sets saved to `output/visualizations/`:

1. **Energy Analysis** (`energy_analysis.png`)
   - Major energy flows over 24 hours
   - Generation vs consumption comparison  
   - Battery storage level tracking
   - Grid import/export analysis

2. **Water Analysis** (`water_analysis.png`)
   - Water flows and supply/demand balance
   - Storage tank levels
   - Flow balance verification

3. **Dashboard** (`dashboard.png`)
   - Complete system overview with 10 charts
   - Performance summary and key metrics
   - Data quality information

### 📈 Data Exports
CSV files for further analysis:
- `energy_flows.csv` - All energy flow data
- `energy_storage.csv` - Battery/thermal storage levels  
- `water_flows.csv` - All water flow data
- `water_storage.csv` - Water tank levels

## Understanding the Simulation

### 🔋 Energy System Components
- **Solar PV**: Realistic generation profile based on NASA weather data
- **Battery**: 50 kWh storage with charge/discharge optimization
- **Grid**: Import/export electricity as needed
- **Heat Pump**: Efficient heating using electricity
- **Thermal Storage**: Heat buffer tank for space heating
- **Loads**: Electrical and heating demand profiles

### 💧 Water System Components  
- **Rainwater Harvesting**: Collection from realistic rainfall data
- **Storage Tank**: Water storage with overflow management
- **Water Pond**: Natural storage with evaporation/infiltration
- **Grid Water**: Municipal supply as backup
- **Demand**: Drinking water and other consumption

### 🧮 Simulation Engine
- **Rule-Based Optimization**: Priority-based energy/water flow dispatch
- **24-Hour Analysis**: Hour-by-hour system operation
- **Balance Verification**: Conservation law checking
- **Real Data**: Based on actual building and weather profiles

## Troubleshooting

### Common Issues

**"ModuleNotFoundError: No module named 'matplotlib'"**
```bash
pip install matplotlib seaborn pandas
```

**"FileNotFoundError: Cannot find data files"**
- Make sure you're running from the workspace root that contains both `Systemiser/` and the data directories
- Check that `SankeyDiagram/data/` and `apps/WeatherMan/` exist

**"No output files found"**
- Run the simulation first: `python run_demo.py`
- Check the logs in `systemiser_demo.log` for errors

### Data Requirements
The simulation needs these files to work properly:
- `../SankeyDiagram/data/schoonschip_sc1/schoonschip_sc1_house1_result_converted.csv`
- `../apps/WeatherMan/apis/NASA/output/light/nasa_power_light.json`

## Next Steps

After running the demo:

1. **Explore Results**: Open the generated PNG files to view system analysis
2. **Modify Parameters**: Edit `utils/system_setup.py` to change component capacities
3. **Add Components**: Extend the system with new energy/water components
4. **Analyze Data**: Use the CSV exports for detailed analysis in Excel/Python
5. **Custom Visualizations**: Modify `visualizer.py` to create custom charts

## Architecture

```
Systemiser/
├── run_demo.py          # Main demo script
├── visualizer.py        # Visualization tool  
├── run.py              # Core simulation engine
├── solver/             # Rule-based optimization
├── system/             # Component definitions
├── utils/              # Helper functions
├── data/               # Configuration files
├── output/             # Results and visualizations
└── logs/               # Execution logs
```

This is an **actively developed** research tool for smart energy community analysis! 🚀 