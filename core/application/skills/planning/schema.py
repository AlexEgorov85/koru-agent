from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from enum import Enum


class StepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanStep(BaseModel):
    step_id: str
    description: str
    capability_name: str
    parameters: Dict[str, Any]
    status: StepStatus = StepStatus.PENDING
    dependencies: List[str] = []  # IDs шагов, которые должны быть выполнены до этого
    estimated_duration: Optional[int] = None  # в секундах


class SubTask(BaseModel):
    subtask_id: str
    description: str
    complexity: str  # low, medium, high
    estimated_steps: int


class DecompositionStrategy(str, Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HIERARCHICAL = "hierarchical"


class CreatePlanInput(BaseModel):
    goal: str
    max_steps: int = 10
    context: Optional[str] = None


class CreatePlanOutput(BaseModel):
    plan_id: str
    goal: str
    steps: List[PlanStep]
    metadata: Dict[str, Any] = {}


class UpdatePlanInput(BaseModel):
    plan_id: str
    new_requirements: str
    context: Optional[str] = None


class UpdatePlanOutput(BaseModel):
    plan_id: str
    updated_steps: List[PlanStep]
    reason: str


class GetNextStepInput(BaseModel):
    plan_id: str
    current_step_id: Optional[str] = None


class GetNextStepOutput(BaseModel):
    step: Optional[PlanStep]
    is_last_step: bool = False
    remaining_steps_count: int = 0


class UpdateStepStatusInput(BaseModel):
    plan_id: str
    step_id: str
    status: StepStatus
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class UpdateStepStatusOutput(BaseModel):
    success: bool
    updated_step: PlanStep
    next_step: Optional[PlanStep] = None


class DecomposeTaskInput(BaseModel):
    task_id: str
    task_description: str
    context: Optional[str] = None
    max_subtasks: int = 5


class DecomposeTaskOutput(BaseModel):
    parent_task_id: str
    original_task: str
    subtasks: List[SubTask]
    decomposition_strategy: DecompositionStrategy
    metadata: Dict[str, Any] = {}


class MarkTaskCompletedInput(BaseModel):
    task_id: str
    plan_id: str
    result_summary: Optional[str] = None


class MarkTaskCompletedOutput(BaseModel):
    success: bool
    completed_task_id: str
    affected_steps: List[str]


class ErrorAnalysisOutput(BaseModel):
    error_type: str
    reason: str
    suggested_fix: str
    severity: str  # low, medium, high
    reasoning: str
    summary: str