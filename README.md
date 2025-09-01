

![executa_llama](https://github.com/user-attachments/assets/18780f97-24f7-4b2d-afd2-4d112a6cd47f)

# ExecutaLlama (Llamatrama Agent)

> Conversational, web-based, and CLI control of your Raspberry Pi (or any Linux host) via SSH, powered by Llama models and Tailscale.

---

## Features
- **Web Dashboard**: Modern, step-by-step UI for device selection, planning, approval, and execution. Breadcrumbs and workflow banners guide the user.
- **CLI & API**: All features accessible via HTTP endpoints and CLI (curl, Python requests, etc).
- **SSH Control**: Run any Linux command on any device (including the Pi itself) via SSH, with support for Tailscale tailnet IPs.
- **Conversational Agent**: Llama-powered natural language to command translation and planning.
- **Session Logging**: All actions and responses are logged for traceability.
- **User Auth**: Secure login, password hashing, and file-backed user store.
- **Tailscale Integration**: Control any device on your tailnet, or run the server on the Pi and control itself.
- **Advanced Workflows**: Chain commands, manage files, run system checks, and more.

---

## Quick Start

### 1. Install dependencies
```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r llamatrama_agent/requirements.txt
```

### 2. Start the server
```bash
uvicorn llamatrama_agent.web.main:app --reload --port 8000
```

### 3. Open the dashboard
Visit [http://localhost:8000](http://localhost:8000) in your browser.

### 4. Login
Default credentials:
- Username: `admin`
- Password: `admin`

Change the password after first login for security.

---

## Web Dashboard Workflow

1. **Select Device**: Choose a device from your tailnet or add one manually (IP, SSH user, password/key).
2. **Plan (CourseCheck)**: Generate a step-by-step plan for your task using natural language.
3. **Review Plan**: See the planned commands and reasoning. Approve or edit as needed.
4. **Approve & Execute**: Run the approved command(s) on the device. Output is shown live.
5. **Session Log**: Review all actions and outputs for auditing.

Breadcrumbs and workflow banners guide you through each step.

---

## CLI/API Usage

All features are available via HTTP endpoints. Example (using curl):

```bash
# Login and save cookie
curl -X POST -F "username=admin" -F "password=admin" http://localhost:8000/login -c cookies.txt

# List devices
curl http://localhost:8000/devices -b cookies.txt

# Test SSH connection
curl -X POST http://localhost:8000/device-test -F "device_ip=192.168.1.23" -F "ssh_user=jdd" -F "ssh_password=" -b cookies.txt

# Run a command
curl -X POST http://localhost:8000/course-run -F "action=ssh:ls /home/pi" -F "device_ip=192.168.1.23" -F "ssh_user=jdd" -F "ssh_password=" -b cookies.txt
```

---

## Advanced SSH Workflows (Examples)

- Create and read a file:
   - `echo 'Hello from Llamatrama!' > /tmp/llama_test.txt`
   - `cat /tmp/llama_test.txt`
- List running processes: `ps aux | grep sshd`
- Check disk and memory: `df -h && free -m`
- Chain commands: `mkdir -p /tmp/llama_dir && mv /tmp/llama_test.txt /tmp/llama_dir/ && ls -l /tmp/llama_dir/`
- Download a file: `wget -O /tmp/llama_download.txt https://www.example.com`

---

## Running on the Pi (Self-Control)

You can run the server directly on your Raspberry Pi and control it via the dashboard or API:

1. Start the server on the Pi (see above).
2. Use `localhost`, `127.0.0.1`, or the Pi's Tailscale IP as the device IP.
3. All SSH commands will run on the same Pi.

You can also control the Pi from any other device on your tailnet using its Tailscale IP.

---

## Security & Auth

- Passwords are hashed and stored in `users.json`.
- Change the default admin password after first login.
- All SSH actions require authentication.
- Tailscale integration is recommended for secure, private networking.

---

## Project Structure

```
llamatrama_agent/
├── agent.py              # Main conversational agent
├── web/                  # Web dashboard (FastAPI, HTML, JS, CSS)
├── tools/                # SSH and other tool logic
├── plugins/              # Extendable agent tools
├── outputs/              # Markdown logs of prompt/response pairs
├── requirements.txt      # Python dependencies
└── README.md             # Project documentation
```

---

## Contributing & Credits

- Built by yavru421 and contributors.
- Powered by Llama models, FastAPI, Paramiko, Tailscale, and more.

---

**Warning:** This agent interacts with real devices. Use caution with commands that may modify or delete files.
# Trigger workflow
