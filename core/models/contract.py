"""Contract model representing input/output schemas for capabilities."""

from pydantic import BaseModel, Field
from typing import Dict, Any


class Contract(BaseModel):
    """Represents a contract (input/output schema) for a capability."""
    
    capability_name: str
    version: str
    direction: str  # "input" or "output"
    schema_data: Dict[str, Any] = Field(default_factory=dict, alias='schema')  # JSON schema definition