from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel


ResponseModel = TypeVar(
    "ResponseModel",
    bound=BaseModel,
)


class LLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, str]],
        response_schema: type[ResponseModel],
    ) -> ResponseModel:
        raise NotImplementedError