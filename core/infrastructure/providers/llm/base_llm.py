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


from core.models.types.llm_types import LLMHealthStatus, LLMRequest, LLMResponse, StructuredOutputConfig
from core.infrastructure.providers.base_provider import BaseProvider, ProviderHealthStatus
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.infrastructure.event_bus.unified_event_bus import UnifiedEventBus


class BaseLLMProvider(BaseProvider, ABC):
    """
    Базовый класс для всех LLM-провайдеров.

    АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
    1. Инверсия зависимостей: Зависит только от абстракций (LLMPort)
    2. Единый контракт: Все методы имеют стандартизированную сигнатуру
    3. Безопасность по умолчанию: Встроенные ограничения и валидация
    4. Наблюдаемость: Автоматическое логирование и метрики
    5. Отказоустойчивость: Грациозная деградация при ошибках


    ИСПОЛЬЗОВАНИЕ:
    # Для структурированной генерации используйте LLMOrchestrator:
    orchestrator = app_context.llm_orchestrator
    response = await orchestrator.execute_structured(
        request=request,
        provider=llm_provider,
        max_retries=3
    )
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

        # Контекст вызова для публикации событий (устанавливается через set_call_context)
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

    async def _log_llm_call_start(self, request: LLMRequest) -> None:
        """Логирование начала LLM вызова."""
        self.log.info("📝 LLM вызов | Модель: %s | Промт: %d симв. | Max tokens: %d | Temperature: %s",
                      self.model_name, len(request.prompt), request.max_tokens, request.temperature,
                      extra={"event_type": EventType.LLM_CALL})

        self.log.debug("Промт LLM (%d симв.): %s", len(request.prompt), request.prompt,
                       extra={"event_type": EventType.LLM_CALL})

    async def _log_llm_call_end(self, response: LLMResponse, elapsed_time: float) -> None:
        """Логирование завершения LLM вызова."""
        if response.finish_reason == "error":
            error_msg = 'unknown'
            if response.metadata:
                if isinstance(response.metadata, dict):
                    error_msg = response.metadata.get('error', 'unknown')
                elif isinstance(response.metadata, str):
                    error_msg = response.metadata
            self.log.error("❌ LLM ответ | Модель: %s | Ошибка: %s | Время: %.2fс",
                           self.model_name, error_msg, elapsed_time,
                           extra={"event_type": EventType.LLM_ERROR})
        else:
            content_length = len(response.content) if response.content else 0
            self.log.info("✅ LLM ответ | Модель: %s | Ответ: %d симв. | Токенов: %s | Время: %.2fс | Причина: %s",
                          self.model_name, content_length, response.tokens_used, elapsed_time, response.finish_reason,
                          extra={"event_type": EventType.LLM_RESPONSE})

            if response.content:
                self.log.debug("Ответ LLM: %s", response.content,
                               extra={"event_type": EventType.LLM_RESPONSE})

    async def _log_llm_call_error(self, error: Exception, elapsed_time: float) -> None:
        """Логирование ошибки LLM вызова."""
        self.log.error("❌ LLM ошибка | Модель: %s | %s: %s | Время: %.2fс",
                       self.model_name, type(error).__name__, str(error), elapsed_time,
                       extra={"event_type": EventType.LLM_ERROR}, exc_info=True)
    
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

    def _validate_response_content(self, response: LLMResponse) -> bool:
        """
        Проверка что ответ от LLM не пустой.

        АРХИТЕКТУРА:
        - Проверяет все возможные поля ответа
        - Используется в _generate_impl() для раннего детектирования ошибок
        - Возвращает True только если есть непустой контент

        ПАРАМЕТРЫ:
        - response: Ответ от LLM

        ВОЗВРАЩАЕТ:
        - bool: True если ответ содержит непустой контент
        """
        # Проверяем parsed_content (структурированный ответ)
        if response.parsed_content is not None:
            return True

        # Проверяем content
        if response.content and response.content.strip():
            return True

        # Проверяем raw_response.content
        if response.raw_response and response.raw_response.content:
            if response.raw_response.content.strip():
                return True

        return False

    def get_model_info(self) -> Dict[str, Any]:
        """Получение информации о модели."""
        info = super().get_info()
        info["model_name"] = self.model_name
        info["health_status"] = self.health_status.value
        return info