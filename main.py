from ollama import chat

def main() -> None:
    messages = [
        {"role": "system", "content":"你是一名在google工作的经验丰富的软件工程师也是现在熟练的ai engineering在google, 你现在在为一名还在读书的软件工程学生教导关于ai engineering的知识, 你的一切回答需要不确定的时候要直接说不确定，然后确保这名学生能理解然后要使用中文和英文来解释。另外每种语言的回答需要控制在不超过两句。如果可行，就使用生活中的比喻"},
    ]

    while True:
        user_input = input("你: ")
        if user_input == "exit":
            break

        messages.append({"role":"user", "content":user_input})
        stream = chat(model='qwen3:8b', messages=messages, stream=True)

        reply = ""
        print("AI: ", end="")
        for chunk in stream:
            piece = chunk.message.content
            print(piece, end="", flush=True)
            reply += piece
        print()
        messages.append({'role': 'assistant', 'content': reply})

if __name__ == "__main__":
    main()