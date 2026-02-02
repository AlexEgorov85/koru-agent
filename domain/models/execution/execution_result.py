from dataclasses import dataclass
from typing import Any, Optional
from domain.models.execution.execution_status import ExecutionStatus


@dataclass
class ExecutionResult:
    """
    Класс для хранения результата выполнения действия.
    
    ПОЛЯ:
    - status: Статус выполнения (ExecutionStatus)
    - observation_item_id: ID элемента с результатом наблюдения вDataContext
    - summary: Краткое описание результата
    - error: Описание ошибки (если есть)
    - result: Результат выполнения (опционально)
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    result = ExecutionResult(
        status=ExecutionStatus.SUCCESS,
        observation_item_id="obs_123",
        summary="Запрос к базе данных выполнен успешно"
    )
    
    ОСОБЕННОСТИ:
    - observation_item_id может быть None при ошибке
    - summary всегда содержит человекочитаемое описание
    - error заполняется только при статусе FAILED
    """
    status: ExecutionStatus
    result: Optional[Any]
    observation_item_id: Optional[str]
    summary: str
    error: Optional[str] = None