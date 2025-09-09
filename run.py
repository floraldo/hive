#!/usr/bin/env python3
import argparse
from orchestrator.main import HiveOrchestrator

def main():
    parser = argparse.ArgumentParser(description="Hive Multi-Agent Orchestrator")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without making changes")
    parser.add_argument("--no-auto-merge", action="store_true", help="Disable auto-merge on PRs")
    args = parser.parse_args()
    
    orchestrator = HiveOrchestrator(
        dry_run=args.dry_run,
        auto_merge=not args.no_auto_merge
    )
    
    print("🐝 Hive Orchestrator Ready")
    print("=" * 50)
    
    while True:
        goal = input("\n👑 Queen awaits your command (or 'exit'): ")
        if goal.lower() in ['exit', 'quit']:
            break
        
        orchestrator.run_task(goal)
        
        # Return to main branch
        if not args.dry_run:
            orchestrator.git.repo.git.checkout("main")
    
    print("\n🐝 Hive shutting down gracefully")

if __name__ == "__main__":
    main()