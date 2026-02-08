from dataclasses import dataclass
from typing import Any, Optional, Dict
from domain.models.execution.execution_status import ExecutionStatus
from datetime import datetime


@dataclass
class ExecutionResult:
    """
    Класс для хранения результата выполнения действия.
    
    ПОЛЯ:
    - status: Статус выполнения (ExecutionStatus)
    - observation_item_id: ID элемента с результатом наблюдения в DataContext
    - summary: Краткое описание результата
    - error: Описание ошибки (если есть)
    - result: Результат выполнения (опционально)
    - execution_time: Время выполнения операции
    - progress_metadata: Метаданные прогресса выполнения
    - action_metadata: Метаданные действия
    - iteration_number: Номер итерации ReAct (если применимо)
    - undo_operation: Информация о возможности отката операции
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    result = ExecutionResult(
        status=ExecutionStatus.SUCCESS,
        observation_item_id="obs_123",
        summary="Запрос к базе данных выполнен успешно",
        execution_time=0.125
    )
    
    ОСОБЕННОСТИ:
    - observation_item_id может быть None при ошибке
    - summary всегда содержит человекочитаемое описание
    - error заполняется только при статусе FAILED
    - execution_time позволяет отслеживать производительность
    - progress_metadata содержит информацию о прогрессе выполнения
    """
    status: ExecutionStatus
    result: Optional[Any]
    observation_item_id: Optional[str]
    summary: str
    error: Optional[str] = None
    execution_time: float = 0.0  # Время выполнения операции в секундах
    progress_metadata: Optional[Dict[str, Any]] = None  # Метаданные прогресса
    action_metadata: Optional[Dict[str, Any]] = None    # Метаданные действия
    iteration_number: Optional[int] = None              # Номер итерации ReAct
    undo_operation: Optional[Dict[str, Any]] = None     # Информация для отката операции
    timestamp: datetime = None                          # Время создания результата
    
    # Добавляем атрибут для хранения событий для публикации
    events_to_publish: Optional[list] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.progress_metadata is None:
            self.progress_metadata = {}
        if self.action_metadata is None:
            self.action_metadata = {}
        if self.events_to_publish is None:
            self.events_to_publish = []
