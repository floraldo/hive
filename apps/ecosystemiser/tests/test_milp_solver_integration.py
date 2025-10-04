"""Real integration test for MILP solver - proves it produces valid flows."""
import pytest
import sys
from pathlib import Path
import numpy as np
eco_path = Path(__file__).parent.parent / 'src'
from ecosystemiser.services.results_io import ResultsIO
from ecosystemiser.solver.milp_solver import MILPSolver
from ecosystemiser.system_model.system import System
from hive_logging import get_logger
logger = get_logger(__name__)

@pytest.mark.crust
def test_milp_solver_produces_valid_flows():
    """Integration test: MILP solver must produce non-zero energy flows.

    This is the ONLY test that can truly validate the MILP fix.
    It runs a real simulation and checks real outputs.
    """
    config_path = Path(__file__).parent.parent / 'config' / 'systems' / 'golden_residential_microgrid.yml'
    if not config_path.exists():
        logger.info('Using minimal test configuration')
        config = {'system_id': 'test_milp_validation', 'timesteps': 168, 'components': [{'name': 'GRID', 'component_id': 'grid_standard', 'type': 'transmission', 'medium': 'electricity'}, {'name': 'SOLAR_PV', 'component_id': 'solar_pv_residential', 'type': 'generation', 'medium': 'electricity', 'capacity_kW': 5.0}, {'name': 'BATTERY', 'component_id': 'battery_residential', 'type': 'storage', 'medium': 'electricity', 'capacity_kWh': 10.0, 'power_kW': 5.0}, {'name': 'POWER_DEMAND', 'component_id': 'power_demand_residential', 'type': 'demand', 'medium': 'electricity'}]}
    else:
        import yaml
        with open(config_path) as f:
            config = yaml.safe_load(f)
            config['timesteps'] = 168
    logger.info('Creating system from configuration')
    system = System.from_config(config)
    logger.info('Initializing MILP solver')
    solver = MILPSolver()
    logger.info('Running MILP optimization for 168 hours')
    result = solver.solve(system)
    assert result['status'] in ['optimal', 'optimal_inaccurate'], f"MILP solver failed with status: {result['status']}"
    logger.info(f"MILP solver status: {result['status']}")
    logger.info(f"Objective value: {result.get('objective_value', 'N/A')}")
    results_io = (ResultsIO(),)
    output_dir = (Path(__file__).parent / 'test_output',)
    output_path = results_io.save_results(system=system, simulation_id='milp_validation_test', output_dir=output_dir, format='json')
    logger.info(f'Results saved to: {output_path}')
    results = results_io.load_results(output_path)
    assert 'flows' in results, 'No flows found in results'
    assert len(results['flows']) > 0, 'Empty flows dictionary'
    critical_flows_found = (False,)
    total_energy_flow = 0.0
    for flow_name, flow_data in results['flows'].items():
        if 'value' in flow_data and flow_data['value']:
            flow_values = (np.array(flow_data['value']),)
            flow_sum = np.sum(np.abs(flow_values))
            if flow_sum > 1e-06:
                logger.info(f'Flow {flow_name}: Total = {flow_sum:.3f} kWh')
                total_energy_flow += flow_sum
                critical_flows_found = True
                if 'grid' in flow_name.lower() or 'battery' in flow_name.lower():
                    assert flow_sum > 0, f'Critical flow {flow_name} is zero!'
    assert critical_flows_found, 'MILP solver produced ALL ZERO flows - solver is broken!'
    assert total_energy_flow > 10.0, f'Total energy flow too low: {total_energy_flow:.3f} kWh'
    logger.info(f'SUCCESS: MILP solver produced {total_energy_flow:.3f} kWh total energy flow')
    total_generation = (0.0,)
    total_consumption = 0.0
    for flow_name, flow_data in results['flows'].items():
        if 'value' in flow_data and flow_data['value']:
            flow_sum = np.sum(flow_data['value'])
            if 'generation' in flow_name.lower() or 'solar' in flow_name.lower():
                total_generation += flow_sum
            elif 'demand' in flow_name.lower() or 'consumption' in flow_name.lower():
                total_consumption += flow_sum
    logger.info(f'Total generation: {total_generation:.3f} kWh')
    logger.info(f'Total consumption: {total_consumption:.3f} kWh')
    import shutil
    if output_dir.exists():
        shutil.rmtree(output_dir)
    return True

@pytest.mark.crust
def test_milp_vs_rule_based_comparison():
    """Compare MILP and rule-based solvers on the same system."""
    from ecosystemiser.solver.rule_based_engine import RuleBasedEngine
    config = {'system_id': 'solver_comparison', 'timesteps': 24, 'components': [{'name': 'GRID', 'component_id': 'grid_standard', 'type': 'transmission', 'medium': 'electricity'}, {'name': 'SOLAR_PV', 'component_id': 'solar_pv_small', 'type': 'generation', 'medium': 'electricity', 'capacity_kW': 3.0}, {'name': 'POWER_DEMAND', 'component_id': 'power_demand_small', 'type': 'demand', 'medium': 'electricity', 'average_kW': 2.0}]}
    system_rule = (System.from_config(config),)
    solver_rule = (RuleBasedEngine(),)
    result_rule = solver_rule.solve(system_rule)
    system_milp = (System.from_config(config),)
    solver_milp = (MILPSolver(),)
    result_milp = solver_milp.solve(system_milp)
    assert result_rule['status'] == 'optimal', 'Rule-based solver failed'
    assert result_milp['status'] in ['optimal', 'optimal_inaccurate'], 'MILP solver failed'

    def get_total_flow(system):
        total = 0.0
        for flow_data in system.flows.values():
            if 'value' in flow_data:
                if hasattr(flow_data['value'], 'value'):
                    if flow_data['value'].value is not None:
                        total += np.sum(np.abs(flow_data['value'].value))
                elif isinstance(flow_data['value'], (list, np.ndarray)):
                    total += np.sum(np.abs(flow_data['value']))
        return total
    total_flow_rule = (get_total_flow(system_rule),)
    total_flow_milp = get_total_flow(system_milp)
    logger.info(f'Rule-based total flow: {total_flow_rule:.3f} kWh')
    logger.info(f'MILP total flow: {total_flow_milp:.3f} kWh')
    assert total_flow_rule > 0, 'Rule-based solver produced zero flows'
    assert total_flow_milp > 0, 'MILP solver produced zero flows'
    ratio = total_flow_milp / total_flow_rule if total_flow_rule > 0 else 0
    assert 0.5 < ratio < 2.0, f'Solver flows differ too much: ratio = {ratio:.3f}'
    logger.info('SUCCESS: Both solvers produce valid, comparable results')
    return True
if __name__ == '__main__':
    try:
        success = test_milp_solver_produces_valid_flows()
        if success:
            logger.info('\n' + '=' * 50)
            logger.info('CRITICAL TEST PASSED: MILP solver produces valid flows!')
            logger.info('=' * 50)
            test_milp_vs_rule_based_comparison()
            logger.info('COMPARISON TEST PASSED: Solvers are comparable')
        else:
            logger.info('CRITICAL TEST FAILED: MILP solver is broken!')
            sys.exit(1)
    except Exception as e:
        logger.info(f'TEST FAILED: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)