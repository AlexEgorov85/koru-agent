from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from pathlib import Path
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

    # ← КРИТИЧЕСКИ ВАЖНО: предзагруженные ресурсы
    resolved_prompts: Dict[str, str] = Field(default_factory=dict)
    resolved_input_contracts: Dict[str, Dict] = Field(default_factory=dict)
    resolved_output_contracts: Dict[str, Dict] = Field(default_factory=dict)

    # Идентификатор варианта (для логирования)
    variant_id: str = Field(..., description="Уникальный ID варианта компонента")

    # ← НОВОЕ: Путь к манифесту
    manifest_path: Optional[Path] = Field(None, description="Путь к манифесту компонента")
    
    # ← НОВОЕ: Ограничения из манифеста
    constraints: Optional[Dict[str, Any]] = Field(None, description="Ограничения из манифеста")
    
    # ← НОВОЕ: Владелец из манифеста
    owner: Optional[str] = Field(None, description="Владелец компонента из манифеста")

    # ← НОВОЕ: Критические ресурсы
    critical_resources: Dict[str, bool] = Field(default_factory=dict, description="Критические ресурсы, которые должны быть загружены")

    # Флаги поведения компонента
    side_effects_enabled: bool = Field(default=True, description="Разрешены ли побочные эффекты (запись, изменение данных)")
    detailed_metrics: bool = Field(default=False, description="Сборить ли подробную метрику")

    # Параметры выполнения
    parameters: Dict[str, Any] = Field(default_factory=dict)
    dependencies: List[str] = Field(default_factory=list)

    # Метаданные для аудита
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: Optional[str] = None

    # ← НОВОЕ: Настройки LLM для управления structured output
    llm_settings: Dict[str, Any] = Field(default_factory=dict, description={
        "description": "Настройки LLM для управления structured output",
        "use_native_structured_output": "Использовать нативную поддержку схемы провайдером (True) или вшивать в промпт (False)",
        "schema_in_prompt": "Встраивать ли JSON схему в текст промпта (устаревший режим)",
        "max_retries": "Максимальное количество попыток генерации валидного ответа",
        "provider_specific": "Специфичные настройки для конкретного провайдера"
    })

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