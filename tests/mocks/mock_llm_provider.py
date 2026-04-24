"""
Mock LLM Provider для тестирования агента.

Возвращает заготовленные JSON-ответы из фикстур, поддерживая различные сценарии:
- act: возвращает решение выполнить действие
- finish: возвращает решение завершить работу
- error: возвращает ошибку для проверки recovery
- custom: возвращает кастомный ответ из файла
"""

import json
import os
from typing import Any, Dict, List, Optional
from pathlib import Path

from core.infrastructure.providers.llm.base_llm import BaseLLMProvider
from core.models.types.llm_types import LLMRequest, LLMResponse


class MockLLMProvider(BaseLLMProvider):
    """Mock провайдер для детерминированного тестирования LLM-вызовов."""

    def __init__(
        self,
        fixtures_dir: str = "tests/fixtures/llm_responses",
        scenario: str = "default",
        response_sequence: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Инициализация mock провайдера.

        Args:
            fixtures_dir: Директория с фикстурами ответов
            scenario: Название сценария (имя файла без .json)
            response_sequence: Явно заданная последовательность ответов (приоритет над файлами)
        """
        super().__init__(model_name="mock", config={})
        self.fixtures_dir = Path(fixtures_dir)
        self.scenario = scenario
        self.response_sequence = response_sequence or []
        self.call_index = 0
        self._load_scenario()

    def _load_scenario(self):
        """Загружает сценарий из файла если не задана последовательность."""
        if self.response_sequence:
            return

        scenario_file = self.fixtures_dir / f"{self.scenario}.json"
        if scenario_file.exists():
            with open(scenario_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.response_sequence = data.get("responses", [])
        else:
            # Default scenario inline
            self.response_sequence = self._get_default_scenario()

    def _get_default_scenario(self) -> List[Dict[str, Any]]:
        """Возвращает стандартный сценарий для базовых тестов."""
        return [
            {
                "type": "act",
                "action": "sql_tool.execute",
                "parameters": {
                    "query": "SELECT COUNT(*) FROM users"
                },
                "reasoning": "Нужно получить количество пользователей"
            },
            {
                "type": "act",
                "action": "sql_tool.execute",
                "parameters": {
                    "query": "SELECT * FROM users LIMIT 10"
                },
                "reasoning": "Получаем первые 10 записей"
            },
            {
                "type": "finish",
                "answer": "Данные успешно получены и обработаны.",
                "confidence": 0.95
            }
        ]

    async def _generate_impl(self, request: LLMRequest) -> LLMResponse:
        """
        Реализация генерации на основе заранее заданной последовательности.

        Args:
            request: Запрос (игнорируется в mock, используется для совместимости)

        Returns:
            LLMResponse с ответом из последовательности
        """
        if self.call_index >= len(self.response_sequence):
            # Если ответы закончились, возвращаем finish по умолчанию
            return LLMResponse(
                content="Лимит ответов mock провайдера исчерпан.",
                finish_reason="stop",
                usage={"prompt_tokens": 0, "completion_tokens": 10, "total_tokens": 10},
                metadata={"type": "finish"}
            )

        response = self.response_sequence[self.call_index]
        self.call_index += 1

        # Обработка типа ответа
        response_type = response.get("type", "act")

        if response_type == "error":
            # Симуляция ошибки
            return LLMResponse(
                content="",
                finish_reason="error",
                tokens_used=0,
                metadata={
                    "type": "error",
                    "error": response.get("error", "Unknown error"),
                    "retry": response.get("retry", False),
                    "suggestion": response.get("suggestion", "")
                }
            )

        elif response_type == "finish":
            return LLMResponse(
                content=response.get("answer", ""),
                finish_reason="stop",
                tokens_used=20,
                metadata={
                    "type": "finish",
                    "confidence": response.get("confidence", 0.8),
                    "sources": response.get("sources", [])
                }
            )

        elif response_type == "act":
            import json
            action_data = {
                "type": "act",
                "action": response.get("action", "unknown"),
                "parameters": response.get("parameters", {}),
                "reasoning": response.get("reasoning", "")
            }
            return LLMResponse(
                content=json.dumps(action_data, ensure_ascii=False),
                finish_reason="stop",
                tokens_used=30,
                metadata={"type": "act"}
            )

        elif response_type == "custom":
            # Возвращаем кастомный ответ как есть
            import json
            custom_content = response.get("content", {})
            return LLMResponse(
                content=json.dumps(custom_content, ensure_ascii=False) if isinstance(custom_content, dict) else str(custom_content),
                finish_reason="stop",
                tokens_used=10,
                metadata={"type": "custom"}
            )

        else:
            # По умолчанию act
            import json
            action_data = {
                "type": "act",
                "action": "unknown",
                "parameters": {},
                "reasoning": ""
            }
            return LLMResponse(
                content=json.dumps(action_data, ensure_ascii=False),
                finish_reason="stop",
                tokens_used=30,
                metadata={"type": "act"}
            )

    def reset(self):
        """Сбрасывает счётчик вызовов для повторного использования."""
        self.call_index = 0

    def get_call_count(self) -> int:
        """Возвращает количество сделанных вызовов."""
        return self.call_index

    def get_remaining_calls(self) -> int:
        """Возвращает количество оставшихся запланированных вызовов."""
        return max(0, len(self.response_sequence) - self.call_index)

    async def generate_stream(self, request: LLMRequest):
        """
        Потоковая генерация (не поддерживается в mock).

        Raises:
            NotImplementedError: Потоковый режим не поддерживается
        """
        raise NotImplementedError("Stream mode is not supported in MockLLMProvider")

    async def initialize(self):
        """Инициализация провайдера (mock, ничего не делает)."""
        self.health_status = "healthy"
        self.log.info("MockLLMProvider initialized")

    async def shutdown(self):
        """Завершение работы провайдера (mock, ничего не делает)."""
        self.health_status = "shutdown"
        self.log.info("MockLLMProvider shutdown")

    async def health_check(self) -> bool:
        """Проверка здоровья провайдера (всегда True для mock)."""
        return self.health_status == "healthy"
