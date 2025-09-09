#!/usr/bin/env python3
"""
Hive Headless MAS Launcher
Simple script to start the complete autonomous development system
"""

import os
import sys
import time
import signal
import pathlib
import subprocess
from typing import List, Dict

class HiveLauncher:
    """Launcher for the complete Hive headless MAS system"""
    
    def __init__(self):
        self.root = pathlib.Path(__file__).parent
        self.processes: Dict[str, subprocess.Popen] = {}
        self.running = False
    
    def launch_orchestrator(self):
        """Launch the main orchestrator process"""
        print("🚀 Starting Hive Orchestrator...")
        try:
            process = subprocess.Popen(
                [sys.executable, "orchestrator.py"],
                cwd=str(self.root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self.processes["orchestrator"] = process
            print("✅ Orchestrator started (PID: {})".format(process.pid))
            return True
        except Exception as e:
            print(f"❌ Failed to start orchestrator: {e}")
            return False
    
    def launch_worker(self, worker_id: str, interval: int = 15):
        """Launch a specific worker process"""
        print(f"🤖 Starting {worker_id} worker...")
        try:
            process = subprocess.Popen(
                [sys.executable, "headless_workers.py", worker_id, "--interval", str(interval)],
                cwd=str(self.root),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            self.processes[worker_id] = process
            print(f"✅ {worker_id.title()} worker started (PID: {process.pid})")
            return True
        except Exception as e:
            print(f"❌ Failed to start {worker_id} worker: {e}")
            return False
    
    def check_processes(self):
        """Check if all processes are still running"""
        failed_processes = []
        for name, process in self.processes.items():
            if process.poll() is not None:
                # Process has died
                failed_processes.append(name)
                print(f"⚠️  {name} process has died (exit code: {process.returncode})")
        
        # Remove dead processes
        for name in failed_processes:
            del self.processes[name]
        
        return len(failed_processes) == 0
    
    def stop_all(self):
        """Stop all running processes"""
        print("\n🛑 Stopping all processes...")
        
        for name, process in self.processes.items():
            try:
                print(f"   Stopping {name}...")
                process.terminate()
                
                # Wait for graceful shutdown
                try:
                    process.wait(timeout=5)
                    print(f"   ✅ {name} stopped gracefully")
                except subprocess.TimeoutExpired:
                    # Force kill if necessary
                    process.kill()
                    print(f"   🔨 {name} force killed")
            except Exception as e:
                print(f"   ⚠️  Error stopping {name}: {e}")
        
        self.processes.clear()
        print("✅ All processes stopped")
    
    def show_status(self):
        """Show status of all processes"""
        print(f"\n📊 Hive MAS Status ({len(self.processes)} processes)")
        print("=" * 50)
        
        if not self.processes:
            print("   No processes running")
            return
        
        for name, process in self.processes.items():
            status = "🟢 Running" if process.poll() is None else "🔴 Dead"
            print(f"   {status} {name:>12} (PID: {process.pid})")
        
        print(f"\n💡 Use Ctrl+C to stop all processes")
        print(f"💡 Use 'python hive_cli.py status' for detailed system status")
    
    def run_full_system(self):
        """Run the complete Hive MAS system"""
        print("🚀 Launching Hive Headless Multi-Agent System")
        print("=" * 60)
        
        # Set up signal handler for graceful shutdown
        def signal_handler(signum, frame):
            self.running = False
            print("\n🛑 Shutdown signal received...")
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
        try:
            # Launch orchestrator
            if not self.launch_orchestrator():
                return False
            
            time.sleep(2)  # Give orchestrator time to start
            
            # Launch all workers
            workers = ["queen", "frontend", "backend", "infra"]
            for worker in workers:
                if not self.launch_worker(worker):
                    print(f"⚠️  Continuing without {worker} worker...")
                time.sleep(1)  # Stagger worker starts
            
            print(f"\n✅ Hive MAS launched successfully!")
            print(f"📊 {len(self.processes)} processes running")
            
            # Initial status display
            self.show_status()
            
            # Main monitoring loop
            self.running = True
            while self.running:
                time.sleep(30)  # Check every 30 seconds
                
                if not self.check_processes():
                    print("⚠️  Some processes have failed. System may not function properly.")
                
                # Optional: show periodic status
                # self.show_status()
            
        except KeyboardInterrupt:
            print("\n🛑 Shutdown requested by user")
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
        finally:
            self.stop_all()
            print("\n🏁 Hive MAS shutdown complete")
            
        return True
    
    def quick_start(self):
        """Quick start with minimal output"""
        print("🚀 Quick starting Hive MAS...")
        
        # Start orchestrator and all workers in background
        success = True
        success &= self.launch_orchestrator()
        time.sleep(2)
        
        for worker in ["queen", "frontend", "backend", "infra"]:
            success &= self.launch_worker(worker)
            time.sleep(0.5)
        
        if success:
            print(f"✅ Hive MAS started successfully! ({len(self.processes)} processes)")
            print("💡 Processes running in background. Use 'python hive_cli.py status' to monitor.")
            return True
        else:
            print("❌ Some processes failed to start")
            self.stop_all()
            return False

def main():
    """Main entry point"""
    launcher = HiveLauncher()
    
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "quick":
            # Quick start and exit
            launcher.quick_start()
        elif command == "status":
            # Show status using CLI
            subprocess.run([sys.executable, "hive_cli.py", "status"])
        elif command == "stop":
            # Stop any running processes (basic implementation)
            print("🛑 Stopping Hive MAS processes...")
            try:
                subprocess.run(["pkill", "-f", "orchestrator.py"])
                subprocess.run(["pkill", "-f", "headless_workers.py"])
                print("✅ Processes stopped")
            except Exception as e:
                print(f"⚠️  Error stopping processes: {e}")
        else:
            print("Usage: python start_headless_mas.py [quick|status|stop]")
            print("   quick  - Start in background and exit")
            print("   status - Show system status")
            print("   stop   - Stop all processes")
            print("   (no args) - Start with monitoring")
    else:
        # Full interactive start
        launcher.run_full_system()

if __name__ == "__main__":
    main()