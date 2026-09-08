from app.config import LLM_PROVIDER
from app.llm.ollama import OllamaProvider
from app.llm.provider import LLMProvider


def get_llm_provider() -> LLMProvider:
    if LLM_PROVIDER == "ollama":
        return OllamaProvider()

    raise ValueError(
        f"Unsupported LLM provider: {LLM_PROVIDER}"
    )