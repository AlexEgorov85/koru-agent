"""
Типы данных для LLM порта.
Содержит стандартизованные типы, необходимые для работы со всеми LLM провайдерами.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

class LLMHealthStatus(str, Enum):
    """
    Стандартизированные статусы здоровья для LLM провайдеров.
    
    ПРИНЦИПЫ:
    - Единый контракт для всех провайдеров
    - Поддержка graceful degradation
    - Интеграция с системой мониторинга
    
    ИСПОЛЬЗОВАНИЕ:
    status = provider.health_status
    if status == LLMHealthStatus.HEALTHY:
        proceed_with_request()
    elif status == LLMHealthStatus.DEGRADED:
        use_fallback_strategy()
    """
    HEALTHY = "healthy"        # Все системы работают нормально
    DEGRADED = "degraded"      # Работает с ограничениями (низкая производительность, частичный функционал)
    UNHEALTHY = "unhealthy"    # Критические проблемы, провайдер недоступен
    UNKNOWN = "unknown"        # Статус неизвестен (инициализация, нет данных)

@dataclass
class LLMRequest:
    """
    Стандартизированная структура запроса к LLM.
    
    АРХИТЕКТУРНАЯ РОЛЬ:
    - Определяет контракт для всех LLM провайдеров
    - Обеспечивает типизацию и валидацию параметров
    - Поддерживает расширяемость без изменения бизнес-логики
    
    ПОЛЯ:
    - prompt: Основной текст запроса
    - system_prompt: Роль системы/ассистента
    - temperature: Креативность генерации (0.0-1.0)
    - max_tokens: Максимальная длина ответа
    - top_p: Фильтрация токенов по вероятности
    - frequency_penalty: Штраф за повторение
    - presence_penalty: Штраф за новые токены
    - stream: Флаг потоковой генерации
    - meta Дополнительные параметры для конкретных провайдеров
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    request = LLMRequest(
        prompt="Объясни квантовые вычисления",
        system_prompt="Ты — эксперт по физике",
        temperature=0.7,
        max_tokens=500,
        metadata={"response_format": {"type": "json_object"}}
    )
    """
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 500
    top_p: float = 0.95
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stream: bool = False
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        """Валидация параметров после инициализации."""
        if self.metadata is None:
            self.metadata = {}
        
        # Валидация числовых параметров
        self.temperature = max(0.0, min(1.0, self.temperature))
        self.max_tokens = max(1, min(4096, self.max_tokens))
        self.top_p = max(0.0, min(1.0, self.top_p))
        self.frequency_penalty = max(0.0, min(2.0, self.frequency_penalty))
        self.presence_penalty = max(0.0, min(2.0, self.presence_penalty))

@dataclass
class LLMResponse:
    """
    Стандартизированная структура ответа от LLM.
    
    ПРИНЦИПЫ:
    - Единый формат для всех провайдеров
    - Поддержка метрик и отладки
    - Типизированное содержимое
    
    ПОЛЯ:
    - content: Сгенерированный текст
    - model: Название модели, которая сгенерировала ответ
    - tokens_used: Количество использованных токенов
    - generation_time: Время генерации в секундах
    - finish_reason: Причина завершения генерации
    - meta Дополнительные метаданные для анализа
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    response = await provider.generate(request)
    print(f"Модель: {response.model}")
    print(f"Токенов использовано: {response.tokens_used}")
    print(f"Время генерации: {response.generation_time:.2f}с")
    print(f"Ответ: {response.content}")
    """
    content: str
    model: str
    tokens_used: int
    generation_time: float
    finish_reason: str = "stop"
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        
        # Валидация
        self.tokens_used = max(0, self.tokens_used)
        self.generation_time = max(0.0, self.generation_time)

class LLMProviderType(str, Enum):
    """Типы LLM провайдеров для метрик и логирования."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic" 
    LOCAL_LLAMA = "local_llama"
    GEMINI = "gemini"
    CUSTOM = "custom"