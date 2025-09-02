# PiControl Agent

PiControl Agent is a Python-based conversational assistant that executes real Linux commands on a remote Raspberry Pi via SSH, powered by local or remote Llama models. It lets you manage, inspect, and automate your Raspberry Pi from anywhere using natural language.

## Key Features

- Conversational to-command translation (LLM powered)
- Secure SSH execution (Paramiko) supporting password or key auth
- Tailscale support: seamless private access over your tailnet
- Rich Raspberry Pi management toolkit:
  - System info (CPU, memory, disk, OS, uptime, temperature)
  - Update / upgrade packages
  - Reboot / shutdown
  - Manage systemd services (status / restart)
  - List & kill processes
  - Install / remove packages
  - List USB & I2C devices
  - GPIO read / write (needs wiringPi / gpio util)
  - Pi camera photos (needs `raspistill`)
  - Cron: schedule / list / remove jobs
  - Network: ping + speed tests
  - Resource usage (disk, memory, CPU)
  - Tailscale status, IP, restart, version
- Pluggable tool pattern (easy to extend)
- Color-coded terminal style output
- Automatic Markdown session logging (every 5 prompt/response pairs)
- `.env` based credential & API key management

## Project Structure
```
llamatrama_agent/
├── agent.py              # Main conversational agent entrypoint
├── tools/
│   └── ssh_tool.py       # SSH command execution logic & helpers
├── plugins/              # Optional function/tool plugins
├── outputs/              # Markdown logs of prompt/response batches
├── web/                  # Simple web UI (Flask/FastAPI style entry in main.py)
├── requirements.txt      # Python dependencies
├── .env                  # API + SSH secrets (NOT committed)
└── README.md             # Documentation
```

## Quick Start
1. Clone repo & install deps:
   ```bash
   pip install -r requirements.txt
   ```
2. Create a `.env` file in `llamatrama_agent/` with (example):
   ```bash
   LLAMA_API_KEY=your_key_here
   SSH_HOST=100.x.y.z         # Use Tailscale IP if using Tailscale
   SSH_USER=pi
   SSH_PASSWORD=your_password # or omit if using key
   SSH_KEY_PATH=~/.ssh/id_rsa # optional
   ```
3. (Optional) On the Pi install utilities you plan to use:
   ```bash
   sudo apt update && sudo apt install -y wiringpi python3-picamera speedtest-cli
   ```
4. Run the agent locally:
   ```bash
   python agent.py
   ```
5. Chat in natural language, e.g.:
   > "Check CPU temperature and list the last 5 running processes"

## Tailscale Notes
If the Raspberry Pi is in your tailnet, obtain the IP with:
```bash
tailscale ip -4
```
Set that as `SSH_HOST` for secure access without opening ports. The agent can also request Tailscale service status, restart it, or report version.

## Logging
- Every 5 prompt/response exchanges are appended to a rotating Markdown file in `outputs/` (e.g. `session_1.md`).
- SSH command stdout/stderr are embedded for auditability.

## Extending
Add new operational capabilities by creating a module in `plugins/` that exposes a callable tool function. Register or auto-discover it in the agent (see existing examples like `duck_search.py`). Keep functions:
- Pure (side effects only via SSH where possible)
- Fast (avoid long blocking operations without streaming)
- Described with a clear docstring to help the model choose them

## Roadmap Ideas
- Structured JSON mode for stable downstream parsing
- WebSocket live command streaming
- Fine-grained RBAC on dangerous commands
- Automatic test coverage for new plugin tools
- Docker container packaging

## Safety Warning
This agent can run destructive commands on a real device. Review outputs carefully. Prefer read-only or diagnostic commands unless you're sure.

## Credits
Inspired by & extends concepts from PiControl (Raspberry Pi command & monitoring workflows) and general LLM tool-use agent patterns.
