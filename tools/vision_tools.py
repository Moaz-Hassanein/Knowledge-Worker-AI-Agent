import base64
import json
from pathlib import Path

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage


VISION_PROMPT = """
You are a data extraction system.

Extract the requested data from the provided image.

Return ONLY valid JSON.

Required fields:
{required_data}

Rules:
- Do not invent values.
- If a value cannot be read, return null.
- Preserve numbers as numbers.
- Preserve product names exactly.
- Extract every visible row that matches the requested data.
"""


def extract_from_image(
    image_path: str,
    required_data: list[str],
) -> dict:

    llm = ChatOllama(
        model="gemma4:31b-cloud",
        temperature=0,
    )

    image_bytes = Path(image_path).read_bytes()
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    message = HumanMessage(
        content=[
            {
                "type": "text",
                "text": VISION_PROMPT.format(
                    required_data=", ".join(required_data)
                ),
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{image_b64}"
                },
            },
        ]
    )

    response = llm.invoke([message])

    content = response.content
    if isinstance(content, list):
        content = "".join(
            item if isinstance(item, str) else item.get("text", "")
            for item in content
        )

    return json.loads(content)