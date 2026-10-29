import httpx
from typing import Literal
from ollama import chat


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


def get_weather(latitude: float, longitude: float) -> float:
    """Get the current air temperrature at a location

    Args:
        latitude: Latitude of the location in decimal degrees, e.g. 4.39 for Miri
        longitude: Longitude of the location in decimal degrees, e.g. 113.99 for Miri.

    Returns:
        The current air temperature 2 meters above ground, in degrees Celsius
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m",
    }
    response = httpx.get(url, params=params)
    response.raise_for_status()
    # if the api return the error the program will down
    data = response.json()
    return data["current"]["temperature_2m"]


available_tools = {
    "get_weather": get_weather,
    "calculate": calculate,
}


def main():
    messages = [
        {"role":"system","content":"""你是查天气的助手可以调用get_weather和calculate两个工具。get_weather的回传单位是Celsius。如果用户要求fahrenheit的时候你
        需要调用calculate工具来计算，只要包含到需要计算的部分一切调用calculate工具来计算, Celsius -> fahrenheit  的公式是 fahrenheit = celsius * 9 / 5 + 32"""},
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
            messages.append(
                {
                    "role":"tool",
                    "content":str(result),
                    "tool_name":name
                }
            )

    print("Stopped: reached max steps")


if __name__ == "__main__":
    main()
