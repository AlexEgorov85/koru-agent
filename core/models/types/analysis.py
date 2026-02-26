"""
Модели для LLM анализа.

Универсальные модели для любого типа анализа:
- character (анализ героев книг)
- theme (анализ тем)
- category (классификация)
- и т.д.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, Literal
from datetime import datetime


class AnalysisResult(BaseModel):
    """
    Универсальный результат LLM анализа.
    
    Подходит для:
    - Анализа героев книг
    - Анализа тем документов
    - Классификации контента
    - Извлечения сущностей
    
    Attributes:
        entity_id: ID сущности (book_id, doc_id, etc.)
        analysis_type: Тип анализа ("character", "theme", etc.)
        result: Любые результаты анализа
        confidence: Уверенность (0-1)
        reasoning: Обоснование
        analyzed_at: Дата анализа
        error: Ошибка
    """
    entity_id: str
    analysis_type: str
    result: Dict[str, Any]
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    reasoning: Optional[str] = None
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    error: Optional[str] = None
    
    @validator('confidence')
    def validate_confidence(cls, v):
        """Валидация уверенности."""
        if v < 0.0 or v > 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v
    
    def is_valid(self) -> bool:
        """Проверка валидности анализа."""
        return self.error is None and self.confidence >= 0.8
    
    def to_dict(self) -> dict:
        """Конвертация в dict."""
        return {
            "entity_id": self.entity_id,
            "analysis_type": self.analysis_type,
            "result": self.result,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "analyzed_at": self.analyzed_at.isoformat(),
            "error": self.error
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "AnalysisResult":
        """Создание из dict."""
        return cls(
            entity_id=data["entity_id"],
            analysis_type=data["analysis_type"],
            result=data.get("result", {}),
            confidence=data.get("confidence", 0.5),
            reasoning=data.get("reasoning"),
            analyzed_at=datetime.fromisoformat(data["analyzed_at"]),
            error=data.get("error")
        )
    
    class Config:
        json_schema_extra = {
            "example": {
                "entity_id": "book_1",
                "analysis_type": "character",
                "result": {
                    "main_character": "Евгений Онегин",
                    "gender": "male"
                },
                "confidence": 0.95,
                "reasoning": "Имя в названии"
            }
        }


class BookWithCharacter(BaseModel):
    """
    Книга с информацией о главном герое.
    
    Attributes:
        book_id: ID книги
        book_title: Название книги
        author_name: Имя автора
        main_character: Имя главного героя
        gender: Пол героя
        confidence: Уверенность
    """
    book_id: int
    book_title: str
    author_name: str
    main_character: Optional[str]
    gender: Optional[str]
    confidence: float
    
    class Config:
        json_schema_extra = {
            "example": {
                "book_id": 1,
                "book_title": "Евгений Онегин",
                "author_name": "Александр Пушкин",
                "main_character": "Евгений Онегин",
                "gender": "male",
                "confidence": 0.95
            }
        }
