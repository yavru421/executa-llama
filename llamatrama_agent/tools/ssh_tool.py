# --- Llama Grab: Tailscale File Send to /llama_grab ---
def llama_grab_send(session, filename, destination):
    """
    Send a file from /llama_grab on the Pi to /llama_grab on another tailnet device using Tailscale file send.
    filename: Name of the file in /llama_grab
    destination: Tailscale device name or IP (as shown in 'tailscale status')
    """
    src_path = f"/llama_grab/{filename}"
    # The receiving device will be prompted to save to /llama_grab
    cmd = f"tailscale file send {src_path} {destination}"
    return session.send_command(cmd)
# --- Tailscale File Send ---
def tailscale_file_send(session, file_path, destination):
    """
    Send a file from the Pi to another device on the tailnet using Tailscale's file send feature.
    file_path: Path to the file on the Pi
    destination: Tailscale device name or IP (as shown in 'tailscale status')
    """
    cmd = f"tailscale file send {file_path} {destination}"
    return session.send_command(cmd)
# --- Diagnostics/Test Suite ---
def pi_diagnostics(session):
    """
    Run a suite of diagnostic commands to verify Pi connectivity and core features.
    Returns a dict of results.
    """
    results = {}
    try:
        results['system_info'] = pi_system_info(session)
        results['disk_usage'] = pi_disk_usage(session)
        results['memory_usage'] = pi_memory_usage(session)
        results['cpu_temp'] = pi_cpu_temp(session)
        results['uptime'] = pi_uptime(session)
        results['tailscale_status'] = tailscale_status(session)
        results['tailscale_ip'] = tailscale_ip(session)
        results['service_ssh'] = pi_service_status(session, 'ssh')
        results['list_processes'] = pi_list_processes(session)
        results['list_usb'] = pi_list_usb_devices(session)
        results['list_cron'] = pi_list_cron(session)
    except Exception as e:
        results['error'] = str(e)
    return results
# --- Raspberry Pi Management Features ---

def pi_system_info(session):
    """Get detailed system information (CPU, memory, disk, OS, uptime)."""
    cmd = "uname -a && lsb_release -a && uptime && free -h && df -h && vcgencmd measure_temp"
    return session.send_command(cmd)

def pi_update_upgrade(session):
    """Update and upgrade all packages on the Pi."""
    cmd = "sudo apt-get update && sudo apt-get upgrade -y"
    return session.send_command(cmd)

def pi_reboot(session):
    """Reboot the Raspberry Pi."""
    return session.send_command("sudo reboot")

def pi_shutdown(session):
    """Shutdown the Raspberry Pi."""
    return session.send_command("sudo shutdown now")

def pi_service_status(session, service):
    """Get the status of a systemd service (e.g., 'ssh', 'tailscaled')."""
    return session.send_command(f"systemctl status {service}")

def pi_service_restart(session, service):
    """Restart a systemd service (e.g., 'ssh', 'tailscaled')."""
    return session.send_command(f"sudo systemctl restart {service}")

def pi_list_processes(session):
    """List running processes."""
    return session.send_command("ps aux | head -30")

def pi_kill_process(session, pid):
    """Kill a process by PID."""
    return session.send_command(f"kill {pid}")

def pi_install_package(session, package):
    """Install a package via apt."""
    return session.send_command(f"sudo apt-get install -y {package}")

def pi_remove_package(session, package):
    """Remove a package via apt."""
    return session.send_command(f"sudo apt-get remove -y {package}")

def pi_list_usb_devices(session):
    """List connected USB devices."""
    return session.send_command("lsusb")

def pi_list_i2c_devices(session):
    """List I2C devices (requires i2c-tools)."""
    return session.send_command("i2cdetect -y 1")

def pi_gpio_read(session, pin):
    """Read a GPIO pin (requires gpio utility)."""
    return session.send_command(f"gpio read {pin}")

def pi_gpio_write(session, pin, value):
    """Write to a GPIO pin (requires gpio utility)."""
    return session.send_command(f"gpio write {pin} {value}")

def pi_take_photo(session, filename="image.jpg"):
    """Take a photo with the Pi camera (requires raspistill)."""
    return session.send_command(f"raspistill -o {filename}")

def pi_schedule_task(session, cron_line):
    """Add a cron job (provide full cron line, e.g., '* * * * * command')."""
    return session.send_command(f'(crontab -l; echo "{cron_line}") | crontab -')

def pi_list_cron(session):
    """List current user's cron jobs."""
    return session.send_command("crontab -l")

def pi_remove_cron(session, pattern):
    """Remove cron jobs matching a pattern."""
    return session.send_command(f'crontab -l | grep -v "{pattern}" | crontab -')

def pi_ping(session, target):
    """Ping a target from the Pi."""
    return session.send_command(f"ping -c 4 {target}")

def pi_speedtest(session):
    """Run a speed test (requires speedtest-cli)."""
    return session.send_command("speedtest-cli")

def pi_disk_usage(session):
    """Show disk usage details."""
    return session.send_command("df -h")

def pi_memory_usage(session):
    """Show memory usage details."""
    return session.send_command("free -h")

def pi_cpu_temp(session):
    """Show CPU temperature."""
    return session.send_command("vcgencmd measure_temp")

def pi_uptime(session):
    """Show system uptime."""
    return session.send_command("uptime")
class SSHSessionManager:
    """
    Manages multiple persistent SSH sessions to a Raspberry Pi (optionally with tmux).
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

SSH_HOST = os.getenv("SSH_HOST")  # Set this to your Pi's Tailscale IP for secure tailnet access
# --- Tailscale Management Commands ---
def tailscale_status(session):
    """Get the status of Tailscale on the Raspberry Pi."""
    return session.send_command("tailscale status")

def tailscale_ip(session):
    """Get the Tailscale IP address of the Raspberry Pi."""
    return session.send_command("tailscale ip")

def tailscale_restart(session):
    """Restart the Tailscale service on the Raspberry Pi."""
    return session.send_command("sudo systemctl restart tailscaled")

def tailscale_version(session):
    """Get the installed Tailscale version."""
    return session.send_command("tailscale version")


from typing import Optional

def tailscale_funnel_create(session, name: str, port: int, hostname: Optional[str] = None, proto: str = 'tcp', target_port: Optional[int] = None):
    """
    Create a Tailscale Funnel on the remote device via the tailscale CLI.
    - name: friendly funnel name
    - port: local port to expose
    - hostname: optional custom hostname
    - proto: protocol (tcp/udp)
    - target_port: if different from port on the device
    Returns the CLI output as string.
    """
    cmd = f"sudo tailscale funnel create --name {name} --port {port} --proto {proto}"
    if target_port:
        cmd += f" --target-port {target_port}"
    if hostname:
        cmd += f" --hostname {hostname}"
    return session.send_command(cmd, timeout=30)


def tailscale_funnel_list(session, json_output: bool = True):
    """
    List funnels on the remote device. If json_output is True, attempt to use --json and parse.
    Returns raw output (string) or parsed JSON (stringified) depending on tailscale support.
    """
    if json_output:
        out = session.send_command("sudo tailscale funnel list --json", timeout=20)
        # Some tailscale versions may not support --json; fall back
        if not out or 'unknown flag' in out.lower() or 'unrecognized' in out.lower():
            out = session.send_command("sudo tailscale funnel list", timeout=20)
        return out
    else:
        return session.send_command("sudo tailscale funnel list", timeout=20)


def tailscale_funnel_delete(session, identifier: str):
    """
    Delete a funnel by ID or name on the remote device.
    """
    cmd = f"sudo tailscale funnel delete {identifier}"
    return session.send_command(cmd, timeout=20)
SSH_USER = os.getenv("SSH_USER")
SSH_KEY_PATH = os.getenv("SSH_KEY_PATH", os.path.expanduser("~/.ssh/id_rsa"))
SSH_PASSWORD = os.getenv("SSH_PASSWORD")

class PersistentSSHSession:
    """
    Maintains a persistent SSH shell session using Paramiko invoke_shell().
    Allows command chaining, stateful execution, and interactive prompt handling.
    """
    def __init__(self, host=None, user=None, password=None, key_path=None):
        self.ssh = paramiko.SSHClient()
        self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.connected = False
        self.shell = None
        self.host = host or SSH_HOST
        self.user = user or SSH_USER
        self.password = password or SSH_PASSWORD
        self.key_path = key_path or SSH_KEY_PATH
        self._connect()

    def _connect(self):
        try:
            if self.key_path and os.path.exists(self.key_path):
                try:
                    key = paramiko.RSAKey.from_private_key_file(self.key_path)
                    self.ssh.connect(str(self.host), username=str(self.user), pkey=key, timeout=10)
                    self.connected = True
                except paramiko.PasswordRequiredException as e:
                    raise RuntimeError(f"SSH key requires a password: {e}") from e
                except paramiko.AuthenticationException:
                    pass
                except paramiko.SSHException as e:
                    raise RuntimeError(f"SSH key authentication error: {e}") from e
                except FileNotFoundError as e:
                    raise RuntimeError(f"SSH key file not found: {e}") from e
            if not self.connected and self.password:
                try:
                    self.ssh.connect(str(self.host), username=str(self.user), password=self.password, timeout=10)
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
    Run system detection commands and return baseline info for Raspberry Pi.
    """
    session = PersistentSSHSession()
    cmd = "uname -a && whoami && pwd && hostname && ip addr"
    output = session.send_command(cmd)
    session.close()
    return {"system_info": output}

def stress_test_checks() -> dict:
    """
    Run stress test commands for Raspberry Pi system health and concurrency.
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
