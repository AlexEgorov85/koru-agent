from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


class LLMProviderType(Enum):
    """
    Типы LLM-провайдеров.
    """
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL_LLAMA = "local_llama"
    COHERE = "cohere"
    HUGGINGFACE = "huggingface"


class LLMDecisionType(str, Enum):
    """
    Типы решений от LLM
    """
    EXECUTE_TOOL = "execute_tool"      # Выполнить инструмент (после валидации системой)
    PLAN_NEXT_STEP = "plan_next_step"  # Запланировать следующий шаг
    ASK_USER = "ask_user"              # Запросить уточнение у пользователя
    STOP = "stop"                      # Завершить выполнение


@dataclass
class LLMRequest:
    """
    Запрос к LLM.
    """
    prompt: str
    system_prompt: Optional[str] = None
    max_tokens: int = 1000
    temperature: float = 0.7
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    stop_sequences: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    # НОВОЕ: поддержка версионности промтов
    system_prompt_version_id: Optional[str] = None
    user_prompt_version_id: Optional[str] = None
    template_context: Optional[Dict[str, Any]] = None  # Контекст для подстановки переменных в шаблоны
    expected_response_schema: Optional[Dict[str, Any]] = None  # Ожидаемая схема ответа


@dataclass
class LLMResponse:
    """
    Ответ от LLM.
    """
    raw_text: str                      # Сырой ответ от LLM (для аудита)
    model: str
    tokens_used: int
    generation_time: float
    parsed: Optional[Dict[str, Any]] = None   # Валидированное решение (после парсинга)
    validation_error: Optional[str] = None    # Ошибка валидации (если есть)
    validation_attempts: int = 0       # Кол-во попыток валидации
    validation_chain: Optional[List[str]] = None  # Цепочка действий при валидации
    finish_reason: str = ""
    is_truncated: bool = False         # Флаг обрезанного ответа
    metadata: Optional[Dict[str, Any]] = None


class LLMHealthStatus(Enum):
    """
    Статус работоспособности LLM-провайдера.
    """
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"