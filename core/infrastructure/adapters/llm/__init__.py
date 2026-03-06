"""
Адаптеры для LLMPort.
"""
from core.infrastructure.adapters.llm.llama_adapter import (
    LlamaCppAdapter,
    MockLLMAdapter,
)

__all__ = [
    "LlamaCppAdapter",
    "MockLLMAdapter",
]
