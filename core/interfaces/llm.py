"""
Интерфейс для работы с LLM.

Определяет контракт для всех реализаций LLM (LlamaCpp, vLLM, OpenAI, и т.д.).
"""

from typing import Protocol, List, Dict, Any, Optional


class LLMInterface(Protocol):
    """
    Интерфейс для работы с LLM.

    АБСТРАКЦИЯ: Определяет что нужно для генерации текста.
    РЕАЛИЗАЦИИ: LlamaCppProvider, MockLLMProvider, OpenAIProvider.
    """

    async def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        stop_sequences: Optional[List[str]] = None
    ) -> str:
        """
        Сгенерировать текстовый ответ.

        ARGS:
        - messages: Список сообщений в формате [{"role": "user", "content": "..."}]
        - temperature: Температура генерации (0.0-1.0)
        - max_tokens: Максимальное количество токенов
        - stop_sequences: Последовательности для остановки генерации

        RETURNS:
        - Сгенерированный текст
        """
        ...

    async def generate_structured(
        self,
        messages: List[Dict[str, str]],
        response_schema: Dict[str, Any],
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Сгенерировать структурированный ответ (JSON).

        ARGS:
        - messages: Список сообщений
        - response_schema: JSON Schema ожидаемого ответа
        - temperature: Температура генерации

        RETURNS:
        - Словарь с полями согласно схеме
        """
        ...

    async def count_tokens(self, messages: List[Dict[str, str]]) -> int:
        """
        Подсчитать количество токенов в сообщениях.

        ARGS:
        - messages: Список сообщений

        RETURNS:
        - Количество токенов
        """
        ...
