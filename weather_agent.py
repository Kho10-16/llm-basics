import httpx
from typing import Literal
from ollama import chat


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
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m",
        "temperature_unit": unit,
    }
    response = httpx.get(url, params=params)
    response.raise_for_status()
    data = response.json()
    return data["current"]["temperature_2m"]


# Literal 只会是其中的这几个
def calculate(a: float, b: float, operator: Literal["+", "-", "*", "/"]) -> float:
    """Do one basic arithmetic operation on two numbers.

    Always use this tool for math instead of calculating yourself.

    Args:
        a: The first number.
        b: The second number,
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

available_tools = {
    "get_weather": get_weather,
    "calculate": calculate,
}


def main():
    messages = [
        {
            "role": "system",
            "content": (
                "你是查天气的助手，可以调用 get_weather 和1 calculate 两个工具。"
                "get_weather可以用unit参数直接回传celsius 或 fahrenheit"
                '用户要华氏度时，调用 get_weather 并传 unit="fahrenheit", 不要自己换算。'
                "其他数学计算一律使用 calculate 工具"
                "回答时要注明单位，用纯文字回答，不要用LaTex"
            ),
        },
        {"role": "user", "content": "What is temperature in Miri in Fahrenheit?"},
    ]
    tools = [get_weather, calculate]

    for step in range(10):
        print(f"--- step {step+1} ---")
        response = chat(model="qwen3:8b", messages=messages, tools=tools)
        messages.append(response.message)

        if not response.message.tool_calls:
            print("answer:", response.message.content)
            return

        for call in response.message.tool_calls:
            name = call.function.name
            function = available_tools.get(name)

            if function is None:
                result = f"Error: unknown tool '{name}'"
            else:
                try:
                    result = function(**call.function.arguments)
                except Exception as e:
                    result = f"Error: {e}"

            print(f"[tool] {name}({call.function.arguments}) -> {result}")
            messages.append({"role": "tool", "content": str(result), "tool_name": name})

    print("Stopped: reached max steps")


if __name__ == "__main__":
    main()
