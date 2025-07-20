import os
from dotenv import load_dotenv
from llama_api_client import LlamaAPIClient
from llama_api_client.types import SystemMessageParam, UserMessageParam
from tools.ssh_tool import execute_remote_command
from rich.console import Console

console = Console()
load_dotenv()

llama = LlamaAPIClient(api_key=os.getenv("LLAMA_API_KEY"))

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

def main():
    console.print("[bold magenta]Llamatrama Agent Online. Type 'exit' to quit.[/bold magenta]")

    chat_history = []
    chat_history.append(SystemMessageParam(role="system", content="You are a helpful assistant connected to a real remote Kali Linux system via SSH. You can execute actual shell commands on the system when needed. Always be clear that you are interacting with a real machine, and inform the user of any risks or limitations."))

    pair_count = 0
    file_index = 1
    md_pairs = []

    while True:
        user_input = console.input("[cyan]You:[/cyan] ")
        if user_input.lower() in ["exit", "quit"]:
            break

        # Add user input to history
        chat_history.append(UserMessageParam(role="user", content=user_input))

        # Send message to LLaMA for decision-making
        response = llama.chat.completions.create(
            model="Llama-4-Maverick-17B-128E-Instruct-FP8",
            messages=chat_history + [
                SystemMessageParam(role="system", content="If the user's request requires a Linux shell command, summarize it briefly and then say '[RUN]' followed by the instruction to be passed to the shell tool. Otherwise, just reply conversationally. Remember: you are connected to a real remote Kali Linux system via SSH, and your actions will affect the actual machine."),
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
