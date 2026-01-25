
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional


class ExecutionStatus(str, Enum):
    """
    Перечисление возможных статусов выполнения действия.
    
    СТАТУСЫ:
    - SUCCESS: Действие выполнено успешно
    - FAILED: Действие завершилось с ошибкой
    
    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    if result.status == ExecutionStatus.SUCCESS:
        process_result(result.observation_item_id)
    elif result.status == ExecutionStatus.FAILED:
        handle_error(result.error)
    
    ЗАМЕЧАНИЕ:
    В будущем можно расширить перечисление дополнительными статусами,
    например, PARTIAL_SUCCESS или TIMEOUT.
    """
    SUCCESS = "success"
    FAILED = "failed"

@dataclass
class ExecutionResult:
    """
    Класс для хранения результата выполнения действия.
    
    ПОЛЯ:
    - status: Статус выполнения (ExecutionStatus)
    - observation_item_id: ID элемента с результатом наблюдения вDataContext
    - summary: Краткое описание результата
    - error: Описание ошибки (если есть)
    
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
