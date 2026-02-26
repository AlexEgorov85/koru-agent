"""
Схемы данных для планирования.

Содержит Pydantic-модели, используемые в навыке планирования.
"""
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class StepStatus(str, Enum):
    """Статус шага плана."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class DecompositionStrategy(str, Enum):
    """Стратегии декомпозиции задач."""
    HIERARCHICAL = "hierarchical"
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    ADAPTIVE = "adaptive"


class PlanStep(BaseModel):
    """Модель шага плана."""
    id: str = Field(..., description="Уникальный идентификатор шага")
    description: str = Field(..., description="Описание шага")
    dependencies: List[str] = Field(default_factory=list, description="ID шагов, от которых зависит этот шаг")
    status: StepStatus = Field(default=StepStatus.PENDING, description="Статус выполнения шага")
    assigned_to: Optional[str] = Field(None, description="Кому назначен шаг")
    estimated_duration_minutes: Optional[int] = Field(None, description="Оценка времени выполнения в минутах")
    actual_duration_minutes: Optional[int] = Field(None, description="Фактическое время выполнения в минутах")


class SubTask(BaseModel):
    """Модель подзадачи."""
    id: str = Field(..., description="Уникальный идентификатор подзадачи")
    description: str = Field(..., description="Описание подзадачи")
    parent_task_id: str = Field(..., description="ID родительской задачи")
    status: StepStatus = Field(default=StepStatus.PENDING, description="Статус выполнения подзадачи")


class CreatePlanInput(BaseModel):
    """Входная схема для создания плана."""
    goal: str = Field(..., description="Цель, для достижения которой создается план")
    constraints: List[str] = Field(default_factory=list, description="Ограничения при планировании")
    resources: List[str] = Field(default_factory=list, description="Доступные ресурсы")
    decomposition_strategy: DecompositionStrategy = Field(
        default=DecompositionStrategy.HIERARCHICAL,
        description="Стратегия декомпозиции задач"
    )


class CreatePlanOutput(BaseModel):
    """Выходная схема для создания плана."""
    plan_id: str = Field(..., description="ID созданного плана")
    steps: List[PlanStep] = Field(..., description="Шаги плана")
    estimated_duration_hours: Optional[float] = Field(None, description="Оценка общей длительности в часах")


class UpdatePlanInput(BaseModel):
    """Входная схема для обновления плана."""
    plan_id: str = Field(..., description="ID плана для обновления")
    goal: Optional[str] = Field(None, description="Новая цель плана")
    constraints: Optional[List[str]] = Field(None, description="Новые ограничения")
    resources: Optional[List[str]] = Field(None, description="Новые ресурсы")


class UpdatePlanOutput(BaseModel):
    """Выходная схема для обновления плана."""
    plan_id: str = Field(..., description="ID обновленного плана")
    updated: bool = Field(..., description="Успешно ли обновлен план")


class GetNextStepInput(BaseModel):
    """Входная схема для получения следующего шага."""
    plan_id: str = Field(..., description="ID плана")
    current_step_id: Optional[str] = Field(None, description="ID текущего шага")


class GetNextStepOutput(BaseModel):
    """Выходная схема для получения следующего шага."""
    next_step: Optional[PlanStep] = Field(None, description="Следующий шаг плана")
    is_finished: bool = Field(False, description="Завершен ли план")


class UpdateStepStatusInput(BaseModel):
    """Входная схема для обновления статуса шага."""
    plan_id: str = Field(..., description="ID плана")
    step_id: str = Field(..., description="ID шага для обновления статуса")
    new_status: StepStatus = Field(..., description="Новый статус шага")
    notes: Optional[str] = Field(None, description="Дополнительные заметки")


class UpdateStepStatusOutput(BaseModel):
    """Выходная схема для обновления статуса шага."""
    step_id: str = Field(..., description="ID обновленного шага")
    updated_status: StepStatus = Field(..., description="Новый статус шага")
    success: bool = Field(..., description="Успешно ли обновлен статус")


class DecomposeTaskInput(BaseModel):
    """Входная схема для декомпозиции задачи."""
    task_description: str = Field(..., description="Описание задачи для декомпозиции")
    strategy: DecompositionStrategy = Field(
        default=DecompositionStrategy.HIERARCHICAL,
        description="Стратегия декомпозиции"
    )
    max_depth: int = Field(default=3, description="Максимальная глубина декомпозиции")


class DecomposeTaskOutput(BaseModel):
    """Выходная схема для декомпозиции задачи."""
    subtasks: List[SubTask] = Field(..., description="Результат декомпозиции - список подзадач")


class MarkTaskCompletedInput(BaseModel):
    """Входная схема для пометки задачи как выполненной."""
    plan_id: str = Field(..., description="ID плана")
    step_id: str = Field(..., description="ID шага для пометки как выполненного")
    result: Optional[str] = Field(None, description="Результат выполнения шага")


class MarkTaskCompletedOutput(BaseModel):
    """Выходная схема для пометки задачи как выполненной."""
    step_id: str = Field(..., description="ID выполненного шага")
    success: bool = Field(..., description="Успешно ли помечен шаг как выполненный")
    next_steps: List[PlanStep] = Field(default_factory=list, description="Следующие шаги, которые можно выполнить")


class ErrorAnalysisOutput(BaseModel):
    """Выходная схема для анализа ошибок."""
    error_type: str = Field(..., description="Тип ошибки")
    cause_analysis: str = Field(..., description="Анализ причины ошибки")
    suggested_fix: str = Field(..., description="Предлагаемое решение")
    severity: str = Field(..., description="Серьезность ошибки (low, medium, high)")