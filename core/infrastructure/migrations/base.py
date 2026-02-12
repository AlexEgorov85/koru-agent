"""
Базовые классы для миграций промптов и контрактов.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class Migration(ABC):
    """
    Базовый класс для всех миграций.
    
    ATTRIBUTES:
    - version_from: исходная версия
    - version_to: целевая версия
    """
    version_from: str
    version_to: str

    @abstractmethod
    def up(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Метод миграции вперед (апгрейд).
        
        ARGS:
        - data: исходные данные
        
        RETURNS:
        - обновленные данные
        """
        pass

    @abstractmethod
    def down(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Метод миграции назад (даунгрейд).
        
        ARGS:
        - data: данные после миграции вперед
        
        RETURNS:
        - данные в исходном состоянии
        """
        pass


class PromptMigration(Migration):
    """
    Базовый класс для миграций промптов.
    """
    pass


class ContractMigration(Migration):
    """
    Базовый класс для миграций контрактов.
    """
    pass