import libtmux
import time
import json
import datetime
from pathlib import Path

class TmuxController:
    def __init__(self, session_name="hive-swarm"):
        server = libtmux.Server()
        self.session = server.find_where({"session_name": session_name})
        if not self.session:
            raise Exception(f"Session '{session_name}' not found. Run ./setup.sh first")
        
        self.log_dir = Path("logs")
        self.log_dir.mkdir(exist_ok=True)
        self.task_counter = 0
        print(f"✅ Connected to hive swarm: {session_name}")
    
    def send_to_agent(self, agent_name, command):
        """Send command with sentinel markers for reliable parsing"""
        pane = self.session.find_where({"pane_title": agent_name})
        if not pane:
            print(f"⚠️ Agent '{agent_name}' not found")
            return None
        
        # Generate unique task ID
        self.task_counter += 1
        task_id = f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{self.task_counter}"
        
        # Wrap command with sentinels
        full_command = (
            f"===BEGIN TASK {task_id}===\n"
            f"{command}\n"
            f"When complete, print exactly:\n"
            f"STATUS: success|partial|blocked|failed\n"
            f"CHANGES: <files changed or summary>\n"
            f"NEXT: <recommended next action>\n"
            f"LAST_CMD: <last shell command executed>\n"
            f"===END TASK {task_id}==="
        )
        
        # Log the command
        self._log_event({
            "type": "command",
            "agent": agent_name,
            "task_id": task_id,
            "command": command
        })
        
        # Send line by line
        for line in full_command.splitlines():
            pane.send_keys(line)
            pane.send_keys("")  # Enter
            time.sleep(0.1)  # Prevent overwhelming
        
        return task_id
    
    def read_agent_status(self, agent_name, task_id, timeout=60):
        """Read status with sentinel-based parsing"""
        pane = self.session.find_where({"pane_title": agent_name})
        if not pane:
            return {"status": "error", "changes": "agent not found", "next": ""}
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            time.sleep(2)
            
            # Capture pane output
            output = pane.capture_pane(start=-200)
            
            # Find task boundaries
            start_marker = f"===BEGIN TASK {task_id}==="
            end_marker = f"===END TASK {task_id}==="
            
            task_output = self._extract_between_markers(output, start_marker, end_marker)
            if task_output:
                status_info = self._parse_footer(task_output)
                if status_info:
                    self._log_event({
                        "type": "status",
                        "agent": agent_name,
                        "task_id": task_id,
                        **status_info
                    })
                    return status_info
        
        return {"status": "timeout", "changes": "", "next": ""}
    
    def _extract_between_markers(self, lines, start_marker, end_marker):
        """Extract lines between sentinel markers"""
        try:
            start_idx = None
            end_idx = None
            
            for i, line in enumerate(lines):
                if start_marker in line:
                    start_idx = i
                elif end_marker in line and start_idx is not None:
                    end_idx = i
                    break
            
            if start_idx is not None and end_idx is not None:
                return lines[start_idx:end_idx+1]
        except Exception as e:
            print(f"Marker extraction error: {e}")
        
        return None
    
    def _parse_footer(self, lines):
        """Parse STATUS/CHANGES/NEXT from task output"""
        status = changes = next_step = None
        
        for line in lines:
            line = line.strip()
            if line.startswith("STATUS:"):
                status = line.split("STATUS:", 1)[1].strip()
            elif line.startswith("CHANGES:"):
                changes = line.split("CHANGES:", 1)[1].strip()
            elif line.startswith("NEXT:"):
                next_step = line.split("NEXT:", 1)[1].strip()
        
        if status:
            return {"status": status, "changes": changes or "", "next": next_step or ""}
        return None
    
    def _log_event(self, event):
        """Log to JSONL with timestamp"""
        event["timestamp"] = datetime.datetime.now().isoformat()
        log_file = self.log_dir / f"hive_{datetime.date.today()}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(event) + "\n")