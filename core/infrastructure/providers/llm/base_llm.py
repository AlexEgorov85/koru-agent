"""
Базовый класс для всех LLM провайдеров.
Реализует стандартный интерфейс для работы с различными LLM бэкендами.
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from core.retry_policy.retry_and_error_policy import RetryPolicy
from models.llm_types import LLMHealthStatus, LLMRequest, LLMResponse

logger = logging.getLogger(__name__)

class BaseLLMProvider(ABC):
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
        self.model_name = model_name
        self.config = config or {}
        self.is_initialized = False
        self.health_status = LLMHealthStatus.UNKNOWN
        self.last_health_check = None
        self.creation_time = time.time()
        self.request_count = 0
        self.error_count = 0
        self.avg_response_time = 0.0
        self.retry_policy = None
        logger.info(f"Создан LLM-провайдер для модели: {model_name}")
    
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
    async def generate_structured(self, prompt: str, output_schema: Dict[str, Any], 
                                system_prompt: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        """Генерация структурированных данных по JSON Schema."""
        pass
    
    def _update_metrics(self, response_time: float, success: bool = True):
        """Обновление внутренних метрик провайдера."""
        self.request_count += 1
        if not success:
            self.error_count += 1
        
        # Обновляем среднее время ответа с экспоненциальным сглаживанием
        alpha = 0.2
        self.avg_response_time = alpha * response_time + (1 - alpha) * self.avg_response_time
        
        # Обновляем состояние здоровья на основе ошибок
        if self.error_count > 5 and self.request_count > 10:
            error_rate = self.error_count / self.request_count
            if error_rate > 0.2:
                self.health_status = LLMHealthStatus.DEGRADED
            if error_rate > 0.5:
                self.health_status = LLMHealthStatus.UNHEALTHY
    
    def set_retry_policy(self, policy: RetryPolicy):
        """Установка политики повторных попыток."""
        self.retry_policy = policy
    
    def get_model_info(self) -> Dict[str, Any]:
        """Получение информации о модели."""
        return {
            "model_name": self.model_name,
            "provider_type": self.__class__.__name__,
            "is_initialized": self.is_initialized,
            "health_status": self.health_status.value,
            "uptime_seconds": time.time() - self.creation_time,
            "request_count": self.request_count,
            "error_count": self.error_count,
            "avg_response_time": self.avg_response_time
        }