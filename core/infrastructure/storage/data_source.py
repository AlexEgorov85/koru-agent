"""
Интерфейс для источника данных, который предоставляет доступ к ресурсам системы.
"""
from abc import ABC, abstractmethod
from typing import List
from core.models.data.prompt import Prompt
from core.models.data.contract import Contract


class IDataSource(ABC):
    """Интерфейс для источника данных системы."""

    @abstractmethod
    async def load_prompt(self, capability: str, version: str) -> Prompt:
        """
        Загрузка промпта по capability и версии.
        
        Args:
            capability: имя capability (например, "planning.create_plan")
            version: версия промпта (например, "v1.0.0")
            
        Returns:
            Prompt: объект промпта
            
        Raises:
            FileNotFoundError: если промпт не найден
            ValueError: если данные некорректны
        """
        pass

    @abstractmethod
    async def load_contract(self, capability: str, version: str, direction: str) -> Contract:
        """
        Загрузка контракта по capability, версии и направлению.
        
        Args:
            capability: имя capability (например, "planning.create_plan")
            version: версия контракта (например, "v1.0.0")
            direction: направление контракта ("input" или "output")
            
        Returns:
            Contract: объект контракта
            
        Raises:
            FileNotFoundError: если контракт не найден
            ValueError: если данные некорректны
        """
        pass

    @abstractmethod
    async def list_prompts(self) -> List[Prompt]:
        """
        Сканирование и возврат всех доступных промптов.
        
        Returns:
            List[Prompt]: список всех промптов в системе
        """
        pass

    @abstractmethod
    async def list_contracts(self) -> List[Contract]:
        """
        Сканирование и возврат всех доступных контрактов.
        
        Returns:
            List[Contract]: список всех контрактов в системе
        """
        pass