from enum import Enum
from pydantic import BaseModel, field_validator
from typing import List, Dict, Any, Optional
from domain.models.execution.execution_status import ExecutionStatus  # Используем общий enum


class AgentState(BaseModel):
    """
    Явное состояние агента.
    Не содержит логики — только данные.
    """

    step: int = 0
    error_count: int = 0
    no_progress_steps: int = 0
    finished: bool = False
    metrics: Dict[str, Any] = {}
    history: List[str] = []
    current_plan_step: Optional[str] = None

