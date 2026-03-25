"""
Manifest модели для компонентов.
"""
from dataclasses import dataclass, field
from typing import Optional, Dict, Any

from core.models.enums.common_enums import ComponentType, ComponentStatus


@dataclass
class QualityMetrics:
    accuracy: float = 0.0
    latency_ms: float = 0.0
    token_usage: int = 0
    error_rate: float = 0.0
    test_coverage: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Manifest:
    component_id: str
    component_type: ComponentType
    version: str
    owner: str
    status: ComponentStatus
    description: Optional[str] = None
    dependencies: Optional[list] = None
    quality_metrics: Optional[QualityMetrics] = None
