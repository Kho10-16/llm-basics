import httpx
from ollama import chat

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
        "latitude":latitude,
        "longitude":longitude,
        "current": "temperature_2m",
    }
    response = httpx.get(url, params=params)
    response.raise_for_status()
    # if the api return the error the program will down
    data = response.json()
    return data["current"]["temperature_2m"]

def main():
    messages =[
        {"role":"user","content":"What's the temperature in Kuching right now?"}
    ]
    response = chat(
        model='qwen3:8b',
        messages=messages,
        tools=[get_weather],
    )
    messages.append(response.message)

    for call in response.message.tool_calls or []:
        if call.function.name == "get_weather":
            result = get_weather(**call.function.arguments)
            print(f"[tool] get_weather({call.function.arguments}) -> {result}")
            messages.append({
                "role":"tool",
                "content": str(result),
                "tool_name": call.function.name
            })

    final = chat(model="qwen3:8b", messages=messages, tools=[get_weather])
    print("answer:", final.message.content)

if __name__ == "__main__":
    main()