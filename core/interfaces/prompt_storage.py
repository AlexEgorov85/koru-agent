"""
Интерфейс для хранилища промптов.
"""

from typing import Protocol, Optional
from core.models.enums.common_enums import ComponentType
from core.models.data.prompt import Prompt


class PromptStorageInterface(Protocol):
    """Интерфейс для хранилища промптов."""

    async def load(
        self,
        capability_name: str,
        version: str,
        component_type: Optional[ComponentType] = None
    ) -> Prompt:
        """
        Загрузка промпта из файловой системы.

        ARGS:
        - capability_name: имя capability
        - version: версия промпта
        - component_type: тип компонента

        RETURNS:
        - Prompt: объект промпта
        """
        ...

    async def exists(
        self,
        capability_name: str,
        version: str,
        component_type: Optional[ComponentType] = None
    ) -> bool:
        """
        Проверка существования промпта.

        ARGS:
        - capability_name: имя capability
        - version: версия промпта
        - component_type: тип компонента

        RETURNS:
        - bool: True если промпт существует
        """
        ...

    async def save(
        self,
        capability_name: str,
        version: str,
        prompt: Prompt,
        component_type: Optional[ComponentType] = None
    ) -> None:
        """
        Сохранение промпта в файловую систему.

        ARGS:
        - capability_name: имя capability
        - version: версия промпта
        - prompt: объект промпта
        - component_type: тип компонента
        """
        ...
