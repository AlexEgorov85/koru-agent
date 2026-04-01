"""
Типы данных для LLM порта.
Содержит стандартизованные типы, необходимые для работы со всеми LLM провайдерами.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Generic, TypeVar, List, Union
from pydantic import BaseModel as PydanticBaseModel, Field
import json
from pydantic import ValidationError

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

class StructuredOutputConfig(PydanticBaseModel):
    """
    Конфигурация структурированного вывода.
    Вынесен в отдельную модель для гибкости и переиспользования.
    
    Поддерживает:
    - schema_def как dict (JSON Schema)
    - schema_def как Pydantic модель (автоматически конвертируется в JSON Schema)
    """
    output_model: str  # Имя модели (для сериализации в события)
    schema_def: Dict[str, Any]  # JSON Schema или Pydantic модель (конвертируется автоматически)
    max_retries: int = Field(default=3, ge=1, le=5)
    strict_mode: bool = Field(default=True, description="Строгая валидация (все поля обязательны)")
    
    def __init__(self, **data):
        # Автоматическая конвертация Pydantic модели в JSON Schema
        schema_def = data.get('schema_def')
        if schema_def is not None and hasattr(schema_def, 'model_json_schema'):
            data['schema_def'] = schema_def.model_json_schema()
        super().__init__(**data)

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
    - structured_output: Опциональная конфигурация структурированного вывода
    - metadata: Дополнительные параметры для конкретных провайдеров
    - correlation_id: ID для трассировки запроса
    - capability_name: Имя capability для интеграции с PromptService

    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    request = LLMRequest(
        prompt="Объясни квантовые вычисления",
        system_prompt="Ты — эксперт по физике",
        temperature=0.7,
        max_tokens=500,
        structured_output=StructuredOutputConfig(
            output_model="ExplanationOutput",
            schema=ExplanationOutput.model_json_schema(),
            max_retries=3
        )
    )
    """
    prompt: str
    system_prompt: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 500
    top_p: float = 0.95
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop_sequences: Optional[List[str]] = None  # Последовательности для остановки генерации
    stream: bool = False
    structured_output: Optional[StructuredOutputConfig] = Field(
        default=None,
        description="Конфигурация структурированного вывода. Если None — возвращается сырой текст."
    )
    metadata: Dict[str, Any] = None
    correlation_id: Optional[str] = None
    capability_name: Optional[str] = None  # Для интеграции с PromptService

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
class RawLLMResponse:
    """
    Сырой ответ от LLM (без структуризации).
    """
    content: str
    model: str
    tokens_used: int
    generation_time: float
    finish_reason: str = "stop"
    raw_provider_response: Any = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}

        # Валидация
        self.tokens_used = max(0, self.tokens_used)
        self.generation_time = max(0.0, self.generation_time)

T = TypeVar('T', bound=PydanticBaseModel)

@dataclass
class LLMResponse(Generic[T]):
    """
    УНИВЕРСАЛЬНЫЙ ответ от LLM.
    
    Поддерживает:
    - Обычные текстовые ответы (content)
    - Структурированные ответы (parsed_content)
    - Сырой ответ для отладки (raw_response)

    ПОЛЯ:
    - content: Текст ответа (для простых запросов)
    - parsed_content: Pydantic модель (для структурированных запросов)
    - raw_response: Сырой ответ с метаданными
    - tokens_used: Количество токенов
    - generation_time: Время генерации
    - finish_reason: Причина завершения
    - validation_errors: Ошибки валидации (для структурированных)
    - metadata: Дополнительные данные

    ПРИМЕРЫ:
    # Простой текстовый ответ
    response = LLMResponse(
        content="Привет, мир!",
        model="llama-3.2",
        tokens_used=50
    )
    
    # Структурированный ответ
    response = LLMResponse(
        parsed_content=ReasoningModel(reason="...", action="..."),
        raw_response=RawLLMResponse(content='{"reason": "..."}', ...),
        model="llama-3.2",
        tokens_used=150
    )
    """
    # Контент (для простых ответов)
    content: str = ""
    
    # Структурированный контент (для JSON ответов)
    parsed_content: Optional[T] = None
    
    # Сырой ответ с метаданными
    raw_response: Optional['RawLLMResponse'] = None
    
    # Метаданные
    model: str = "unknown"
    tokens_used: int = 0
    generation_time: float = 0.0
    finish_reason: str = "stop"
    metadata: Dict[str, Any] = None
    
    # Для структурированных ответов
    parsing_attempts: int = 0
    validation_errors: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.validation_errors is None:
            self.validation_errors = []
        
        # Валидация
        self.tokens_used = max(0, self.tokens_used)
        self.generation_time = max(0.0, self.generation_time)
    
    @property
    def success(self) -> bool:
        """True если нет ошибок валидации."""
        return len(self.validation_errors) == 0
    
    @property
    def is_structured(self) -> bool:
        """True если это структурированный ответ."""
        return self.parsed_content is not None

class LLMProviderType(str, Enum):
    """Типы LLM провайдеров для метрик и логирования."""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL_LLAMA = "local_llama"
    GEMINI = "gemini"
    CUSTOM = "custom"