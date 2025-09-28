#!/usr/bin/env python3
"""
Remote utility functions for Hive Deployment.
Adapted from SmartHoodsOptimisationTool Apper project.
"""

import fnmatch
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from hive_logging import get_logger

from .ssh_client import SSHClient


def parse_deployignore(local_dir: str) -> List[str]:
    """
    Parse .deployignore file and return list of patterns to exclude.

    Args:
        local_dir: The local directory containing the .deployignore file

    Returns:
        List of patterns to exclude from deployment
    """
    ignore_patterns = []
    deployignore_path = os.path.join(local_dir, ".deployignore")

    if os.path.exists(deployignore_path):
        try:
            with open(deployignore_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        ignore_patterns.append(line)
            logging.info(f"Loaded {len(ignore_patterns)} ignore patterns from .deployignore")
        except Exception as e:
            logging.warning(f"Error reading .deployignore: {e}")

    return ignore_patterns


def should_ignore_path(path: str, ignore_patterns: List[str], base_dir: str = "") -> bool:
    """
    Check if a path should be ignored based on .deployignore patterns.

    Args:
        path: The path to check (relative to base directory)
        ignore_patterns: List of patterns from .deployignore
        base_dir: Base directory for relative path calculation

    Returns:
        True if the path should be ignored
    """
    # Normalize path separators
    path = path.replace("\\\\", "/")

    for pattern in ignore_patterns:
        # Handle directory patterns (ending with /)
        if pattern.endswith("/"):
            if path.startswith(pattern) or "/" + pattern in path:
                return True
        # Handle file patterns
        elif fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(os.path.basename(path), pattern):
            return True

    return False


def find_available_port(ssh: SSHClient, start_port: int, max_search: int) -> Optional[int]:
    """Finds an available TCP port on the remote server."""
    logging.info(f"Searching for available port starting from {start_port}...")
    try:
        # Try ss first, fallback to netstat
        cmd = "ss -tlpn"
        exit_code, stdout, stderr = ssh.execute_command(cmd)

        if exit_code != 0:
            logging.warning(f"'ss -tlpn' failed: {stderr}. Trying 'netstat -tlpn'.")
            cmd = "netstat -tlpn"
            exit_code, stdout, stderr = ssh.execute_command(cmd)
            if exit_code != 0:
                logging.error(f"Both 'ss' and 'netstat' failed: {stderr}. Cannot determine used ports.")
                return None

        listening_ports = set()
        # Combined regex to handle various ss/netstat outputs for IPv4/IPv6 LISTEN state
        # Looks for LISTEN state and extracts IP:Port or *:Port
        pattern = re.compile(r"LISTEN\\s+\\d+\\s+\\d+\\s+([0-9.:\\[\\]]+):(\\d+)")

        for line in stdout.splitlines():
            match = pattern.search(line)
            if match:
                try:
                    port_str = match.group(2)
                    listening_ports.add(int(port_str))
                except (ValueError, IndexError):
                    logging.debug(f"Could not parse port from matched line: {line}")
                    continue

        logging.debug(f"Currently listening ports found: {sorted(list(listening_ports))}")

        for i in range(max_search):
            port = start_port + i
            if port not in listening_ports:
                logging.info(f"Port {port} appears available.")
                return port

        logging.error(f"Could not find an available port between {start_port} and {start_port + max_search - 1}.")
        return None

    except Exception as e:
        logging.error(f"Error finding available port: {e}", exc_info=True)
        return None


def run_remote_command(
    ssh_client: SSHClient,
    command: str,
    config: Dict[str, Any],
    sudo: bool = False,
    check: bool = True,
    log_output: bool = True,
) -> Tuple[int, str, str]:
    """
    Executes a command on the remote server using the provided SSH client.

    Args:
        ssh_client: An initialized and connected SSHClient instance.
        command: The shell command to execute.
        config: The application configuration dictionary.
        sudo: If True, executes the command using sudo.
        check: If True, raise an exception if the command returns a non-zero exit code.
        log_output: If True, logs stdout and stderr.

    Returns:
        A tuple containing (exit_code, stdout, stderr).

    Raises:
        Exception: If 'check' is True and the command returns a non-zero exit code.
    """
    sudo_prefix = "sudo " if sudo else ""
    logging.debug(f"Running remote command: {sudo_prefix}{command}")

    exit_code, stdout, stderr = ssh_client.execute_command(command, sudo=sudo)

    if exit_code != 0:
        logging.warning(f"Remote command failed (Exit Code: {exit_code}): {sudo_prefix}{command}")
        if stdout and log_output:
            logging.warning(f"  STDOUT: {stdout}")
        if stderr and log_output:
            logging.warning(f"  STDERR: {stderr}")
        if check:
            raise Exception(
                f"Remote command failed with exit code {exit_code}: {sudo_prefix}{command}. Stderr: {stderr}"
            )
    else:
        logging.debug(f"Remote command succeeded (Exit Code: 0): {sudo_prefix}{command}")
        if stdout and log_output:
            logging.debug(f"  STDOUT: {stdout}")
        if stderr and log_output:
            logging.debug(f"  STDERR: {stderr}")

    return exit_code, stdout, stderr


def upload_directory(
    ssh_client: SSHClient,
    local_dir: str,
    remote_dir: str,
    config: Dict[str, Any],
    sudo_upload: bool = False,
) -> bool:
    """
    Uploads a local directory to a remote server via SFTP.

    Args:
        ssh_client: An initialized and connected SSHClient instance.
        local_dir: The path to the local directory to upload.
        remote_dir: The path to the destination directory on the remote server.
        config: The application configuration dictionary.
        sudo_upload: If True, attempts to use sudo for creating the remote directory.

    Returns:
        True if the upload was successful, False otherwise.
    """
    local_path = Path(local_dir)
    if not local_path.is_dir():
        logging.error(f"Local directory not found: {local_dir}")
        return False

    # Parse .deployignore patterns
    ignore_patterns = parse_deployignore(local_dir)
    if ignore_patterns:
        logging.info(f"Using .deployignore with {len(ignore_patterns)} patterns")

    try:
        if not ssh_client.sftp:
            ssh_client.sftp = ssh_client.client.open_sftp()

        logging.info(f"Creating remote directory (if needed): {remote_dir}")
        # Use run_remote_command for directory creation
        exit_code, _, stderr = run_remote_command(
            ssh_client,
            f"mkdir -p '{remote_dir}'",
            config,
            sudo=sudo_upload,
            check=False,
            log_output=False,
        )
        if exit_code != 0:
            # Check if error is "File exists" - that's okay
            if "File exists" not in stderr:
                logging.error(f"Failed to create remote directory {remote_dir}: {stderr}")
                return False

        # Walk through the local directory
        for root, dirs, files in os.walk(local_dir):
            # Create corresponding remote directories
            relative_path = Path(root).relative_to(local_path)
            relative_path_str = str(relative_path).replace("\\\\", "/")

            # Check if this directory should be ignored
            if relative_path_str != "." and should_ignore_path(relative_path_str + "/", ignore_patterns):
                logging.debug(f"Ignoring directory: {relative_path_str}")
                dirs.clear()  # Don't walk into subdirectories
                continue

            remote_root = os.path.join(remote_dir, str(relative_path)).replace("\\\\", "/")

            if relative_path != Path("."):  # Don't try to create the base dir again
                logging.debug(f"Creating remote subdirectory: {remote_root}")
                exit_code, _, stderr = run_remote_command(
                    ssh_client,
                    f"mkdir -p '{remote_root}'",
                    config,
                    sudo=sudo_upload,
                    check=False,
                    log_output=False,
                )
                # Again, ignore "File exists" type errors
                if exit_code != 0 and "File exists" not in stderr:
                    logging.warning(f"Could not create remote subdirectory {remote_root}: {stderr}")

            # Upload files
            for filename in files:
                # Check if this file should be ignored
                file_relative_path = os.path.join(relative_path_str, filename).replace("\\\\", "/")
                if should_ignore_path(file_relative_path, ignore_patterns):
                    logging.debug(f"Ignoring file: {file_relative_path}")
                    continue

                local_file_path = os.path.join(root, filename)
                remote_file_path = os.path.join(remote_root, filename).replace("\\\\", "/")
                try:
                    logging.debug(f"Uploading {local_file_path} to {remote_file_path}")
                    ssh_client.sftp.put(local_file_path, remote_file_path)
                except Exception as e:
                    logging.error(f"Failed to upload {local_file_path} to {remote_file_path}: {e}")

        logging.info(f"Successfully uploaded directory {local_dir} to {remote_dir}")
        return True

    except Exception as e:
        logging.error(f"Error during directory upload: {e}", exc_info=True)
        return False


def find_next_app_name(ssh: SSHClient, base_dir: str, prefix: str, config: dict) -> Optional[str]:
    """Finds the next available app name (e.g., app1, app2) on the remote server."""
    logging.info(f"Finding existing apps in '{base_dir}' with prefix '{prefix}'...")
    # Use find for potentially better handling of names and errors
    # -maxdepth 1 to only look in the base_dir
    # -type d for directories
    # -name 'prefix[0-9]*' to match the pattern
    cmd = f"find '{base_dir}' -maxdepth 1 -type d -name '{prefix}[0-9]*' 2>/dev/null"
    exit_code, stdout, stderr = ssh.execute_command(cmd)

    if exit_code != 0:
        logging.error(f"Error running find command in {base_dir}: {stderr}")
        return None

    existing_nums = set()
    pattern = re.compile(rf".*/{prefix}(\\d+)$")

    if not stdout:
        logging.info(f"No existing apps found with prefix '{prefix}'. Starting with {prefix}1.")
        return f"{prefix}1"

    for line in stdout.splitlines():
        match = pattern.match(line.strip())
        if match:
            try:
                existing_nums.add(int(match.group(1)))
            except ValueError:
                logging.warning(f"Could not parse number from directory name: {line}")
                continue

    if not existing_nums:
        logging.info(f"No numbered apps matched pattern '{prefix}[0-9]*'. Starting with {prefix}1.")
        return f"{prefix}1"

    next_num = 1
    while next_num in existing_nums:
        next_num += 1

    next_app_name = f"{prefix}{next_num}"
    logging.info(f"Found existing app numbers: {sorted(list(existing_nums))}")
    logging.info(f"Next available app name will be: {next_app_name}")
    return next_app_name
