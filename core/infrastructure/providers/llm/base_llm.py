"""
Базовый класс для всех LLM провайдеров.
Реализует стандартный интерфейс для работы с различными LLM бэкендами.

АРХИТЕКТУРА CORRELATION ID:
- correlation_id генерируется ЗДЕСЬ, в базовом классе
- Один ID для пары prompt/response (трассировка запроса)
- Инкапсулировано в провайдере (паттерны не знают о correlation_id)
- Все провайдеры наследуют единое поведение автоматически
"""

import time
import uuid
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from core.retry_policy.retry_and_error_policy import RetryPolicy
from core.models.types.llm_types import LLMHealthStatus, LLMRequest, LLMResponse, StructuredOutputConfig, StructuredLLMResponse
from core.infrastructure.providers.base_provider import BaseProvider, ProviderHealthStatus
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus, EventType


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

    CORRELATION ID:
    - Генерируется в generate_structured() для каждого вызова
    - Публикуется в событиях LLM_PROMPT_GENERATED и LLM_RESPONSE_RECEIVED
    - Одинаковый для пары промпт-ответ (трассировка запроса)
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

        # Логгер для LLM вызовов больше не используется — всё логирование через event_bus_logger
        self._llm_logger = None

        # Контекст вызова для логирования (устанавливается через set_call_context)
        self._event_bus: Optional[UnifiedEventBus] = None
        self._session_id: str = "system"
        self._agent_id: str = "system"
        self._component: str = "unknown"
        self._phase: str = "unknown"
        self._goal: str = "unknown"

    def set_call_context(
        self,
        event_bus: UnifiedEventBus,
        session_id: str,
        agent_id: str = None,
        component: str = None,
        phase: str = None,
        goal: str = None
    ):
        """
        Установка контекста вызова для логирования событий.

        ВАЖНО: correlation_id НЕ передаётся здесь — он генерируется
        автоматически в generate_structured() для каждого вызова.

        ПАРАМЕТРЫ:
        - event_bus: EventBus для публикации событий
        - session_id: ID сессии
        - agent_id: ID агента
        - component: компонент вызывающий LLM
        - phase: фаза выполнения (think/act)
        - goal: цель выполнения
        """
        self._event_bus = event_bus
        self._session_id = session_id
        self._agent_id = agent_id or "system"
        self._component = component or "unknown"
        self._phase = phase or "unknown"
        self._goal = goal or "unknown"

    async def _publish_prompt_event(
        self,
        request: LLMRequest,
        correlation_id: str
    ):
        """
        Публикация события о генерации промпта.

        ПАРАМЕТРЫ:
        - request: LLM запрос
        - correlation_id: ID для трассировки (генерируется в generate_structured)
        """
        if not self._event_bus:
            return

        await self._event_bus.publish(
            event_type=EventType.LLM_PROMPT_GENERATED,
            data={
                "component": self._component,
                "phase": self._phase,
                "system_prompt": request.system_prompt or "",
                "user_prompt": request.prompt,
                "prompt_length": len(request.prompt),
                "temperature": request.temperature,
                "max_tokens": request.max_tokens,
                "session_id": self._session_id,
                "agent_id": self._agent_id,
                "goal": self._goal,
            },
            source=f"{self._component}.llm_provider",
            session_id=self._session_id,
            agent_id=self._agent_id,
            correlation_id=correlation_id,
        )

    async def _publish_response_event(
        self,
        response: StructuredLLMResponse,
        correlation_id: str,
        elapsed_time: float
    ):
        """
        Публикация события о получении ответа.

        ПАРАМЕТРЫ:
        - response: Ответ от LLM
        - correlation_id: ID для трассировки (тот же что и у промпта)
        - elapsed_time: Время выполнения
        """
        if not self._event_bus:
            return

        # Извлекаем контент для логирования
        response_content = ""
        if hasattr(response, 'parsed_content'):
            response_content = str(response.parsed_content)[:500]
        elif hasattr(response, 'content'):
            response_content = str(response.content)[:500]

        await self._event_bus.publish(
            event_type=EventType.LLM_RESPONSE_RECEIVED,
            data={
                "component": self._component,
                "phase": self._phase,
                "response": response_content,
                "elapsed_ms": elapsed_time * 1000,
                "session_id": self._session_id,
                "agent_id": self._agent_id,
                "goal": self._goal,
            },
            source=f"{self._component}.llm_provider",
            session_id=self._session_id,
            agent_id=self._agent_id,
            correlation_id=correlation_id,
        )

    async def _publish_error_event(
        self,
        error: Exception,
        correlation_id: str,
        elapsed_time: float
    ):
        """
        Публикация события об ошибке LLM вызова.

        ПАРАМЕТРЫ:
        - error: Исключение
        - correlation_id: ID для трассировки
        - elapsed_time: Время до ошибки
        """
        if not self._event_bus:
            return

        await self._event_bus.publish(
            event_type=EventType.LLM_RESPONSE_RECEIVED,
            data={
                "component": self._component,
                "phase": self._phase,
                "error_type": type(error).__name__,
                "error_message": str(error)[:500],
                "elapsed_ms": elapsed_time * 1000,
                "session_id": self._session_id,
                "agent_id": self._agent_id,
                "goal": self._goal,
            },
            source=f"{self._component}.llm_provider",
            session_id=self._session_id,
            agent_id=self._agent_id,
            correlation_id=correlation_id,
        )

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

        # Логирует полный промт
        await self.event_bus_logger.info(f"Промт LLM ({len(request.prompt)} симв.): {request.prompt}")

    async def _log_llm_call_end(self, response: LLMResponse, elapsed_time: float) -> None:
        """
        Логирование завершения LLM вызова.

        Логирует:
        - Длину ответа
        - Время генерации
        - Статус (успех/ошибка)
        - Полный ответ
        """
        if response.finish_reason == "error":
            error_msg = 'unknown'
            if response.metadata:
                if isinstance(response.metadata, dict):
                    error_msg = response.metadata.get('error', 'unknown')
                elif isinstance(response.metadata, str):
                    error_msg = response.metadata
            await self.event_bus_logger.error(
                f"❌ LLM ответ | Модель: {self.model_name} | "
                f"Ошибка: {error_msg} | "
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

            # Логирует полный ответ
            if response.content:
                await self.event_bus_logger.info(f"Ответ LLM: {response.content}")

    async def _log_llm_call_error(self, error: Exception, elapsed_time: float) -> None:
        """
        Логирование ошибки LLM вызова.

        Логирует:
        - Тип ошибки
        - Время до ошибки
        """
        await self.event_bus_logger.error(
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
    ) -> LLMResponse:
        """
        Реализация генерации структурированных данных в подклассе.

        АРХИТЕКТУРА:
        - Провайдер ТОЛЬКО выполняет синхронный вызов модели
        - Возвращает сырой текст (LLMResponse)
        - Без retry, без парсинга JSON, без валидации
        - Вся логика структурированного вывода в LLMOrchestrator

        ПАРАМЕТРЫ:
        - request (LLMRequest): Запрос с configuration структурированного вывода

        ВОЗВРАЩАЕТ:
        - LLMResponse: Сырой ответ от модели
        """
        pass

    async def generate_structured(
        self,
        request: LLMRequest
    ) -> StructuredLLMResponse:
        """
        Генерация структурированных данных по JSON Schema.

        ВАЖНО: Этот метод для обратной совместимости.
        Для нового кода используйте LLMOrchestrator.execute_structured().

        АРХИТЕКТУРА:
        1. Вызывает _generate_structured_impl() для получения сырого ответа
        2. Парсит JSON и валидирует по схеме
        3. Возвращает StructuredLLMResponse

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
        # ✅ ГЕНЕРАЦИЯ correlation_id на уровне провайдера
        correlation_id = str(uuid.uuid4())

        start_time = time.time()

        # Публикация события LLM_PROMPT_GENERATED
        await self._publish_prompt_event(request, correlation_id)

        # Логирование начала вызова
        await self.event_bus_logger.info(
            f"📝 LLM структурированный вызов | Модель: {self.model_name} | "
            f"Промт: {len(request.prompt)} симв. | "
            f"Schema: {request.structured_output.output_model if request.structured_output else 'unknown'} | "
            f"correlation_id: {correlation_id}"
        )

        try:
            # Вызов реализации в подклассе (возвращает сырой LLMResponse)
            raw_response = await self._generate_structured_impl(request)

            # Парсинг и валидация (для обратной совместимости)
            # В новом коде это делает LLMOrchestrator
            structured_response = await self._parse_and_validate_structured_response(
                raw_response=raw_response,
                schema=request.structured_output.schema_def if request.structured_output else None,
                output_model=request.structured_output.output_model if request.structured_output else "Unknown"
            )

            # Логирование завершения
            elapsed = time.time() - start_time
            await self.event_bus_logger.info(
                f"✅ LLM структурированный ответ | Модель: {self.model_name} | "
                f"Время: {elapsed:.2f}с | "
                f"Попыток: {structured_response.parsing_attempts} | "
                f"correlation_id: {correlation_id}"
            )

            # Публикация события LLM_RESPONSE_RECEIVED
            await self._publish_response_event(structured_response, correlation_id, elapsed)

            return structured_response

        except Exception as e:
            # Логирование ошибки
            elapsed = time.time() - start_time
            await self.event_bus_logger.error(
                f"❌ LLM структурированная ошибка | Модель: {self.model_name} | "
                f"{type(e).__name__}: {str(e)[:200]} | "
                f"Время: {elapsed:.2f}с | "
                f"correlation_id: {correlation_id}"
            )

            # Публикация события об ошибке
            await self._publish_error_event(e, correlation_id, elapsed)
            raise

    async def _parse_and_validate_structured_response(
        self,
        raw_response: LLMResponse,
        schema: Optional[Dict[str, Any]],
        output_model: str
    ) -> StructuredLLMResponse:
        """
        Парсинг и валидация структурированного ответа.

        ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ - используется в generate_structured().
        В новом коде LLMOrchestrator выполняет эту логику.

        ПАРАМЕТРЫ:
        - raw_response: Сырой ответ от LLM
        - schema: JSON Schema для валидации
        - output_model: Имя модели для создания Pydantic класса

        ВОЗВРАЩАЕТ:
        - StructuredLLMResponse: Результат с валидной моделью
        """
        import json
        from pydantic import ValidationError, create_model

        # Извлечение JSON из ответа
        json_content = self._extract_json_from_response(raw_response.content)

        try:
            # Парсинг JSON
            parsed_json = json.loads(json_content)

            # Создание динамической Pydantic модели
            temp_model = self._create_pydantic_from_schema(output_model, schema)

            # Валидация
            parsed_content = temp_model.model_validate(parsed_json)

            # Успех
            return StructuredLLMResponse(
                parsed_content=parsed_content,
                raw_response=RawLLMResponse(
                    content=raw_response.content,
                    model=raw_response.model,
                    tokens_used=raw_response.tokens_used,
                    generation_time=raw_response.generation_time,
                    finish_reason=raw_response.finish_reason,
                    metadata=raw_response.metadata
                ),
                parsing_attempts=1,
                validation_errors=[],
                provider_native_validation=False
            )

        except (json.JSONDecodeError, ValidationError) as e:
            # Ошибка парсинга/валидации
            return StructuredLLMResponse(
                parsed_content=None,  # type: ignore
                raw_response=RawLLMResponse(
                    content=raw_response.content,
                    model=raw_response.model,
                    tokens_used=raw_response.tokens_used,
                    generation_time=raw_response.generation_time,
                    finish_reason="error",
                    metadata={"error": str(e)}
                ),
                parsing_attempts=1,
                validation_errors=[{
                    "error_type": type(e).__name__,
                    "message": str(e)
                }],
                provider_native_validation=False
            )

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