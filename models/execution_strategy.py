from enum import Enum
from pydantic import BaseModel
from typing import Dict, Any, Optional, List


class ExecutionStrategyType(str, Enum):
    """
    Тип стратегии выполнения.
    """
    REACT_COMPOSABLE = "react_composable"
    PLAN_AND_EXECUTE_COMPOSABLE = "plan_and_execute_composable"
    TOOL_USE_COMPOSABLE = "tool_use_composable"
    REFLECTION_COMPOSABLE = "reflection_composable"
    CODE_ANALYSIS_DEFAULT = "code_analysis.default"
    DATABASE_QUERY_DEFAULT = "database_query.default"
    RESEARCH_DEFAULT = "research.default"
    THINKING = "thinking"
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