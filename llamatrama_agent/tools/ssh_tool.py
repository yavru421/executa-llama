import paramiko
import os
from dotenv import load_dotenv

load_dotenv()

SSH_HOST = os.getenv("SSH_HOST")
SSH_USER = os.getenv("SSH_USER")
SSH_KEY_PATH = os.getenv("SSH_KEY_PATH", os.path.expanduser("~/.ssh/id_rsa"))
SSH_PASSWORD = os.getenv("SSH_PASSWORD")

def execute_remote_command(command: str) -> str:
    if not SSH_HOST or not SSH_USER:
        raise ValueError("SSH_HOST and SSH_USER must be set in the .env file.")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    connected = False
    try:
        if SSH_KEY_PATH and os.path.exists(SSH_KEY_PATH):
            try:
                key = paramiko.RSAKey.from_private_key_file(SSH_KEY_PATH)
                ssh.connect(str(SSH_HOST), username=str(SSH_USER), pkey=key, timeout=10)
                connected = True
            except paramiko.AuthenticationException:
                pass
            except paramiko.SSHException as e:
                return f"SSH key authentication error: {e}"
            except FileNotFoundError as e:
                return f"SSH key file not found: {e}"
            except paramiko.PasswordRequiredException as e:
                return f"SSH key requires a password: {e}"
        if not connected and SSH_PASSWORD:
            try:
                ssh.connect(str(SSH_HOST), username=str(SSH_USER), password=SSH_PASSWORD, timeout=10)
                connected = True
            except paramiko.AuthenticationException as e:
                ssh.close()
                return f"Authentication failed: {e}"
            except Exception as e:
                ssh.close()
                return f"SSH password authentication error: {e}"
        if not connected:
            ssh.close()
            return "Authentication failed: No valid SSH key or password, or credentials are incorrect."
        try:
            _, stdout, stderr = ssh.exec_command(command)
            output = stdout.read().decode(errors="ignore")
            error = stderr.read().decode(errors="ignore")
            ssh.close()
            return output or error
        except Exception as e:
            ssh.close()
            return f"Command execution failed: {e}"
    except Exception as e:
        ssh.close()
        return f"SSH connection error: {e}"
