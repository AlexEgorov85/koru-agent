"""
Manifest модели для компонентов.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any


class ComponentType(Enum):
    SKILL = "skill"
    TOOL = "tool"
    SERVICE = "service"


class ComponentStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DEPRECATED = "deprecated"


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
