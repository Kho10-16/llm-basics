import json
from typing import Literal
from pydantic import BaseModel

from ollama import chat

class Expense(BaseModel):
    item: str
    amount: float
    category: Literal["餐饮", "交通", "购物", "娱乐", "其他"]

class ExpenseList(BaseModel):
    expenses: list[Expense]

def main() -> None:
    text = "跟朋友吃火锅，我付了五十块"

    response = chat(
        model="qwen3:8b",
        messages=[
            {
                "role":"system",
                "content":"从用户的句子里提取所有消费记录。如果没有消费，就回传空的列表。",
            },
            {"role":"user", "content":text},
        ],
        format=ExpenseList.model_json_schema(),
    )

    raw = response.message.content
    print("模型回传的原始文字：")
    print(raw)

    result = ExpenseList.model_validate_json(raw)

    if not result.expenses:
        print("没有找到消费记录")

    for expense in result.expenses:
        print(f"{expense.item}: RM{expense.amount} ({expense.category})")

if __name__ == "__main__":
    main()

