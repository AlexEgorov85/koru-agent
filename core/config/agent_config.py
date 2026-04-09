from pydantic import BaseModel, Field, ConfigDict
from typing import Dict, Optional, Literal, Any
from datetime import datetime
import uuid


class AgentConfig(BaseModel):
    """
    Конфигурация агента с фиксированными версиями промптов и контрактов.
    Создаётся ОДИН РАЗ при запуске агента и не изменяется во время выполнения.
    """
    model_config = ConfigDict(frozen=True)  # Неизменяемая конфигурация
    
    # Идентификатор и метаданные
    config_id: str = Field(default_factory=lambda: f"cfg_{uuid.uuid4().hex[:8]}")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    source: Literal["explicit", "auto_resolved"] = Field("auto_resolved")
    
    # Версии промптов: {capability_name: version}
    prompt_versions: Dict[str, str] = Field(default_factory=dict)
    
    # Версии контрактов: {contract_name: version}
    contract_versions: Dict[str, str] = Field(default_factory=dict)
    
    # Параметры поведения агента
    max_steps: int = Field(10, ge=1, le=50)
    max_retries: int = Field(3, ge=0, le=10)
    temperature: float = Field(0.7, ge=0.0, le=1.0)
    
    # Флаги для тестирования
    allow_inactive_resources: bool = Field(False)
    
    # Фильтрация capability для промта размышлений
    capability_filter: Dict[str, Any] = Field(
        default_factory=lambda: {
            "include_hidden": False,
            "component_types": ["skill"],
        }
    )
    
    @classmethod
    def auto_resolve(cls, system_context: Any) -> 'AgentConfig':
        """
        Автоматическое разрешение конфигурации на основе активных версий.
        Вызывается при отсутствии явной конфигурации.
        """
        # Получаем реестр активных версий из существующего механизма
        # В проекте используется файловая структура с метаданными в промптах
        prompt_service = system_context.get_resource("prompt_service")
        if not prompt_service:
            raise RuntimeError("PromptService не зарегистрирован в системном контексте")
        
        # Сканируем директорию промптов и определяем активные версии
        # Логика: файлы НЕ в папке archived/ + статус 'active' в метаданных
        active_prompts = prompt_service.scan_active_prompts()
        
        # Формируем конфигурацию
        return cls(
            prompt_versions={
                cap: info["version"] 
                for cap, info in active_prompts.items() 
                if info.get("status") == "active"
            },
            source="auto_resolved"
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Сериализация для сохранения в отчёт бенчмарка"""
        return self.model_dump(mode='json')