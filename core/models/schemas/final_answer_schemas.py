"""
Схемы данных для финального ответа.

Содержит Pydantic-модели, используемые в навыке финального ответа.
"""
from typing import Dict, Any, List
from pydantic import BaseModel, Field


class FinalAnswerRequest(BaseModel):
    """Входная схема для генерации финального ответа."""
    query: str = Field(..., description="Исходный запрос пользователя")
    supporting_information: List[str] = Field(..., description="Поддерживающая информация, собранная в ходе выполнения")
    context_summary: Dict[str, Any] = Field(..., description="Сводка контекста выполнения")
    confidence_threshold: float = Field(default=0.7, description="Порог уверенности для генерации ответа")


class FinalAnswerResponse(BaseModel):
    """Выходная схема для финального ответа."""
    final_answer: str = Field(..., description="Финальный сформированный ответ")
    sources: List[str] = Field(default_factory=list, description="Источники информации, использованные для формирования ответа")
    confidence_score: float = Field(..., description="Уровень уверенности в ответе")
    remaining_questions: List[str] = Field(default_factory=list, description="Вопросы, остающиеся без ответа")
    summary_of_steps: str = Field(..., description="Краткое резюме шагов, приведших к ответу")