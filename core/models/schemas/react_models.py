"""
Модели данных для ReAct стратегии.

Содержит Pydantic-модели, используемые в ReAct стратегии агента.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ReasoningAnalysis(BaseModel):
    """Модель анализа текущей ситуации."""
    current_situation: str = Field(..., description="Текущая ситуация и контекст")
    progress_assessment: str = Field(..., description="Оценка прогресса к цели")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Уверенность в решении (0.0-1.0)")
    errors_detected: bool = Field(default=False, description="Обнаружены ли ошибки")


class RecommendedAction(BaseModel):
    """Модель рекомендованного действия."""
    action_type: str = Field(default="execute_capability", description="Тип действия")
    capability_name: str = Field(..., description="Имя capability для выполнения")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Параметры для capability")
    reasoning: str = Field(..., description="Обоснование выбора действия")


class ReasoningResult(BaseModel):
    """Модель результата рассуждения."""
    analysis: ReasoningAnalysis = Field(..., description="Анализ текущей ситуации")
    recommended_action: RecommendedAction = Field(..., description="Рекомендованное действие")
    needs_rollback: bool = Field(default=False, description="Требуется ли откат")
    rollback_steps: int = Field(default=0, description="Количество шагов для отката")