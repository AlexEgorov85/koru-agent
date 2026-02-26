"""
Базовый класс для всех LLM провайдеров.
Реализует стандартный интерфейс для работы с различными LLM бэкендами.
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from core.retry_policy.retry_and_error_policy import RetryPolicy
from core.models.types.llm_types import LLMHealthStatus, LLMRequest, LLMResponse, StructuredOutputConfig, StructuredLLMResponse
from core.infrastructure.providers.base_provider import BaseProvider, ProviderHealthStatus

logger = logging.getLogger(__name__)

class BaseLLMProvider(BaseProvider, ABC):
    """
    Базовый класс для всех LLM-провайдеров.

    АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
    1. Инверсия зависимостей: Зависит только от абстракций (LLMPort)
    2. Единый контракт: Все методы имеют стандартизированную сигнатуру
    3. Безопасность по умолчанию: Встроенные ограничения и валидация
    4. Наблюдаемость: Автоматическое логирование и метрики
    5. Отказоустойчивость: Грациозная деградация при ошибках

    МЕТОДЫ:
    - initialize(): Асинхронная инициализация провайдера
    - shutdown(): Корректное завершение работы
    - health_check(): Проверка состояния здоровья
    - generate(): Генерация текста
    - generate_structured(): Генерация структурированных данных
    - _update_metrics(): Обновление внутренних метрик

    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    provider = VLLMProvider("mistral-7b", config)
    await provider.initialize()
    response = await provider.generate(LLMRequest(prompt="Привет!"))
    print(response.content)
    """

    def __init__(self, model_name: str, config: Optional[Dict[str, Any]] = None):
        """
        Инициализация LLM-провайдера.

        ПАРАМЕТРЫ:
        - model_name: Название модели
        - config: Конфигурация провайдера
        """
        super().__init__(name=model_name, config=config)
        self.model_name = model_name
        self.health_status = LLMHealthStatus.UNKNOWN
        self.last_health_check = None
    
    @abstractmethod
    async def initialize(self) -> bool:
        """Асинхронная инициализация провайдера."""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Корректное завершение работы провайдера."""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Проверка здоровья провайдера."""
        pass

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Генерация текста на основе запроса."""
        pass

    @abstractmethod
    async def generate_structured(self, request: LLMRequest) -> Dict[str, Any]:
        """
        Генерация структурированных данных по JSON Schema.

        Args:
            request (LLMRequest): Запрос к LLM с информацией о структурированном выводе

        Returns:
            Dict[str, Any]: Структурированные данные
        """
        pass

    async def generate_for_capability(self, system_prompt: str, user_input: str, capabilities) -> tuple:
        """
        Генерация для конкретной capability.

        ПАРАМЕТРЫ:
        - system_prompt: Системный промпт
        - user_input: Ввод пользователя
        - capabilities: Доступные capabilities

        ВОЗВРАЩАЕТ:
        - tuple: (capability_name, parameters)
        """
        schema = {
            "type": "object",
            "properties": {
                "capability_name": {"type": "string", "description": "Название выбранной capability"},
                "parameters": {"type": "object", "description": "Параметры для вызова capability"}
            },
            "required": ["capability_name", "parameters"]
        }

        result = await self.generate_structured(
            prompt=user_input,
            output_schema=schema,
            system_prompt=system_prompt
        )

        capability_name = result.get("capability_name")
        parameters = result.get("parameters")
        return (capability_name, parameters)

    def _update_metrics(self, response_time: float, success: bool = True):
        """Обновление внутренних метрик провайдера."""
        super()._update_metrics(response_time, success)
        
        # Специфичная логика для LLM
        if self.error_count > 0 and self.request_count > 1:
            error_rate = self.error_count / self.request_count
            if error_rate > 0.95:
                self.health_status = LLMHealthStatus.UNHEALTHY
            elif error_rate >= 0.5:
                self.health_status = LLMHealthStatus.DEGRADED

    def get_model_info(self) -> Dict[str, Any]:
        """Получение информации о модели."""
        info = super().get_info()
        info["model_name"] = self.model_name
        info["health_status"] = self.health_status.value
        return info