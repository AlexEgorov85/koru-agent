"""
Сервис контрактов с изолированным кэшем.

АРХИТЕКТУРА:
- Не зависит от хранилищ напрямую
- Использует предзагруженные ресурсы из ComponentConfig
- Кэш контрактов изолирован в рамках экземпляра сервиса
"""
from typing import Dict, Tuple, Optional, Any
from core.application.services.base_service import BaseService, ServiceInput, ServiceOutput
from core.config.component_config import ComponentConfig
from core.models.errors.version_not_found import VersionNotFoundError


class ContractService(BaseService):
    """
    Сервис контрактов с ИЗОЛИРОВАННЫМ кэшем.
    Создаётся НОВЫЙ экземпляр для каждого ApplicationContext.
    """

    # Явная декларация зависимостей
    DEPENDENCIES = []  # Нет зависимостей

    @property
    def description(self) -> str:
        return "Сервис контрактов с изолированным кэшем"

    def __init__(
        self,
        name: str = "contract_service",
        application_context: 'ApplicationContext' = None,
        component_config: ComponentConfig = None,
        executor = None
    ):
        # Call the parent constructor with proper parameters - передаём component_config явно
        super().__init__(
            name=name,
            application_context=application_context,
            component_config=component_config,  # ← Передаём напрямую!
            executor=executor
        )
        # Кэш: {(capability, direction): schema}
        self.contracts: Dict[Tuple[str, str], Dict] = {}  # ← Изолированный кэш!
