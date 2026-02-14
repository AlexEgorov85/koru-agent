"""
Интерфейсы для хранилищ компонентов системы.

СОДЕРЖИТ:
- IPromptStorage: интерфейс для хранилища промптов
- IContractStorage: интерфейс для хранилища контрактов
- IStorageResult: общий интерфейс для результатов хранилищ
"""
from abc import ABC, abstractmethod
from typing import Protocol, TypeVar, Generic, Optional
from pathlib import Path
from enum import Enum
from core.models.prompt import Prompt
from core.models.contract import Contract


class ComponentType(Enum):
    """Тип компонента для качественного поиска."""
    SKILL = "skill"
    SERVICE = "service"
    STRATEGY = "strategy"
    TOOL = "tool"
    SQL_GENERATION = "sql_generation"
    CONTRACT = "contract"
    DEFAULT = "default"  # для случаев, когда тип неизвестен


class IStorageResult(ABC):
    """Базовый интерфейс для результатов хранилищ."""
    
    @property
    @abstractmethod
    def is_success(self) -> bool:
        """Успешно ли выполнение операции."""
        pass
    
    @property
    @abstractmethod
    def error_message(self) -> Optional[str]:
        """Сообщение об ошибке, если операция не удалась."""
        pass


class IPromptStorage(ABC):
    """Интерфейс для хранилища промптов."""

    @abstractmethod
    async def load(self, capability_name: str, version: str, component_type: Optional[ComponentType] = None) -> Prompt:
        """
        Загрузка промпта из файловой системы.

        ARGS:
        - capability_name: имя capability (например, "planning.create_plan")
        - version: версия промпта (например, "v1.0.0")
        - component_type: тип компонента для качественного поиска (опционально)

        RETURNS:
        - Prompt: объект промпта

        RAISES:
        - VersionNotFoundError: если версия не найдена
        - ValidationError: если данные некорректны
        """
        pass

    @abstractmethod
    async def exists(self, capability_name: str, version: str, component_type: Optional[ComponentType] = None) -> bool:
        """
        Проверка существования промпта без загрузки содержимого.

        ARGS:
        - capability_name: имя capability
        - version: версия промпта
        - component_type: тип компонента для качественного поиска (опционально)

        RETURNS:
        - bool: True если промпт существует
        """
        pass

    @abstractmethod
    async def save(self, capability_name: str, version: str, prompt: Prompt, component_type: Optional[ComponentType] = None) -> None:
        """
        Сохранение промпта в файловую систему.

        ARGS:
        - capability_name: имя capability (например, "planning.create_plan")
        - version: версия промпта (например, "v1.0.0")
        - prompt: объект промпта для сохранения
        - component_type: тип компонента для качественного поиска (опционально)

        RAISES:
        - IOError: если не удалось сохранить файл
        """
        pass


class IContractStorage(ABC):
    """Интерфейс для хранилища контрактов."""

    @abstractmethod
    async def load(self, capability_name: str, version: str, direction: str, component_type: Optional[ComponentType] = None) -> Contract:
        """
        Загрузка контракта из файловой системы.

        ARGS:
        - capability_name: имя capability (например, "planning.create_plan")
        - version: версия контракта (например, "v1.0.0")
        - direction: направление контракта ("input" или "output")
        - component_type: тип компонента для качественного поиска (опционально)

        RETURNS:
        - Contract: объект контракта

        RAISES:
        - VersionNotFoundError: если версия не найдена
        - ValidationError: если данные некорректны
        """
        pass

    @abstractmethod
    async def exists(self, capability_name: str, version: str, direction: str, component_type: Optional[ComponentType] = None) -> bool:
        """
        Проверка существования контракта без загрузки содержимого.

        ARGS:
        - capability_name: имя capability
        - version: версия контракта
        - direction: направление контракта ("input" или "output")
        - component_type: тип компонента для качественного поиска (опционально)

        RETURNS:
        - bool: True если контракт существует
        """
        pass

    @abstractmethod
    async def save(self, capability_name: str, version: str, direction: str, contract: Contract, component_type: Optional[ComponentType] = None) -> None:
        """
        Сохранение контракта в файловую систему.

        ARGS:
        - capability_name: имя capability (например, "planning.create_plan")
        - version: версия контракта (например, "v1.0.0")
        - direction: направление контракта ("input" или "output")
        - contract: объект контракта для сохранения
        - component_type: тип компонента для качественного поиска (опционально)

        RAISES:
        - IOError: если не удалось сохранить файл
        """
        pass