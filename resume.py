from typing import Literal
from pydantic import BaseModel
from ollama import chat

class Project(BaseModel):
    name: str
    description: str

class Resume(BaseModel):
    name: str
    school: str
    skills: list[str]  
    project: list[Project]

def main() -> None:
    text = """
    Kho Chien Young, Curtin Malaysia 软件工程系二年级学生。
    会用 Python, Java, JavaScript 和 Git
    做过一个天气查询程序， 用httpx和asyncio同时查询多个城市的气温
    也做过一个命令行聊天机器人，用ollama在本地跑qwen3模型，支持多轮对话和streaming
    """

    response = chat(
        model='qwen3:8b',
        messages = [
            {"role":"system","content":"从用户提供的简历文字中提取资料。"},
            {"role":"user","content":text},
        ],
        format = Resume.model_json_schema(),
    )

    raw = response.message.content
    result = Resume.model_validate_json(raw)

    print(f"名字：{result.name}")
    print(f"学校：{result.school}")
    print(f"技能：{', '.join(result.skills)}")
    print("项目：")
    for p in result.project:
        print(f"  - {p.name}: {p.description}")

if __name__ == "__main__":
    main()
