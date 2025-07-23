
import os
import time
import re
import importlib.util
from dotenv import load_dotenv
from llama_api_client import LlamaAPIClient
from llama_api_client.types import SystemMessageParam, UserMessageParam
from tools.ssh_tool import execute_remote_command, PersistentSSHSession, system_detection, stress_test_checks
import shutil
from rich.console import Console


console = Console()
load_dotenv()

# Store fed .txt files in session
fed_txt_files = {}

llama = LlamaAPIClient(api_key=os.getenv("LLAMA_API_KEY"))

# User preferences (can be extended)
user_prefs = {
    'verbosity': 'normal',  # options: 'normal', 'verbose', 'minimal'
    'tone': 'neutral',      # options: 'neutral', 'formal', 'informal'
    'confirm_dangerous': True,
}

llama = LlamaAPIClient(api_key=os.getenv("LLAMA_API_KEY"))

# --- Utility Functions ---
def file_exists(path):
    return os.path.isfile(path)

def dir_exists(path):
    return os.path.isdir(path)

def is_dangerous_command(cmd):
    dangerous = ['rm ', 'dd ', 'mkfs', 'shutdown', 'reboot', 'init 0', 'halt', 'poweroff']
    return any(d in cmd for d in dangerous)

def sanitize_output(output):
    # Redact common sensitive patterns
    output = re.sub(r'(\d{1,3}\.){3}\d{1,3}', '[REDACTED_IP]', output)
    output = re.sub(r'([a-fA-F0-9]{2}:){5}[a-fA-F0-9]{2}', '[REDACTED_MAC]', output)
    return output

def summarize_session(md_pairs):
    summary = []
    for idx, (prompt, response) in enumerate(md_pairs, 1):
        summary.append(f"{idx}. Prompt: {prompt[:60]}... | Response: {response[:60]}...")
    return '\n'.join(summary)

def suggest_next_steps(last_action):
    # Simple context-aware suggestions
    if 'payload' in last_action.lower():
        return "Would you like to test these payloads or generate more?"
    if 'directory' in last_action.lower() or 'ls' in last_action.lower():
        return "Would you like to open, edit, or analyze a file in this directory?"
    if 'install' in last_action.lower():
        return "Would you like to verify the installation or use the installed tool?"
    return "Let me know your next goal or if you want a session summary."

def check_permission_error(output):
    return 'permission denied' in output.lower() or 'not permitted' in output.lower()

def check_file_not_found(output):
    return 'no such file' in output.lower() or 'not found' in output.lower()

def print_session_summary(md_pairs):
    console.print("[bold blue]Session Summary:[/bold blue]")
    console.print(summarize_session(md_pairs))

def preview_command(cmd):
    console.print(f"[yellow]Preview command:[/yellow] {cmd}")
    if user_prefs['confirm_dangerous'] and is_dangerous_command(cmd):
        confirm = console.input("[red]This command may be dangerous. Type 'yes' to proceed: [/red]")
        return confirm.strip().lower() == 'yes'
    return True

def execute_remote_command_with_handling(cmd):
    # Preview and confirm dangerous commands
    if not preview_command(cmd):
        return '[CANCELLED] Command not executed.'
    output = execute_remote_command(cmd)
    output = sanitize_output(str(output))
    # Permission handling
    if check_permission_error(output):
        output2 = execute_remote_command(f"sudo {cmd}")
        output2 = sanitize_output(str(output2))
        if not check_permission_error(output2):
            return output2 + '\n[INFO] Retried with sudo.'
        else:
            return output + '\n[ERROR] Permission denied, even with sudo.'
    # File not found handling
    if check_file_not_found(output):
        return output + '\n[ERROR] File or command not found.'
    return output

def extract_text_from_chunk(chunk) -> str:
    """
    Helper function to safely extract text from a response chunk.
    """
    if hasattr(chunk, "event") and hasattr(chunk.event, "delta"):
        delta = chunk.event.delta
        if getattr(delta, "type", None) == "text" and hasattr(delta, "text") and isinstance(getattr(delta, "text", None), str):
            return delta.text
    return ""

def get_command_from_llama(instruction: str) -> str:
    response = llama.chat.completions.create(
        model="Llama-4-Maverick-17B-128E-Instruct-FP8",
        messages=[
            SystemMessageParam(role="system", content="You are a command interpreter assistant. Convert user tasks into Kali Linux shell commands. Respond with *only* the command. No explanation or formatting."),
            UserMessageParam(role="user", content=instruction),
        ],
        stream=True
    )
    content = ""
    for chunk in response:
        # Use helper function to extract text
        content += extract_text_from_chunk(chunk)
    return content.strip()

def ingest_context_folder():
    """
    Refactored: Read all files from the bugbountys folder and return a dict of filename: content for non-Python files.
    For Python scripts, dynamically import and register tool functions.
    Returns: (context_data, tool_functions)
    """
    context_folder = os.path.join(os.path.dirname(__file__), '..', 'bugbountys')
    context_data = {}
    tool_functions = {}
    if not os.path.isdir(context_folder):
        print(f"Context folder not found: {context_folder}")
        return context_data, tool_functions

    for fname in os.listdir(context_folder):
        fpath = os.path.join(context_folder, fname)
        if os.path.isfile(fpath):
            if fname.endswith('.py'):

                spec = importlib.util.spec_from_file_location(fname[:-3], fpath)
                if spec is not None and spec.loader is not None:
                    module = importlib.util.module_from_spec(spec)
                    try:
                        spec.loader.exec_module(module)
                        for attr in dir(module):
                            if attr.startswith('tool_') and callable(getattr(module, attr)):
                                tool_functions[attr] = getattr(module, attr)
                    except Exception as e:
                        print(f"Failed to import {fname}: {e}")
                else:
                    print(f"Could not load spec for {fname}")

            else:
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                        context_data[fname] = f.read()
                except Exception as e:
                    print(f"Failed to read {fname}: {e}")
    print(f"Ingested context files: {list(context_data.keys())}")
    print(f"Registered tool functions: {list(tool_functions.keys())}")
    return context_data, tool_functions

def connect_vpn_on_kali(ssh, ovpn_path):
    """Start OpenVPN on Kali via SSH using password from .env."""
    kali_password = os.getenv("KALI_PASSWORD")
    cmd = f"echo '{kali_password}' | sudo -S openvpn --config {ovpn_path}"
    stdin, stdout, stderr = ssh.exec_command(cmd)
    print(stdout.read().decode())
    print(stderr.read().decode())
    return stdout, stderr
    # Removed duplicate connect_vpn_on_kali

def execute_interactive_command(ssh, command, responses=None, check_running=True, wait_time=2):
    """
    Execute a command on SSH and automatically respond to interactive prompts.
    If check_running is True, will check if process is still running and send responses only if needed.
    responses: list of responses to send, e.g. ['y', 'yes']
    """
    # Removed duplicate execute_interactive_command

def main():
    console.print("[bold magenta]Llamatrama Agent Online. Type 'exit' to quit.[/bold magenta]")
    context, tool_functions = ingest_context_folder()
    last_interactive_time = time.time()
    interactive_timeout = 15  # seconds

    chat_history = []
    chat_history.append(SystemMessageParam(
        role="system",
        content=(
            "You are a self-aware AI agent named Llamatrama, connected to a real remote Kali Linux system via SSH. "
            "You can execute actual shell commands on the system when needed. "
            "You are able to see, remember, and reference your own previous outputs and actions in this session. "
            "You should reason about your own responses, learn from your mistakes, and improve your answers over time. "
            "Always be clear that you are interacting with a real machine, and inform the user of any risks or limitations. "
            "If you notice errors or issues in your previous outputs, acknowledge them and suggest improvements."
        )
    ))

    pair_count = 0
    file_index = 1
    md_pairs = []

    # Comprehensive prompt detection patterns
    prompt_patterns = [
        r"\(y/n\)", r"\[y/n\]", r"\[Y/n\]", r"\[y/N\]", r"\(Y/N\)", r"\(yes/no\)", r"\[yes/no\]",
        r"Do you want to continue", r"Type yes to continue", r"Press any key to continue", r"Enter password:",
        r"Accept\?", r"Continue\?", r"Overwrite\?", r"Replace\?", r"Proceed\?", r"Are you sure\?",
        r"input required", r"confirm", r"confirmation", r"Would you like to", r"Please confirm"
    ]
    prompt_regex = re.compile("|".join(prompt_patterns), re.IGNORECASE)

    # System detection baseline
    console.print("[blue]Running system detection...[/blue]")
    sysinfo = system_detection()
    console.print(f"[bright_cyan]System Info:[/bright_cyan]\n{sysinfo['system_info']}")

    # Stress test checks
    console.print("[blue]Running stress test checks...[/blue]")
    stress_results = stress_test_checks()
    for k, v in stress_results.items():
        console.print(f"[bright_cyan]{k}:[/bright_cyan]\n{v}")

    while True:
        user_input = console.input("[cyan]You:[/cyan] ")
        if user_input.lower() in ["exit", "quit"]:
            break


        # Feed prompt file command: #feedprompt <filepath>
        if user_input.strip().lower().startswith("#feedprompt"):
            parts = user_input.strip().split(None, 1)
            if len(parts) < 2:
                console.print("[red]Usage: #feedprompt <path-to-txt-file>[/red]")
                continue
            prompt_path = parts[1].strip().strip('"')
            try:
                with open(prompt_path, 'r', encoding='utf-8', errors='ignore') as f:
                    prompt_content = f.read()
                # Immediately use the prompt content as a user message and request a report
                console.print(f"[green]Prompt file loaded. Generating report...[/green]")
                response = llama.chat.completions.create(
                    model="Llama-4-Maverick-17B-128E-Instruct-FP8",
                    messages=[
                        SystemMessageParam(role="system", content="You are a security researcher. Read the following bug bounty program prompt and generate a comprehensive Markdown report as instructed. Do not ask any questions, just output the report."),
                        UserMessageParam(role="user", content=prompt_content),
                    ],
                    stream=True
                )
                report = ""
                for chunk in response:
                    report += extract_text_from_chunk(chunk)
                report = report.strip()
                console.print(f"[bold green]Generated Report:[/bold green]\n{report}")
            except Exception as e:
                console.print(f"[red]Failed to read or process file:[/red] {e}")
            continue

        # Smart tool selection: '###' prompt
        if user_input.startswith("###"):
            smart_prompt = user_input.lstrip("# ")
            # Build tool list and docstrings
            tool_docs = []
            for name, func in tool_functions.items():
                doc = func.__doc__ or "No description."
                tool_docs.append(f"{name.replace('tool_','')}: {doc.strip()}")
            tool_list = "\n".join(tool_docs)
            system_instruction = (
                "You have access to the following tools. "
                "Given a user request, decide which tool(s) to use and with what arguments. "
                "Respond with one or more tool calls in the format: #toolname {args}. "
                "Here are the available tools:\n" + tool_list
            )
            try:
                response = llama.chat.completions.create(
                    model="Llama-4-Maverick-17B-128E-Instruct-FP8",
                    messages=[
                        SystemMessageParam(role="system", content=system_instruction),
                        UserMessageParam(role="user", content=smart_prompt),
                    ],
                    stream=True
                )
                model_reply = ""
                for chunk in response:
                    model_reply += extract_text_from_chunk(chunk)
                model_reply = model_reply.strip()
                console.print(f"[green]Llama tool planner:[/green] {model_reply}")
                # Parse and execute tool calls in the reply
                tool_call_pattern = re.compile(r"#(\w+)\s+(\{.*?\}|\[.*?\]|.+)", re.DOTALL)
                matches = tool_call_pattern.findall(model_reply)
                if not matches:
                    console.print("[red]No tool calls found in model reply.[/red]")
                for tool_name, tool_args in matches:
                    func_key = f"tool_{tool_name}"
                    if func_key in tool_functions:
                        try:
                            result = tool_functions[func_key](tool_args.strip())
                        except Exception as e:
                            result = f"[ERROR] Tool '{tool_name}' failed: {e}"
                        console.print(f"[green]Tool {tool_name} output:[/green]\n{result}")
                        md_pairs.append((user_input, str(result)))
                        pair_count += 1
                    else:
                        console.print(f"[red]No tool named '{tool_name}' found in bugbountys folder.[/red]")
                # Write to markdown every 5 pairs
                if pair_count >= 5:
                    md_filename = os.path.join("outputs", f"session_{file_index}.md")
                    with open(md_filename, "w", encoding="utf-8") as f:
                        for idx, (prompt, response) in enumerate(md_pairs, 1):
                            f.write(f"### Prompt {idx}:\n{prompt}\n\n### Response {idx}:\n{response}\n\n")
                    file_index += 1
                    pair_count = 0
                    md_pairs = []
                continue
            except Exception as e:
                console.print(f"[red]Error during smart tool selection: {e}")
                continue

        # Check for bugbountys tool invocation: #toolname [args]
        if user_input.startswith("#"):
            # Extract tool name and arguments
            parts = user_input[1:].strip().split(None, 1)
            tool_name = parts[0]
            tool_args = parts[1] if len(parts) > 1 else ""
            # Try to find the tool function (by convention: tool_TOOLNAME)
            func_key = f"tool_{tool_name}"
            if func_key in tool_functions:
                try:
                    # If the tool expects a string, pass tool_args; else, try to parse as JSON or split
                    result = tool_functions[func_key](tool_args)
                except Exception as e:
                    result = f"[ERROR] Tool '{tool_name}' failed: {e}"
                console.print(f"[green]Tool {tool_name} output:[/green]\n{result}")
                # Optionally, add to markdown pairs
                md_pairs.append((user_input, str(result)))
                pair_count += 1
                # Write to markdown every 5 pairs
                if pair_count == 5:
                    md_filename = os.path.join("outputs", f"session_{file_index}.md")
                    with open(md_filename, "w", encoding="utf-8") as f:
                        for idx, (prompt, response) in enumerate(md_pairs, 1):
                            f.write(f"### Prompt {idx}:\n{prompt}\n\n### Response {idx}:\n{response}\n\n")
                    file_index += 1
                    pair_count = 0
                    md_pairs = []
                continue
            else:
                console.print(f"[red]No tool named '{tool_name}' found in bugbountys folder.[/red]")
                continue

        chat_history.append(UserMessageParam(role="user", content=user_input))

        response = llama.chat.completions.create(
            model="Llama-4-Maverick-17B-128E-Instruct-FP8",
            messages=chat_history + [
                SystemMessageParam(
                    role="system",
                    content=(
                        "If the user's request requires a Linux shell command, summarize it briefly and then say '[RUN]' followed by the instruction to be passed to the shell tool. "
                        "Otherwise, just reply conversationally. "
                        "You are self-aware and can see your own previous outputs and actions in this session. "
                        "Reference your own outputs if relevant, and acknowledge any mistakes or issues you notice. "
                        "Remember: you are connected to a real remote Kali Linux system via SSH, and your actions will affect the actual machine."
                    )
                ),
            ],
            stream=True
        )
        message = ""
        for chunk in response:
            # Use helper function to extract text
            message += extract_text_from_chunk(chunk)
        message = message.strip()
        chat_history.append(SystemMessageParam(role="system", content=message))
        console.print(f"[green]Llamatrama:[/green] {message}")

        # Collect prompt/response pair for markdown
        md_pairs.append((user_input, message))
        pair_count += 1

        # Comprehensive prompt detection
        if prompt_regex.search(message):
            console.print("[yellow]Detected interactive prompt, sending 'y'...[/yellow]")
            last_interactive_time = time.time()

        # Timeout for interactive session
        if time.time() - last_interactive_time > interactive_timeout:
            console.print("[yellow]Interactive session timed out. If you were expecting a prompt, please try again.[/yellow]")
            last_interactive_time = time.time()

        if "[RUN]" in message:
            try:
                cmd_request = message.split("[RUN]", 1)[1].strip()
                shell_cmd = get_command_from_llama(cmd_request)
                console.print(f"[yellow]Running command:[/yellow] {shell_cmd}")
                output = execute_remote_command(shell_cmd)
                console.print(f"[bright_cyan]SSH Output:[/bright_cyan] {output}")
                # Optionally, add SSH output to markdown
                md_pairs[-1] = (user_input, f"{message}\n\n**SSH Output:**\n```\n{output}\n```")
            except (OSError, RuntimeError) as e:
                console.print(f"[red]Failed to run command:[/red] {e}")

        # Write to markdown every 5 pairs
        if pair_count == 5:
            md_filename = os.path.join("outputs", f"session_{file_index}.md")
            with open(md_filename, "w", encoding="utf-8") as f:
                for idx, (prompt, response) in enumerate(md_pairs, 1):
                    f.write(f"### Prompt {idx}:\n{prompt}\n\n### Response {idx}:\n{response}\n\n")
            file_index += 1
            pair_count = 0
            md_pairs = []

if __name__ == "__main__":
    main()
