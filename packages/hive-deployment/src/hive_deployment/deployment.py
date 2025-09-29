from __future__ import annotations

#!/usr/bin/env python3
"""
Deployment Utilities for Hive Applications
Adapted from SmartHoodsOptimisationTool Apper project
"""

import os
import time
from pathlib import Path
from typing import Any

from hive_logging import get_logger

from .remote_utils import find_available_port, run_remote_command, upload_directory
from .ssh_client import SSHClient, create_ssh_client_from_config


# --- Configuration (load from environment or config) ---
def get_deployment_config() -> dict[str, str]:
    """Get deployment configuration from environment variables with sensible defaults."""
    return {
        "base_remote_apps_dir": os.environ.get("BASE_REMOTE_APPS_DIR", "/home/deploy/apps"),
        "nginx_conf_d_dir": os.environ.get("NGINX_CONF_D_DIR", "/etc/nginx/conf.d"),
        "systemd_service_dir": os.environ.get("SYSTEMD_SERVICE_DIR", "/etc/systemd/system"),
        "server_user": os.environ.get("SERVER_USER", "deploy"),
        "nginx_user_group": os.environ.get("NGINX_USER_GROUP", "www-data"),
    }


# Configure a logger for this module
log = get_logger("hive_deployment")

# --- Core Deployment Functions ---


def connect_to_server(config: dict[str, Any]) -> SSHClient | None:
    """
    Establishes an SSH connection to the remote server.

    Args:
        config: The application configuration dictionary with SSH settings

    Returns:
        An SSHClient instance if successful, None otherwise
    """
    log.info("Establishing SSH connection to server...")
    try:
        ssh = create_ssh_client_from_config(config)
        if not ssh.connect():
            log.error("SSH connection failed.")
            return None
        log.info("SSH connection established successfully.")
        return ssh
    except Exception as e:
        log.error(f"Error establishing SSH connection: {e}", exc_info=True)
        return None


def determine_deployment_paths(app_name: str, deployment_config: dict[str, str] | None = None) -> dict[str, str]:
    """
    Determines all necessary paths for deployment.

    Args:
        app_name: The name of the application
        deployment_config: Optional deployment configuration. If None, loads from environment.

    Returns:
        A dictionary containing various deployment paths
    """
    if deployment_config is None:
        deployment_config = get_deployment_config()

    remote_app_dir = f"{deployment_config['base_remote_apps_dir']}/{app_name}"
    paths = {
        "remote_app_dir": remote_app_dir,
        "venv_path": f"{remote_app_dir}/venv",
        "req_path": f"{remote_app_dir}/requirements.txt",
        "env_file_path": f"{remote_app_dir}/instance/.env",
        "systemd_service_path": f"{deployment_config['systemd_service_dir']}/{app_name}.service",
        "nginx_conf_path": f"{deployment_config['nginx_conf_d_dir']}/{app_name}.conf",
    }
    return paths


def deploy_upload_app(ssh: SSHClient, local_app_path: Path, remote_app_dir: str, config: dict[str, Any]) -> bool:
    """
    Uploads the application files to the remote server.

    Args:
        ssh: The SSH client
        local_app_path: The local path to the application directory
        remote_app_dir: The remote path where the app should be uploaded
        config: The application configuration dictionary

    Returns:
        True if successful, False otherwise
    """
    log.info(f"Uploading application files from {local_app_path} to {remote_app_dir}...")
    try:
        return upload_directory(ssh, local_app_path, remote_app_dir, config=config, sudo_upload=False)
    except Exception as e:
        log.error(f"Error uploading application files: {e}", exc_info=True)
        return False


def deploy_setup_venv(ssh: SSHClient, venv_path: str, req_path: str, config: dict[str, Any]) -> bool:
    """
    Sets up a virtual environment and installs dependencies.

    Args:
        ssh: The SSH client
        venv_path: The path to the virtual environment
        req_path: The path to the requirements.txt file
        config: The application configuration dictionary

    Returns:
        True if successful, False otherwise
    """
    log.info(f"Setting up virtual environment at {venv_path}...")

    # Check if venv already exists
    exit_code, _, _ = ssh.execute_command(f"test -d '{venv_path}'")
    venv_exists = exit_code == 0

    if not venv_exists:
        exit_code, _, stderr = run_remote_command(ssh, f"python3 -m venv '{venv_path}'", config=config, check=False)
        if exit_code != 0:
            log.error(f"Failed to create virtual environment: {stderr}")
            return False
        log.info("Virtual environment created successfully.")
    else:
        log.info(f"Virtual environment already exists at {venv_path}.")

    # Install dependencies
    pip_path = f"{venv_path}/bin/pip"

    # Upgrade pip (optional, can continue if failed)
    run_remote_command(ssh, f"'{pip_path}' install --upgrade pip", config=config, check=False)

    # Install requirements
    log.info(f"Installing dependencies from {req_path}...")
    exit_code, stdout, stderr = run_remote_command(
        ssh, f"'{pip_path}' install -r '{req_path}'", config=config, check=False
    )
    if exit_code != 0:
        log.error(f"Failed to install dependencies: {stderr}")
        return False

    log.info("Dependencies installed successfully.")
    return True


def deploy_update_env_file(ssh: SSHClient, env_file_path: str, port: int, config: dict[str, Any]) -> bool:
    """
    Updates the environment file with the port assignment.

    Args:
        ssh: The SSH client
        env_file_path: The path to the .env file
        port: The assigned port number
        config: The application configuration dictionary

    Returns:
        True if successful, False otherwise
    """
    log.info(f"Updating environment file {env_file_path} with port {port}...")

    # Remove existing FLASK_RUN_PORT line if exists
    run_remote_command(ssh, f"sed -i '/^FLASK_RUN_PORT=/d' {env_file_path}", config=config, check=False)

    # Add new FLASK_RUN_PORT line
    exit_code, _, stderr = run_remote_command(
        ssh, f"echo 'FLASK_RUN_PORT={port}' >> {env_file_path}", config=config, check=False
    )
    if exit_code != 0:
        log.error(f"Failed to add FLASK_RUN_PORT to .env file: {stderr}")
        return False

    log.info(f".env file updated with FLASK_RUN_PORT={port}.")
    return True


def deploy_set_permissions(
    ssh: SSHClient, remote_app_dir: str, config: dict[str, Any], deployment_config: dict[str, str] | None = None
) -> bool:
    """
    Sets the appropriate permissions for the application files.

    Args:
        ssh: The SSH client,
        remote_app_dir: The remote path to the application directory,
        config: The application configuration dictionary

    Returns:
        True if successful, False otherwise,
    """
    log.info(f"Setting permissions for {remote_app_dir}...")

    # Set ownership,
    depl_config = deployment_config or get_deployment_config()
    server_user = depl_config["server_user"]
    nginx_user_group = depl_config["nginx_user_group"]
    exit_code, _, stderr = run_remote_command(
        ssh, f"chown -R {server_user}:{nginx_user_group} '{remote_app_dir}'", config=config, sudo=True, check=False
    )
    if exit_code != 0:
        (log.error(f"Failed to set ownership: {stderr}"),)
        return False

    # Set permissions,
    exit_code, _, stderr = run_remote_command(
        ssh, f"chmod -R u=rwx,g=rwx,o=rx '{remote_app_dir}'", config=config, sudo=True, check=False
    )
    if exit_code != 0:
        (log.error(f"Failed to set base permissions (775): {stderr}"),)
        return False

    # Ensure instance/static directories exist,
    run_remote_command(
        ssh, f"mkdir -p '{remote_app_dir}/instance' '{remote_app_dir}/static'", config=config, sudo=True, check=False
    )

    # Set group ID bit and write permissions,
    run_remote_command(
        ssh, f"chmod g+s '{remote_app_dir}/instance' '{remote_app_dir}/static'", config=config, sudo=True, check=False
    )
    run_remote_command(ssh, f"chmod g+w '{remote_app_dir}/instance'", config=config, sudo=True, check=False)

    log.info("Permissions set successfully.")
    return True


def deploy_systemd_service(
    ssh: SSHClient,
    app_name: str,
    remote_app_dir: str,
    venv_path: str,
    systemd_service_path: str,
    port: int,
    config: dict[str, Any],
    workers: int = 3,
    restart_sec: int = 5,
    custom_exec_start: str = None,
    deployment_config: dict[str, str] | None = None,
) -> bool:
    """
    Creates and enables a systemd service for the application.

    Args:
        ssh: The SSH client,
        app_name: The name of the application,
        remote_app_dir: The remote path to the application directory,
        venv_path: The path to the virtual environment,
        systemd_service_path: The path where the systemd service file should be created,
        port: The assigned port number,
        config: The application configuration dictionary,
        workers: Number of Gunicorn worker processes,
        restart_sec: Seconds to wait before restarting on failure,
        custom_exec_start: Optional custom ExecStart command (if None, uses default Gunicorn)

    Returns:
        True if successful, False otherwise,
    """
    log.info(f"Creating systemd service file for {app_name}...")

    # Use the custom ExecStart or create the default Gunicorn one,
    if custom_exec_start:
        exec_start = (custom_exec_start,)
    else:
        exec_start = f"{venv_path}/bin/gunicorn --workers {workers} --bind 127.0.0.1:{port} wsgi:application"

    # Create systemd service file content,
    depl_config = deployment_config or get_deployment_config()
    server_user = depl_config["server_user"]
    nginx_user_group = depl_config["nginx_user_group"]
    systemd_content = f"""[Unit]
Description=Gunicorn instance for {app_name}
After=network.target,
[Service]
User={server_user}
Group={nginx_user_group}
WorkingDirectory={remote_app_dir}
Environment="SCRIPT_NAME=/{app_name}",
ExecStart={exec_start}
StandardOutput=journal,
StandardError=journal,
SyslogIdentifier={app_name}
Restart=on-failure,
RestartSec={restart_sec}s,
[Install]
WantedBy=multi-user.target"""

    # Create a temporary file for the service,
    temp_service_path = f"/tmp/{app_name}.service_{int(time.time())}"

    # Upload the service file to the temporary location,
    if not ssh.upload_file(systemd_content.encode("utf-8"), temp_service_path, sudo=False):
        log.error("Failed to upload systemd service file to temporary location.")
        return False

    # Move the service file to the proper location,
    exit_code, _, stderr = run_remote_command(
        ssh, f"mv -f {temp_service_path} {systemd_service_path}", config=config, sudo=True, check=False
    )
    if exit_code != 0:
        (log.error(f"Failed to move systemd service file to {systemd_service_path}: {stderr}"),)
        return False

    # Set permissions,
    run_remote_command(ssh, f"chmod 644 {systemd_service_path}", config=config, sudo=True, check=False)

    # Clear Python Cache,
    log.info(f"Clearing __pycache__ in {remote_app_dir}...")
    run_remote_command(
        ssh,
        f"find '{remote_app_dir}' -type d -name '__pycache__' -exec rm -rf {{}} +",
        config=config,
        sudo=False,
        check=False,
        log_output=True,
    )

    # Reload systemd daemon,
    log.info("Reloading systemd daemon...")
    run_remote_command(ssh, "systemctl daemon-reload", config=config, sudo=True, check=False)

    # Stop the service if it's already running,
    log.info(f"Stopping {app_name}.service (if running)...")
    run_remote_command(ssh, f"systemctl stop {app_name}.service", config=config, sudo=True, check=False)
    time.sleep(1)

    # Enable and restart the service,
    log.info(f"Enabling and restarting {app_name}.service...")
    run_remote_command(ssh, f"systemctl enable {app_name}.service", config=config, sudo=True, check=False)

    exit_code, _, stderr = run_remote_command(
        ssh, f"systemctl restart {app_name}.service", config=config, sudo=True, check=False
    )
    if exit_code != 0:
        (log.error(f"Failed to start/restart {app_name}.service: {stderr}"),)
        # Show service status and logs for debugging,
        run_remote_command(
            ssh, f"systemctl status {app_name}.service --no-pager -l", config=config, sudo=True, check=False
        )
        run_remote_command(
            ssh, f"journalctl -u {app_name}.service --no-pager -n 50", config=config, sudo=True, check=False
        )
        return False

    # Wait for service to stabilize,
    log.info("Waiting for service to stabilize...")
    time.sleep(2)

    # Check service status with retry logic,
    log.info(f"Checking status of {app_name}.service...")
    max_retries = (10,)
    retry_delay = (2,)
    service_active = False

    for attempt in range(max_retries):
        log.info(f"Attempt {attempt + 1}/{max_retries} to check service status...")
        exit_code, stdout, stderr = run_remote_command(
            ssh, f"systemctl is-active {app_name}.service", config=config, sudo=True, check=False, log_output=False
        )

        if exit_code == 0:
            log.info(f"{app_name}.service is active.")
            service_active = True
            break
        elif exit_code == 3:  # systemd code for 'activating'
            log.info(f"{app_name}.service is still activating...")
        else:
            log.error(f"{app_name}.service check failed with exit code {exit_code}: {stderr}")
            break

        if attempt < max_retries - 1:
            time.sleep(retry_delay)

    if not service_active:
        log.error(f"{app_name}.service did not become active after {max_retries} attempts.")
        run_remote_command(
            ssh, f"systemctl status {app_name}.service --no-pager -l", config=config, sudo=True, check=False
        )
        run_remote_command(
            ssh, f"journalctl -u {app_name}.service --no-pager -n 50", config=config, sudo=True, check=False
        )
        return False

    log.info(f"{app_name}.service started successfully.")
    return True


def deploy_nginx_config(ssh: SSHClient, app_name: str, nginx_conf_path: str, port: int, config: dict[str, Any]) -> bool:
    """
    Creates an Nginx configuration snippet for the application.

    Args:
        ssh: The SSH client,
        app_name: The name of the application,
        nginx_conf_path: The path where the Nginx configuration file should be created,
        port: The assigned port number,
        config: The application configuration dictionary

    Returns:
        True if successful, False otherwise,
    """
    log.info(f"Creating Nginx configuration snippet for {app_name}...")

    # Create Nginx configuration content,
    nginx_content = f"""# Configuration for {app_name}
# Redirect non-slash version to slash version for consistency,
location = /{app_name} {{
    return 301 $scheme://$host$request_uri/;,
}}

# Main location block for the app,
location /{app_name}/ {{
    proxy_pass http://127.0.0.1:{port};,
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Prefix /{app_name};
}}
"""

    # Create a temporary file for the Nginx configuration,
    temp_nginx_path = f"/tmp/{app_name}.conf_{int(time.time())}"

    # Upload the Nginx configuration to the temporary location,
    if not ssh.upload_file(nginx_content.encode("utf-8"), temp_nginx_path, sudo=False):
        log.error("Failed to upload Nginx configuration to temporary location.")
        return False

    # Move the Nginx configuration to the proper location,
    exit_code, _, stderr = run_remote_command(
        ssh, f"mv -f {temp_nginx_path} {nginx_conf_path}", config=config, sudo=True, check=False
    )
    if exit_code != 0:
        (log.error(f"Failed to move Nginx configuration to {nginx_conf_path}: {stderr}"),)
        return False

    # Set permissions,
    run_remote_command(ssh, f"chmod 644 {nginx_conf_path}", config=config, sudo=True, check=False)

    # Test Nginx configuration,
    log.info("Testing Nginx configuration...")
    exit_code, _, stderr = run_remote_command(ssh, "nginx -t", config=config, sudo=True, check=False)
    if exit_code != 0:
        (log.error(f"Nginx configuration test failed: {stderr}"),)
        return False

    # Reload Nginx,
    log.info("Reloading Nginx...")
    exit_code, _, stderr = run_remote_command(ssh, "systemctl reload nginx", config=config, sudo=True, check=False)
    if exit_code != 0:
        (log.error(f"Failed to reload Nginx: {stderr}"),)
        return False

    # Wait for nginx to stabilize,
    time.sleep(2)

    log.info("Nginx configuration applied successfully.")
    return True


def verify_deployment(
    ssh: SSHClient,
    app_name: str,
    base_url: str | None = None,
    config: dict[str, Any] = None,
    timeout: int = 20,
    wait_time: int = 5,
    expected_content: str = None,
) -> bool:
    """
    Verifies that the application is running correctly after deployment.

    Args:
        ssh: The SSH client,
        app_name: The name of the application,
        base_url: The base URL where the application is hosted (defaults to BASE_URL env var),
        config: The application configuration dictionary,
        timeout: Timeout in seconds for HTTP requests,
        wait_time: Wait time in seconds before verification,
        expected_content: Optional custom content to verify on root page

    Returns:
        True if verification passes, False otherwise,
    """
    import requests

    # Get base_url from environment if not provided,
    if base_url is None:
        base_url = os.environ.get("BASE_URL")
        if base_url is None:
            log.error("base_url not provided and BASE_URL environment variable not set")
            return False

    log.info(f"Verifying deployment for {app_name}...")

    # URLs to check,
    app_url = (f"{base_url}/{app_name}/",)
    health_url = (f"{base_url}/{app_name}/health",)
    status_url = f"{base_url}/{app_name}/status"

    # Wait for service to start,
    log.info(f"Waiting {wait_time} seconds before verification...")
    time.sleep(wait_time)

    # Define headers for the requests,
    headers = {"User-Agent": "HiveDeploymentVerification/1.0"}

    verification_passed = True

    # Check root URL,
    try:
        (log.info(f"Verifying Root URL: {app_url}"),)
        response = requests.get(app_url, timeout=timeout, allow_redirects=True, verify=True, headers=headers)
        (log.info(f"Status Code: {response.status_code}"),)
        response.raise_for_status()
        log.info("Root URL check PASSED.")
    except Exception as e:
        (log.error(f"Root Verification FAILED: {e}"),)
        verification_passed = False

    # Check health URL if it exists,
    try:
        (log.info(f"Verifying Health URL: {health_url}"),)
        response = requests.get(health_url, timeout=timeout, verify=True, headers=headers)
        if response.status_code == 200:
            log.info("Health URL check PASSED.")
        else:
            log.warning(f"Health URL returned {response.status_code}")
    except Exception as e:
        log.warning(f"Health URL check failed (not critical): {e}")

    return verification_passed


# --- High-Level Deployment Function ---


def execute_deployment_steps(
    app_name: str,
    local_app_path: Path,
    config: dict[str, Any],
    app_specific_function=None,
    base_url: str | None = None,
    start_port: int = 5001,
    max_ports: int = 50,
) -> bool:
    """
    Executes all deployment steps for an application, handling errors and logging.

    Args:
        app_name: The name of the application,
        local_app_path: The local path to the application directory,
        config: The application configuration dictionary,
        app_specific_function: Optional function to run app-specific deployment steps,
        base_url: The base URL where the application will be hosted,
        start_port: The starting port number to search for an available port,
        max_ports: The maximum number of ports to search

    Returns:
        True if the deployment was successful, False otherwise,
    """
    log.info(f"--- Starting Deployment for {app_name} ---")

    # Get base_url from environment if not provided,
    if base_url is None:
        base_url = os.environ.get("BASE_URL")
        if base_url is None:
            log.error("base_url not provided and BASE_URL environment variable not set")
            return False

    ssh = (None,)
    assigned_port = (None,)
    success = False

    try:
        # 1. Connect to Server,
        ssh = connect_to_server(config)
        if not ssh:
            raise ConnectionError("Failed to establish SSH connection.")

        # 2. Determine Paths
        paths = determine_deployment_paths(app_name)

        # 3. Find Available Port
        assigned_port = find_available_port(ssh, start_port, max_ports)
        if assigned_port is None:
            raise Exception(f"Could not find available port on remote server starting from {start_port}.")
        log.info(f"Assigned port: {assigned_port}")

        # 4. Upload App Files
        if not deploy_upload_app(ssh, local_app_path, paths["remote_app_dir"], config):
            raise Exception("Failed to upload application files.")

        # 5. Setup Virtual Environment & Install Dependencies
        if not deploy_setup_venv(ssh, paths["venv_path"], paths["req_path"], config):
            raise Exception("Failed to set up virtual environment or install dependencies.")

        # 6. Update .env file with assigned port
        if not deploy_update_env_file(ssh, paths["env_file_path"], assigned_port, config):
            log.warning("Failed to update .env file with port. Continuing...")

        # 7. Set Final Permissions
        if not deploy_set_permissions(ssh, paths["remote_app_dir"], config):
            raise Exception("Failed to set permissions.")

        # 8. Create/Update Systemd Service
        if not deploy_systemd_service(
            ssh,
            app_name,
            paths["remote_app_dir"],
            paths["venv_path"],
            paths["systemd_service_path"],
            assigned_port,
            config,
        ):
            raise Exception("Failed to deploy systemd service.")

        # 9. Create/Update Nginx Config
        if not deploy_nginx_config(ssh, app_name, paths["nginx_conf_path"], assigned_port, config):
            raise Exception("Failed to deploy Nginx configuration.")

        # 10. Execute App-Specific Steps if provided
        if app_specific_function:
            try:
                if not app_specific_function(ssh, paths, assigned_port, config):
                    log.warning("App-specific deployment steps failed. Deployment may be incomplete.")
            except Exception as app_err:
                (log.warning(f"Error in app-specific deployment steps: {app_err}"),)
                log.warning("Continuing with deployment process despite app-specific errors.")

        # 11. Verify Deployment
        verification_result = verify_deployment(ssh, app_name, base_url=base_url, config=config)
        if verification_result:
            log.info("Deployment verification passed.")
        else:
            log.warning("Deployment verification failed. The app might not be functioning correctly.")

        # Deployment Completed Summary
        log.info(f"--- Deployment Completed Successfully for {app_name} ---")
        (log.info(f"App URL: {base_url}/{app_name}/"),)
        (log.info(f"Service: {app_name}.service"),)
        log.info(f"Nginx Conf: {paths['nginx_conf_path']}")

        success = True

    except ConnectionError as e:
        (log.error(f"Deployment FAILED - Connection Error: {e}"),)
    except Exception as e:
        (log.error(f"Deployment FAILED: {e}", exc_info=True),)
    finally:
        if ssh:
            log.info("Closing SSH connection.")
            ssh.close()

    if success:
        log.info(f"--- Deployment Finished Successfully for {app_name} ---")
    else:
        log.error(f"--- Deployment Finished with Errors for {app_name} ---")

    return success


def deploy_application(ssh: SSHClient, app_name: str, local_app_path: Path, config: dict[str, Any], **kwargs) -> bool:
    """
    High-level function to deploy an application.

    Args:
        ssh: The SSH client connection,
        app_name: The name of the application,
        local_app_path: The local path to the application directory,
        config: The application configuration dictionary,
        **kwargs: Additional arguments passed to execute_deployment_steps

    Returns:
        True if the deployment was successful, False otherwise,
    """
    return execute_deployment_steps(app_name=app_name, local_app_path=local_app_path, config=config, **kwargs)


def rollback_deployment(
    ssh: SSHClient, app_name: str, config: dict[str, Any], deployment_config: dict[str, str] | None = None
) -> bool:
    """
    Rollback a failed deployment by stopping services and optionally removing files.

    Args:
        ssh: The SSH client connection,
        app_name: The name of the application,
        config: The application configuration dictionary

    Returns:
        True if the rollback was successful, False otherwise,
    """
    log.info(f"Starting rollback for {app_name}")

    try:
        # Stop the systemd service,
        service_name = (f"{app_name}.service",)
        cmd = (f"sudo systemctl stop {service_name}",)
        run_remote_command(ssh, cmd, f"Stop {service_name}")

        # Disable the service,
        cmd = (f"sudo systemctl disable {service_name}",)
        run_remote_command(ssh, cmd, f"Disable {service_name}")

        # Remove nginx config,
        depl_config = deployment_config or get_deployment_config()
        nginx_conf = (f"{depl_config['nginx_conf_d_dir']}/{app_name}.conf",)
        cmd = (f"sudo rm -f {nginx_conf}",)
        run_remote_command(ssh, cmd, "Remove nginx config")

        # Reload nginx,
        cmd = ("sudo nginx -t && sudo systemctl reload nginx",)
        run_remote_command(ssh, cmd, "Reload nginx")

        # Optionally remove application directory,
        if config.get("rollback_remove_files", False):
            remote_app_dir = (f"{depl_config['base_remote_apps_dir']}/{app_name}",)
            cmd = (f"sudo rm -rf {remote_app_dir}",)
            run_remote_command(ssh, cmd, "Remove application directory")

        log.info(f"Rollback completed for {app_name}")
        return True

    except Exception as e:
        (log.error(f"Rollback failed for {app_name}: {e}"),)
        return False
