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

    async def initialize(self) -> bool:
        """Инициализация ContractService с использованием предзагруженных ресурсов из ComponentConfig."""
        try:
            # Используем предзагруженные контракты из ComponentConfig
            # Они уже были загружены в ComponentConfig через DataRepository

            # Загружаем входные контракты
            input_versions = self.component_config.input_contract_versions
            missing_contracts = []
            for capability, version in input_versions.items():
                # Получаем схему контракта из resolved_input_contracts в ComponentConfig (предзагруженные ресурсы)
                if capability in self.component_config.resolved_input_contracts:
                    schema = self.component_config.resolved_input_contracts[capability]
                    self.contracts[(capability, "input")] = schema
                else:
                    missing_contracts.append(f"input:{capability}@{version}")

            # Загружаем выходные контракты
            output_versions = self.component_config.output_contract_versions
            for capability, version in output_versions.items():
                if capability in self.component_config.resolved_output_contracts:
                    schema = self.component_config.resolved_output_contracts[capability]
                    self.contracts[(capability, "output")] = schema
                else:
                    missing_contracts.append(f"output:{capability}@{version}")

            # Логируем отсутствующие контракты (но не блокируем инициализацию)
            if missing_contracts:
                self.event_bus_logger.warning_sync(
                    f"Отсутствуют контракты в предзагруженных ресурсах: {missing_contracts}"
                )

            self._initialized = True
            self.event_bus_logger.info_sync(
                f"ContractService инициализирован: загружено {len(self.contracts)} контрактов"
            )
            return True
        except Exception as e:
            self.event_bus_logger.error_sync(f"Ошибка инициализации ContractService: {e}")
            return False

    def get_contract(self, capability_name: str, direction: str) -> Dict:
        """Возвращает контракт из ИЗОЛИРОВАННОГО кэша."""
        if not self._initialized:
            raise RuntimeError(
                f"Сервис '{self.name}' не инициализирован. "
                f"Вызовите .initialize() перед использованием."
            )

        key = (capability_name, direction)
        if key not in self.contracts:
            raise KeyError(
                f"Контракт для capability '{capability_name}' ({direction}) не найден в кэше. "
                f"Доступные: {[k for k in self.contracts.keys() if k[0] == capability_name]}"
            )

        return self.contracts[key]

    def get_all_contracts(self) -> Dict[Tuple[str, str], Dict]:
        """Возвращает копию кэша контрактов (для отладки)."""
        if not self._initialized:
            raise RuntimeError(
                f"Сервис '{self.name}' не инициализирован. "
                f"Вызовите .initialize() перед использованием."
            )
        return self.contracts.copy()

    # DEPRECATED: preload_contracts удалён — используйте предзагруженные ресурсы из ComponentConfig

    def get_contract_schema_from_cache(self, capability_name: str, direction: str) -> Dict:
        """
        Возвращает схему контракта ТОЛЬКО из кэша (без обращения к хранилищу).
        Совместимость с BaseComponent.
        """
        if not self._initialized:
            raise RuntimeError(
                f"Сервис '{self.name}' не инициализирован. "
                f"Вызовите .initialize() перед использованием."
            )

        key = (capability_name, direction)
        if key not in self.contracts:
            raise KeyError(
                f"Контракт для capability '{capability_name}' ({direction}) не найден в кэше. "
                f"Доступные: {[k for k in self.contracts.keys() if k[0] == capability_name]}"
            )

        return self.contracts[key]

    def _get_event_type_for_success(self) -> 'EventType':
        """Возвращает тип события для успешного выполнения сервиса контрактов."""
        from core.infrastructure.event_bus.unified_event_bus import EventType
        return EventType.PROVIDER_REGISTERED

    def _execute_impl(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: 'ExecutionContext'
    ) -> Dict[str, Any]:
        """
        Реализация бизнес-логики сервиса контрактов (СИНХРОННАЯ).

        ВАЖНО: Валидация входа/выхода и метрики выполняются в BaseComponent.execute()
        Здесь только бизнес-логика.
        """
        # Получение контракта по capability
        direction = parameters.get("direction", "input")
        contract = self.get_contract(capability.name, direction)

        return {
            "capability": capability.name,
            "direction": direction,
            "schema": contract
        }
