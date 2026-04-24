"""
Модели для конфигурируемых шагов агента.

АРХИТЕКТУРА:
- StepConfig — декларативная конфигурация шага из YAML
- StepInstance —runtime-экземпляр шага с состоянием выполнения
- StepMetrics — метрики выполнения конкретного шага

ПРИМЕР ИСПОЛЬЗОВАНИЯ:
```python
from core.agent.models import StepConfig

config = StepConfig(
    capability="sql_generation.generate",
    timeout_ms=30000,
    max_retries=2,
    on_error="fallback",
    fallback_capability="sql_generation.simple"
)
```
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, List, Optional, Any, Literal
from datetime import datetime
from enum import Enum


class StepOnErrorStrategy(str, Enum):
    """Стратегия обработки ошибок шага."""
    RETRY = "retry"           # Повторить с задержкой
    FALLBACK = "fallback"     # Переключиться на fallback_capability
    STOP = "stop"             # Остановить выполнение агента


class StepConfig(BaseModel):
    """
    Конфигурация шага агента.
    
    АТРИБУТЫ:
    - capability: имя capability для выполнения (обязательно)
    - description: человекочитаемое описание шага
    - timeout_ms: таймаут выполнения в миллисекундах
    - max_retries: максимальное количество попыток (0 = без retry)
    - retry_delay_ms: базовая задержка между попытками
    - retry_backoff_multiplier: множитель экспоненциального backoff
    - on_error: стратегия обработки ошибок
    - fallback_capability: резервная capability при ошибке
    - metadata: дополнительные метаданные для кастомной логики
    - parallel_group: опциональная группа для параллельного выполнения
    - depends_on: список step_id от которых зависит этот шаг
    """
    model_config = ConfigDict(frozen=False)  # Мутабельная для runtime-модификаций
    
    # Обязательные поля
    capability: str = Field(..., description="Имя capability для выполнения")
    
    # Опциональные поля
    description: Optional[str] = Field(None, description="Описание шага")
    timeout_ms: int = Field(default=60000, gt=0, le=300000, description="Таймаут в мс")
    max_retries: int = Field(default=1, ge=0, le=5, description="Максимум попыток")
    retry_delay_ms: int = Field(default=1000, ge=0, le=10000, description="Базовая задержка retry")
    retry_backoff_multiplier: float = Field(default=2.0, ge=1.0, le=5.0, description="Множитель backoff")
    
    # Обработка ошибок
    on_error: StepOnErrorStrategy = Field(default=StepOnErrorStrategy.RETRY)
    fallback_capability: Optional[str] = Field(None, description="Резервная capability")
    
    # Метаданные
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Дополнительные метаданные")
    
    # Параллельное выполнение (Phase 4)
    parallel_group: Optional[str] = Field(None, description="Группа для параллельного выполнения")
    depends_on: List[str] = Field(default_factory=list, description="Зависимости от других шагов")
    
    def has_fallback(self) -> bool:
        """Проверка наличия fallback capability."""
        return self.fallback_capability is not None and len(self.fallback_capability) > 0
    
    def has_retry(self) -> bool:
        """Проверка необходимости retry."""
        return self.max_retries > 0
    
    def get_timeout_seconds(self) -> float:
        """Получить таймаут в секундах."""
        return self.timeout_ms / 1000.0
    
    def get_retry_delay_seconds(self, attempt: int) -> float:
        """
        Рассчитать задержку перед retry с экспоненциальным backoff.
        
        ПАРАМЕТРЫ:
        - attempt: номер попытки (0-based)
        
        ВОЗВРАЩАЕТ:
        - задержка в секундах
        """
        delay_ms = self.retry_delay_ms * (self.retry_backoff_multiplier ** attempt)
        return delay_ms / 1000.0


class StepExecutionStatus(str, Enum):
    """Статус выполнения шага."""
    PENDING = "pending"       # Ожидает выполнения
    RUNNING = "running"       # Выполняется
    COMPLETED = "completed"   # Успешно завершён
    FAILED = "failed"         # Завершён с ошибкой
    TIMEOUT = "timeout"       # Превышен таймаут
    FALLBACK_USED = "fallback_used"  # Использован fallback
    SKIPPED = "skipped"       # Пропущен (зависимость не выполнена)


class StepAttempt(BaseModel):
    """
    Информация об одной попытке выполнения шага.
    
    АТРИБУТЫ:
    - attempt_number: номер попытки (1-based)
    - started_at: время начала попытки
    - completed_at: время завершения попытки
    - duration_ms: длительность в мс
    - status: статус попытки
    - error: описание ошибки (если была)
    - error_type: тип ошибки
    """
    attempt_number: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    status: StepExecutionStatus
    error: Optional[str] = None
    error_type: Optional[str] = None


class StepMetrics(BaseModel):
    """
    Метрики выполнения шага.
    
    АТРИБУТЫ:
    - step_id: идентификатор шага
    - capability: имя выполненной capability
    - total_attempts: общее количество попыток
    - successful_attempt: номер успешной попытки (если была)
    - fallback_triggered: был ли использован fallback
    - total_duration_ms: общая длительность всех попыток
    - avg_duration_ms: средняя длительность попытки
    - attempts: детализация по попыткам
    """
    step_id: str
    capability: str
    total_attempts: int = 0
    successful_attempt: Optional[int] = None
    fallback_triggered: bool = False
    total_duration_ms: int = 0
    avg_duration_ms: float = 0.0
    attempts: List[StepAttempt] = Field(default_factory=list)
    
    def add_attempt(self, attempt: StepAttempt):
        """Добавить информацию о попытке."""
        self.attempts.append(attempt)
        self.total_attempts += 1
        
        if attempt.duration_ms:
            self.total_duration_ms += attempt.duration_ms
            self.avg_duration_ms = self.total_duration_ms / self.total_attempts
        
        if attempt.status == StepExecutionStatus.COMPLETED:
            self.successful_attempt = attempt.attempt_number
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь."""
        return self.model_dump(mode='json')


class StepInstance(BaseModel):
    """
    Runtime-экземпляр шага с состоянием выполнения.
    
    АТРИБУТЫ:
    - step_id: уникальный идентификатор экземпляра
    - config: конфигурация шага
    - status: текущий статус выполнения
    - metrics: метрики выполнения
    - data: результат выполнения (если завершён)
    - created_at: время создания
    - updated_at: время последнего обновления
    """
    step_id: str
    config: StepConfig
    status: StepExecutionStatus = StepExecutionStatus.PENDING
    metrics: StepMetrics = None  # type: ignore
    data: Optional[Dict[str, Any]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    def __init__(self, **data):
        super().__init__(**data)
        if self.metrics is None:
            self.metrics = StepMetrics(
                step_id=self.step_id,
                capability=self.config.capability
            )
    
    def mark_running(self):
        """Отметить шаг как выполняемый."""
        self.status = StepExecutionStatus.RUNNING
        self.updated_at = datetime.utcnow()
    
    def mark_completed(self, data: Optional[Dict[str, Any]] = None):
        """Отметить шаг как завершённый успешно."""
        self.status = StepExecutionStatus.COMPLETED
        self.data = data
        self.updated_at = datetime.utcnow()
    
    def mark_failed(self, error: str, error_type: Optional[str] = None):
        """Отметить шаг как завершённый с ошибкой."""
        self.status = StepExecutionStatus.FAILED
        self.data = {"error": error, "error_type": error_type}
        self.updated_at = datetime.utcnow()
    
    def mark_timeout(self):
        """Отметить шаг как превысивший таймаут."""
        self.status = StepExecutionStatus.TIMEOUT
        self.updated_at = datetime.utcnow()
    
    def mark_fallback_used(self):
        """Отметить что был использован fallback."""
        self.status = StepExecutionStatus.FALLBACK_USED
        self.metrics.fallback_triggered = True
        self.updated_at = datetime.utcnow()
    
    def is_finished(self) -> bool:
        """Проверка завершённости шага."""
        return self.status in {
            StepExecutionStatus.COMPLETED,
            StepExecutionStatus.FAILED,
            StepExecutionStatus.TIMEOUT,
            StepExecutionStatus.SKIPPED
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация в словарь."""
        return {
            "step_id": self.step_id,
            "capability": self.config.capability,
            "status": self.status.value,
            "metrics": self.metrics.to_dict(),
            "data": self.data,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }
