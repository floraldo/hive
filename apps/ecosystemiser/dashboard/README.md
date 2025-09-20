# EcoSystemiser Climate Dashboard

An interactive web interface for exploring climate data through the EcoSystemiser API.

## Features

- 🌍 **Interactive Location Selection**: Enter coordinates or city names
- 📅 **Flexible Time Periods**: Select by year or custom date range
- 📊 **Multiple Data Sources**: NASA POWER, Meteostat, ERA5, PVGIS, and more
- 📈 **Real-time Visualization**: Interactive plots with Plotly
- 📥 **Data Export**: Download as CSV, JSON, or Parquet
- 📋 **Detailed Statistics**: Summary stats and data quality metrics

## Installation

1. Navigate to the dashboard directory:
```bash
cd apps/EcoSystemiser/dashboard
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

1. Start the dashboard:
```bash
streamlit run app.py
```

2. Open your browser to `http://localhost:8501`

3. Configure your query in the sidebar:
   - Select location (coordinates or city name)
   - Choose time period
   - Select data source and variables
   - Click "Get Climate Profile"

4. Explore the results:
   - View interactive time series plots
   - Check summary statistics
   - Download data in various formats
   - Inspect the full API manifest

## Dashboard Layout

### Sidebar (Query Configuration)
- **Location Input**: Coordinates or city name with presets
- **Time Period**: Year or custom date range
- **Data Configuration**: Source, mode, resolution, and variables

### Main Panel (Results)
- **Summary Statistics**: Key metrics at a glance
- **Time Series Plot**: Interactive visualization with zoom/pan
- **Tabbed Interface**:
  - Raw Data: Browse the time series data
  - Manifest: Full API response details
  - Statistics: Detailed variable statistics
  - Download: Export in multiple formats

## Advanced Features

### Variable Selection
- Quick select buttons for common variable sets (Temperature, Solar, etc.)
- Multi-select with search functionality
- Grouped by category for easy navigation

### Visualization Options
- Dual Y-axis for variables with different units
- Hover tooltips with unified x-axis
- Responsive design for various screen sizes

### Data Export
- **CSV**: For Excel/spreadsheet analysis
- **JSON**: Complete manifest with metadata
- **Parquet**: Efficient format for large datasets

## Tips

- 💡 Use Parquet format for large datasets to preserve data types
- 🔄 The dashboard caches API responses during your session
- 📊 Select up to 3 variables for optimal plot readability
- 🌡️ Temperature and solar variables automatically use separate Y-axes

## Troubleshooting

### Common Issues

1. **Import Error**: Make sure you're in the correct directory with access to the EcoSystemiser package
2. **API Timeout**: Try reducing the time period or number of variables
3. **Missing Data**: Some sources may not have all variables for all periods

### Performance Tips

- Start with shorter time periods (1 month) for testing
- Use hourly or daily resolution for long time periods
- Limit variables to those you actually need

## Development

To modify the dashboard:

1. Edit `app.py` for main interface changes
2. Add visualization functions to `utils/visualizations.py`
3. Test changes with `streamlit run app.py --server.runOnSave true`

## Future Enhancements

- [ ] Map widget for visual location selection
- [ ] Comparison view for multiple locations
- [ ] Advanced QC report visualization
- [ ] Caching of API responses
- [ ] Export to Jupyter notebook
- [ ] Mobile-responsive design improvements