"""
Модель конфигурации для системных ресурсов (навыки, инструменты, сервисы).
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Optional, Literal, Any
from datetime import datetime
import uuid


class SystemResourcesConfig(BaseModel):
    """
    Конфигурация системных ресурсов (навыки, инструменты, сервисы).
    Создается ОДИН РАЗ при инициализации SystemContext и не изменяется во время выполнения.
    """
    model_config = ConfigDict(frozen=True)  # Неизменяемая конфигурация
    
    # Идентификатор и метаданные
    config_id: str = Field(default_factory=lambda: f"sys_cfg_{uuid.uuid4().hex[:8]}")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    source: Literal["explicit", "auto_resolved"] = Field("auto_resolved")
    
    # Версии промптов для ресурсов системы: {resource_identifier: version}
    resource_prompt_versions: Dict[str, str] = Field(default_factory=dict)
    
    # Версии контрактов для ресурсов системы: {contract_name: version}
    resource_contract_versions: Dict[str, str] = Field(default_factory=dict)
    
    # Флаги для тестирования
    allow_inactive_resources: bool = Field(False)
    
    @classmethod
    def auto_resolve(cls, system_context: Any) -> 'SystemResourcesConfig':
        """
        Автоматическое разрешение конфигурации ресурсов на основе активных версий.
        Вызывается при отсутствии явной конфигурации.
        """
        # Получаем реестр активных версий из существующего механизма
        prompt_service = system_context.get_resource("prompt_service")
        if not prompt_service:
            raise RuntimeError("PromptService не зарегистрирован в системном контексте")
        
        # Сканируем директорию промптов и определяем активные версии
        active_prompts = prompt_service.scan_active_prompts()
        
        # Формируем конфигурацию
        return cls(
            resource_prompt_versions={
                res_id: info["version"] 
                for res_id, info in active_prompts.items() 
                if info.get("status") == "active"
            },
            source="auto_resolved"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация для сохранения в логи/отчеты"""
        return self.model_dump(mode='json')