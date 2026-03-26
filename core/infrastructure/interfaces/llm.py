"""
Интерфейс для LLM.

Определяет контракт для всех реализаций LLM (LlamaCpp, vLLM, OpenAI, и т.д.).
"""

from typing import Protocol, List, Dict, Any, Optional
from core.models.types.llm_types import LLMHealthStatus


class LLMInterface(Protocol):
    """
    Интерфейс для работы с LLM.

    АБСТРАКЦИЯ: Определяет что нужно для генерации текста.
    РЕАЛИЗАЦИИ: LlamaCppProvider, MockLLMProvider, OpenAIProvider.
    """

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Сгенерировать текстовый ответ.

        ARGS:
        - prompt: Запрос пользователя
        - system_prompt: Системный промпт (роль)
        - temperature: Температура генерации (0.0-1.0)
        - max_tokens: Максимальное количество токенов

        RETURNS:
        - Сгенерированный текст
        """
        ...

    async def generate_structured(
        self,
        prompt: str,
        response_schema: Dict[str, Any],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1
    ) -> Dict[str, Any]:
        """
        Сгенерировать структурированный ответ (JSON).

        ARGS:
        - prompt: Запрос пользователя
        - response_schema: JSON Schema ожидаемого ответа
        - system_prompt: Системный промпт (роль)
        - temperature: Температура генерации

        RETURNS:
        - Словарь с полями согласно схеме
        """
        ...

    async def health_check(self) -> LLMHealthStatus:
        """
        Проверка здоровья LLM.

        RETURNS:
        - Статус здоровья
        """
        ...
