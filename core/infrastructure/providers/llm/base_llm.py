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

    ЛОГИРОВАНИЕ LLM ВЫЗОВОВ:
    - Промты и ответы логируются на уровне INFO в файл agent.log
    - Включает: длину промта, длину ответа, время генерации, модель
    - Реализовано в базовом классе для всех провайдеров автоматически
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

        # Логгер для LLM вызовов (отдельный от общего логгера класса)
        self._llm_logger = logging.getLogger(f"llm.{self.__class__.__name__}")

        # Принудительно устанавливаем уровень INFO чтобы логи писались в файл
        self._llm_logger.setLevel(logging.INFO)

        # Добавляем handler для записи в agent.log если ещё не добавлен
        if not self._llm_logger.handlers:
            # Получаем root logger handlers (файловый handler)
            root_logger = logging.getLogger()
            for handler in root_logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    self._llm_logger.addHandler(handler)
                    break

        # event_bus_logger будет инициализирован в initialize()
        self.event_bus_logger = None

    async def _log_llm_call_start(self, request: LLMRequest) -> None:
        """
        Логирование начала LLM вызова.

        Логирует:
        - Длину промта
        - Параметры генерации (temperature, max_tokens)
        - Модель
        """
        await self.event_bus_logger.info(
            f"📝 LLM вызов | Модель: {self.model_name} | "
            f"Промт: {len(request.prompt)} симв. | "
            f"Max tokens: {request.max_tokens} | "
            f"Temperature: {request.temperature}"
        )

        # DEBUG: полный промт (только в файл)
        await self.event_bus_logger.debug(f"Промт LLM: {request.prompt[:500]}..." if len(request.prompt) > 500 else f"Промт LLM: {request.prompt}")

    async def _log_llm_call_end(self, response: LLMResponse, elapsed_time: float) -> None:
        """
        Логирование завершения LLM вызова.

        Логирует:
        - Длину ответа
        - Время генерации
        - Статус (успех/ошибка)
        """
        if response.finish_reason == "error":
            await self.event_bus_logger.error(
                f"❌ LLM ответ | Модель: {self.model_name} | "
                f"Ошибка: {response.metadata.get('error', 'unknown') if response.metadata else 'unknown'} | "
                f"Время: {elapsed_time:.2f}с"
            )
        else:
            content_length = len(response.content) if response.content else 0
            await self.event_bus_logger.info(
                f"✅ LLM ответ | Модель: {self.model_name} | "
                f"Ответ: {content_length} симв. | "
                f"Токенов: {response.tokens_used} | "
                f"Время: {elapsed_time:.2f}с | "
                f"Причина: {response.finish_reason}"
            )

            # DEBUG: полный ответ (только в файл)
            if response.content:
                await self.event_bus_logger.debug(f"Ответ LLM: {response.content[:500]}..." if len(response.content) > 500 else f"Ответ LLM: {response.content}")

    async def _log_llm_call_error(self, error: Exception, elapsed_time: float) -> None:
        """
        Логирование ошибки LLM вызова.

        Логирует:
        - Тип ошибки
        - Время до ошибки
        """
        self.event_bus_logger.error(
            f"❌ LLM ошибка | Модель: {self.model_name} | "
            f"{type(error).__name__}: {str(error)[:200]} | "
            f"Время: {elapsed_time:.2f}с"
        )
    
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
    async def _generate_impl(self, request: LLMRequest) -> LLMResponse:
        """
        Реализация генерации текста в подклассе.
        
        ПАРАМЕТРЫ:
        - request (LLMRequest): Запрос на генерацию
        
        ВОЗВРАЩАЕТ:
        - LLMResponse: Ответ от модели
        """
        pass

    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Генерация текста на основе запроса с логированием.
        
        ЛОГИРОВАНИЕ:
        - Начало вызова: промт, параметры
        - Завершение: ответ, время генерации
        - Ошибки: тип и сообщение
        
        ПАРАМЕТРЫ:
        - request (LLMRequest): Запрос на генерацию
        
        ВОЗВРАЩАЕТ:
        - LLMResponse: Ответ от модели
        """
        start_time = time.time()
        
        # Логирование начала вызова
        await self._log_llm_call_start(request)
        
        try:
            # Вызов реализации
            response = await self._generate_impl(request)
            
            # Логирование завершения
            elapsed = time.time() - start_time
            await self._log_llm_call_end(response, elapsed)
            
            return response
            
        except Exception as e:
            # Логирование ошибки
            elapsed = time.time() - start_time
            await self._log_llm_call_error(e, elapsed)
            raise

    @abstractmethod
    async def _generate_structured_impl(
        self,
        request: LLMRequest
    ) -> StructuredLLMResponse:
        """
        Реализация генерации структурированных данных в подклассе.
        
        ПАРАМЕТРЫ:
        - request (LLMRequest): Запрос с configuration структурированного вывода
        
        ВОЗВРАЩАЕТ:
        - StructuredLLMResponse: Типизированный ответ с валидной моделью
        
        RAISES:
        - StructuredOutputError: Если не удалось получить валидный ответ
        - ValueError: Если request.structured_output не указан
        """
        pass

    async def generate_structured(
        self,
        request: LLMRequest
    ) -> StructuredLLMResponse:
        """
        Генерация структурированных данных по JSON Schema с логированием.

        ЛОГИРОВАНИЕ:
        - Начало вызова: промт, параметры, схема
        - Завершение: ответ, время генерации, количество попыток
        - Ошибки: тип и сообщение

        ПАРАМЕТРЫ:
        - request (LLMRequest): Запрос с configuration структурированного вывода
          request.structured_output должен содержать:
          - output_model: Имя модели
          - schema_def: JSON Schema
          - max_retries: Количество попыток
          - strict_mode: Строгая валидация

        ВОЗВРАЩАЕТ:
        - StructuredLLMResponse: Типизированный ответ с валидной моделью
          - parsed_content: Pydantic модель с данными
          - raw_response: Сырой ответ для отладки
          - parsing_attempts: Количество попыток парсинга
          - validation_errors: Ошибки предыдущих попыток

        RAISES:
        - StructuredOutputError: Если не удалось получить валидный ответ после всех попыток
        - ValueError: Если request.structured_output не указан
        """
        start_time = time.time()
        
        # Логирование начала вызова
        self.event_bus_logger.info(
            f"📝 LLM структурированный вызов | Модель: {self.model_name} | "
            f"Промт: {len(request.prompt)} симв. | "
            f"Schema: {request.structured_output.output_model if request.structured_output else 'unknown'} | "
            f"Max retries: {request.structured_output.max_retries if request.structured_output else 3}"
        )
        
        try:
            # Вызов реализации
            response = await self._generate_structured_impl(request)
            
            # Логирование завершения
            elapsed = time.time() - start_time
            self.event_bus_logger.info(
                f"✅ LLM структурированный ответ | Модель: {self.model_name} | "
                f"Время: {elapsed:.2f}с | "
                f"Попыток: {response.parsing_attempts if hasattr(response, 'parsing_attempts') else 1}"
            )
            
            return response
            
        except Exception as e:
            # Логирование ошибки
            elapsed = time.time() - start_time
            self.event_bus_logger.error(
                f"❌ LLM структурированная ошибка | Модель: {self.model_name} | "
                f"{type(e).__name__}: {str(e)[:200]} | "
                f"Время: {elapsed:.2f}с"
            )
            raise

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