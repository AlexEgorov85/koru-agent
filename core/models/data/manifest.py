from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any
from datetime import datetime

from core.models.enums.common_enums import ComponentStatus, ComponentType
from .base_template_validator import TemplateValidatorMixin


class QualityMetrics(BaseModel):
    success_rate_target: float = Field(ge=0.0, le=1.0, default=0.95)
    avg_execution_time_ms: float = Field(ge=0, default=500)
    error_rate_threshold: float = Field(ge=0.0, le=1.0, default=0.05)


class SuccessMetrics(BaseModel):
    goal_completion_rate: float = Field(ge=0.0, le=1.0, default=0.90)
    user_satisfaction_score: float = Field(ge=0.0, le=5.0, default=4.5)
    retry_rate: float = Field(ge=0.0, le=1.0, default=0.10)


class ChangelogEntry(BaseModel):
    version: str
    date: str
    author: str
    changes: List[str]


class Manifest(TemplateValidatorMixin, BaseModel):
    component_id: str = Field(..., min_length=1)
    component_type: ComponentType
    version: str = Field(..., pattern=r"^v\d+\.\d+\.\d+$")
    owner: str = Field(..., min_length=1)
    status: ComponentStatus = ComponentStatus.DRAFT
    
    contract: Optional[Dict[str, str]] = None
    constraints: Optional[Dict[str, Any]] = None
    
    quality_metrics: Optional[QualityMetrics] = None
    success_metrics: Optional[SuccessMetrics] = None
    
    dependencies: Dict[str, List[str]] = Field(default_factory=lambda: {
        "components": [],
        "tools": [],
        "services": []
    })
    
    changelog: List[ChangelogEntry] = Field(default_factory=list)
    
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: Optional[str] = None
    
    @validator('updated_at', always=True)
    def set_updated_at(cls, v, values):
        return v or datetime.utcnow().isoformat()

    def validate_templates(self) -> list[str]:
        """
        Валидация всех шаблонов в манифесте.
        Сейчас манифесты не содержат шаблонов, но метод предусмотрен для унификации.
        
        Returns:
            list: список предупреждений
        """
        # Манифесты не содержат шаблонов, поэтому возвращаем пустой список
        return []