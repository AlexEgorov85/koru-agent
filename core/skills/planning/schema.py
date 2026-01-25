"""Схемы данных для навыка планирования.
ОСОБЕННОСТИ РЕАЛИЗАЦИИ:
- Использование современных стандартов Pydantic v2
- Строгая типизация с валидацией
- Поддержка иерархического планирования
- Интеграция с ExecutionGateway через стандартизованные схемы
- Поддержка получения следующего шага и обновления статусов
АРХИТЕКТУРНЫЕ ПРИНЦИПЫ:
- Схемы являются контрактом между LLM и ExecutionGateway
- Валидация происходит ДО выполнения capability
- Все схемы сериализуемы в JSON
- Поддержка версионирования и эволюции схем"""
from typing import List, Optional, Dict, Any, Literal, Union
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime, timezone
from enum import Enum
import uuid

# ==========================================================
# Enumerations для типизации
# ==========================================================
class TaskStatus(str, Enum):
    """Статусы выполнения задачи."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class TaskPriority(str, Enum):
    """Приоритеты задач."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class UpdateType(str, Enum):
    """Типы обновлений плана."""
    PROGRESS = "progress"
    ERROR_CORRECTION = "error_correction"
    GOAL_CHANGE = "goal_change"
    STRATEGY_CHANGE = "strategy_change"

class DecompositionStrategy(str, Enum):
    """Стратегии декомпозиции задач."""
    BY_TIME = "по_времени"
    BY_FUNCTIONS = "по_функциям"
    BY_DATA = "по_данным"
    MIXED = "смешанная"

class PlanStatus(str, Enum):
    """Статусы плана."""
    ACTIVE = "active"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"

# ==========================================================
# Базовые схемы для шагов и задач
# ==========================================================
class PlanStep(BaseModel):
    """Схема одного шага в плане.
    
    ПОЛЯ:
    - step_id: Уникальный идентификатор шага
    - description: Описание действия
    - status: Текущий статус выполнения
    - estimated_time: Оценка времени выполнения в минутах
    - required_capabilities: Необходимые capability для выполнения
    - dependencies: Зависимости от других шагов
    - priority: Приоритет шага
    - parameters: Параметры для capability
    - result_summary: Краткое описание результата (после выполнения)
    - error: Описание ошибки (при наличии)
    - completed_at: Время завершения
    - updated_at: Время последнего обновления
    """
    step_id: str = Field(..., description="Уникальный идентификатор шага")
    description: str = Field(..., min_length=10, max_length=500, description="Описание действия")
    status: TaskStatus = Field(TaskStatus.PENDING, description="Текущий статус выполнения")
    estimated_time: int = Field(15, ge=1, le=240, description="Оценка времени выполнения в минутах")
    required_capabilities: List[str] = Field(..., min_items=1, max_items=5, description="Необходимые capability для выполнения")
    dependencies: List[str] = Field(default_factory=list, description="Зависимости от других шагов (step_id)")
    priority: TaskPriority = Field(TaskPriority.MEDIUM, description="Приоритет шага")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Параметры для capability")
    result_summary: Optional[str] = Field(None, max_length=1000, description="Краткое описание результата")
    error: Optional[str] = Field(None, max_length=1000, description="Описание ошибки")
    completed_at: Optional[datetime] = Field(None, description="Время завершения")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Время последнего обновления")

    @field_validator('dependencies')
    @classmethod
    def validate_dependencies(cls, v):
        for dep in v:
            if not dep.startswith("step_"):
                raise ValueError(f"Неверный формат dependency ID: {dep}")
        return v

    @field_validator('required_capabilities')
    @classmethod
    def validate_capabilities(cls, v):
        return [cap.strip().lower() for cap in v if cap.strip()]

class PlanMetadata(BaseModel):
    """Метаданные плана.
    
    ПОЛЯ:
    - created_at: Время создания
    - updated_at: Время обновления
    - max_steps: Максимальное количество шагов
    - strategy: Стратегия планирования
    - confidence: Уверенность в плане (0.0-1.0)
    - version: Версия плана
    - status: Текущий статус плана
    """
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Время создания")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Время обновления")
    max_steps: int = Field(10, ge=2, le=50, description="Максимальное количество шагов")
    strategy: str = Field("iterative", max_length=50, description="Стратегия планирования")
    confidence: float = Field(0.7, ge=0.0, le=1.0, description="Уверенность в плане")
    version: int = Field(1, ge=1, description="Версия плана")
    status: PlanStatus = Field(PlanStatus.ACTIVE, description="Текущий статус плана")

# ==========================================================
# Схемы для capability get_next_step
# ==========================================================
class GetNextStepInput(BaseModel):
    """Параметры для получения следующего шага из плана."""
    plan_id: str = Field(..., description="ID плана для анализа")
    context: Optional[str] = Field(None, max_length=2000, description="Дополнительный контекст для анализа")

class GetNextStepOutput(BaseModel):
    """Схема выходных данных для получения следующего шага.
    
    ПОЛЯ:
    - step: Данные следующего шага
    - requires_analysis: Требуется ли дополнительный анализ шага
    - recommendations: Рекомендации для выполнения шага
    - dependencies_met: Выполнены ли все зависимости
    - estimated_execution_time: Оценка времени выполнения в минутах
    - confidence: Уверенность в возможности выполнения шага
    """
    step: Dict[str, Any] = Field(..., description="Данные следующего шага")
    requires_analysis: bool = Field(True, description="Требуется ли дополнительный анализ шага")
    recommendations: List[str] = Field(..., min_items=1, max_items=5, description="Рекомендации для выполнения шага")
    dependencies_met: bool = Field(True, description="Выполнены ли все зависимости")
    estimated_execution_time: int = Field(15, ge=1, le=240, description="Оценка времени выполнения в минутах")
    confidence: float = Field(0.7, ge=0.0, le=1.0, description="Уверенность в возможности выполнения шага")

# ==========================================================
# Схемы для capability update_step_status
# ==========================================================
class UpdateStepStatusInput(BaseModel):
    """Параметры для обновления статуса шага."""
    plan_id: str = Field(..., description="ID плана")
    step_id: str = Field(..., description="ID шага для обновления")
    status: TaskStatus = Field(..., description="Новый статус шага")
    result_summary: Optional[str] = Field(None, max_length=1000, description="Краткое описание результата")
    error: Optional[str] = Field(None, max_length=1000, description="Описание ошибки при статусе failed")
    context: Optional[str] = Field(None, max_length=2000, description="Контекст обновления")

class PlanAdjustment(BaseModel):
    """Схема корректировки плана."""
    step_id: str = Field(..., description="ID шага для корректировки")
    status: Optional[TaskStatus] = Field(None, description="Новый статус шага")
    description: Optional[str] = Field(None, max_length=500, description="Обновленное описание шага")
    estimated_time: Optional[int] = Field(None, ge=1, le=240, description="Обновленная оценка времени")
    reason: str = Field(..., min_length=10, max_length=300, description="Причина корректировки")

class UpdateStepStatusOutput(BaseModel):
    """Схема выходных данных для обновления статуса шага.
    
    ПОЛЯ:
    - plan_id: ID обновленного плана
    - step_id: ID обновленного шага
    - previous_status: Предыдущий статус шага
    - new_status: Новый статус шага
    - requires_plan_adjustment: Требуется ли корректировка плана
    - plan_adjustments: Список рекомендуемых корректировок плана
    - next_recommended_step_id: ID следующего рекомендуемого шага
    - impact_assessment: Оценка влияния на общий план
    """
    plan_id: str = Field(..., description="ID обновленного плана")
    step_id: str = Field(..., description="ID обновленного шага")
    previous_status: TaskStatus = Field(..., description="Предыдущий статус шага")
    new_status: TaskStatus = Field(..., description="Новый статус шага")
    requires_plan_adjustment: bool = Field(False, description="Требуется ли корректировка плана")
    plan_adjustments: List[PlanAdjustment] = Field(default_factory=list, description="Список рекомендуемых корректировок плана")
    next_recommended_step_id: Optional[str] = Field(None, description="ID следующего рекомендуемого шага")
    impact_assessment: str = Field(..., min_length=10, max_length=500, description="Оценка влияния на общий план")

# ==========================================================
# Схемы для capability create_plan
# ==========================================================
class CreatePlanInput(BaseModel):
    """Параметры для создания плана."""
    goal: str = Field(..., min_length=10, max_length=1000, description="Основная цель, для которой создается план")
    max_steps: int = Field(10, ge=2, le=20, description="Максимальное количество шагов в плане")
    context: Optional[str] = Field(None, max_length=2000, description="Контекст для создания плана")
    strategy: Literal["iterative", "hierarchical", "goal_oriented"] = Field("iterative", description="Стратегия планирования")

class CreatePlanOutput(BaseModel):
    """Схема выходных данных для создания плана."""
    plan_id: str = Field(..., description="Уникальный ID плана")
    goal: str = Field(..., description="Цель, для которой создан план")
    steps: List[PlanStep] = Field(..., min_items=2, max_items=20, description="Список шагов плана")
    metadata: PlanMetadata = Field(..., description="Метаданные плана")

    @field_validator('plan_id')
    @classmethod
    def validate_plan_id(cls, v):
        if not v.startswith("plan_"):
            raise ValueError("plan_id должен начинаться с 'plan_'")
        return v

    @field_validator('steps')
    @classmethod
    def validate_steps_order(cls, v):
        """Проверка, что шаги имеют последовательные ID."""
        step_ids = [step.step_id for step in v]
        # Проверяем, что ID следуют в порядке возрастания
        numeric_ids = [int(step_id.split('_')[1]) for step_id in step_ids]
        if sorted(numeric_ids) != numeric_ids:
            raise ValueError("Шаги должны быть упорядочены по возрастанию ID")
        return v

# ==========================================================
# Схемы для capability update_plan
# ==========================================================
class UpdatedStep(BaseModel):
    """Схема обновленного шага в плане."""
    step_id: str = Field(..., description="ID шага для обновления")
    description: Optional[str] = Field(None, max_length=500, description="Обновленное описание")
    status: Optional[TaskStatus] = None
    estimated_time: Optional[int] = Field(None, ge=1, le=240, description="Обновленная оценка времени")
    required_capabilities: Optional[List[str]] = Field(None, min_items=1, max_items=5)
    dependencies: Optional[List[str]] = None
    priority: Optional[TaskPriority] = None
    reason: str = Field(..., min_length=10, max_length=500, description="Причина обновления")

class UpdatePlanInput(BaseModel):
    """Параметры для обновления плана."""
    plan_id: str = Field(..., description="ID обновляемого плана")
    updates: List[UpdatedStep] = Field(..., min_items=1, description="Изменения для шагов плана")
    context: Optional[str] = Field(None, max_length=2000, description="Контекст для обновления")

class UpdatePlanOutput(BaseModel):
    """Схема выходных данных для обновления плана."""
    plan_id: str = Field(..., description="Новый ID обновленного плана")
    original_plan_id: str = Field(..., description="ID исходного плана")
    update_reason: str = Field(..., min_length=10, max_length=500, description="Причина обновления")
    updated_steps: List[UpdatedStep] = Field(..., min_items=1, description="Список обновленных шагов")
    metadata: Dict[str, Any] = Field(default_factory=lambda: {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "update_type": UpdateType.PROGRESS.value,
        "confidence": 0.7
    })

    @model_validator(mode='after')
    def validate_plan_ids(self):
        if not self.plan_id.startswith("plan_"):
            raise ValueError("plan_id должен начинаться с 'plan_'")
        if not self.original_plan_id.startswith("plan_"):
            raise ValueError("original_plan_id должен начинаться с 'plan_'")
        return self

# ==========================================================
# Схемы для capability decompose_task
# ==========================================================
class Subtask(BaseModel):
    """Схема подзадачи для декомпозиции.
    
    ПОЛЯ:
    - subtask_id: Уникальный идентификатор подзадачи
    - description: Описание подзадачи
    - complexity: Сложность подзадачи
    - estimated_time: Оценка времени выполнения
    - dependencies: Зависимости от других подзадач
    - required_capabilities: Необходимые capability
    """
    subtask_id: str = Field(..., description="Уникальный ID подзадачи")
    description: str = Field(..., min_length=10, max_length=300, description="Описание подзадачи")
    complexity: float = Field(0.5, ge=0.1, le=1.0, description="Сложность подзадачи (0.1-1.0)")
    estimated_time: int = Field(..., ge=1, le=60, description="Оценка времени в минутах")
    dependencies: List[str] = Field(default_factory=list, description="Зависимости от других подзадач")
    required_capabilities: List[str] = Field(..., min_items=1, max_items=5, description="Необходимые capability")

    @field_validator('dependencies')
    @classmethod
    def validate_subtask_dependencies(cls, v):
        for dep in v:
            if not dep.startswith("subtask_"):
                raise ValueError(f"Неверный формат dependency ID для подзадачи: {dep}")
        return v

class DecomposeTaskInput(BaseModel):
    """Параметры для декомпозиции задачи."""
    task_id: str = Field(..., description="ID декомпозируемой задачи")
    task_description: str = Field(..., min_length=20, max_length=1000, description="Описание задачи для декомпозиции")
    context: Optional[str] = Field(None, max_length=2000, description="Контекст для декомпозиции")
    strategy: Optional[DecompositionStrategy] = Field(None, description="Стратегия декомпозиции")

class DecomposeTaskOutput(BaseModel):
    """Схема выходных данных для декомпозиции задачи."""
    parent_task_id: str = Field(..., description="ID родительской задачи")
    original_task: str = Field(..., description="Исходное описание задачи")
    subtasks: List[Subtask] = Field(..., min_items=2, max_items=10, description="Список подзадач")
    decomposition_strategy: DecompositionStrategy = Field(DecompositionStrategy.BY_FUNCTIONS, description="Стратегия декомпозиции")
    metadata: Dict[str, Any] = Field(default_factory=lambda: {
        "decomposed_at": datetime.now(timezone.utc).isoformat(),
        "confidence": 0.7,
        "version": 1
    })

# ==========================================================
# Схемы для capability mark_task_completed
# ==========================================================
class NextRecommendedAction(BaseModel):
    """Схема рекомендуемого следующего действия.
    
    ПОЛЯ:
    - action: Описание действия
    - priority: Приоритет действия
    - related_step_id: ID связанного шага
    """
    action: str = Field(..., min_length=10, max_length=300, description="Описание действия")
    priority: TaskPriority = Field(TaskPriority.MEDIUM, description="Приоритет действия")
    related_step_id: Optional[str] = Field(None, description="ID связанного шага")

class PlanImpact(BaseModel):
    """Схема воздействия на план.
    
    ПОЛЯ:
    - plan_adjustment_needed: Требуется ли корректировка плана
    - confidence_in_completion: Уверенность в завершении
    - lessons_learned: Извлеченные уроки
    """
    plan_adjustment_needed: bool = Field(False, description="Требуется ли корректировка плана")
    confidence_in_completion: float = Field(0.7, ge=0.0, le=1.0, description="Уверенность в завершении")
    lessons_learned: List[str] = Field(default_factory=list, max_items=10, description="Извлеченные уроки")

class MarkTaskCompletedInput(BaseModel):
    """Параметры для отметки задачи как завершенной."""
    task_id: str = Field(..., description="ID завершаемой задачи")
    result_summary: str = Field(..., min_length=10, max_length=1000, description="Краткое описание результата")
    quality_score: float = Field(0.7, ge=0.0, le=1.0, description="Оценка качества выполнения (0.0-1.0)")
    time_spent_minutes: int = Field(15, ge=1, le=240, description="Фактическое время выполнения в минутах")

class MarkTaskCompletedOutput(BaseModel):
    """Схема выходных данных для отметки задачи как завершенной."""
    task_id: str = Field(..., description="ID завершенной задачи")
    status: Literal["completed"] = "completed"
    completion_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="Время завершения")
    result_summary: str = Field(..., min_length=10, max_length=1000, description="Краткое описание результата")
    quality_score: float = Field(0.7, ge=0.0, le=1.0, description="Оценка качества выполнения (0.0-1.0)")
    time_spent_minutes: int = Field(15, ge=1, le=240, description="Фактическое время выполнения в минутах")
    next_recommended_actions: List[NextRecommendedAction] = Field(default_factory=list, description="Рекомендуемые следующие действия")
    impact_on_plan: PlanImpact = Field(default_factory=PlanImpact, description="Воздействие на план")