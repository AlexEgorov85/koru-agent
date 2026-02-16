"""
Модели данных для ReAct стратегии.

Содержит Pydantic-модели, используемые в ReAct стратегии агента.
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ReasoningAnalysis(BaseModel):
    """Модель анализа текущей ситуации."""
    thoughts: str = Field(..., description="Мысли агента о текущей ситуации")
    observations: List[str] = Field(..., description="Наблюдения, сделанные на основе контекста")
    gaps_in_knowledge: List[str] = Field(default_factory=list, description="Пробелы в знаниях, требующие дополнительных действий")
    confidence_level: float = Field(..., description="Уровень уверенности в анализе")


class RecommendedAction(BaseModel):
    """Модель рекомендованного действия."""
    action_type: str = Field(..., description="Тип действия (например, 'search', 'calculate', 'answer')")
    action_name: str = Field(..., description="Имя конкретного действия или инструмента")
    parameters: Dict[str, Any] = Field(..., description="Параметры для выполнения действия")
    reason: str = Field(..., description="Причина выбора этого действия")
    expected_outcome: str = Field(..., description="Ожидаемый результат выполнения действия")


class ReasoningResult(BaseModel):
    """Модель результата рассуждения."""
    analysis: ReasoningAnalysis = Field(..., description="Анализ текущей ситуации")
    recommended_action: RecommendedAction = Field(..., description="Рекомендованное действие")
    priority: int = Field(..., description="Приоритет действия (1 - высший)")
    alternative_actions: List[RecommendedAction] = Field(default_factory=list, description="Альтернативные действия")
    risk_assessment: Optional[str] = Field(None, description="Оценка рисков выбранного действия")