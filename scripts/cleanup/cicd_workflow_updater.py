#!/usr/bin/env python3
"""
CI/CD Workflow Updater - Step 2: Update GitHub Workflows

This script updates all GitHub workflow files to use the new
consolidated script paths instead of the old ones.
"""

import re
from pathlib import Path


class WorkflowUpdater:
    """Updates GitHub workflow files with new script paths"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.workflows_dir = project_root / ".github" / "workflows"
        self.updates_made = []

        # Mapping of old script paths to new consolidated paths
        self.script_mappings = {
            # Test runners
            "scripts/run_integration_tests.py": "scripts/testing/run_tests.py --comprehensive",
            "scripts/run_comprehensive_integration_tests.py": "scripts/testing/run_tests.py --all",
            "scripts/validate_golden_rules.py": "scripts/testing/run_tests.py --golden-rules",
            "scripts/validate_integration_tests.py": "scripts/testing/run_tests.py --quick",
            "scripts/quick-test.sh": "scripts/testing/health-check.sh",
            # Security audits
            "scripts/security_check.py": "scripts/security/run_audit.py --quick",
            "scripts/audit_dependencies.py": "scripts/security/run_audit.py --dependencies",
            "scripts/operational_excellence/security_audit.py": "scripts/security/run_audit.py --comprehensive",
            # Cleanup and maintenance
            "scripts/comprehensive_code_cleanup.py": "scripts/maintenance/repository_hygiene.py --all",
            "scripts/hive_clean.py": "scripts/maintenance/repository_hygiene.py --db-cleanup",
            "scripts/operational_excellence/comprehensive_cleanup.py": "scripts/maintenance/repository_hygiene.py --all",
            "scripts/operational_excellence/targeted_cleanup.py": "scripts/maintenance/repository_hygiene.py",
            # Code fixers
            "scripts/fix_type_hints.py": "scripts/maintenance/fixers/code_fixers.py --type-hints",
            "scripts/fix_global_state.py": "scripts/maintenance/fixers/code_fixers.py --global-state",
            "scripts/modernize_type_hints.py": "scripts/maintenance/fixers/code_fixers.py --type-hints",
            "scripts/smart_final_fixer.py": "scripts/maintenance/fixers/code_fixers.py --all",
            # Database operations
            "scripts/init_db_simple.py": "scripts/database/setup.py --init",
            "scripts/optimize_database.py": "scripts/database/setup.py --optimize",
            "scripts/seed_database.py": "scripts/database/setup.py --seed",
            # Performance and monitoring
            "scripts/operational_excellence/ci_performance_analyzer.py": "scripts/analysis/async_resource_patterns.py",
            "scripts/operational_excellence/production_monitor.py": "scripts/testing/health-check.sh",
            # Setup scripts (moved but same functionality)
            "scripts/initial_setup.sh": "scripts/setup/initial_setup.sh",
            "scripts/setup_pre_commit.sh": "scripts/setup/setup_pre_commit.sh",
            "scripts/setup_github_secrets.sh": "scripts/setup/setup_github_secrets.sh",
        }

    def scan_workflow_files(self) -> list[Path]:
        """Find all GitHub workflow files"""
        if not self.workflows_dir.exists():
            print(f"[WARNING] No .github/workflows directory found at {self.workflows_dir}")
            return []

        workflow_files = list(self.workflows_dir.glob("*.yml")) + list(self.workflows_dir.glob("*.yaml"))
        print(f"Found {len(workflow_files)} workflow files to scan")
        return workflow_files

    def update_workflow_file(self, workflow_file: Path) -> bool:
        """Update a single workflow file"""
        try:
            content = workflow_file.read_text(encoding="utf-8")
            original_content = content
            updates_in_file = 0

            # Apply each mapping
            for old_path, new_path in self.script_mappings.items():
                # Match various patterns where scripts might be referenced
                patterns = [
                    # Direct python execution
                    rf"python\s+{re.escape(old_path)}",
                    # Script execution with arguments
                    rf"{re.escape(old_path)}(\s+[^\n]*)?",
                    # In run commands
                    rf"run:\s*[|\n\s]*.*{re.escape(old_path)}",
                ]

                for pattern in patterns:
                    matches = re.findall(pattern, content)
                    if matches:
                        # Replace the old path with new path
                        content = re.sub(
                            rf"{re.escape(old_path)}(\s+[^\n]*)?",
                            lambda m: new_path
                            + (m.group(1) if m.group(1) and not new_path.endswith(m.group(1).strip()) else ""),
                            content,
                        )
                        updates_in_file += len(matches)
                        print(f"  Updated {len(matches)} references to {old_path}")

            if content != original_content:
                # Create backup
                backup_path = workflow_file.with_suffix(workflow_file.suffix + ".backup")
                backup_path.write_text(original_content, encoding="utf-8")

                # Write updated content
                workflow_file.write_text(content, encoding="utf-8")

                self.updates_made.append(
                    {
                        "file": str(workflow_file.relative_to(self.project_root)),
                        "updates": updates_in_file,
                        "backup": str(backup_path.relative_to(self.project_root)),
                    },
                )

                print(f"[UPDATED] {workflow_file.name}: {updates_in_file} changes")
                return True
            else:
                print(f"[SKIP] {workflow_file.name}: No changes needed")
                return False

        except Exception as e:
            print(f"[ERROR] Failed to update {workflow_file}: {e}")
            return False

    def update_all_workflows(self) -> bool:
        """Update all workflow files"""
        print("Step 2: Updating CI/CD Workflows")
        print("=" * 50)

        workflow_files = self.scan_workflow_files()
        if not workflow_files:
            print("[WARNING] No workflow files found to update")
            return True

        updated_count = 0
        for workflow_file in workflow_files:
            print(f"\nProcessing {workflow_file.name}...")
            if self.update_workflow_file(workflow_file):
                updated_count += 1

        print(f"\n[SUMMARY] Updated {updated_count}/{len(workflow_files)} workflow files")
        return True

    def generate_update_report(self) -> str:
        """Generate workflow update report"""
        report = f"""# CI/CD Workflow Update Report

**Generated**: {__import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Summary

- **Workflows Scanned**: {len(self.scan_workflow_files())}
- **Workflows Updated**: {len(self.updates_made)}
- **Total Script References Updated**: {sum(update["updates"] for update in self.updates_made)}

## Updated Files

| Workflow File | Changes | Backup Location |
|---------------|---------|-----------------|
"""

        for update in self.updates_made:
            report += f"| {update['file']} | {update['updates']} | {update['backup']} |\n"

        report += """

## Script Path Mappings Applied

| Old Path | New Path |
|----------|----------|
"""

        for old_path, new_path in self.script_mappings.items():
            report += f"| {old_path} | {new_path} |\n"

        report += """

## Next Steps

1. **Test CI/CD Pipeline**: Push a test commit to verify all workflows execute successfully
2. **Monitor First Run**: Check that all script references resolve correctly
3. **Remove Backups**: After verification, remove .backup files
4. **Proceed to Step 3**: Begin addressing logging violations

## Rollback Instructions

If issues occur, restore original workflows:

```bash
# Restore all workflow backups
for backup in .github/workflows/*.backup; do
    mv "$backup" "${backup%.backup}"
done
```

---

*CI/CD workflows updated to use consolidated script structure.*
"""

        return report


def main():
    """Main execution function"""
    print("CI/CD Workflow Updater - Step 2")
    print("=" * 40)

    project_root = Path(__file__).parent.parent.parent
    updater = WorkflowUpdater(project_root)

    # Update all workflows
    success = updater.update_all_workflows()

    # Generate report
    report = updater.generate_update_report()
    report_path = project_root / "scripts" / "cleanup" / "cicd_update_report.md"
    report_path.write_text(report, encoding="utf-8")

    print(f"\nUpdate report saved: {report_path}")

    if success and updater.updates_made:
        print("\n[SUCCESS] CI/CD workflows updated successfully!")
        print("Next: Test the pipeline with a commit to verify all workflows work")
        return 0
    elif success and not updater.updates_made:
        print("\n[INFO] No workflow updates were needed")
        return 0
    else:
        print("\n[ERROR] Some workflow updates failed")
        return 1


if __name__ == "__main__":
    exit(main())



