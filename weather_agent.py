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
        {"role": "user", "content": "What is 12.5 times 8?"},
    ]
    response = chat(
        model="qwen3:8b",
        messages=messages,
        tools=[get_weather, calculate],
    )
    if not response.message.tool_calls:
        print(f"answer: {response.message.content}")
        return
    print("first:", response.message)
    messages.append(response.message)

    for call in response.message.tool_calls or []:
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
                "role": "tool",
                "content": str(result),
                "tool_name": name,
            }
        )
    final = chat(model="qwen3:8b", messages=messages, tools=[get_weather, calculate])
    print("answer:", final.message.content)


if __name__ == "__main__":
    main()
