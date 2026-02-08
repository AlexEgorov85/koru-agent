"""
Реестр компонуемых паттернов.
"""
from typing import Dict, Type, Optional, List
from application.agent.composable_patterns.base import ComposablePattern


class ComposablePatternRegistry:
    """Реестр компонуемых паттернов."""
    
    def __init__(self):
        self._patterns: Dict[str, Type[ComposablePattern]] = {}
        self._instances: Dict[str, ComposablePattern] = {}
    
    def register_pattern(self, name: str, pattern_class: Type[ComposablePattern]):
        """Регистрация класса паттерна по имени."""
        self._patterns[name] = pattern_class
    
    def get_pattern_class(self, name: str) -> Optional[Type[ComposablePattern]]:
        """Получение класса паттерна по имени."""
        return self._patterns.get(name)
    
    def create_pattern(self, name: str, **kwargs) -> Optional[ComposablePattern]:
        """Создание экземпляра паттерна."""
        pattern_class = self._patterns.get(name)
        if not pattern_class:
            return None
        
        instance = pattern_class(**kwargs)
        self._instances[name] = instance
        return instance
    
    def get_pattern(self, name: str) -> Optional[ComposablePattern]:
        """Получение существующего экземпляра паттерна или создание нового."""
        if name in self._instances:
            return self._instances[name]
        
        return self.create_pattern(name)
    
    def list_patterns(self) -> List[str]:
        """Список всех зарегистрированных имен паттернов."""
        return list(self._patterns.keys())