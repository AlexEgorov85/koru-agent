from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from domain.abstractions.base_skill import BaseSkill


class ISkillRegistry(ABC):
    """Интерфейс реестра навыков"""
    
    @abstractmethod
    def register_skill(self, skill: BaseSkill) -> None:
        """Регистрация навыка"""
        pass
    
    @abstractmethod
    def get_skill(self, name: str) -> Optional[BaseSkill]:
        """Получение навыка по имени"""
        pass
    
    @abstractmethod
    def get_all_skills(self) -> Dict[str, BaseSkill]:
        """Получение всех навыков"""
        pass
    
    @abstractmethod
    def filter_skills_by_category(self, category: str) -> Dict[str, BaseSkill]:
        """Фильтрация навыков по категории"""
        pass
    
    @abstractmethod
    def get_skill_dependencies(self, name: str) -> List[str]:
        """Получение зависимостей навыка"""
        pass
    
    @abstractmethod
    def is_skill_ready(self, name: str) -> bool:
        """Проверка готовности навыка"""
        pass
    
    @abstractmethod
    def remove_skill(self, name: str) -> bool:
        """Удаление навыка по имени"""
        pass