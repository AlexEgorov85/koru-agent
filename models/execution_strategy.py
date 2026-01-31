from enum import Enum
from pydantic import BaseModel
from typing import Dict, Any, Optional, List


class ExecutionStrategyType(str, Enum):
    """
    Тип стратегии выполнения.
    """
    REACT = "react"
    PLANNING = "planning"
    THINKING = "thinking"
    EVALUATION = "evaluation"
    FALLBACK = "fallback"
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"


class StrategyStatus(str, Enum):
    """
    Статус результата стратегии.
    """
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    RUNNING = "running"
    PENDING = "pending"


class ExecutionStrategy(BaseModel):
    """
    Модель стратегии выполнения.
    """
    name: str
    description: str
    strategy_type: ExecutionStrategyType
    parameters: Dict[str, Any] = {}
    enabled: bool = True
    metadata: Dict[str, Any] = {}


class StrategyConfig(BaseModel):
    """
    Конфигурация стратегии.
    """
    name: str
    strategy_name: str
    parameters: Dict[str, Any] = {}
    enabled: bool = True
    metadata: Dict[str, Any] = {}


class StrategyResult(BaseModel):
    """
    Результат выполнения стратегии.
    """
    status: str
    result_data: Dict[str, Any]
    error: Optional[str] = None
    metadata: Dict[str, Any] = {}