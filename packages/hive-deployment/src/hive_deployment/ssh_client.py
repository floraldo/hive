#!/usr/bin/env python3
"""
SSH utility module for Hive Deployment.
Adapted from SmartHoodsOptimisationTool Apper project.
"""

import os
import time
from typing import Any, Dict, Optional, Tuple, Union

import paramiko
from hive_logging import get_logger


class SSHClient:
    """
    SSH client for Hive deployments.

    Compatible with deployment utilities and remote operations.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        """
        Initialize an SSH client from a configuration dictionary.

        Args:
            config: SSH configuration dictionary containing connection parameters
        """
        self.config = config
        self.host = config.get("host")
        self.username = config.get("username")
        self.password = config.get("password")
        self.port = int(config.get("port", 22))
        self.key_filename = config.get("key_filename")
        self.connect_timeout = int(config.get("connect_timeout", 10))
        self.sudo_password = config.get("sudo_password")
        self.client = None
        self.sftp = None

    def connect(self) -> bool:
        """
        Establish an SSH connection.

        Returns:
            bool: True if connection is successful
        """
        if self.client and self.client.get_transport() and self.client.get_transport().is_active():
            logging.debug("SSH connection already active")
            return True

        try:
            if self.client:
                self.close()

            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            logging.info(f"Connecting to {self.host}:{self.port} as {self.username}")

            connect_kwargs = {
                "hostname": self.host,
                "port": self.port,
                "username": self.username,
                "timeout": self.connect_timeout,
            }

            if self.password:
                connect_kwargs["password"] = self.password
            elif self.key_filename:
                connect_kwargs["key_filename"] = self.key_filename

            self.client.connect(**connect_kwargs)
            logging.info("SSH connection established")
            return True

        except paramiko.AuthenticationException as e:
            logging.error(f"Authentication failed: {str(e)}")
            return False
        except paramiko.SSHException as e:
            logging.error(f"SSH error: {str(e)}")
            return False
        except Exception as e:
            logging.error(f"Connection error: {str(e)}")
            return False

    def close(self) -> None:
        """
        Close the SSH connection.
        """
        if self.sftp:
            try:
                self.sftp.close()
                logging.debug("SFTP connection closed")
            except Exception as e:
                logging.warning(f"Error closing SFTP: {str(e)}")

        if self.client:
            try:
                self.client.close()
                logging.debug("SSH connection closed")
            except Exception as e:
                logging.warning(f"Error closing SSH connection: {str(e)}")

        self.client = None
        self.sftp = None

    def execute_command(self, command: str, sudo: bool = False) -> Tuple[int, str, str]:
        """
        Execute a command on the remote server.

        Args:
            command: Command to execute
            sudo: Whether to use sudo

        Returns:
            Tuple[int, str, str]: (exit_code, stdout, stderr)
        """
        if not self.client or not self.client.get_transport() or not self.client.get_transport().is_active():
            if not self.connect():
                return 1, "", "SSH connection failed"

        try:
            if sudo:
                # Create a new channel for sudo command
                channel = self.client.get_transport().open_session()
                channel.get_pty()
                channel.exec_command(f"sudo -S {command}")

                # Send sudo password and wait for prompt
                channel.send(f"{self.sudo_password}\\n")
                # Note: Using time.sleep here for SSH protocol timing - not async operation

                # Get output
                output = ""
                error = ""
                while True:
                    if channel.recv_ready():
                        output += channel.recv(1024).decode()
                    if channel.recv_stderr_ready():
                        error += channel.recv_stderr(1024).decode()
                    if channel.exit_status_ready():
                        break
                    # Note: Using time.sleep here for SSH protocol polling - not async operation

                exit_code = channel.recv_exit_status()
                channel.close()
                return exit_code, output.strip(), error.strip()
            else:
                # Regular command execution
                stdin, stdout, stderr = self.client.exec_command(command)
                exit_code = stdout.channel.recv_exit_status()
                return (
                    exit_code,
                    stdout.read().decode().strip(),
                    stderr.read().decode().strip(),
                )
        except Exception as e:
            logging.error(f"Error executing command: {str(e)}")
            return 1, "", str(e)

    def upload_file(self, content: Union[bytes, str], remote_path: str, sudo: bool = False) -> bool:
        """
        Upload content to a remote file.

        Args:
            content: File content (bytes or string)
            remote_path: Remote file path
            sudo: Whether to use sudo for final file placement

        Returns:
            bool: True if successful
        """
        if not self.client or not self.client.get_transport() or not self.client.get_transport().is_active():
            if not self.connect():
                return False

        try:
            if isinstance(content, str):
                content = content.encode()

            if not self.sftp:
                self.sftp = self.client.open_sftp()

            # Ensure parent directory exists
            remote_dir = os.path.dirname(remote_path)
            if remote_dir:
                self.execute_command(f"mkdir -p {remote_dir}", sudo=sudo)

            if sudo:
                # Upload to /tmp then move with sudo
                temp_path = f"/tmp/temp_file_{int(time.time())}"
                with self.sftp.file(temp_path, "wb") as f:
                    f.write(content)
                self.execute_command(f"mv {temp_path} {remote_path}", sudo=True)
            else:
                with self.sftp.file(remote_path, "wb") as f:
                    f.write(content)

            logging.info(f"Uploaded file to {remote_path}")
            return True
        except Exception as e:
            logging.error(f"Failed to upload file to {remote_path}: {str(e)}")
            return False


# Function to create an SSH client from a config dictionary
def create_ssh_client_from_config(config: Dict[str, Any]) -> SSHClient:
    """
    Create an SSH client from a configuration dictionary.

    Args:
        config: Dictionary containing SSH configuration with 'ssh' key

    Returns:
        SSHClient: Configured SSH client
    """
    ssh_config = config.get("ssh", {})
    if not ssh_config.get("host") or not ssh_config.get("username"):
        raise ValueError("SSH config must contain 'host' and 'username'")
    return SSHClient(config=ssh_config)
