"""
Типы данных для JsonParsingService.

АРХИТЕКТУРА:
- JsonParseStatus — статус операции парсинга
- JsonParseResult — результат с полной трассировкой шагов
"""
from enum import Enum
from pydantic import BaseModel, Field
from typing import Any, Optional, Dict, List


class JsonParseStatus(str, Enum):
    """Статус операции парсинга JSON."""
    SUCCESS = "success"
    EXTRACT_ERROR = "extract_error"
    PARSE_ERROR = "parse_error"
    VALIDATION_ERROR = "validation_error"
    MODEL_ERROR = "model_error"


class JsonParseResult(BaseModel):
    """
    Результат парсинга JSON ответа LLM.

    ПОЛЯ:
    - status: Статус операции
    - raw_input: Исходный текст от LLM
    - extracted_json: Извлечённая JSON строка (после очистки от markdown)
    - parsed_data: Распарсенный dict (до валидации схемой)
    - pydantic_model: Экземпляр Pydantic модели (после валидации)
    - error_type: Тип ошибки (если есть)
    - error_message: Сообщение об ошибке
    - error_details: Детали ошибок валидации (список dict с loc, msg, type)
    - processing_steps: Трассировка шагов парсинга (для отладки)
    """
    status: JsonParseStatus
    raw_input: str
    extracted_json: Optional[str] = None
    parsed_data: Optional[Any] = None  # dict, list, или любой JSON тип
    pydantic_model: Optional[Any] = Field(None, exclude=True)  # Не сериализуется
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    error_details: Optional[List[Dict[str, Any]]] = None
    processing_steps: List[str] = Field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Сериализация для передачи через ActionExecutor."""
        result = {
            "status": self.status.value,
            "raw_input": self.raw_input,
            "extracted_json": self.extracted_json,
            "parsed_data": self.parsed_data,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "error_details": self.error_details,
            "processing_steps": self.processing_steps
        }
        # Сериализуем Pydantic модель если есть
        if self.pydantic_model is not None:
            if hasattr(self.pydantic_model, "model_dump"):
                result["pydantic_model_data"] = self.pydantic_model.model_dump()
            else:
                result["pydantic_model_data"] = str(self.pydantic_model)
        return result
