"""
Base classes and enums for LLMOrchestrator.

Содержит:
- CallStatus: статусы LLM вызова
- RetryAttempt: информация о попытке структурированного вывода
- LLMMetrics: метрики LLM вызовов
- CallRecord: запись о вызове в реестре
"""
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, Optional, List
from datetime import datetime


class CallStatus(str, Enum):
    """Статусы LLM вызова."""
    PENDING = "pending"           # Ожидает запуска
    RUNNING = "running"           # Выполняется
    COMPLETED = "completed"       # Успешно завершён
    TIMED_OUT = "timed_out"       # Превышен таймаут (но поток ещё работает)
    FAILED = "failed"             # Ошибка выполнения
    CANCELLED = "cancelled"       # Отменён пользователем


@dataclass
class RetryAttempt:
    """Информация о попытке структурированного вывода."""
    attempt_number: int
    prompt: str
    raw_response: Optional[str]  # Сырой JSON текст
    parsed_content: Optional[Any] = None  # Распарсенная Pydantic модель
    success: bool = False
    error_type: Optional[str] = None  # "json_error", "validation_error", "incomplete", "timeout"
    error_message: Optional[str] = None
    duration: float = 0.0
    tokens_used: int = 0


@dataclass
class LLMMetrics:
    """Метрики LLM вызовов."""
    total_calls: int = 0
    completed_calls: int = 0
    timed_out_calls: int = 0
    failed_calls: int = 0
    orphaned_calls: int = 0  # Вызовы завершившиеся после таймаута
    total_generation_time: float = 0.0
    total_wait_time: float = 0.0  # Время ожидания в таймаутах
    cache_hits: int = 0
    
    # Метрики для структурированного вывода
    structured_calls: int = 0
    structured_success: int = 0
    structured_retries: int = 0  # Общее количество повторных попыток
    total_retry_attempts: int = 0  # Сумма всех попыток по всем вызовам

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.completed_calls / self.total_calls

    @property
    def structured_success_rate(self) -> float:
        if self.structured_calls == 0:
            return 0.0
        return self.structured_success / self.structured_calls

    @property
    def average_generation_time(self) -> float:
        if self.completed_calls == 0:
            return 0.0
        return self.total_generation_time / self.completed_calls

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "completed_calls": self.completed_calls,
            "timed_out_calls": self.timed_out_calls,
            "failed_calls": self.failed_calls,
            "orphaned_calls": self.orphaned_calls,
            "success_rate": self.success_rate,
            "average_generation_time": self.average_generation_time,
            "structured_calls": self.structured_calls,
            "structured_success": self.structured_success,
            "structured_success_rate": self.structured_success_rate,
            "structured_retries": self.structured_retries,
            "total_retry_attempts": self.total_retry_attempts
        }


@dataclass
class CallRecord:
    """Запись о LLM вызове в реестре."""
    call_id: str
    status: CallStatus
    request: Any
    provider: Any
    start_time: float
    timeout: float
    session_id: Optional[str] = None
    agent_id: Optional[str] = None
    step_number: Optional[int] = None
    phase: Optional[str] = None
    result: Any = None
    error: Optional[str] = None
    end_time: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    late_result: Any = None  # Результат пришедший после таймаута

    @property
    def elapsed(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time

    @property
    def is_active(self) -> bool:
        return self.status in (CallStatus.PENDING, CallStatus.RUNNING)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "status": self.status.value,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "step_number": self.step_number,
            "phase": self.phase,
            "start_time": datetime.fromtimestamp(self.start_time).isoformat() if self.start_time else None,
            "end_time": datetime.fromtimestamp(self.end_time).isoformat() if self.end_time else None,
            "elapsed": self.elapsed,
            "timeout": self.timeout,
            "error": self.error,
            "has_result": self.result is not None,
            "metadata": self.metadata
        }
