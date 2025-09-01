# The above code is importing the `json` module in Python, which provides functions for encoding and
# decoding JSON data.
import json

import os
import time
import re
import importlib.util
import subprocess
import sys
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


def run_tool_safely(tool_name, tool_args, timeout=10):
    """Run a registered tool safely. Try subprocess execution using the module path first
    (to isolate imports and allow timeouts). If that fails, fall back to in-process call.
    Returns a string result.
    """
    func_key = f"tool_{tool_name}"
    # Attempt subprocess if module path available
    g = globals()
    tool_funcs = g.get('tool_functions', {})
    tool_module_paths = g.get('tool_module_paths', {})
    module_path = tool_module_paths.get(func_key)
    if module_path and os.path.exists(module_path):
        try:
            # Run python -c to import the module and call the tool function
            runner = [sys.executable, "-c",
                      ("import json, sys, importlib.util; "
                       f"spec=importlib.util.spec_from_file_location('m','{module_path.replace('\\','\\\\')}'); "
                       "m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m); "
                       "res = m." + func_key + "(sys.argv[1] if len(sys.argv)>1 else '') ; print(res)")]
            proc = subprocess.run(runner + [tool_args], capture_output=True, text=True, timeout=timeout)
            if proc.returncode == 0:
                return proc.stdout.strip() or proc.stderr.strip()
            return proc.stdout.strip() or proc.stderr.strip() or f"[ERROR] Non-zero exit: {proc.returncode}"
        except subprocess.TimeoutExpired:
            return f"[ERROR] Tool '{tool_name}' timed out after {timeout}s"
        except Exception as e:
            # Fall through to in-process
            pass

    # Fallback: call in-process if available
    if func_key in tool_funcs:
        try:
            return tool_funcs[func_key](tool_args)
        except Exception as e:
            return f"[ERROR] Tool '{tool_name}' failed in-process: {e}"
    return f"[ERROR] Tool '{tool_name}' not found"

def execute_remote_command_with_handling(cmd):
    # Preview and confirm dangerous commands
    if not preview_command(cmd):
        return '[CANCELLED] Command not executed.'
    res = execute_remote_command(cmd)
    output = sanitize_output(str(res.get('output') if isinstance(res, dict) else res))
    # Permission handling
    if check_permission_error(output):
        res2 = execute_remote_command(f"sudo {cmd}")
        output2 = sanitize_output(str(res2.get('output') if isinstance(res2, dict) else res2))
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


def summarize_and_respond(user_prompt: str, context_text: str = "") -> str:
    """
    Ask the Llama model to summarize recent actions (context_text) and then respond to the user's prompt
    with a brief explanation of what was done and an answer to the user's request.
    Returns the combined summary + response text.
    """
    system = SystemMessageParam(role="system", content=(
        "You are a concise assistant that: 1) summarizes what actions were taken recently, "
        "based on the provided context, and 2) responds to the user's prompt with next steps or an answer. "
        "Keep the summary short (2-6 sentences), then provide a clear response to the user's prompt."
    ))
    user_msg = UserMessageParam(role="user", content=(f"Context:\n{context_text}\n\nUser prompt: {user_prompt}\n\nPlease summarize what was done and then answer the prompt."))
    try:
        resp = llama.chat.completions.create(
            model="Llama-4-Scout-17B-16E-Instruct-FP8",
            messages=[system, user_msg],
            stream=True
        )
        out = ""
        for chunk in resp:
            out += extract_text_from_chunk(chunk)
        return out.strip()
    except Exception as e:
        return f"[LLM ERROR] {e}"


def plan_course(conversation_text: str) -> str:
    """
    Produce a 5-step course plan (prompts + actions) based on the conversation_text.
    Returns a JSON-like string (preferably valid JSON array) describing the next 5 prompts and SSH actions.
    Each item should be an object: {"prompt": "...", "action": "ssh:..."} or similar.
    """
    system = SystemMessageParam(role="system", content=(
        "You are a planning assistant. Given the conversation so far, produce a clear, actionable plan of the next 5 steps. "
        "Each step must be an object with keys: 'prompt' (what to ask the user/LLM) and 'action' (what to execute, prefixed with 'ssh:' if a shell command). "
        "Return ONLY a JSON array with exactly 5 items. Keep entries short and executable."
    ))
    user_msg = UserMessageParam(role="user", content=(f"Conversation:\n{conversation_text}\n\nPlease return a JSON array of 5 steps."))
    try:
        resp = llama.chat.completions.create(
            model="Llama-4-Maverick-17B-128E-Instruct-FP8",
            messages=[system, user_msg],
            stream=True
        )
        out = ""
        for chunk in resp:
            out += extract_text_from_chunk(chunk)
        return out.strip()
    except Exception as e:
        return f"[LLM ERROR] {e}"


def aggregate_agents(actions: list, user_prompt: str = "") -> str:
    """
    Aggregate a list of agent actions (strings) and produce a single coherent response that
    summarizes what the agents did and answers the user's prompt in the context of those actions.
    """
    system = SystemMessageParam(role="system", content=(
        "You are the coordinator agent. Given a list of actions from different sub-agents, "
        "summarize concisely what each agent did (one line each), then provide a short unified "
        "recommendation or answer to the user's follow-up prompt. Keep it structured and actionable."
    ))
    # Build the content for the model
    actions_text = "\n".join(f"- {a}" for a in actions)
    user_content = f"Actions:\n{actions_text}\n\nUser follow-up: {user_prompt}\n\nPlease produce: 1) A 3-5 line summary of actions, 2) A concise answer to the follow-up, and 3) Next steps (bullet list)."
    user_msg = UserMessageParam(role="user", content=user_content)
    try:
        resp = llama.chat.completions.create(
            model="Llama-4-Scout-17B-16E-Instruct-FP8",
            messages=[system, user_msg],
            stream=True
        )
        out = ""
        for chunk in resp:
            out += extract_text_from_chunk(chunk)
        return out.strip()
    except Exception as e:
        return f"[LLM ERROR] {e}"

def ingest_context_folder():
    """
    Refactored: Read all files from the plugins folder and return a dict of filename: content for non-Python files.
    For Python scripts, dynamically import and register tool functions.
    Returns: (context_data, tool_functions)
    """
    # plugins are located in the same package directory under 'plugins'
    context_folder = os.path.join(os.path.dirname(__file__), 'plugins')
    context_data = {}
    tool_functions = {}
    tool_module_paths = {}
    if not os.path.isdir(context_folder):
        print(f"Context folder not found: {context_folder}")
        return context_data, tool_functions, {}

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
                                # store absolute module file path for safe subprocess execution
                                tool_module_paths[attr] = os.path.abspath(fpath)
                    except Exception as e:
                        print(f"Failed to import {fname}: {e}")
                else:
                    print(f"Could not load spec for {fname}")
            # Ignore .txt files related to bug bounty prompts
            elif fname.endswith('.txt'):
                if fname == 'bounty_one.txt':
                    print(f"Ignoring bug bounty prompt file: {fname}")
                    continue
                # For any other .txt, include as context
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                        context_data[fname] = f.read()
                except Exception as e:
                    print(f"Failed to read {fname}: {e}")
            else:
                try:
                    with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                        context_data[fname] = f.read()
                except Exception as e:
                    print(f"Failed to read {fname}: {e}")
    print(f"Ingested context files: {list(context_data.keys())}")
    print(f"Registered tool functions: {list(tool_functions.keys())}")
    return context_data, tool_functions, tool_module_paths


## Removed connect_vpn_on_kali and execute_interactive_command (Kali/bug bounty specific)

def load_persistent_memory(memory_path="persistent_memory.json"):
    if os.path.exists(memory_path):
        try:
            with open(memory_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Convert dicts to SystemMessageParam/UserMessageParam objects
            history = []
            for msg in data:
                if msg.get("role") == "system":
                    history.append(SystemMessageParam(**msg))
                else:
                    history.append(UserMessageParam(**msg))
            return history
        except Exception as e:
            print(f"Failed to load persistent memory: {e}")
    return []

def save_persistent_memory(chat_history, memory_path="persistent_memory.json"):
    try:
        # Convert message objects to dicts
        data = [msg.__dict__ for msg in chat_history]
        with open(memory_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Failed to save persistent memory: {e}")

def main():
    console.print("[bold magenta]Llamatrama Agent Online. Type 'exit' to quit.[/bold magenta]")
    context, tool_functions, tool_module_paths = ingest_context_folder()
    last_interactive_time = time.time()
    interactive_timeout = 15  # seconds

    chat_history = load_persistent_memory()
    if not chat_history:
        chat_history.append(SystemMessageParam(
            role="system",
            content=(
                "You are PiControl, a friendly, conversational, and helpful AI assistant connected to a real Raspberry Pi via SSH. "
                "You can execute real shell commands, remember important details, and keep track of ongoing conversations. "
                "Speak naturally, ask clarifying questions if needed, and use a warm, approachable tone. "
                "If you make a mistake, acknowledge it and suggest improvements. "
                "You have persistent memory: you can recall facts, preferences, and previous conversations from past sessions. "
                "Always be clear about your capabilities and any risks when running commands. "
                "Your goal is to make the user's experience smooth, safe, and enjoyable."
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

    # Optional: System detection and stress test
    run_checks = console.input("[yellow]Run system detection and stress test checks at startup? (y/n): [/yellow]").strip().lower()
    if run_checks == 'y':
        console.print("[blue]Running system detection...[/blue]")
        sysinfo = system_detection()
        console.print(f"[bright_cyan]System Info:[/bright_cyan]\n{sysinfo['system_info']}")
        console.print("[blue]Running stress test checks...[/blue]")
        stress_results = stress_test_checks()
        for k, v in stress_results.items():
            console.print(f"[bright_cyan]{k}:[/bright_cyan]\n{v}")
    else:
        console.print("[green]Startup checks skipped. You can run them anytime with #diagnostics or by request.[/green]")

    while True:
        user_input = console.input("[cyan]You:[/cyan] ")
        if user_input.lower() in ["exit", "quit"]:
            break



        # Save persistent memory after every user input
        save_persistent_memory(chat_history)

        # Feed prompt file command: #feedprompt <filepath>
        if user_input.strip().lower().startswith("#feedprompt"):
            parts = user_input.strip().split(None, 1)
            if len(parts) < 2:
                console.print("[red]Usage: #feedprompt <path-to-txt-file>[/red]")
                continue
            prompt_path = parts[1].strip().strip('"')
            # Bug bounty prompt logic removed; not relevant for Raspberry Pi control
            console.print("[yellow]Bug bounty prompt logic removed in PiControl refactor.[/yellow]")
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
                            result = run_tool_safely(tool_name, tool_args.strip(), timeout=10)
                        except Exception as e:
                            result = f"[ERROR] Tool '{tool_name}' failed: {e}"
                        console.print(f"[green]Tool {tool_name} output:[/green]\n{result}")
                        md_pairs.append((user_input, str(result)))
                        pair_count += 1
                    else:
                        console.print(f"[red]No tool named '{tool_name}' found in plugins folder.[/red]")
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

        # Diagnostics command: #diagnostics
        if user_input.strip().lower() == "#diagnostics":
            from tools.ssh_tool import PersistentSSHSession, pi_diagnostics
            session = PersistentSSHSession()
            console.print("[blue]Running full Pi diagnostics...[/blue]")
            results = pi_diagnostics(session)
            session.close()
            for k, v in results.items():
                console.print(f"[bold green]{k}:[/bold green]\n{v}\n")
            md_pairs.append((user_input, str(results)))
            pair_count += 1
            if pair_count == 5:
                md_filename = os.path.join("outputs", f"session_{file_index}.md")
                with open(md_filename, "w", encoding="utf-8") as f:
                    for idx, (prompt, response) in enumerate(md_pairs, 1):
                        f.write(f"### Prompt {idx}:\n{prompt}\n\n### Response {idx}:\n{response}\n\n")
                file_index += 1
                pair_count = 0
                md_pairs = []
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
                    # Run tool via safe runner (subprocess with timeout or fallback)
                    result = run_tool_safely(tool_name, tool_args, timeout=10)
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
                console.print(f"[red]No tool named '{tool_name}' found in plugins folder.[/red]")
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
                        "Remember: you are connected to a real remote Raspberry Pi via SSH, and your actions will affect the actual device."
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

        # Allow the model to call tools at its discretion anywhere in its reply using the
        # syntax: #toolname {json} or #toolname args. If tool calls are present, execute them,
        # append the outputs to the conversation, and ask the model to continue (one follow-up pass).
        tool_call_pattern = re.compile(r"#(\w+)\s+(\{.*?\}|\[.*?\]|.+)", re.DOTALL)
        matches = tool_call_pattern.findall(message)
        if matches:
            for tool_name, tool_args in matches:
                func_key = f"tool_{tool_name}"
                if func_key in tool_functions:
                    try:
                        result = run_tool_safely(tool_name, tool_args.strip(), timeout=10)
                    except Exception as e:
                        result = f"[ERROR] Tool '{tool_name}' failed: {e}"
                    console.print(f"[green]Autoplay Tool {tool_name} output:[/green]\n{result}")
                    # Add tool output to markdown pairs and chat history so the model can see it
                    md_pairs.append((f"#${tool_name}", str(result)))
                    pair_count += 1
                    chat_history.append(SystemMessageParam(role="system", content=f"[TOOL OUTPUT] {tool_name}: {result}"))
                else:
                    console.print(f"[red]No tool named '{tool_name}' found in plugins folder.[/red]")
            # Request a follow-up response from the model after tool outputs are available
            try:
                follow = llama.chat.completions.create(
                    model="Llama-4-Maverick-17B-128E-Instruct-FP8",
                    messages=chat_history,
                    stream=True
                )
                follow_reply = ""
                for chunk in follow:
                    follow_reply += extract_text_from_chunk(chunk)
                follow_reply = follow_reply.strip()
                chat_history.append(SystemMessageParam(role="system", content=follow_reply))
                console.print(f"[green]Llamatrama (after tools):[/green] {follow_reply}")
                md_pairs.append(("[tool-followup]", follow_reply))
                pair_count += 1
            except Exception as e:
                console.print(f"[red]Error while getting follow-up from model after tool run: {e}")

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
                res = execute_remote_command(shell_cmd)
                output = res.get('output') if isinstance(res, dict) else res
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
