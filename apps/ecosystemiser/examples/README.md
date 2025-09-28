# EcoSystemiser Examples

This directory contains demonstration scripts and example configurations for EcoSystemiser v3.0.

## 🎯 Demo Scripts

### `run_full_demo.py` - Complete Platform Showcase

A comprehensive end-to-end demonstration that showcases the full power of the EcoSystemiser platform through a real-world Berlin microgrid design workflow.

**Scenario**: Design a cost-optimal residential microgrid for Berlin with ≥80% renewable energy fraction.

**Workflow**:
1. **Problem Definition** - Define optimization objectives and constraints
2. **GA Optimization** - Find Pareto-optimal designs using NSGA-II
3. **Design Selection** - Choose balanced solution from Pareto front
4. **MC Analysis** - Assess financial risk under uncertainty
5. **Report Generation** - Create professional HTML reports

**Usage**:
```bash
# Run the full demonstration
python examples/run_full_demo.py

# Follow the interactive prompts
# Reports will be generated in the results/ directory
```

**Expected Output**:
- Interactive progress visualization
- Pareto frontier with 3 optimal solutions
- Uncertainty analysis with 95% confidence intervals
- Professional HTML reports ready for stakeholders

### `parametric_sweep_example.py` - Parameter Studies

Demonstrates how to run systematic parameter studies to understand system sensitivity.

**Usage**:
```bash
python examples/parametric_sweep_example.py
```

## 📋 Configuration Examples

### Basic Optimization Config
```yaml
# config/basic_optimization.yml
system:
  name: "Basic Microgrid"
  location:
    latitude: 52.52
    longitude: 13.405

optimization:
  algorithm: nsga2
  objectives:
    - minimize_cost
    - maximize_renewable_fraction
  variables:
    - name: solar_capacity_kw
      min: 50
      max: 500
    - name: battery_capacity_kwh
      min: 100
      max: 1000
```

### Monte Carlo Config
```yaml
# config/uncertainty_analysis.yml
system:
  name: "Risk Assessment"

uncertainty:
  method: monte_carlo
  samples: 1000
  parameters:
    - name: electricity_price
      distribution: normal
      mean: 0.25
      std: 0.05
    - name: solar_cost
      distribution: uniform
      min: 800
      max: 1200
```

## 🚀 Running Examples

### Prerequisites
```bash
# Ensure EcoSystemiser is installed
pip install -e .

# Or run from Docker
docker-compose up -d
```

### Step-by-Step Demo
```bash
# 1. Run the full demonstration
cd apps/ecosystemiser
python examples/run_full_demo.py

# 2. View generated reports
ls results/
# reports/
#   ├── report_ga_berlin_20240928_143022.html
#   └── report_mc_berlin_20240928_143055.html

# 3. Open reports in browser
open results/report_ga_berlin_20240928_143022.html
```

### Custom Studies
```bash
# Run your own optimization
ecosys discover optimize config/your_config.yml --report

# Run uncertainty analysis
ecosys discover analyze config/your_config.yml --method monte_carlo --report
```

## 📊 Expected Results

The demo generates realistic results based on validated models:

**Genetic Algorithm Results**:
- Pareto front with 3 solutions
- Trade-off between cost (€2.1-2.8M) and renewables (82-94%)
- Optimal design: 380kW solar + 550kWh battery + 2 wind turbines

**Monte Carlo Results**:
- TCO uncertainty: €1.95-2.95M (95% CI)
- Primary risk factor: Electricity price volatility (65% sensitivity)
- Risk metrics: VaR₉₅, CVaR₉₅, probability distributions

## 🔧 Customization

### Adding New Examples

1. Create new Python script in `examples/`
2. Follow the pattern:
   ```python
   from ecosystemiser.services.study_service import StudyService
   from hive_logging import get_logger

   logger = get_logger(__name__)

   def main():
       # Your example logic here
       pass

   if __name__ == "__main__":
       main()
   ```

3. Add configuration files in `config/`
4. Update this README with documentation

### Configuration Templates

See `config/` directory for template configurations:
- `basic_optimization.yml` - Simple GA setup
- `uncertainty_analysis.yml` - Monte Carlo configuration
- `multi_objective.yml` - Complex multi-objective problem
- `climate_data.yml` - Climate data integration example

## 🐛 Troubleshooting

### Common Issues

**Import Errors**:
```bash
# Ensure Python path is set
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Or install in development mode
pip install -e .
```

**Missing Dependencies**:
```bash
# Install all requirements
pip install -r requirements.txt

# For development
pip install -r requirements-dev.txt
```

**Data Access Issues**:
```bash
# Check internet connection for climate data
# Verify API keys if using premium sources
```

## 📝 Notes

- Examples use simulated data for consistent demonstrations
- Real optimizations may take longer depending on problem complexity
- Generated reports are self-contained HTML files suitable for sharing
- All examples follow production code patterns and best practices

## 🤝 Contributing Examples

We welcome community contributions of examples! Please:

1. Follow the existing code style
2. Include proper documentation
3. Add configuration templates
4. Test thoroughly before submitting
5. Update this README

For questions about examples, please [open an issue](https://github.com/your-org/hive/issues) or contact the development team.