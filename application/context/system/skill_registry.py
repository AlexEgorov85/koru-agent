from typing import Dict, List, Optional
from domain.abstractions.system.i_skill_registry import ISkillRegistry
from domain.abstractions.skills.base_skill import BaseSkill
from domain.models.system.skill_metadata import SkillMetadata


class SkillRegistry(ISkillRegistry):
    """Реализация реестра навыков"""
    
    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}
        self._tool_registry = None  # Будет установлен позже для проверки зависимостей
    
    def set_tool_registry(self, tool_registry):
        """Установка ссылки на реестр инструментов для проверки зависимостей"""
        self._tool_registry = tool_registry
    
    def register_skill(self, skill: BaseSkill) -> None:
        """Регистрация навыка с уникальным именем"""
        if skill.name in self._skills:
            raise ValueError(f"Навык с именем '{skill.name}' уже зарегистрирован")
        
        self._skills[skill.name] = skill
    
    def get_skill(self, name: str) -> Optional[BaseSkill]:
        """Получение навыка по имени"""
        return self._skills.get(name)
    
    def get_all_skills(self) -> Dict[str, BaseSkill]:
        """Получение всех навыков"""
        return self._skills.copy()
    
    def filter_skills_by_category(self, category: str) -> Dict[str, BaseSkill]:
        """Фильтрация навыков по категории"""
        filtered_skills = {}
        
        for name, skill in self._skills.items():
            # Проверяем, есть ли у навыка атрибут category
            if hasattr(skill, 'category') and skill.category == category:
                filtered_skills[name] = skill
            # Если навык имеет метаданные, проверяем их тоже
            elif hasattr(skill, '__metadata__') and skill.__metadata__.category == category:
                filtered_skills[name] = skill
        
        return filtered_skills
    
    def get_skill_dependencies(self, name: str) -> List[str]:
        """Получение зависимостей навыка"""
        skill = self._skills.get(name)
        if skill is None:
            # Возвращаем пустой список, если навык не найден, вместо выбрасывания исключения
            return []
        
        # Проверяем, есть ли у навыка атрибут required_tools
        if hasattr(skill, 'required_tools'):
            return skill.required_tools
        # Если навык имеет метаданные, проверяем их тоже
        elif hasattr(skill, '__metadata__'):
            return skill.__metadata__.required_tools
        else:
            return []
    
    def is_skill_ready(self, name: str) -> bool:
        """Проверка готовности навыка (все зависимости зарегистрированы)"""
        skill = self._skills.get(name)
        if skill is None:
            return False
        
        # Получаем зависимости навыка
        dependencies = self.get_skill_dependencies(name)
        
        # Если нет реестра инструментов, невозможно проверить зависимости
        if self._tool_registry is None:
            return False
        
        # Проверяем, зарегистрированы ли все требуемые инструменты
        for dep_name in dependencies:
            if self._tool_registry.get_tool(dep_name) is None:
                return False
        
        return True
    
    def remove_skill(self, name: str) -> bool:
        """Удаление навыка по имени"""
        if name in self._skills:
            del self._skills[name]
            return True
        return False