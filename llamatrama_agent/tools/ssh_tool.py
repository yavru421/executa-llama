class SSHSessionManager:
    """
    Manages multiple persistent SSH sessions (optionally with tmux).
    """
    def __init__(self):
        self.sessions = {}

    def create_session(self, name=None, use_tmux=False):
        session = PersistentSSHSession()
        if use_tmux and name:
            tmux_cmd = f"tmux new -As {name}"
            session.send_command(tmux_cmd)
        self.sessions[name or str(len(self.sessions)+1)] = session
        return session

    def get_session(self, name):
        return self.sessions.get(name)

    def close_session(self, name):
        session = self.sessions.pop(name, None)
        if session:
            session.close()

    def list_sessions(self):
        return list(self.sessions.keys())

def browse_files(session, path="."):
    """List files and directories at the given path."""
    cmd = f"ls -al {path}"
    return session.send_command(cmd)

def read_file(session, filepath):
    """Read contents of a file."""
    cmd = f"cat {filepath}"
    return session.send_command(cmd)

def edit_file(session, filepath, new_content):
    """Overwrite file with new content using echo and heredoc."""
    # Use heredoc for multi-line content
    heredoc = f"cat <<'EOF' > {filepath}\n{new_content}\nEOF"
    return session.send_command(heredoc)

def create_file(session, filepath, content=""):
    """Create a new file with optional content."""
    if content:
        return edit_file(session, filepath, content)
    else:
        cmd = f"touch {filepath}"
        return session.send_command(cmd)

def delete_file(session, filepath):
    """Delete a file."""
    cmd = f"rm -f {filepath}"
    return session.send_command(cmd)

def create_directory(session, dirpath):
    """Create a new directory."""
    cmd = f"mkdir -p {dirpath}"
    return session.send_command(cmd)

def delete_directory(session, dirpath):
    """Delete a directory and its contents."""
    cmd = f"rm -rf {dirpath}"
    return session.send_command(cmd)

def move_file(session, src, dest):
    """Move or rename a file."""
    cmd = f"mv {src} {dest}"
    return session.send_command(cmd)

def copy_file(session, src, dest):
    """Copy a file."""
    cmd = f"cp {src} {dest}"
    return session.send_command(cmd)
import paramiko
import os
import threading  # Removed, not used
import time
from dotenv import load_dotenv

load_dotenv()

SSH_HOST = os.getenv("SSH_HOST")
SSH_USER = os.getenv("SSH_USER")
SSH_KEY_PATH = os.getenv("SSH_KEY_PATH", os.path.expanduser("~/.ssh/id_rsa"))
SSH_PASSWORD = os.getenv("SSH_PASSWORD")

class PersistentSSHSession:
    """
    Maintains a persistent SSH shell session using Paramiko invoke_shell().
    Allows command chaining, stateful execution, and interactive prompt handling.
    """
    def __init__(self):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.connected = False
        self.shell = None
        self._connect()

    def _connect(self):
        try:
            if SSH_KEY_PATH and os.path.exists(SSH_KEY_PATH):
                try:
                    key = paramiko.RSAKey.from_private_key_file(SSH_KEY_PATH)
                    self.ssh.connect(str(SSH_HOST), username=str(SSH_USER), pkey=key, timeout=10)
                    self.connected = True
                except paramiko.PasswordRequiredException as e:
                    raise RuntimeError(f"SSH key requires a password: {e}") from e
                except paramiko.AuthenticationException:
                    pass
                except paramiko.SSHException as e:
                    raise RuntimeError(f"SSH key authentication error: {e}") from e
                except FileNotFoundError as e:
                    raise RuntimeError(f"SSH key file not found: {e}") from e
            if not self.connected and SSH_PASSWORD:
                try:
                    self.ssh.connect(str(SSH_HOST), username=str(SSH_USER), password=SSH_PASSWORD, timeout=10)
                    self.connected = True
                except paramiko.AuthenticationException as e:
                    self.ssh.close()
                    raise RuntimeError(f"Authentication failed: {e}") from e
                except paramiko.SSHException as e:
                    self.ssh.close()
                    raise RuntimeError(f"SSH password authentication error: {e}") from e
            if not self.connected:
                self.ssh.close()
                raise RuntimeError("Authentication failed: No valid SSH key or password, or credentials are incorrect.")
            self.shell = self.ssh.invoke_shell()
            time.sleep(1)  # Let shell initialize
            self._flush_shell()
        except Exception as e:
            self.ssh.close()
            raise RuntimeError(f"SSH connection error: {e}")

    def _flush_shell(self):
        """Flush any initial shell output."""
        if self.shell and self.shell.recv_ready():
            self.shell.recv(4096)

    def close(self):
        if self.shell:
            self.shell.close()
        self.ssh.close()

    def send_command(self, command, responses=None, timeout=10, expect_prompt=None):
        """
        Send a command to the persistent shell, handle interactive prompts, and return output.
        responses: list of responses to send if prompt detected.
        expect_prompt: regex pattern to match prompt.
        """
        if not self.shell:
            raise RuntimeError("SSH shell not initialized.")
        self.shell.send(command + '\n')
        output = ""
        start_time = time.time()
        while True:
            if self.shell and self.shell.recv_ready():
                chunk = self.shell.recv(4096).decode(errors="ignore")
                output += chunk
                # If prompt detected, send responses
                if expect_prompt and responses:
                    import re
                    if re.search(expect_prompt, chunk, re.IGNORECASE):
                        for resp in responses:
                            self.shell.send(resp + '\n')
                            time.sleep(0.5)
            if time.time() - start_time > timeout:
                break
            time.sleep(0.2)
        return output

def execute_remote_command(command: str, responses=None, validate=True) -> dict:
    """
    Execute a command with chaining, validation, and feedback loop.
    Returns dict: {output, error, status, attempted_commands}
    """
    session = PersistentSSHSession()
    attempted = []
    output = ""
    error = ""
    status = "success"
    # Command chaining logic
    chained_cmd = (
        f"{command} || echo '[ERROR] Command failed'"
    )
    attempted.append(chained_cmd)
    try:
        result = session.send_command(chained_cmd, responses=responses)
        output = result
        # Improved response validation
        if validate:
            error_keywords = [
                "Permission denied", "command not found", "not recognized", "No such file or directory",
                "Failed", "E:", "error:", "ERROR:", "Operation not permitted", "Could not", "is not installed"
            ]
            if any(kw in output for kw in error_keywords):
                error = next(kw for kw in error_keywords if kw in output)
                status = "error"
            elif "[ERROR]" in output:
                # Only set error if output is empty or contains error keywords
                if not output.strip() or any(kw in output for kw in error_keywords):
                    error = "Command failed."
                    status = "error"
            elif not output.strip():
                # Retry with verbosity
                verbose_cmd = f"{command} -v || {command} --verbose || echo '[ERROR] Verbose failed'"
                attempted.append(verbose_cmd)
                output = session.send_command(verbose_cmd, responses=responses)
                if not output.strip():
                    error = "No output returned."
                    status = "error"
        session.close()
    except RuntimeError as e:
        error = str(e)
        status = "error"
        session.close()
    return {
        "output": output,
        "error": error,
        "status": status,
        "attempted_commands": attempted
    }

def system_detection() -> dict:
    """
    Run system detection commands and return baseline info.
    """
    session = PersistentSSHSession()
    cmd = "uname -a && whoami && pwd && hostname && ip addr"
    output = session.send_command(cmd)
    session.close()
    return {"system_info": output}

def stress_test_checks() -> dict:
    """
    Run stress test commands for system health and concurrency.
    """
    session = PersistentSSHSession()
    checks = {
        "background_ping": "ping -c 4 8.8.8.8 &",
        "cpu": "top -b -n1 | head -20",
        "memory": "free -h",
        "disk": "df -h",
        "logs": "journalctl -n 20",
        "concurrent_ls": "ls /tmp & ls /var & ls /home &"
    }
    results = {}
    for k, v in checks.items():
        results[k] = session.send_command(v)
    session.close()
    return results
