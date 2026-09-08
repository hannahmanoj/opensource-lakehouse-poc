from typing import TypeVar

import httpx
from pydantic import BaseModel

from app.config import (
    LLM_BASE_URL,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_TIMEOUT_SECONDS,
)
from app.llm.provider import LLMProvider


ResponseModel = TypeVar(
    "ResponseModel",
    bound=BaseModel,
)


class OllamaProvider(LLMProvider):
    async def generate(
        self,
        messages: list[dict[str, str]],
        response_schema: type[ResponseModel],
    ) -> ResponseModel:
        async with httpx.AsyncClient(
            base_url=LLM_BASE_URL,
            timeout=LLM_TIMEOUT_SECONDS,
        ) as client:
            response = await client.post(
                "/api/chat",
                json={
                    "model": LLM_MODEL,
                    "messages": messages,
                    "stream": False,
                    "think": False,
                    "format": (
                        response_schema.model_json_schema()
                    ),
                    "options": {
                        "temperature": LLM_TEMPERATURE,
                    },
                },
            )

            response.raise_for_status()

            body = response.json()
            content = body["message"]["content"]

            return response_schema.model_validate_json(
                content
            )