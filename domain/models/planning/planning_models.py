"""
Схемы валидации для PlanningSkill
"""
from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class PlanInput(BaseModel):
    """Входные параметры для генерации плана"""
    requirements: str
    project_context: Optional[Dict[str, Any]] = {}
    constraints: Optional[List[str]] = []
    priority: Optional[str] = "normal"  # "low", "normal", "high", "critical"
    estimated_effort_hours: Optional[int] = None


class PlanOutput(BaseModel):
    """Выходные параметры для генерации плана"""
    success: bool
    plan: List[Dict[str, Any]]
    estimated_duration: Optional[int]  # в часах
    risk_assessment: Optional[Dict[str, Any]]
    error: Optional[str]


class CodeGenerationInput(BaseModel):
    """Входные параметры для генерации кода"""
    requirements: str
    target_language: str
    target_framework: Optional[str] = None
    existing_code_context: Optional[str] = None
    style_guidelines: Optional[List[str]] = []
    security_requirements: Optional[List[str]] = []


class CodeGenerationOutput(BaseModel):
    """Выходные параметры для генерации кода"""
    success: bool
    generated_code: str
    file_path: Optional[str]
    dependencies: Optional[List[str]]
    quality_score: Optional[float]
    error: Optional[str]


class TaskBreakdownInput(BaseModel):
    """Входные параметры для разбиения задачи"""
    task_description: str
    project_context: Optional[Dict[str, Any]] = {}
    required_skills: Optional[List[str]] = []
    time_constraints: Optional[Dict[str, Any]] = {}


class TaskBreakdownOutput(BaseModel):
    """Выходные параметры для разбиения задачи"""
    success: bool
    subtasks: List[Dict[str, Any]]
    estimated_complexity: Optional[str]  # "trivial", "easy", "medium", "hard", "very_hard"
    required_skills: Optional[List[str]]
    error: Optional[str]