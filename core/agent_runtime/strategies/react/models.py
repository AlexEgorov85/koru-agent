"""
Pydantic модели для структурированных рассуждений.
ОСОБЕННОСТИ:
- Все модели вынесены в отдельный файл
- Четкая структура и валидация
- Поддержка вложенных объектов
- Автоматическая генерация JSON Schema
"""
from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator

class AnalysisResult(BaseModel):
    """
    Модель для анализа текущей ситуации.
    """
    current_situation: str = Field(..., description="Анализ текущей ситуации, контекста и выполненных шагов", min_length=10, max_length=1000)
    progress_assessment: str = Field(..., description="Оценка прогресса в достижении цели", min_length=5, max_length=500)
    confidence: float = Field(..., description="Уровень уверенности в текущем подходе (0.0 - нет уверенности, 1.0 - полная уверенность)", ge=0.0, le=1.0)
    errors_detected: bool = Field(..., description="Обнаружены ли ошибки в последних шагах")
    consecutive_errors: int = Field(..., description="Количество последовательных ошибок", ge=0)
    has_plan: bool = Field(..., description="Существует ли текущий план действий")
    plan_status: str = Field(..., description="Статус текущего плана (active/completed/failed)")
    execution_time: float = Field(..., description="Время выполнения сессии в секундах", ge=0.0)
    no_progress_steps: int = Field(..., description="Количество шагов без значимого прогресса", ge=0)
    result_last_step: str = Field(..., description="Корректен результат на последнем шаге? Какие выводы можно из этого сделать?", min_length=5, max_length=500)
    param_last_step: str = Field(..., description="Значения в параметрах вызова навыка соотвествуют описанию полей параметров?", min_length=5, max_length=500)

class RecommendedAction(BaseModel):
    """
    Модель для рекомендуемого действия агента.
    """
    action_type: Literal["execute_capability", "rollback", "stop"] = Field(..., description="Тип рекомендуемого действия")
    capability_name: Optional[str] = Field(None, description="Имя capability для выполнения (только для action_type=execute_capability)")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Параметры для capability (только для action_type=execute_capability)")
    reasoning: str = Field(..., description="Обоснование выбора действия", min_length=10)

class ReasoningResult(BaseModel):
    """
    Основная модель для результатов структурированных рассуждений.
    """
    analysis: AnalysisResult = Field(..., description="Детальный анализ текущей ситуации")
    needs_rollback: bool = Field(..., description="Требуется ли откат на предыдущие шаги")
    rollback_steps: Optional[int] = Field(None, description="Количество шагов для отката (только если needs_rollback=true)", ge=1, le=3)
    recommended_action: RecommendedAction = Field(..., description="Детали рекомендуемого действия")
    alternative_approaches: List[str] = Field(
        default_factory=list,
        description="Список альтернативных подходов",
        max_items=5
    )

    @model_validator(mode='after')
    def validate_rollback_requirements(self):
        """Валидация: rollback_steps требуется если needs_rollback=true."""
        if self.needs_rollback and self.rollback_steps is None:
            raise ValueError("rollback_steps required when needs_rollback is true")
        if not self.needs_rollback and self.rollback_steps is not None:
            raise ValueError("rollback_steps should not be provided when needs_rollback is false")
        
        return self