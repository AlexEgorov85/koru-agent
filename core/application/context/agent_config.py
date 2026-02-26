"""
Конфигурация агента - версионируемая конфигурация для изолированной сессии.
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from core.config.component_config import ComponentConfig


@dataclass
class AgentConfig:
    """
    Конфигурация агента для изолированной сессии.
    
    ОТЛИЧИЯ ОТ СИСТЕМНОЙ КОНФИГУРАЦИИ:
    - Версионируемая (может отличаться от сессии к сессии)
    - Содержит только прикладные компоненты (навыки, инструменты)
    - Может переопределять глобальные настройки для конкретной сессии
    - Поддерживает изолированные кэши для каждого агента
    """
    
    # Идентификатор агента
    agent_id: str
    
    # Название агента
    name: str = "default_agent"
    
    # Описание агента
    description: str = ""
    
    # Настройки навыков
    skills: Dict[str, ComponentConfig] = field(default_factory=dict)
    
    # Настройки инструментов
    tools: Dict[str, ComponentConfig] = field(default_factory=dict)
    
    # Настройки сервисов
    services: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    
    # Дополнительные параметры
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Включена ли сессия
    enabled: bool = True
    
    # Путь к данным агента
    data_dir: Optional[str] = None
    
    # Таймауты
    timeouts: Dict[str, int] = field(default_factory=lambda: {
        "execution": 300,  # 5 минут
        "initialization": 60,  # 1 минута
        "shutdown": 30  # 30 секунд
    })
    
    def get_skill_config(self, skill_name: str) -> Optional[ComponentConfig]:
        """Получение конфигурации навыка по имени."""
        return self.skills.get(skill_name)
    
    def get_tool_config(self, tool_name: str) -> Optional[ComponentConfig]:
        """Получение конфигурации инструмента по имени."""
        return self.tools.get(tool_name)
    
    def update_skill_config(self, skill_name: str, config: ComponentConfig):
        """Обновление конфигурации навыка."""
        self.skills[skill_name] = config
        
    def update_tool_config(self, tool_name: str, config: ComponentConfig):
        """Обновление конфигурации инструмента."""
        self.tools[tool_name] = config