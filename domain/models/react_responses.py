"""
Pydantic модели для структурированных ответов LLM в ReAct паттерне.
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum


class ReActActionType(str, Enum):
    """Типы действий в ReAct цикле"""
    THINK = "THINK"
    ACT = "ACT"
    OBSERVE = "OBSERVE"
    PLAN = "PLAN"
    REFLECT = "REFLECT"
    STOP = "STOP"
    ERROR = "ERROR"


class ReActResponse(BaseModel):
    """
    Структурированный ответ от LLM для ReAct паттерна.
    """
    action: ReActActionType = Field(..., description="Тип действия для выполнения")
    thought: str = Field(..., description="Рассуждение агента")
    action_input: Optional[Dict[str, Any]] = Field(default=None, description="Входные параметры для действия")
    observation: Optional[str] = Field(default=None, description="Наблюдение за результатом действия")
    next_action: Optional[ReActActionType] = Field(default=None, description="Следующее действие в цикле")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Уверенность в решении")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Дополнительные метаданные")


class ReActStepResponse(BaseModel):
    """
    Ответ от LLM для одного шага ReAct цикла.
    """
    thought: str = Field(..., description="Рассуждение агента")
    action: str = Field(..., description="Название действия для выполнения")
    action_input: Dict[str, Any] = Field(default_factory=dict, description="Параметры действия")
    next_action_expected: Optional[ReActActionType] = Field(default=None, description="Ожидаемое следующее действие")


class ReActPlanStep(BaseModel):
    """
    Шаг в плане ReAct паттерна.
    """
    step_number: int = Field(..., description="Номер шага")
    action: str = Field(..., description="Действие для выполнения")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Параметры действия")
    expected_outcome: str = Field(..., description="Ожидаемый результат")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Уверенность в шаге")


class ReActPlan(BaseModel):
    """
    План выполнения задачи в ReAct паттерне.
    """
    goal: str = Field(..., description="Цель выполнения")
    steps: List[ReActPlanStep] = Field(default_factory=list, description="Шаги плана")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Метаданные плана")


class ReActObservation(BaseModel):
    """
    Структурированное наблюдение за результатом действия.
    """
    action_performed: str = Field(..., description="Выполненное действие")
    action_result: str = Field(..., description="Результат выполнения действия")
    success: bool = Field(default=True, description="Успешно ли выполнено действие")
    error_message: Optional[str] = Field(default=None, description="Сообщение об ошибке")
    processed_result: Optional[Dict[str, Any]] = Field(default=None, description="Обработанный результат")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Уверенность в наблюдении")