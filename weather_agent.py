import httpx
from typing import Literal
from ollama import chat
from pathlib import Path
import time
import random

MAX_RETRIES = 3
RETRY_STATUS = {429, 500, 502, 503, 504}

SANDBOX = Path("sandbox").resolve()
# resolve() 会把相对路径变成完整的真实路劲
MAX_STEPS = 10
NEEDS_APPROVAL = {"write_file"}

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
    return path.read_text(encoding="utf-8")

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

available_tools = {
    "get_weather": get_weather,
    "calculate": calculate,
    "read_file": read_file,
    "write_file": write_file,
    "list_files":list_files,
}


def main():
    messages = [
        {
            "role": "system",
            "content": (
                "你是查天气的助手，可以调用 get_weather 和 calculate 两个工具。另外你还可以读取sandbox里的文件使用 read_file 工具\n"
                "你现在还可以调用write_file来写文件还有list_files来查看文件夹里面有什么文件\n"
                "get_weather可以用unit参数直接回传celsius 或 fahrenheit\n"
                '用户要华氏度时，调用 get_weather 并传 unit="fahrenheit", 不要自己换算。\n'
                "其他数学计算一律使用 calculate 工具\n"
                "回答时要注明单位，用纯文字回答，不要用LaTex"
            ),
        },
        {"role": "user", "content":"What's in my notes file?"},
    ]
    tools = [get_weather, calculate, read_file, write_file,list_files]

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
            function = available_tools.get(name)

            if function is None:
                result = f"Error: unknown tool '{name}'"
            elif name in NEEDS_APPROVAL and not ask_human(name, call.function.arguments):
                result = "Error: the user denied this action. Do not retry it. Ask the user what they want instead."
            else:
                try:
                    result = function(**call.function.arguments)
                except Exception as e:
                    result = f"Error: {e}"

            print(f"[tool] {name}({call.function.arguments}) -> {str(result)[:100]}")
            messages.append({"role": "tool", "content": str(result), "tool_name": name})

    print("Stopped: reached max steps")

if __name__ == "__main__":
    main()
