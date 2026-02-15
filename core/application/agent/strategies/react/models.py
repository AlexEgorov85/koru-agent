"""
Модели для ReAct стратегии в новой архитектуре
"""
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional


class ReasoningAnalysis(BaseModel):
    """Анализ текущей ситуации"""
    current_situation: str = Field(..., description="Текущая ситуация")
    progress_assessment: str = Field(..., description="Оценка прогресса")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Уверенность в оценке")
    errors_detected: bool = Field(False, description="Обнаружены ли ошибки")
    consecutive_errors: int = Field(0, description="Количество последовательных ошибок")
    execution_time: float = Field(0.0, description="Время выполнения")
    no_progress_steps: int = Field(0, description="Количество шагов без прогресса")


class RecommendedAction(BaseModel):
    """Рекомендованное действие"""
    action_type: str = Field(..., description="Тип действия")
    capability_name: str = Field(..., description="Название capability для выполнения")
    parameters: Dict[str, Any] = Field(..., description="Параметры для выполнения")
    reasoning: str = Field(..., description="Обоснование выбора действия")


class ReasoningResult(BaseModel):
    """Результат структурированного рассуждения"""
    analysis: ReasoningAnalysis = Field(..., description="Анализ текущей ситуации")
    recommended_action: RecommendedAction = Field(..., description="Рекомендованное действие")
    needs_rollback: bool = Field(False, description="Требуется ли откат")
    rollback_steps: int = Field(1, description="Количество шагов для отката")
    action_type: str = Field("execute_capability", description="Тип действия по умолчанию")