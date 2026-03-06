"""
Интерфейс для хранилища контрактов.
"""

from typing import Protocol, Optional, Dict, Any, Type
from pydantic import BaseModel
from core.models.enums.common_enums import ComponentType
from core.models.data.contract import Contract


class ContractStorageInterface(Protocol):
    """Интерфейс для хранилища контрактов."""

    async def load(
        self,
        capability_name: str,
        version: str,
        direction: str,
        component_type: Optional[ComponentType] = None
    ) -> Contract:
        """
        Загрузка контракта из файловой системы.

        ARGS:
        - capability_name: имя capability
        - version: версия контракта
        - direction: направление (input/output)
        - component_type: тип компонента

        RETURNS:
        - Contract: объект контракта
        """
        ...

    async def exists(
        self,
        capability_name: str,
        version: str,
        direction: str,
        component_type: Optional[ComponentType] = None
    ) -> bool:
        """
        Проверка существования контракта.

        ARGS:
        - capability_name: имя capability
        - version: версия контракта
        - direction: направление (input/output)
        - component_type: тип компонента

        RETURNS:
        - bool: True если контракт существует
        """
        ...

    async def save(
        self,
        capability_name: str,
        version: str,
        contract: Contract,
        direction: str,
        component_type: Optional[ComponentType] = None
    ) -> None:
        """
        Сохранение контракта в файловую систему.

        ARGS:
        - capability_name: имя capability
        - version: версия контракта
        - contract: объект контракта
        - direction: направление (input/output)
        - component_type: тип компонента
        """
        ...

    async def get_schema(
        self,
        capability_name: str,
        version: str,
        direction: str
    ) -> Optional[Type[BaseModel]]:
        """
        Получение Pydantic схемы контракта.

        ARGS:
        - capability_name: имя capability
        - version: версия контракта
        - direction: направление (input/output)

        RETURNS:
        - Pydantic модель или None
        """
        ...
