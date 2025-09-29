#!/usr/bin/env python3
"""
Scripts Directory Refactoring Tool - Phase 2: Consolidation and Deprecation

This script implements Phase 2 of the systematic refactoring plan:
- Creates archive directory for outdated scripts
- Merges redundant scripts into consolidated versions
- Prepares the new directory structure
"""

import json
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class ConsolidationPlan:
    """Plan for consolidating a group of scripts"""
    group_name: str
    target_path: str
    source_scripts: List[str]
    consolidation_method: str  # merge, archive, replace
    new_features: List[str]

@dataclass
class FileOperation:
    """Represents a file operation to be performed"""
    operation: str  # create, move, copy, delete, modify
    source_path: str
    target_path: str
    reason: str

class ScriptsConsolidator:
    """Handles consolidation and reorganization of scripts"""
    
    def __init__(self, scripts_root: Path, metadata_file: Path):
        self.scripts_root = scripts_root
        self.project_root = scripts_root.parent
        self.metadata_file = metadata_file
        self.metadata_map = self._load_metadata()
        self.consolidation_plans: List[ConsolidationPlan] = []
        self.file_operations: List[FileOperation] = []
        
    def _load_metadata(self) -> Dict:
        """Load metadata from Phase 1 analysis"""
        with open(self.metadata_file, 'r') as f:
            return json.load(f)
    
    def create_consolidation_plans(self) -> List[ConsolidationPlan]:
        """Create detailed plans for each consolidation group"""
        print("Phase 2a: Creating Consolidation Plans")
        print("=" * 50)
        
        # Define specific consolidation strategies
        consolidation_strategies = {
            'cleanup_scripts': {
                'target': 'maintenance/repository_hygiene.py',
                'method': 'merge',
                'primary': 'scripts/operational_excellence/comprehensive_cleanup.py',
                'features': [
                    'File organization and cleanup',
                    'Backup file removal', 
                    'Documentation consolidation',
                    'Database cleanup (from hive_clean.py)',
                    'Targeted cleanup modes'
                ]
            },
            'testing_scripts': {
                'target': 'testing/run_tests.py',
                'method': 'merge',
                'primary': 'scripts/run_comprehensive_integration_tests.py',
                'features': [
                    'Comprehensive test execution',
                    'Quick validation mode',
                    'Performance benchmarking',
                    'CI/CD integration'
                ]
            },
            'security_scripts': {
                'target': 'security/run_audit.py', 
                'method': 'merge',
                'primary': 'scripts/operational_excellence/security_audit.py',
                'features': [
                    'Comprehensive security scanning',
                    'Quick security checks',
                    'Vulnerability reporting',
                    'Compliance validation'
                ]
            },
            'database_scripts': {
                'target': 'database/setup.py',
                'method': 'split_merge',
                'features': [
                    'Database initialization and seeding',
                    'Index optimization',
                    'Performance tuning',
                    'Migration support'
                ]
            },
            'fixer_scripts': {
                'target': 'maintenance/fixers/code_fixers.py',
                'method': 'merge',
                'primary': 'scripts/fixes/smart_final_fixer.py',
                'features': [
                    'Type hint fixes',
                    'Global state fixes', 
                    'Logging standardization',
                    'Async pattern fixes',
                    'Golden rules compliance'
                ]
            },
            'async_refactor_scripts': {
                'target': 'archive/',
                'method': 'archive',
                'reason': 'One-time refactoring completed'
            }
        }
        
        # Create plans for each strategy
        for group_name, strategy in consolidation_strategies.items():
            # Find scripts matching this group
            matching_scripts = self._find_matching_scripts(group_name)
            
            if matching_scripts:
                if strategy['method'] == 'archive':
                    plan = ConsolidationPlan(
                        group_name=group_name,
                        target_path=strategy['target'],
                        source_scripts=matching_scripts,
                        consolidation_method=strategy['method'],
                        new_features=[strategy.get('reason', 'Archive outdated scripts')]
                    )
                else:
                    plan = ConsolidationPlan(
                        group_name=group_name,
                        target_path=strategy['target'],
                        source_scripts=matching_scripts,
                        consolidation_method=strategy['method'],
                        new_features=strategy.get('features', [])
                    )
                
                self.consolidation_plans.append(plan)
                print(f"[PLAN] {group_name}: {len(matching_scripts)} scripts -> {strategy['target']}")
        
        print(f"\n[OK] Created {len(self.consolidation_plans)} consolidation plans")
        return self.consolidation_plans
    
    def _find_matching_scripts(self, group_name: str) -> List[str]:
        """Find scripts matching a consolidation group"""
        group_keywords = {
            'cleanup_scripts': ['cleanup', 'clean', 'comprehensive_cleanup', 'targeted_cleanup', 'hive_clean'],
            'testing_scripts': ['test', 'integration', 'validate', 'cert', 'run_comprehensive', 'run_integration'],
            'security_scripts': ['security', 'audit'],
            'database_scripts': ['database', 'db', 'optimize', 'seed', 'init'],
            'fixer_scripts': ['fix_', 'modernize', 'add_type', 'smart_final'],
            'async_refactor_scripts': ['async_worker', 'queen_async', 'worker_async', 'enhance_async']
        }
        
        keywords = group_keywords.get(group_name, [])
        matching_scripts = []
        
        for script_path, metadata in self.metadata_map.items():
            script_name = Path(script_path).name.lower()
            purpose = metadata.get('purpose', '').lower()
            
            if any(keyword in script_name or keyword in purpose for keyword in keywords):
                matching_scripts.append(script_path)
        
        return matching_scripts
    
    def plan_directory_structure(self):
        """Plan the new directory structure"""
        print("\nPhase 2b: Planning Directory Structure")
        print("=" * 50)
        
        # Define new directory structure
        new_structure = {
            'analysis/': [
                'async_resource_patterns.py',
                'ci_performance_analyzer.py', 
                'documentation_analyzer.py',
                'comprehensive_code_cleanup.py'
            ],
            'database/': [
                'setup.py',  # consolidated
                'optimize.py'  # consolidated
            ],
            'daemons/': [
                'ai_planner_daemon.py',
                'ai_reviewer_daemon.py'
            ],
            'maintenance/': [
                'repository_hygiene.py',  # consolidated
                'log_management.py'
            ],
            'maintenance/fixers/': [
                'code_fixers.py'  # consolidated
            ],
            'security/': [
                'run_audit.py'  # consolidated
            ],
            'setup/': [
                'initial_setup.sh',
                'setup_pre_commit.sh',
                'setup_pre_commit.bat',
                'setup_github_secrets.sh'
            ],
            'testing/': [
                'run_tests.py',  # consolidated
                'health-check.sh',
                'quick-test.sh',
                'dev-session.sh'
            ],
            'utils/': [
                'monitor_certification.py',
                'monitor_master_plan.py',
                'hive_queen.py',  # launcher scripts
                'hive_dashboard.py',
                'start_async_hive.py'
            ],
            'archive/': [
                # Will be populated with deprecated scripts
            ]
        }
        
        # Plan directory creation operations
        for directory in new_structure.keys():
            target_dir = self.scripts_root / directory
            if not target_dir.exists():
                self.file_operations.append(FileOperation(
                    operation='create',
                    source_path='',
                    target_path=str(target_dir),
                    reason=f'Create new directory structure: {directory}'
                ))
        
        print(f"[PLAN] Planned {len(new_structure)} new directories")
        return new_structure
    
    def plan_file_operations(self):
        """Plan all file move, copy, and consolidation operations"""
        print("\nPhase 2c: Planning File Operations")
        print("=" * 50)
        
        # Archive operations for deprecated scripts
        archive_scripts = [
            'v3_final_cert.py',
            'step_by_step_cert.py', 
            'async_worker.py',
            'worker_async_patch.py',
            'queen_async_enhancement.py',
            'simulate_planner_success.py',
            'hive_complete_review.py'
        ]
        
        for script in archive_scripts:
            script_path = self._find_script_path(script)
            if script_path:
                target_path = self.scripts_root / 'archive' / script
                self.file_operations.append(FileOperation(
                    operation='move',
                    source_path=script_path,
                    target_path=str(target_path),
                    reason=f'Archive deprecated script: {script}'
                ))
        
        # Consolidation operations
        for plan in self.consolidation_plans:
            if plan.consolidation_method == 'merge':
                # Create consolidated script
                self.file_operations.append(FileOperation(
                    operation='create',
                    source_path='',
                    target_path=str(self.scripts_root / plan.target_path),
                    reason=f'Create consolidated script for {plan.group_name}'
                ))
                
                # Archive source scripts
                for source_script in plan.source_scripts:
                    script_name = Path(source_script).name
                    target_path = self.scripts_root / 'archive' / script_name
                    self.file_operations.append(FileOperation(
                        operation='move',
                        source_path=source_script,
                        target_path=str(target_path),
                        reason=f'Archive after consolidation: {script_name}'
                    ))
        
        # Move operations for scripts going to new locations
        move_operations = {
            'scripts/analysis/async_resource_patterns.py': 'analysis/async_resource_patterns.py',
            'scripts/daemons/ai_planner_daemon.py': 'daemons/ai_planner_daemon.py',
            'scripts/daemons/ai_reviewer_daemon.py': 'daemons/ai_reviewer_daemon.py',
            'scripts/log_management.py': 'maintenance/log_management.py',
            'scripts/initial_setup.sh': 'setup/initial_setup.sh',
            'scripts/setup_pre_commit.sh': 'setup/setup_pre_commit.sh',
            'scripts/setup_pre_commit.bat': 'setup/setup_pre_commit.bat',
            'scripts/setup_github_secrets.sh': 'setup/setup_github_secrets.sh',
            'scripts/health-check.sh': 'testing/health-check.sh',
            'scripts/quick-test.sh': 'testing/quick-test.sh',
            'scripts/dev-session.sh': 'testing/dev-session.sh',
            'scripts/hive_queen.py': 'utils/hive_queen.py',
            'scripts/hive_dashboard.py': 'utils/hive_dashboard.py',
            'scripts/start_async_hive.py': 'utils/start_async_hive.py'
        }
        
        for source, target in move_operations.items():
            source_path = self.project_root / source
            if source_path.exists():
                target_path = self.scripts_root / target
                self.file_operations.append(FileOperation(
                    operation='move',
                    source_path=str(source_path),
                    target_path=str(target_path),
                    reason=f'Reorganize into new structure: {Path(target).name}'
                ))
        
        print(f"[PLAN] Planned {len(self.file_operations)} file operations")
    
    def _find_script_path(self, script_name: str) -> Optional[str]:
        """Find the full path of a script by name"""
        for script_path in self.metadata_map.keys():
            if Path(script_path).name == script_name:
                return script_path
        return None
    
    def generate_dry_run_plan(self) -> str:
        """Generate detailed dry-run plan"""
        plan = f"""# Scripts Refactoring Dry-Run Plan

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Total Operations**: {len(self.file_operations)}

## Summary

### Consolidation Plans
{chr(10).join(f"- **{plan.group_name}**: {len(plan.source_scripts)} scripts -> {plan.target_path}" for plan in self.consolidation_plans)}

### Operation Types
- **Create**: {len([op for op in self.file_operations if op.operation == 'create'])}
- **Move**: {len([op for op in self.file_operations if op.operation == 'move'])}
- **Copy**: {len([op for op in self.file_operations if op.operation == 'copy'])}
- **Delete**: {len([op for op in self.file_operations if op.operation == 'delete'])}

## Detailed Operations

### Directory Creation
"""
        
        # Add directory creation operations
        for op in self.file_operations:
            if op.operation == 'create' and op.target_path.endswith('/'):
                plan += f"- CREATE: {op.target_path}\n"
        
        plan += "\n### File Consolidations\n"
        
        # Add consolidation details
        for consolidation_plan in self.consolidation_plans:
            plan += f"\n#### {consolidation_plan.group_name}\n"
            plan += f"**Target**: {consolidation_plan.target_path}\n"
            plan += f"**Method**: {consolidation_plan.consolidation_method}\n"
            plan += f"**Source Scripts**:\n"
            for script in consolidation_plan.source_scripts:
                plan += f"- {Path(script).name}\n"
            plan += f"**New Features**:\n"
            for feature in consolidation_plan.new_features:
                plan += f"- {feature}\n"
        
        plan += "\n### File Operations\n"
        
        # Add all file operations
        for op in self.file_operations:
            if op.operation != 'create' or not op.target_path.endswith('/'):
                plan += f"- **{op.operation.upper()}**: {Path(op.source_path).name if op.source_path else ''} -> {Path(op.target_path).name}\n"
                plan += f"  - Reason: {op.reason}\n"
        
        plan += f"""

## Safety Checks Required

### Before Execution
1. **Backup Current State**: Create full backup of scripts/ directory
2. **Check Dependencies**: Verify no external references to scripts being moved
3. **CI/CD Verification**: Check GitHub workflows for script references
4. **Documentation Update**: Update any README files referencing old paths

### Verification After Execution
1. **Test Consolidated Scripts**: Verify all consolidated scripts work correctly
2. **Check Import Paths**: Ensure all internal script references are updated
3. **Run Golden Tests**: Verify no regressions in architectural compliance
4. **Integration Testing**: Run comprehensive integration tests

## Risk Assessment

### Low Risk Operations
- Moving launcher scripts (hive_queen.py, etc.)
- Creating new directories
- Moving setup scripts

### Medium Risk Operations  
- Consolidating test runners
- Moving daemon scripts
- Archiving old scripts

### High Risk Operations
- Consolidating cleanup scripts (many dependencies)
- Consolidating security scripts (CI/CD integration)
- Consolidating fixer scripts (complex logic)

## Rollback Plan

If issues occur:
1. Stop execution immediately
2. Restore from backup
3. Analyze specific failure
4. Update plan and retry

---

**IMPORTANT**: This is a DRY RUN plan. No files will be modified until explicitly approved and executed.
"""
        
        return plan
    
    def save_plans(self, output_dir: Path):
        """Save all plans to files"""
        output_dir.mkdir(exist_ok=True)
        
        # Save consolidation plans
        plans_data = [
            {
                'group_name': plan.group_name,
                'target_path': plan.target_path,
                'source_scripts': plan.source_scripts,
                'consolidation_method': plan.consolidation_method,
                'new_features': plan.new_features
            }
            for plan in self.consolidation_plans
        ]
        
        with open(output_dir / 'consolidation_plans.json', 'w') as f:
            json.dump(plans_data, f, indent=2)
        
        # Save file operations
        operations_data = [
            {
                'operation': op.operation,
                'source_path': op.source_path,
                'target_path': op.target_path,
                'reason': op.reason
            }
            for op in self.file_operations
        ]
        
        with open(output_dir / 'file_operations.json', 'w') as f:
            json.dump(operations_data, f, indent=2)
        
        # Save dry-run plan
        dry_run_plan = self.generate_dry_run_plan()
        with open(output_dir / 'dry_run_plan.md', 'w', encoding='utf-8') as f:
            f.write(dry_run_plan)
        
        print(f"[SAVE] Plans saved to {output_dir}")

def main():
    """Main execution function"""
    print("Scripts Directory Refactoring - Phase 2: Consolidation")
    print("=" * 60)
    
    scripts_root = Path(__file__).parent.parent
    metadata_file = scripts_root / "cleanup" / "scripts_metadata.json"
    
    if not metadata_file.exists():
        print("❌ Error: Metadata file not found. Please run Phase 1 analysis first.")
        return 1
    
    consolidator = ScriptsConsolidator(scripts_root, metadata_file)
    
    # Phase 2a: Create consolidation plans
    consolidation_plans = consolidator.create_consolidation_plans()
    
    # Phase 2b: Plan directory structure
    new_structure = consolidator.plan_directory_structure()
    
    # Phase 2c: Plan file operations
    consolidator.plan_file_operations()
    
    # Save all plans
    output_dir = scripts_root / "cleanup"
    consolidator.save_plans(output_dir)
    
    # Summary
    print(f"\nConsolidation Planning Complete!")
    print(f"   - {len(consolidation_plans)} consolidation groups planned")
    print(f"   - {len(consolidator.file_operations)} file operations planned")
    print(f"   - Estimated script reduction: {len([op for op in consolidator.file_operations if op.operation == 'move' and 'archive' in op.target_path])} files")
    
    print(f"\nReview Plans:")
    print(f"   - Dry-run plan: {output_dir / 'dry_run_plan.md'}")
    print(f"   - Consolidation details: {output_dir / 'consolidation_plans.json'}")
    print(f"   - File operations: {output_dir / 'file_operations.json'}")
    
    print(f"\nIMPORTANT: Review all plans before executing Phase 3!")
    
    return 0

if __name__ == "__main__":
    exit(main())
