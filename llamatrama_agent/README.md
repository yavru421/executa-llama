## Raspberry Pi Features

PiControl can do almost anything a user can do on the Pi, and more:

- System info (CPU, memory, disk, OS, uptime, temperature)
- Update/upgrade all packages
- Reboot or shutdown the Pi
- Manage systemd services (status, restart)
- List and kill processes
- Install/remove packages
- List USB and I2C devices
- GPIO read/write (requires wiringPi/gpio utility)
- Take photos with Pi camera (requires raspistill)
- Schedule, list, and remove cron jobs
- Ping and run speed tests
- Disk, memory, and CPU usage
- Tailscale management (status, IP, restart, version)

All features are available as agent commands and can be extended further.
# PiControl Agent

PiControl Agent is a Python-based conversational assistant that executes real Linux commands on a remote Raspberry Pi via SSH, powered by Llama models. It is designed for easy, conversational control and monitoring of your Raspberry Pi from anywhere.

- Tailscale support: Use your Pi's Tailscale IP for secure, private SSH access
- Conversational command execution on a real remote Raspberry Pi
- SSH integration using Paramiko (supports key and password authentication)
- Tool-use agent pattern with Llama model for natural language command translation
- Color-coded terminal output for clarity
- Logs every 5 prompt/response pairs to Markdown files in `outputs/`
- `.env` file for secure API and SSH credentials

## Project Structure

```
llamatrama_agent/
├── agent.py              # Main conversational agent
├── tools/
│   └── ssh_tool.py       # SSH command execution logic
├── outputs/              # Markdown logs of prompt/response pairs
│   └── session_1.md      # Example log file
├── logs/                 # (Reserved for future logs)
├── requirements.txt      # Python dependencies
├── .env                  # API key and SSH credentials
└── README.md             # Project documentation
```

## Usage
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Fill in `.env` with your Llama API key and SSH credentials. For Tailscale, set `SSH_HOST` to your Pi's Tailscale IP (find it with `tailscale ip` on the Pi).
## Tailscale Integration

If your Raspberry Pi is connected to your tailnet with Tailscale, you can use its Tailscale IP for SSH connections. This is more secure and works across networks without port forwarding.

You can also run Tailscale management commands from the agent, such as:
- Check Tailscale status
- Get Tailscale IP
- Restart Tailscale service
- Check Tailscale version

These are available as functions in the SSH tool module.
3. Run the agent:
   ```bash
   python agent.py
   ```
4. Interact with the agent in natural language. Commands requiring shell execution will be run on the remote Raspberry Pi.

## Output Logging
- Every 5 prompt/response pairs are saved to a Markdown file in the `outputs/` folder (e.g., `session_1.md`).
- SSH command outputs are included in the logs for traceability.

## Example Output Log
See `outputs/session_1.md` for a sample of how prompts, responses, and SSH outputs are recorded.

## Credits
- PiControl: Raspberry Pi command and monitoring agent

---
**Warning:** This agent interacts with a real Raspberry Pi. Use caution with commands that may modify or delete files.
