from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
from datetime import datetime
from uuid import uuid4


class PromptExecutionSnapshot(BaseModel):
    """
    Снапшот выполнения промта для отладки и мониторинга
    """
    
    id: str = Field(default_factory=lambda: f"snapshot_{uuid4().hex[:12]}")
    prompt_id: str
    session_id: str
    rendered_prompt: str
    variables: Dict[str, Any]
    response: Optional[str] = None
    execution_time: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    success: bool = True
    error_message: Optional[str] = None
    rejection_reason: Optional[str] = None  # Если валидатор отклонил
    provider_response_time: float = 0.0
    
    class Config:
        frozen = True  # Иммутабельность для безопасности