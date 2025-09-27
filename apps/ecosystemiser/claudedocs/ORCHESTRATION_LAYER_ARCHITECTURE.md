# Phase 3: The Orchestration Layer Architecture

## Executive Summary

**ACHIEVED**: Complete Strategy Pattern implementation across all 12 EcoSystemiser components (48 strategy classes)
**NOW BUILDING**: The Orchestration Layer - transforming individual components into a complete simulation platform

The Orchestration Layer represents the final transformation from "engine parts" to a "complete car" - providing high-level services that make the EcoSystemiser platform production-ready for complex energy system analysis.

## Architecture Overview

### Three-Layer System Architecture

```
┌─────────────────────────────────────────────────────┐
│                 🖥️ UI Layer                         │
│           (Web UI, CLI, Jupyter)                   │
└─────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────┐
│              🎯 ORCHESTRATION LAYER                 │
│                                                     │
│  ┌─────────────────┐  ┌─────────────────────────┐   │
│  │ SimulationService│  │    StudyService         │   │
│  │ (Single runs)   │  │ (Multi-simulation)      │   │
│  └─────────────────┘  └─────────────────────────┘   │
│                                                     │
│  ┌─────────────────────────────────────────────┐   │
│  │      RollingHorizonMILPSolver              │   │
│  │         (Advanced workflows)               │   │
│  └─────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
                           │
┌─────────────────────────────────────────────────────┐
│                🔧 CORE MODEL                        │
│                                                     │
│  Strategy Pattern Components (12 components)       │
│  ├─ Energy: Battery, Grid, SolarPV, HeatPump...    │
│  └─ Water: WaterGrid, WaterDemand, WaterStorage... │
│                                                     │
│  Mixed-Fidelity Simulation Engine                  │
│  ├─ SIMPLE: Fast approximate solutions             │
│  ├─ STANDARD: Balanced accuracy/speed              │
│  ├─ DETAILED: High-fidelity physics                │
│  └─ RESEARCH: Maximum complexity modeling          │
└─────────────────────────────────────────────────────┘
```

## The Orchestration Layer Components

### 1. SimulationService: Single Simulation Orchestrator

**Purpose**: Provides a clean, single entry point for running individual simulations

**Responsibilities**:
- **Configuration Management**: Loads and validates simulation parameters
- **System Building**: Constructs component systems from configurations
- **Profile Management**: Handles climate and demand data loading
- **Solver Coordination**: Manages rule-based and MILP solvers
- **Results Management**: Saves and processes simulation outputs
- **Staged Simulations**: Supports multi-domain decomposition workflows

**Key Features**:
```python
# Single simulation execution
service = SimulationService()
config = SimulationConfig(
    simulation_id="residential_energy_system",
    system_config_path="config/systems/residential.yml",
    solver_type="milp",
    climate_input={"location": "Amsterdam", "year": 2023},
    output_config={"directory": "results", "format": "json"}
)
result = service.run_simulation(config)
```

**Staged Simulation Example** (Multi-Domain):
```python
# First solve thermal domain, then electrical domain
config = SimulationConfig(
    simulation_id="multi_domain_optimization",
    stages=[
        StageConfig(
            stage_name="thermal",
            system_config_path="thermal_system.yml",
            solver_type="milp",
            outputs_to_pass=[
                {"component": "heat_pump", "attribute": "P_elec", "as_profile_name": "hp_demand"}
            ]
        ),
        StageConfig(
            stage_name="electrical",
            system_config_path="electrical_system.yml",
            solver_type="milp",
            inputs_from_stage=[
                {"from_stage": "thermal", "profile_name": "hp_demand", "assign_to_component": "power_demand"}
            ]
        )
    ]
)
```

### 2. StudyService: Multi-Simulation Orchestration

**Purpose**: Orchestrates complex studies involving multiple simulations with systematic parameter variations

**Study Types**:

#### A. Parametric Studies
Systematic parameter sweeps across component configurations:
```python
study_config = StudyConfig(
    study_id="battery_sizing_study",
    study_type="parametric",
    parameter_sweeps=[
        ParameterSweepSpec(
            component_name="battery",
            parameter_path="technical.capacity_nominal",
            values=[10, 20, 30, 50, 100]  # kWh
        ),
        ParameterSweepSpec(
            component_name="solar_pv",
            parameter_path="technical.capacity_nominal",
            values=[5, 10, 15, 20]  # kW
        )
    ],
    parallel_execution=True,
    max_workers=4
)
# Generates 5 × 4 = 20 simulations
```

#### B. Fidelity Studies
Compare results across different physics fidelity levels:
```python
fidelity_study = StudyConfig(
    study_id="fidelity_impact_analysis",
    study_type="fidelity",
    fidelity_sweep=FidelitySweepSpec(
        component_names=["battery", "heat_pump"],
        fidelity_levels=["SIMPLE", "STANDARD", "DETAILED", "RESEARCH"]
    )
)
# Tests computational vs accuracy trade-offs
```

#### C. Monte Carlo Studies
Uncertainty quantification with stochastic variations:
```python
monte_carlo_study = StudyConfig(
    study_id="uncertainty_analysis",
    study_type="monte_carlo",
    num_samples=1000,
    uncertainty_specs=[
        {"parameter": "solar_irradiance", "distribution": "normal", "std": 0.1},
        {"parameter": "demand_profile", "distribution": "uniform", "range": [0.8, 1.2]}
    ]
)
```

**Parallel Execution**:
- Automatic detection of independent simulations
- Process-based parallelization for CPU-bound MILP solving
- Configurable worker pool management
- Fault tolerance with partial result collection

### 3. RollingHorizonMILPSolver: Advanced Workflow Engine

**Purpose**: Enables solving large-scale optimization problems that exceed single MILP solver capabilities

**Model Predictive Control Approach**:
1. **Divide**: Split long time horizons into overlapping windows
2. **Optimize**: Solve each window with perfect foresight
3. **Implement**: Apply only the first part of each solution
4. **Update**: Carry storage states forward between windows
5. **Predict**: Use future forecasts for better current decisions

**Configuration Example**:
```python
rh_config = RollingHorizonConfig(
    horizon_hours=24,        # 24-hour optimization windows
    overlap_hours=4,         # 4-hour overlap between windows
    prediction_horizon=72,   # Use 72-hour forecasts
    warmstart=True,         # Use previous solutions as warmstart
    storage_continuity=True  # Enforce energy balance between windows
)

solver = RollingHorizonMILPSolver(system, rh_config)
result = solver.solve()
```

**Key Benefits**:
- **Scalability**: Handle week/month/year horizons that exceed MILP memory limits
- **Real-time Capability**: Fast receding horizon optimization
- **Forecast Integration**: Optimal use of prediction data
- **Storage Continuity**: Maintains energy balance across windows
- **Computational Efficiency**: Parallel window processing possible

## Mixed-Fidelity Simulation Capabilities

### The Power of Strategy Pattern Architecture

Our Strategy Pattern implementation enables unprecedented flexibility in simulation fidelity:

```python
# Example: Mixed-fidelity residential energy system
system_config = {
    "components": {
        "battery": {
            "type": "Battery",
            "technical": {"fidelity_level": "RESEARCH"}  # Detailed degradation modeling
        },
        "solar_pv": {
            "type": "SolarPV",
            "technical": {"fidelity_level": "STANDARD"}  # Balanced temperature effects
        },
        "power_demand": {
            "type": "PowerDemand",
            "technical": {"fidelity_level": "SIMPLE"}    # Fast demand profiling
        },
        "heat_pump": {
            "type": "HeatPump",
            "technical": {"fidelity_level": "DETAILED"}  # Complex COP modeling
        }
    }
}
```

**Fidelity Selection Strategy**:
- **RESEARCH fidelity**: For components under detailed study (battery degradation)
- **DETAILED fidelity**: For components with complex physics (heat pumps)
- **STANDARD fidelity**: For balanced accuracy/speed (solar PV)
- **SIMPLE fidelity**: For well-understood components (basic demand)

### Computational Trade-offs

| Fidelity Level | Physics Accuracy | Computational Cost | Use Case |
|----------------|------------------|-------------------|----------|
| **SIMPLE**     | ⭐⭐☆☆☆          | ⚡⚡⚡⚡⚡           | Rapid screening studies |
| **STANDARD**   | ⭐⭐⭐☆☆          | ⚡⚡⚡☆☆           | Production analysis |
| **DETAILED**   | ⭐⭐⭐⭐☆          | ⚡⚡☆☆☆           | Design optimization |
| **RESEARCH**   | ⭐⭐⭐⭐⭐          | ⚡☆☆☆☆           | Scientific investigation |

## Orchestration Layer Benefits

### 1. **Production-Ready Workflows**
- **Before**: Manual test scripts with hardcoded parameters
- **After**: Professional service APIs with configuration management

### 2. **Systematic Studies**
- **Before**: One-off simulations requiring manual parameter changes
- **After**: Automated parametric sweeps with statistical analysis

### 3. **Scalable Optimization**
- **Before**: Limited to small systems due to MILP solver constraints
- **After**: Rolling horizon enables arbitrarily large time horizons

### 4. **Mixed-Fidelity Intelligence**
- **Before**: All-or-nothing fidelity choices
- **After**: Component-specific fidelity for optimal accuracy/speed trade-offs

### 5. **Enterprise Integration**
- **Before**: Research prototype with ad hoc interfaces
- **After**: Clean APIs ready for web services and automation

## Implementation Status

### ✅ **COMPLETED** (Phase 3.1)
- **SimulationService**: Enhanced with strategy pattern support
- **StudyService**: Complete multi-simulation orchestration
- **RollingHorizonMILPSolver**: Advanced workflow implementation
- **Comprehensive Test Suite**: Full orchestration layer validation
- **Architecture Documentation**: Complete design specification

### 🔄 **IN PROGRESS** (Phase 3.2)
- Integration with existing CLI tools
- Web service API development
- Performance optimization and benchmarking

### 📋 **PLANNED** (Phase 3.3)
- **Advanced Study Types**:
  - Optimization studies with genetic algorithms
  - Robust optimization under uncertainty
  - Multi-objective Pareto frontier analysis
- **Real-time Integration**:
  - Live data feed integration
  - Continuous optimization workflows
  - Alert and monitoring systems
- **Enterprise Features**:
  - Database result storage
  - User management and access control
  - Workflow scheduling and automation

## Usage Examples

### Example 1: Residential Battery Sizing Study
```python
# Compare battery sizes for cost optimization
study_service = StudyService()

result = study_service.run_parameter_sensitivity(
    base_config_path="residential_system.yml",
    parameter_specs=[
        {
            "component_name": "battery",
            "parameter_path": "technical.capacity_nominal",
            "values": [0, 5, 10, 15, 20, 25, 30]  # kWh
        }
    ]
)

# Find optimal battery size
best_config = result.best_result
optimal_battery_size = best_config["parameter_settings"]["battery.technical.capacity_nominal"]
print(f"Optimal battery size: {optimal_battery_size} kWh")
print(f"Annual cost: €{best_config['kpis']['total_cost']:.0f}")
```

### Example 2: District Energy System with Rolling Horizon
```python
# Large district with 168-hour (1 week) optimization
rh_config = RollingHorizonConfig(
    horizon_hours=24,      # 24-hour windows
    overlap_hours=4,       # 4-hour overlap
    prediction_horizon=48  # 48-hour forecasts
)

system = load_district_system("district_config.yml")  # 500+ components
solver = RollingHorizonMILPSolver(system, rh_config)
result = solver.solve()

print(f"Solved {result.num_windows} windows in {result.solve_time:.1f}s")
print(f"District cost: €{result.objective_value:.0f}")
```

### Example 3: Fidelity Impact Analysis
```python
# Study computational vs accuracy trade-offs
study_service = StudyService()

result = study_service.run_fidelity_comparison(
    base_config_path="complex_system.yml",
    components=["battery", "heat_pump", "thermal_storage"]
)

# Analyze fidelity trade-offs
for fidelity_result in result.all_results:
    fidelity = fidelity_result["fidelity_level"]
    solve_time = fidelity_result["solver_metrics"]["solve_time"]
    accuracy = fidelity_result["kpis"]["total_cost"]

    print(f"{fidelity}: {solve_time:.2f}s, Cost: €{accuracy:.0f}")
```

## Conclusion: From Engine Parts to Complete Car

The Orchestration Layer completes the EcoSystemiser transformation:

**🔧 Phase 1**: Built the engine parts (Strategy Pattern components)
**⚙️ Phase 2**: Assembled the engine (Mixed-fidelity system integration)
**🚗 Phase 3**: Built the complete car (Production-ready orchestration services)

**The Result**: A professional energy system simulation platform capable of:
- **Industrial-scale studies** with thousands of parameter combinations
- **Real-time optimization** for operational energy management
- **Research-grade accuracy** with computational efficiency controls
- **Enterprise integration** through clean service APIs

The EcoSystemiser platform is now ready for deployment in academic research, industrial energy planning, and operational energy management scenarios.