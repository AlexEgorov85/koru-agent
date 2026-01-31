"""
Строго типизированные модели для анализа кода без эвристики.
"""
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime


class ErrorLocation(BaseModel):
    """Структурированное представление местоположения ошибки."""
    file_path: str = Field(..., min_length=1, max_length=512)
    line: int = Field(..., ge=1)
    method: Optional[str] = Field(None, max_length=128)
    actual_type: Optional[str] = Field(None, max_length=100)
    expected_type: Optional[str] = Field(None, max_length=100)
    error_message: str = Field(..., min_length=1, max_length=1000)


class CodeContext(BaseModel):
    """Контекст кода, полученный через структурный анализ."""
    target_unit_id: str = Field(..., min_length=5, max_length=255)
    file_path: str = Field(..., min_length=1, max_length=512)
    unit_type: str = Field(..., min_length=3, max_length=20)
    signature: Optional[str] = Field(None, max_length=500)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    source_code_snippet: Optional[str] = Field(None, max_length=2000)


class RootCauseAnalysis(BaseModel):
    """Результат анализа причины ошибки через структурированный промпт."""
    problem_description: str = Field(..., min_length=20, max_length=500)
    problematic_field: str = Field(..., min_length=1, max_length=100)
    actual_value_type: str = Field(..., min_length=1, max_length=50)
    expected_value_type: str = Field(..., min_length=1, max_length=50)
    source_method: str = Field(..., min_length=1, max_length=128)
    source_file: str = Field(..., min_length=1, max_length=512)
    confidence: float = Field(..., ge=0.0, le=1.0)
    requires_llm_fix: bool = Field(...)

    @field_validator('confidence')
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        return round(v, 2)


class FixProposal(BaseModel):
    """Предложение по исправлению, сгенерированное через структурированную генерацию."""
    fixed_code: str = Field(..., min_length=10, max_length=2000)
    location: Dict[str, Any] = Field(...)
    test_case: str = Field(..., min_length=10, max_length=500)
    explanation: str = Field(..., min_length=20, max_length=300)

    @model_validator(mode='after')
    def validate_location(self):
        loc = self.location
        required_keys = {'file_path', 'start_line', 'end_line'}
        if not required_keys.issubset(loc.keys()):
            raise ValueError(f"location must contain {required_keys}")
        if not (1 <= loc['start_line'] <= loc['end_line']):
            raise ValueError("start_line must be <= end_line and >= 1")
        return self


class AnalysisResult(BaseModel):
    """Полный результат анализа кода."""
    error_location: ErrorLocation
    code_context: CodeContext
    root_cause: RootCauseAnalysis
    fix_proposal: Optional[FixProposal] = None
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)
    requires_human_review: bool = Field(False)


class AnalysisState(BaseModel):
    """Состояние выполнения анализа (для сохранения в контексте)."""
    analysis_type: str = Field(..., min_length=5, max_length=50)
    goal: str = Field(..., max_length=1000)
    completed: bool = Field(False)
    completion_reason: Optional[str] = Field(None, max_length=200)
    steps_executed: int = Field(0, ge=0)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    requires_human_review: bool = Field(False)
    start_time: str = Field(..., min_length=10, max_length=50)
    error_context: Optional[Dict[str, Any]] = None