from pydantic import BaseModel, Field
from typing import Dict, Optional
from datetime import datetime, timezone


class ComponentConfig(BaseModel):
    """
    Локальная конфигурация версий для экземпляра компонента.
    Определяет согласованный набор промптов и контрактов (input/output отдельно).
    """
    # Версии промптов: {capability_name: version}
    prompt_versions: Dict[str, str] = Field(default_factory=dict)

    # Версии ВХОДЯЩИХ контрактов: {capability_name: version}
    input_contract_versions: Dict[str, str] = Field(default_factory=dict)

    # Версии ИСХОДЯЩИХ контрактов: {capability_name: version}
    output_contract_versions: Dict[str, str] = Field(default_factory=dict)

    # Идентификатор варианта (для логирования)
    variant_id: Optional[str] = None  # "beta", "v1.0.0", "canary-2024-02"

    # Метаданные для аудита
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: Optional[str] = None
    
    @property
    def variant_key(self) -> str:
        """Уникальный ключ варианта: 'planning@beta'"""
        return f"{self.variant_id or 'default'}"
    
    def get_full_contract_key(self, capability_name: str, direction: str) -> str:
        """
        Формирует полный ключ контракта для внутреннего кэширования.
        Пример: "planning.create_plan.input"
        """
        return f"{capability_name}.{direction}"