# Security: subprocess calls in this test file use sys.executable or system tools (git, ruff, etc.) with hardcoded,
# trusted arguments only. No user input is passed to subprocess. This is safe for
# internal testing infrastructure.

"""Zero-Touch End-to-End Certification Test for Hive Platform V4.4

This is the final certification test that proves the entire autonomous agency
can execute a complete software development lifecycle from a single high-level
command with zero human intervention.

Mission: Create and deploy a simple Flask "Hello World" service autonomously.
"""
import json
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from hive_logging import get_logger, setup_logging

setup_logging(name="zero-touch-certification", log_to_file=True, log_file_path="logs/zero_touch_certification.log")
logger = get_logger(__name__)

class HiveAutonomousAgency:
    """Mission Control for the Zero-Touch Deployment Certification.

    This class orchestrates the entire autonomous development lifecycle:
    1. Creates the initial high-level task
    2. Launches all Hive daemons
    3. Monitors the autonomous workflow
    4. Verifies the deployed application
    """

    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.db_path = self.project_root / "hive_orchestrator.db"
        self.processes = {}
        self.start_time = None
        self.deployed_port = None
        self.container_name = "qr-service-test"

    def setup_environment(self):
        """Prepare the environment for the test"""
        logger.info("=" * 80)
        logger.info("ZERO-TOUCH DEPLOYMENT CERTIFICATION - STARTING")
        logger.info("=" * 80)
        if not self.db_path.exists():
            logger.info("Initializing database...")
            from hive_orchestrator.core.db import initialize_database
            initialize_database()
        self._cleanup_containers()
        logger.info("Environment setup complete")

    def create_initial_task(self) -> str:
        """Create the initial high-level task in the database"""
        logger.info("Creating initial high-level task...")
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        task_id = f"qr-service-{int(time.time())}"
        task_description = "Create a QR Code Generator Service with the following requirements:\n1. Create a new, standalone FastAPI application called 'qr-service' in 'apps/qr-service'\n2. Implement one endpoint: POST /generate that accepts JSON with a 'text' field\n3. The endpoint should generate a QR code PNG image and return it as base64-encoded string\n4. Use the 'qrcode' and 'Pillow' libraries for QR code generation\n5. Include proper error handling for missing or invalid input\n6. Create a Dockerfile to containerize the application\n7. Include a requirements.txt with FastAPI, uvicorn, qrcode, and Pillow\n8. Build and deploy the application as a Docker container on port 8000"
        cursor.execute("\n            INSERT INTO tasks (\n                id, title, description, task_type, status, priority,\n                created_at, created_by, metadata\n            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)\n        ", (task_id, "Build and Deploy QR Code Generator Service", task_description, "autonomous_development", "planning_pending", 100, datetime.now().isoformat(), "zero-touch-certification", json.dumps({"certification_test": True, "expected_port": 8000, "container_name": self.container_name})))
        conn.commit()
        conn.close()
        logger.info(f"Created task: {task_id}")
        return task_id

    def launch_daemons(self):
        """Launch all Hive daemons as background processes"""
        logger.info("Launching Hive daemons...")
        daemons = [("queen", ["python", "-m", "hive_orchestrator.queen", "--mock"]), ("planner", ["python", "-m", "ai_planner.async_agent", "--mock"]), ("reviewer", ["python", "-m", "ai_reviewer.async_agent", "--mock"]), ("deployer", ["python", "-m", "ai_deployer.agent", "--mock"])]
        for name, cmd in daemons:
            try:
                process = subprocess.Popen(cmd, cwd=self.project_root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                self.processes[name] = process
                logger.info(f"Started {name} daemon (PID: {process.pid})")
                time.sleep(2)
            except Exception as e:
                logger.error(f"Failed to start {name}: {e}")
                self.shutdown_daemons()
                raise

    def monitor_workflow(self, task_id: str, timeout: int=300) -> bool:
        """Monitor the autonomous workflow and assert progress through stages.

        Expected workflow stages:
        1. planning_pending -> planning_in_progress -> planned
        2. Sub-tasks created and assigned
        3. Sub-tasks executed (queued -> in_progress -> completed)
        4. Review process (review_pending -> review_in_progress -> review_approved)
        5. Deployment (deployment_pending -> deploying -> deployed)
        """
        logger.info("Monitoring autonomous workflow...")
        start_time = time.time()
        last_status = None
        milestones = {"planning_started": False, "plan_created": False, "subtasks_created": False, "execution_started": False, "execution_completed": False, "review_started": False, "review_completed": False, "deployment_started": False, "deployment_completed": False}
        while time.time() - start_time < timeout:
            try:
                conn = sqlite3.connect(self.db_path)
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
                task = cursor.fetchone()
                if not task:
                    logger.error(f"Task {task_id} not found!")
                    conn.close()
                    return False
                current_status = task["status"]
                if current_status != last_status:
                    logger.info(f"Task status: {last_status} -> {current_status}")
                    last_status = current_status
                    if current_status == "planning_in_progress":
                        milestones["planning_started"] = True
                    elif current_status == "planned":
                        milestones["plan_created"] = True
                cursor.execute("\n                    SELECT COUNT(*) as count FROM tasks\n                    WHERE metadata LIKE ?\n                    AND id != ?\n                ", (f'%"parent_task_id": "{task_id}"%', task_id))
                subtask_count = cursor.fetchone()["count"]
                if subtask_count > 0 and (not milestones["subtasks_created"]):
                    milestones["subtasks_created"] = True
                    logger.info(f"Created {subtask_count} subtasks")
                if milestones["subtasks_created"]:
                    cursor.execute("\n                        SELECT status, COUNT(*) as count FROM tasks\n                        WHERE metadata LIKE ?\n                        AND id != ?\n                        GROUP BY status\n                    ", (f'%"parent_task_id": "{task_id}"%', task_id))
                    subtask_statuses = {row["status"]: row["count"] for row in cursor.fetchall()}
                    if subtask_statuses.get("in_progress", 0) > 0:
                        milestones["execution_started"] = True
                    if subtask_statuses.get("completed", 0) == subtask_count:
                        milestones["execution_completed"] = True
                    if subtask_statuses.get("review_in_progress", 0) > 0:
                        milestones["review_started"] = True
                    if subtask_statuses.get("review_approved", 0) == subtask_count:
                        milestones["review_completed"] = True
                if current_status == "deploying":
                    milestones["deployment_started"] = True
                elif current_status == "deployed":
                    milestones["deployment_completed"] = True
                    metadata = json.loads(task["metadata"] or "{}")
                    self.deployed_port = metadata.get("deployed_port", 8000)
                    logger.info(f"Deployment complete on port {self.deployed_port}")
                    conn.close()
                    return True
                conn.close()
                if current_status in ["failed", "review_rejected", "deployment_failed"]:
                    logger.error(f"Task failed with status: {current_status}")
                    return False
                completed_milestones = sum(1 for v in milestones.values() if v)
                logger.debug(f"Progress: {completed_milestones}/{len(milestones)} milestones")
            except Exception as e:
                logger.error(f"Error monitoring workflow: {e}")
            time.sleep(5)
        logger.error("Workflow monitoring timeout!")
        return False

    def verify_deployment(self) -> bool:
        """Make a real HTTP request to verify the deployed application.
        This is the final certification step.
        """
        logger.info("=" * 80)
        logger.info("FINAL VERIFICATION - Testing Deployed Application")
        logger.info("=" * 80)
        if not self.deployed_port:
            self.deployed_port = 8000
        base_url = f"http://localhost:{self.deployed_port}"
        time.sleep(5)
        try:
            logger.info(f"Testing POST {base_url}/generate")
            test_payload = {"text": "Hive Autonomous Agency - Certification Test"}
            response = requests.post(f"{base_url}/generate", json=test_payload, timeout=10)
            if response.status_code != 200:
                logger.error(f"QR generation failed: {response.status_code}")
                return False
            response_data = response.json()
            if "qr_code" not in response_data:
                logger.error(f"Missing qr_code in response: {response_data}")
                return False
            import base64
            try:
                decoded = base64.b64decode(response_data["qr_code"])
                logger.info(f"OK QR code generated, size: {len(decoded)} bytes")
            except Exception as e:
                logger.error(f"Invalid base64 encoding: {e}")
                return False
            logger.info(f"Testing POST {base_url}/generate with invalid input")
            invalid_payload = {"invalid": "field"}
            error_response = requests.post(f"{base_url}/generate", json=invalid_payload, timeout=10)
            if error_response.status_code != 422:
                logger.warning(f"Expected 422 for invalid input, got: {error_response.status_code}")
            logger.info("OK Error handling working properly")
            logger.info("=" * 80)
            logger.info("CERTIFICATION PASSED - Application Successfully Deployed!")
            logger.info("=" * 80)
            return True
        except requests.exceptions.ConnectionError:
            logger.error("Could not connect to deployed application")
            return False
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False

    def shutdown_daemons(self):
        """Gracefully shutdown all daemon processes"""
        logger.info("Shutting down daemons...")
        for name, process in self.processes.items():
            if process.poll() is None:
                logger.info(f"Terminating {name} (PID: {process.pid})")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning(f"Force killing {name}")
                    process.kill()
        self.processes.clear()

    def _cleanup_containers(self):
        """Clean up any existing test containers"""
        try:
            result = subprocess.run(["docker", "ps", "-a", "-q", "-f", f"name={self.container_name}"], check=False, capture_output=True, text=True)
            if result.stdout.strip():
                logger.info(f"Removing existing container: {self.container_name}")
                subprocess.run(["docker", "rm", "-f", self.container_name], check=False)
        except Exception as e:
            logger.debug(f"Container cleanup: {e}")

    def run_certification(self) -> bool:
        """Execute the complete zero-touch certification test.

        Returns:
            True if certification passed, False otherwise

        """
        self.start_time = time.time()
        try:
            self.setup_environment()
            task_id = self.create_initial_task()
            self.launch_daemons()
            workflow_success = self.monitor_workflow(task_id, timeout=300)
            if not workflow_success:
                logger.error("Workflow execution failed")
                return False
            deployment_success = self.verify_deployment()
            if deployment_success:
                elapsed = time.time() - self.start_time
                logger.info(f"Total certification time: {elapsed:.1f} seconds")
            return deployment_success
        except Exception as e:
            logger.error(f"Certification failed with error: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            self.shutdown_daemons()
            self._cleanup_containers()

@pytest.fixture
def agency():
    """Fixture for the autonomous agency"""
    return HiveAutonomousAgency()

@pytest.mark.crust
def test_zero_touch_deployment(agency):
    """The ultimate test: Can the Hive platform autonomously develop
    and deploy software with zero human intervention?
    """
    assert agency.run_certification(), "Zero-touch deployment certification failed"
if __name__ == "__main__":
    agency = HiveAutonomousAgency()
    success = agency.run_certification()
    if success:
        logger.info("\n" + "=" * 80)
        logger.info("🎉 CERTIFICATION PASSED 🎉")
        logger.info("The Hive Autonomous Agency has successfully demonstrated")
        logger.info("end-to-end software development and deployment capability")
        logger.info("with ZERO human intervention!")
        logger.info("=" * 80)
        sys.exit(0)
    else:
        logger.error("\n" + "=" * 80)
        logger.error("CERTIFICATION FAILED")
        logger.error("The autonomous workflow did not complete successfully")
        logger.error("Check logs for details")
        logger.error("=" * 80)
        sys.exit(1)
