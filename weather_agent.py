import httpx
from typing import Literal
from ollama import chat
from pathlib import Path
import time
import random
import shlex
import subprocess
import sys

MAX_RETRIES = 3
RETRY_STATUS = {429, 500, 502, 503, 504}

SANDBOX = Path("sandbox").resolve()
# resolve() 会把相对路径变成完整的真实路劲
MAX_STEPS = 10
NEEDS_APPROVAL = {"write_file", "edit_file", "run_command"}
READ_FILES = set()
ALLOWED_COMMANDS = {"python"}
MAX_OUTPUT_CHARS = 2000
COMMAND_TIMEOUT = 10

def run_command(command:str) -> str:
    """Run a python command inside the sandbox folder and return its output.

    Only "python" is allowed, e.g. "python hello.py".
    Use "/" in paths, never "\\". Do not run programs that wait for keyboard input.
    Commands are stopped after 10 seconds.

    Args:
        command: The command to run, e.g. "python hello.py"

    Returns:
        The exit code followed by the program's output and error messages.
        Exit code 0 means the program finished without errors.
    """
    parts = check_command(command)

    if parts[0] == 'python':
        parts[0] = sys.executable

    try:
        result = subprocess.run(
            parts,
            cwd=SANDBOX,
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace',
            timeout=COMMAND_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        raise TimeoutError(
            f"Command did not finish within {COMMAND_TIMEOUT} seconds and was stopped."
            " Check for infinite loops or code that waits for input"
        )

    output = result.stdout + result.stderr

    if len(output) > MAX_OUTPUT_CHARS:
        output = output[:MAX_OUTPUT_CHARS] + f"\n... output truncated ({len(output)} characters total)"

    return f"exit code: {result.returncode}\n{output}"

def check_command(command:str) -> list[str]:
    """Check a command before runnint it. Raise if it is not allowed.

    Returns:
        The command split into parts, e.g. ["python", "hello.py"].
    """
    try:
        parts = shlex.split(command)
    except ValueError:
        raise ValueError(f"Could not parse command: {command!r}. Check that quotes are closed")

    # empty string or only space
    if not parts:
        raise ValueError("Empty command")

    program = parts[0]
    if program not in ALLOWED_COMMANDS:
        raise ValueError(
            f"Command '{program}' is not allowed."
            f" Allowed commands: {', '.join(sorted(ALLOWED_COMMANDS))}"
        )

    return parts

def ask_human(name, arguments) -> bool:
    print(f"\n[approval] The agent wants to run: {name}({arguments})")
    answer = input("Allow? (y/n): ").strip().lower()
    return answer == 'y'

def clear_old_tool_results(messages):
    last_model_index = -1
    for i, m in enumerate(messages):
        # enumurate = 他会同时给我第几个（i）和那个东西（m）
        if not isinstance(m, dict):
            last_model_index = i

    for i in range(last_model_index):
        m = messages[i]
        if isinstance(m, dict) and m['role'] == 'tool':
            m['content'] = '[cleared: old tool result. Call the tool again if you need it.]'

def chat_with_retry(messages, tools):
    for attempt in range(MAX_RETRIES):
        try:
            return chat(model='qwen3:8b', messages=messages, tools=tools)
        except ConnectionError as e:
            if attempt == MAX_RETRIES - 1:
                raise
            delay = 2 ** attempt + random.uniform(0,1)
            # random.uniform(0,1) = jitter （随机 0-1秒）
            print(f"[retry] {e} -> waiting {delay:.1f}s")
            time.sleep(delay)

def write_file(filename:str, content:str) -> str:
    """Write text to a file in the sandbox folder. Overwrites the file if it already exists

    Args:
        filename: Name of the file inside the sandbox folder, e.g. "notes.txt"
        content: The text to write into the file

    Returns:
        A confirmation message
    """
    path = (SANDBOX / filename).resolve()
    if not path.is_relative_to(SANDBOX):
        raise PermissionError(f"Access denied: '{filename}' is outside the sandbox folder")
    path.write_text(content, encoding="utf-8")
    return f"Wrote {len(content)} characters to '{filename}'"

def read_file(filename:str) -> str:
    """Read a text file from the sandbox folder.

    Args:
        filename: Name of the file inside the sandbox folder, e.g. "notes.txt"

    Returns:
        The full text content of the file.
    """
    path = (SANDBOX / filename).resolve()
    if not path.is_relative_to(SANDBOX):
        # is_relative_to(SANDBOX) 检查最终路径是否还在沙盒里面
        raise PermissionError(f"Access denied: '{filename}' is outside the sandbox folder")
    if not path.is_file():
        # is_file() 文件不存在，或者是文件夹而不是文件
        raise FileNotFoundError(f"File not found: '{filename}'")
    text = path.read_text(encoding="utf-8")
    READ_FILES.add(path)
    return text

def get_weather(
    latitude: float, longitude: float, unit: Literal["celsius", "fahrenheit"]
) -> float:
    """Get the current air temperature at a location.

    Args:
        latitude: Latitude of the location in decimal degrees, e.g. 4.39 for Miri
        longitude: Longitude of the location in decimal degrees, e.g. 113.99 for Miri
        unit: Temperature unit to return, "celsius" or "fahrenheit". Defaults to "celsius".

    Returns:
        The current air temperature 2 meters above ground, in the requested unit.
    """
    # url = "https://httpbin.org/status/503"
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m",
        "temperature_unit": unit,
    }
    for attempt in range(MAX_RETRIES):
        try:
            response = httpx.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return data['current']['temperature_2m']
        except httpx.HTTPStatusError as e:
            # 由 raise_for_status() 回应
            # 如果不是2xx成功码就丢出
            # 带有 .request 和 .response 属性
            if e.response.status_code not in RETRY_STATUS:
                raise
            if attempt == MAX_RETRIES - 1:
                raise
            reason = f'HTTP {e.response.status_code}'
        except httpx.TransportError as e:
            # 根本没拿到回应， 例如断网， 超时或者各种error
            if attempt == MAX_RETRIES - 1:
                raise
            reason = type(e).__name__
            # 取得错误的类别名称
        delay = 2 ** attempt + random.uniform(0,1)
        print(f"[retry] get_weather: {reason} -> waiting {delay:.1f}s")
        time.sleep(delay)


# Literal 只会是其中的这几个
def calculate(a: float, b: float, operator: Literal["+", "-", "*", "/"]) -> float:
    """Do one basic arithmetic operation on two numbers.

    Always use this tool for math instead of calculating yourself.

    Args:
        a: The first number.
        b: The second number.
        operator: The operation to apply: "+", "-","*", or "/".

    Returns:
        The result of a (operator) b
    """
    if operator == "+":
        return a + b
    elif operator == "-":
        return a - b
    elif operator == "*":
        return a * b
    elif operator == "/":
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
    raise ValueError(f"Unknown operator: {operator}")

def list_files(path:str = ".") -> str:
    """List files and folders inside the sandbox folder.
    
    Args:
        path: a folder inside sandbox, "." means the sandbox root

    Returns:
        One item per line. Folder names end with "/"
    """
    target = (SANDBOX / path).resolve()

    if not target.is_relative_to(SANDBOX.resolve()):
        raise ValueError(f"Access denied: '{path}' is outside the sandbox")

    if not target.is_dir():
        raise ValueError(f"Not a folder: '{path}'")

    items = []
    for item in sorted(target.iterdir()):
        if item.is_dir():
            items.append(f"{item.name}/")
        else:
            items.append(item.name)

    if not items:
        return "(empty folder)"

    return "\n".join(items)

def check_edit(filename: str, old_str: str, new_str: str) -> Path:
    """Run every edit_file check. Raise if the edit cannot successd.
    Returns the resolved path so edit_file doew not need to resolve it
    """
    path = (SANDBOX / filename).resolve()
    if not path.is_relative_to(SANDBOX):
        raise PermissionError(f"Access denieed: '{filename}' is outside the sandbox folder")

    if not path.is_file():
        raise FileNotFoundError(f"File not found: '{filename}'")

    if path not in READ_FILES:
        raise ValueError(
            f"You must read '{filename}' with read_file before editing it."
            " Call read_file first, then try edit_file again."
        )

    if old_str == "":
        raise ValueError("old_str cannot be empty. To write a whole file, use write_file instead")

    count = path.read_text(encoding="utf-8").count(old_str)
    if count == 0:
        raise ValueError(f"old_str not found in '{filename}'. Use read_file to check the exact text")
    if count > 1:
        raise ValueError(
            f"old_str found {count} times in '{filename}'."
            " Include more surrounding text so it matches exactly once"
        )
    
    return path

def edit_file(filename:str, old_str: str, new_str:str) -> str:
    """Edit a text file in the sandbox by replacing one exact piece of text.

    old_str must appear in the file exactly once. If it is not found, or found
    more than once, the edit fails. When it appears more than once, include
    more surrounding text in old_str so it becomes unique.
    Read the file with read_file first so old_str matches exactly.

    Args:
        filename: Name of the file inside the sandbox folder, e.g. "notes.txt"
        old_str: The exact text to replace, including spaces and line breaks
        new_str: The new text to put in its place

    Returns:
        A confirmation message
    """
    path = check_edit(filename, old_str, new_str)
    content = path.read_text(encoding="utf-8")
    path.write_text(content.replace(old_str, new_str, 1), encoding="utf-8")
    return f"Edited '{filename}': replaced 1 occurrence"

available_tools = {
    "get_weather": get_weather,
    "calculate": calculate,
    "read_file": read_file,
    "write_file": write_file,
    "list_files":list_files,
    "edit_file":edit_file,
    "run_command":run_command,
}

PRECHECKS = {
    "edit_file": check_edit,
    "run_command": check_command,
}

def main():
    messages = [
        {
            "role": "system",
            "content": (
                "你是一个私人的coding小助手，你可以在sandbox里看，读，写，改文件并用 run_command 跑python\n"
                "你还可以修改文件内容使用 edit_file 工具不过在edit_file之前你必须调用read_file先。只有在要写整个新文件才用write_file\n"
                "get_weather可以用unit参数直接回传celsius 或 fahrenheit\n"
                '用户要华氏度时，调用 get_weather 并传 unit="fahrenheit", 不要自己换算。\n'
                "其他数学计算一律使用 calculate 工具\n"
                "回答时要注明单位，用纯文字回答，不要用LaTex"
            ),
        },
        {"role": "user", "content":"Run buggy.py. If there is an error, fix it, then run it again to confirm it works."},
    ]
    tools = [get_weather, calculate, read_file, write_file,list_files,edit_file, run_command]

    step = 0
    while step < MAX_STEPS:
        step += 1    
        print(f"--- step {step} ---")
        clear_old_tool_results(messages)
        response = chat_with_retry(messages, tools)
        messages.append(response.message)
        print(f"[context] input tokens: {response.prompt_eval_count}")
        # prompt_eval_count = 这一步送进模型的input token数量

        if not response.message.tool_calls:
            print("answer:", response.message.content)
            return

        for call in response.message.tool_calls:
            name = call.function.name
            arguments = call.function.arguments
            function = available_tools.get(name)

            if function is None:
                result = f"Error: unknown tool '{name}'"
            else:
                try:
                    if name in PRECHECKS:
                        PRECHECKS[name](**arguments)

                    if name in NEEDS_APPROVAL and not ask_human(name, arguments):
                        print(f"\nStopped: you denied {name}({arguments}). Nothing was changed.")
                        return
                    
                    result = function(**call.function.arguments)
                except Exception as e:
                    result = f"Error: {e}"

            print(f"[tool] {name}({call.function.arguments}) -> {str(result)[:100]}")
            messages.append({"role": "tool", "content": str(result), "tool_name": name})

    print("Stopped: reached max steps")

if __name__ == "__main__":
    main()
