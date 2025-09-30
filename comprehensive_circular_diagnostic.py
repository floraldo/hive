#!/usr/bin/env python3
"""
Comprehensive Circular Reversion Diagnostic
==========================================

This script provides a comprehensive diagnostic of the circular ruff reversion issue.
It combines all analysis approaches into one comprehensive tool.
"""

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path


class CircularReversionDiagnostic:
    def __init__(self):
        self.pvgis_path = Path("apps/ecosystemiser/src/ecosystemiser/profile_loader/climate/adapters/pvgis.py")
        self.findings = []
        self.recommendations = []
    
    def log_finding(self, category, severity, message, details=None):
        """Log a finding with severity level"""
        finding = {
            'timestamp': datetime.now().isoformat(),
            'category': category,
            'severity': severity,  # INFO, WARNING, ERROR, CRITICAL
            'message': message,
            'details': details
        }
        self.findings.append(finding)
        
        # Print with appropriate formatting
        severity_icons = {
            'INFO': 'ℹ️',
            'WARNING': '⚠️',
            'ERROR': '❌',
            'CRITICAL': '🚨'
        }
        icon = severity_icons.get(severity, '📝')
        print(f"{icon} [{severity}] {message}")
        if details:
            print(f"    Details: {details}")
    
    def run_command(self, cmd, description=""):
        """Run a command and return the result"""
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            self.log_finding("COMMAND", "ERROR", f"Command timeout: {cmd}", "Command took longer than 30 seconds")
            return -1, "", "Timeout"
        except Exception as e:
            self.log_finding("COMMAND", "ERROR", f"Command failed: {cmd}", str(e))
            return -1, "", str(e)
    
    def check_file_exists(self):
        """Check if pvgis.py exists and get basic info"""
        print("🔍 CHECKING FILE EXISTENCE")
        print("=" * 50)
        
        if not self.pvgis_path.exists():
            self.log_finding("FILE", "CRITICAL", "pvgis.py does not exist", str(self.pvgis_path))
            return False
        
        stat = self.pvgis_path.stat()
        self.log_finding("FILE", "INFO", "pvgis.py exists", {
            'path': str(self.pvgis_path),
            'size': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat()
        })
        
        # Check git status
        code, stdout, stderr = self.run_command(f"git status --porcelain {self.pvgis_path}")
        if code == 0:
            if stdout.strip():
                self.log_finding("GIT", "WARNING", "File has git changes", stdout.strip())
            else:
                self.log_finding("GIT", "INFO", "File has no git changes")
        else:
            self.log_finding("GIT", "ERROR", "Could not check git status", stderr)
        
        return True
    
    def analyze_problematic_line(self):
        """Analyze the specific problematic line"""
        print("\n🎯 ANALYZING PROBLEMATIC LINE")
        print("=" * 50)
        
        try:
            with open(self.pvgis_path, 'r') as f:
                lines = f.readlines()
            
            self.log_finding("FILE", "INFO", f"File has {len(lines)} lines")
            
            # Check around line 607
            start_line = max(600, 0)
            end_line = min(615, len(lines))
            
            problematic_found = False
            for i in range(start_line, end_line):
                line_num = i + 1
                line_content = lines[i].rstrip()
                
                if 'pvgis_cols' in line_content:
                    self.log_finding("SYNTAX", "ERROR", f"Problematic line {line_num} found", {
                        'line_number': line_num,
                        'content': repr(line_content),
                        'has_trailing_comma': line_content.endswith(',') and not line_content.strip().endswith('{')
                    })
                    problematic_found = True
            
            if not problematic_found:
                self.log_finding("SYNTAX", "INFO", "No problematic lines found around line 607")
                
        except Exception as e:
            self.log_finding("FILE", "ERROR", "Could not analyze problematic line", str(e))
    
    def check_active_processes(self):
        """Check for active processes that might be modifying files"""
        print("\n⚡ CHECKING ACTIVE PROCESSES")
        print("=" * 50)
        
        # Check ruff processes
        code, stdout, stderr = self.run_command("ps aux | grep ruff | grep -v grep")
        if stdout:
            self.log_finding("PROCESS", "WARNING", "Active ruff processes found", stdout)
        else:
            self.log_finding("PROCESS", "INFO", "No active ruff processes")
        
        # Check VS Code processes
        code, stdout, stderr = self.run_command("ps aux | grep -i 'visual studio code' | grep -v grep")
        if stdout:
            self.log_finding("PROCESS", "WARNING", "VS Code processes found", stdout)
        else:
            self.log_finding("PROCESS", "INFO", "No VS Code processes")
        
        # Check Python formatter processes
        code, stdout, stderr = self.run_command("ps aux | grep python | grep -E '(format|lint|ruff)' | grep -v grep")
        if stdout:
            self.log_finding("PROCESS", "WARNING", "Python formatter processes found", stdout)
        else:
            self.log_finding("PROCESS", "INFO", "No Python formatter processes")
    
    def check_ruff_configuration(self):
        """Check ruff configuration for conflicts"""
        print("\n🔧 CHECKING RUFF CONFIGURATION")
        print("=" * 50)
        
        # Check root pyproject.toml
        root_pyproject = Path("pyproject.toml")
        if root_pyproject.exists():
            try:
                with open(root_pyproject, 'r') as f:
                    content = f.read()
                
                # Look for skip-magic-trailing-comma
                if 'skip-magic-trailing-comma' in content:
                    lines = content.split('\n')
                    for line in lines:
                        if 'skip-magic-trailing-comma' in line:
                            if 'true' in line:
                                self.log_finding("CONFIG", "CRITICAL", "skip-magic-trailing-comma = true", 
                                               "This setting causes ruff to add invalid trailing commas")
                            elif 'false' in line:
                                self.log_finding("CONFIG", "INFO", "skip-magic-trailing-comma = false", 
                                               "This is the correct setting")
                            break
                else:
                    self.log_finding("CONFIG", "WARNING", "skip-magic-trailing-comma not found in root config")
                
                # Check for COM818 in ignore list
                if 'COM818' in content:
                    self.log_finding("CONFIG", "INFO", "COM818 found in ignore list", 
                                   "This should prevent trailing comma errors")
                else:
                    self.log_finding("CONFIG", "WARNING", "COM818 not found in ignore list", 
                                   "This might allow trailing comma errors")
                    
            except Exception as e:
                self.log_finding("CONFIG", "ERROR", "Could not read root pyproject.toml", str(e))
        else:
            self.log_finding("CONFIG", "ERROR", "Root pyproject.toml not found")
        
        # Check for multiple pyproject.toml files
        pyproject_files = list(Path(".").rglob("pyproject.toml"))
        if len(pyproject_files) > 1:
            self.log_finding("CONFIG", "WARNING", f"Multiple pyproject.toml files found ({len(pyproject_files)})", 
                           [str(f) for f in pyproject_files])
        else:
            self.log_finding("CONFIG", "INFO", "Only one pyproject.toml file found")
    
    def check_vscode_settings(self):
        """Check VS Code settings for conflicts"""
        print("\n💻 CHECKING VS CODE SETTINGS")
        print("=" * 50)
        
        vscode_settings = Path(".vscode/settings.json")
        if vscode_settings.exists():
            try:
                with open(vscode_settings, 'r') as f:
                    settings = json.load(f)
                
                # Check format on save
                format_on_save = settings.get('editor.formatOnSave')
                if format_on_save:
                    self.log_finding("VSCODE", "WARNING", "Format on save enabled", 
                                   "This might cause automatic formatting conflicts")
                else:
                    self.log_finding("VSCODE", "INFO", "Format on save disabled")
                
                # Check line length
                line_length = None
                for key, value in settings.items():
                    if 'line-length' in key.lower():
                        line_length = value
                        break
                
                if line_length:
                    self.log_finding("VSCODE", "WARNING", f"VS Code line length: {line_length}", 
                                   "Check if this conflicts with pyproject.toml")
                
                # Check Python formatter
                python_formatter = settings.get('python.formatting.provider')
                if python_formatter:
                    self.log_finding("VSCODE", "INFO", f"Python formatter: {python_formatter}")
                
            except Exception as e:
                self.log_finding("VSCODE", "ERROR", "Could not read VS Code settings", str(e))
        else:
            self.log_finding("VSCODE", "INFO", "No VS Code settings found")
    
    def check_pre_commit_hooks(self):
        """Check pre-commit hooks"""
        print("\n🔗 CHECKING PRE-COMMIT HOOKS")
        print("=" * 50)
        
        pre_commit_config = Path(".pre-commit-config.yaml")
        if pre_commit_config.exists():
            try:
                with open(pre_commit_config, 'r') as f:
                    content = f.read()
                
                if 'ruff' in content.lower():
                    self.log_finding("PRECOMMIT", "INFO", "Pre-commit config contains ruff hooks")
                    
                    # Extract ruff hooks
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if 'ruff' in line.lower():
                            self.log_finding("PRECOMMIT", "INFO", f"Ruff hook found at line {i+1}", line.strip())
                else:
                    self.log_finding("PRECOMMIT", "INFO", "Pre-commit config does not contain ruff")
                    
            except Exception as e:
                self.log_finding("PRECOMMIT", "ERROR", "Could not read pre-commit config", str(e))
        else:
            self.log_finding("PRECOMMIT", "INFO", "No pre-commit config found")
    
    def test_circular_reversion(self):
        """Test if circular reversion is actually happening"""
        print("\n🧪 TESTING CIRCULAR REVERSION")
        print("=" * 50)
        
        if not self.pvgis_path.exists():
            self.log_finding("TEST", "ERROR", "Cannot test - pvgis.py does not exist")
            return False
        
        # Record initial state
        initial_mtime = self.pvgis_path.stat().st_mtime
        
        # Read original content
        with open(self.pvgis_path, 'r') as f:
            original_content = f.read()
        
        # Make a test modification
        test_content = original_content + f"\n# TEST MODIFICATION {datetime.now().isoformat()}\n"
        
        try:
            # Write test modification
            with open(self.pvgis_path, 'w') as f:
                f.write(test_content)
            
            self.log_finding("TEST", "INFO", "Test modification applied")
            
            # Wait and check for reversion
            reverted = False
            for i in range(3):
                time.sleep(2)
                current_mtime = self.pvgis_path.stat().st_mtime
                
                if current_mtime != initial_mtime:
                    # Check if our modification is still there
                    with open(self.pvgis_path, 'r') as f:
                        current_content = f.read()
                    
                    if "TEST MODIFICATION" not in current_content:
                        self.log_finding("TEST", "CRITICAL", "CIRCULAR REVERSION CONFIRMED!", 
                                       f"Test modification was reverted after {i+1} checks")
                        reverted = True
                        break
                    else:
                        self.log_finding("TEST", "INFO", f"Test modification still present after {i+1} checks")
            
            if not reverted:
                self.log_finding("TEST", "INFO", "No circular reversion detected")
                
        except Exception as e:
            self.log_finding("TEST", "ERROR", "Error during circular reversion test", str(e))
        
        finally:
            # Restore original content
            try:
                with open(self.pvgis_path, 'w') as f:
                    f.write(original_content)
                self.log_finding("TEST", "INFO", "Original content restored")
            except Exception as e:
                self.log_finding("TEST", "ERROR", "Could not restore original content", str(e))
        
        return reverted
    
    def generate_recommendations(self):
        """Generate recommendations based on findings"""
        print("\n💡 GENERATING RECOMMENDATIONS")
        print("=" * 50)
        
        critical_findings = [f for f in self.findings if f['severity'] == 'CRITICAL']
        error_findings = [f for f in self.findings if f['severity'] == 'ERROR']
        warning_findings = [f for f in self.findings if f['severity'] == 'WARNING']
        
        if critical_findings:
            self.recommendations.append("🚨 IMMEDIATE ACTION REQUIRED:")
            for finding in critical_findings:
                self.recommendations.append(f"  - {finding['message']}")
        
        if error_findings:
            self.recommendations.append("\n❌ ERRORS TO FIX:")
            for finding in error_findings:
                self.recommendations.append(f"  - {finding['message']}")
        
        if warning_findings:
            self.recommendations.append("\n⚠️ WARNINGS TO ADDRESS:")
            for finding in warning_findings:
                self.recommendations.append(f"  - {finding['message']}")
        
        # Specific recommendations based on findings
        config_issues = [f for f in self.findings if f['category'] == 'CONFIG']
        if config_issues:
            self.recommendations.append("\n🔧 CONFIGURATION RECOMMENDATIONS:")
            self.recommendations.append("  1. Ensure skip-magic-trailing-comma = false in pyproject.toml")
            self.recommendations.append("  2. Add COM818 to ignore list if needed")
            self.recommendations.append("  3. Align VS Code settings with pyproject.toml")
        
        process_issues = [f for f in self.findings if f['category'] == 'PROCESS']
        if process_issues:
            self.recommendations.append("\n⚡ PROCESS RECOMMENDATIONS:")
            self.recommendations.append("  1. Stop any active ruff processes")
            self.recommendations.append("  2. Disable VS Code format-on-save temporarily")
            self.recommendations.append("  3. Clear ruff cache: python -m ruff clean")
        
        # Print recommendations
        for rec in self.recommendations:
            print(rec)
    
    def generate_report(self):
        """Generate comprehensive diagnostic report"""
        print("\n📊 GENERATING DIAGNOSTIC REPORT")
        print("=" * 50)
        
        report = f"""# Circular Ruff Reversion Diagnostic Report

**Generated:** {datetime.now().isoformat()}
**Target File:** {self.pvgis_path}
**Total Findings:** {len(self.findings)}

## Executive Summary

This diagnostic was performed to investigate the circular ruff reversion issue where
syntax fixes to pvgis.py are automatically reverted by some process or configuration.

## Findings Summary

- **Critical:** {len([f for f in self.findings if f['severity'] == 'CRITICAL'])}
- **Errors:** {len([f for f in self.findings if f['severity'] == 'ERROR'])}
- **Warnings:** {len([f for f in self.findings if f['severity'] == 'WARNING'])}
- **Info:** {len([f for f in self.findings if f['severity'] == 'INFO'])}

## Detailed Findings

"""
        
        for finding in self.findings:
            report += f"### {finding['severity']} - {finding['category']}\n"
            report += f"**Message:** {finding['message']}\n"
            if finding['details']:
                report += f"**Details:** {finding['details']}\n"
            report += f"**Timestamp:** {finding['timestamp']}\n\n"
        
        report += "## Recommendations\n\n"
        for rec in self.recommendations:
            report += f"- {rec}\n"
        
        report += f"""
## Next Steps

1. Review all findings above
2. Implement recommendations based on severity
3. Test resolution with a simple syntax fix
4. Document final solution

## Technical Details

- **Python Version:** {subprocess.run('python --version', shell=True, capture_output=True, text=True).stdout.strip()}
- **Ruff Version:** {subprocess.run('python -m ruff --version', shell=True, capture_output=True, text=True).stdout.strip()}
- **Git Status:** {subprocess.run('git status --porcelain', shell=True, capture_output=True, text=True).stdout.strip() or 'Clean'}
"""
        
        with open("circular_reversion_diagnostic_report.md", "w") as f:
            f.write(report)
        
        self.log_finding("REPORT", "INFO", "Diagnostic report generated", "circular_reversion_diagnostic_report.md")
    
    def run_full_diagnostic(self):
        """Run the complete diagnostic"""
        print("🚨 COMPREHENSIVE CIRCULAR REVERSION DIAGNOSTIC")
        print("=" * 60)
        print("This diagnostic will analyze all possible causes of circular ruff reversion")
        print()
        
        # Run all checks
        if self.check_file_exists():
            self.analyze_problematic_line()
            self.check_active_processes()
            self.check_ruff_configuration()
            self.check_vscode_settings()
            self.check_pre_commit_hooks()
            
            # Ask user if they want to run the circular reversion test
            response = input("\nDo you want to run the circular reversion test? (y/n): ")
            if response.lower() == 'y':
                self.test_circular_reversion()
        
        # Generate recommendations and report
        self.generate_recommendations()
        self.generate_report()
        
        print("\n✅ DIAGNOSTIC COMPLETE")
        print("Check 'circular_reversion_diagnostic_report.md' for the full report")

def main():
    """Main function"""
    diagnostic = CircularReversionDiagnostic()
    diagnostic.run_full_diagnostic()

if __name__ == "__main__":
    main()
