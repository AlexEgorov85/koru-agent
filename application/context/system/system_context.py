from typing import Any, Dict, Optional
from domain.abstractions.tools.base_tool import BaseTool
from domain.abstractions.skills.base_skill import BaseSkill
from application.context.system.tool_registry import ToolRegistry
from application.context.system.skill_registry import SkillRegistry
from application.context.system.config_manager import ConfigManager
from domain.models.system.config import SystemConfig
from domain.abstractions.system.base_system_context import IBaseSystemContext
from domain.abstractions.event_system import IEventPublisher


class SystemContext(IBaseSystemContext):
    """
    Cистемный контекст - чистый реестр компонентов системы.
    
    АРХИТЕКТУРА:
    - Pattern: Registry/Facade
    - Предоставляет доступ только к реестрам компонентов (инструментов, навыков, конфигурации)
    - Не содержит логики выполнения, жизненного цикла или управления событиями
    - Является read-only источником для других компонентов системы
    
    ВНУТРЕННИЕ КОМПОНЕНТЫ:
    - tool_registry: Реестр инструментов
    - skill_registry: Реестр навыков
    - config_manager: Менеджер конфигурации
    """
    
    def __init__(self, config: Optional[SystemConfig] = None):
        """
        Инициализация системного контекста.
        
        ПАРАМЕТРЫ:
        - config: Конфигурация приложения (опционально)
        """
        self.tool_registry = ToolRegistry()
        self.skill_registry = SkillRegistry()
        self.config_manager = ConfigManager(config)
        
        # Связываем реестры для проверки зависимостей
        self.skill_registry.set_tool_registry(self.tool_registry)
    
    def get_resource(self, resource_name: str) -> Any:
        """
        Получить ресурс по имени (реализация интерфейса IBaseSystemContext)
        """
        # Для совместимости с интерфейсом - ищем в навыках
        skill = self.skill_registry.get_skill(resource_name)
        if skill:
            return skill
        
        # Также можем искать инструменты
        tool = self.tool_registry.get_tool(resource_name)
        if tool:
            return tool
            
        return None
    
    def get_event_bus(self) -> IEventPublisher:
        """
        Получить шину событий (реализация интерфейса IBaseSystemContext)
        """
        # Возвращаем None, так как SystemContext не управляет шиной событий
        # Шина событий управляется через SystemOrchestrator
        return None
    
    def initialize(self) -> bool:
        """
        Инициализировать контекст (реализация интерфейса IBaseSystemContext)
        """
        return self.validate()
    
    def shutdown(self) -> None:
        """
        Корректно завершить работу (реализация интерфейса IBaseSystemContext)
        """
        # Выполняем сброс конфигурации
        self.config_manager.reset_config()
    
    # Методы для работы с инструментами
    def register_tool(self, tool: BaseTool) -> None:
        """Регистрация инструмента"""
        self.tool_registry.register_tool(tool)
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Получение инструмента по имени"""
        return self.tool_registry.get_tool(name)
    
    def get_all_tools(self) -> Dict[str, BaseTool]:
        """Получение всех инструментов"""
        return self.tool_registry.get_all_tools()
    
    def filter_tools_by_tag(self, tag: str) -> Dict[str, BaseTool]:
        """Фильтрация инструментов по тегу"""
        return self.tool_registry.filter_tools_by_tag(tag)
    
    def update_tool(self, name: str, tool: BaseTool) -> None:
        """Обновление инструмента"""
        self.tool_registry.update_tool(name, tool)
    
    def remove_tool(self, name: str) -> bool:
        """Удаление инструмента по имени"""
        return self.tool_registry.remove_tool(name)
    
    # Методы для работы с навыками
    def register_skill(self, skill: BaseSkill) -> None:
        """Регистрация навыка"""
        self.skill_registry.register_skill(skill)
    
    def get_skill(self, name: str) -> Optional[BaseSkill]:
        """Получение навыка по имени"""
        return self.skill_registry.get_skill(name)
    
    def get_all_skills(self) -> Dict[str, BaseSkill]:
        """Получение всех навыков"""
        return self.skill_registry.get_all_skills()
    
    def filter_skills_by_category(self, category: str) -> Dict[str, BaseSkill]:
        """Фильтрация навыков по категории"""
        return self.skill_registry.filter_skills_by_category(category)
    
    def get_skill_dependencies(self, name: str) -> list:
        """Получение зависимостей навыка"""
        return self.skill_registry.get_skill_dependencies(name)
    
    def is_skill_ready(self, name: str) -> bool:
        """Проверка готовности навыка"""
        return self.skill_registry.is_skill_ready(name)
    
    def remove_skill(self, name: str) -> bool:
        """Удаление навыка по имени"""
        return self.skill_registry.remove_skill(name)
    
    # Методы для работы с конфигурацией
    def set_config(self, key: str, value: Any) -> None:
        """Установка параметра конфигурации"""
        self.config_manager.set_config(key, value)
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Получение параметра конфигурации"""
        return self.config_manager.get_config(key, default)
    
    def export_config(self) -> Dict[str, Any]:
        """Экспорт конфигурации"""
        return self.config_manager.export_config()
    
    def reset_config(self) -> None:
        """Сброс конфигурации"""
        self.config_manager.reset_config()
    
    def validate(self) -> bool:
        """Валидация системы"""
        # Проверяем, что все зарегистрированные навыки готовы (их зависимости удовлетворены)
        all_skills = self.get_all_skills()
        for skill_name in all_skills:
            if not self.is_skill_ready(skill_name):
                # Вместо выбрасывания исключения, возвращаем False при проблемах с зависимостями
                return False
        
        # Проверяем конфигурацию
        return self.config_manager.validate_config()
