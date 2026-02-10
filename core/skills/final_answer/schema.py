"""Схемы данных для навыка генерации финального ответа."""
from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class FinalAnswerRequest(BaseModel):
    """Запрос на генерацию финального ответа."""
    include_steps: bool = True
    include_evidence: bool = True
    format_type: str = "detailed"  # "concise", "detailed", "structured"
    custom_prompt: Optional[str] = None


class FinalAnswerResponse(BaseModel):
    """Ответ с финальным результатом."""
    final_answer: str
    goal: str
    evidence_count: int
    steps_included: bool
    evidence_included: bool
    format_type: str
    confidence_score: Optional[float] = None
    supporting_data: Optional[Dict[str, Any]] = None