# Llamatrama Agent

Llamatrama Agent is a Python-based conversational assistant that executes real Linux commands on a remote Kali Linux system via SSH, powered by Llama models. It is the second part of the symbolic warhead: Inspectallama (information gathering) and Executallama (command execution).

## Features
- Conversational command execution on a real remote Kali Linux system
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
2. Fill in `.env` with your Llama API key and SSH credentials.
3. Run the agent:
   ```bash
   python agent.py
   ```
4. Interact with the agent in natural language. Commands requiring shell execution will be run on the remote Kali system.

## Output Logging
- Every 5 prompt/response pairs are saved to a Markdown file in the `outputs/` folder (e.g., `session_1.md`).
- SSH command outputs are included in the logs for traceability.

## Example Output Log
See `outputs/session_1.md` for a sample of how prompts, responses, and SSH outputs are recorded.

## Credits
- Inspectallama: Information gathering
- Executallama: Command execution
- Llamatrama: The combined symbolic warhead

---
**Warning:** This agent interacts with a real remote system. Use caution with commands that may modify or delete files.
