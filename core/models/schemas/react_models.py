"""
Модели данных для ReAct стратегии.

Содержит Pydantic-модели, используемые в ReAct стратегии агента.
Согласованы с контрактами в data/contracts/behavior/behavior/behavior.react.think_*.yaml
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ReasoningAnalysis(BaseModel):
    """Модель анализа текущей ситуации."""
    progress: str = Field(..., description="Описание прогресса к цели")
    current_state: str = Field(..., description="Текущее состояние задачи")
    issues: List[str] = Field(default_factory=list, description="Список проблем, если есть")


class ReasoningDecision(BaseModel):
    """Модель решения."""
    next_action: str = Field(..., description="Название следующего действия (capability_name)")
    reasoning: str = Field(..., description="Обоснование выбора")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Параметры для capability")
    expected_outcome: str = Field(..., description="Ожидаемый результат")


class ReasoningResult(BaseModel):
    """
    Модель результата рассуждения.
    
    СООТВЕТСТВУЕТ КОНТРАКТУ: behavior.react.think_output_v1.0.0
    """
    thought: str = Field(..., description="Развёрнутое рассуждение о текущей ситуации")
    analysis: ReasoningAnalysis = Field(..., description="Анализ текущей ситуации")
    decision: ReasoningDecision = Field(..., description="Решение о следующем действии")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Уверенность в решении (0.0-1.0)")
    alternative_actions: List[Dict[str, Any]] = Field(default_factory=list, description="Альтернативные действия")
    stop_condition: bool = Field(..., description="Флаг завершения работы")
    stop_reason: Optional[str] = Field(None, description="Причина остановки")