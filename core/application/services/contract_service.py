"""
Сервис контрактов с изолированным кэшем.
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
    
    @property
    def description(self) -> str:
        return "Сервис контрактов с изолированным кэшем"
    
    def __init__(
        self,
        name: str = "contract_service",
        application_context: 'ApplicationContext' = None,
        component_config: ComponentConfig = None,
        executor = None  # Добавляем executor для совместимости с новой архитектурой
    ):
        # Call the parent constructor with proper parameters
        super().__init__(name, application_context, component_config, executor)
        # Кэш: {(capability, direction): schema}
        self._cached_contracts: Dict[Tuple[str, str], Dict] = {}  # ← Изолированный кэш!
    
    async def initialize(self) -> bool:
        """Инициализация ContractService с использованием предзагруженных ресурсов из ComponentConfig."""
        try:
            self.logger.info(f"ContractService.initialize: resolved_input_contracts={self.component_config.resolved_input_contracts.keys()}")
            self.logger.info(f"ContractService.initialize: input_contract_versions={self.component_config.input_contract_versions}")
            # Используем предзагруженные контракты из ComponentConfig
            # Они уже были загружены в ComponentConfig через DataRepository

            # Загружаем входные контракты
            input_versions = self.component_config.input_contract_versions
            missing_contracts = []
            for capability, version in input_versions.items():
                # Получаем схему контракта из resolved_input_contracts в ComponentConfig (предзагруженные ресурсы)
                if capability in self.component_config.resolved_input_contracts:
                    schema = self.component_config.resolved_input_contracts[capability]
                    self._cached_contracts[(capability, "input")] = schema
                else:
                    self.logger.error(f"Input-контракт {capability}@{version} не найден в предзагруженных ресурсах")
                    missing_contracts.append(f"{capability}@{version} (input)")

            # Загружаем выходные контракты
            output_versions = self.component_config.output_contract_versions
            for capability, version in output_versions.items():
                # Получаем схему контракта из resolved_output_contracts в ComponentConfig (предзагруженные ресурсы)
                if capability in self.component_config.resolved_output_contracts:
                    schema = self.component_config.resolved_output_contracts[capability]
                    self._cached_contracts[(capability, "output")] = schema
                else:
                    self.logger.error(f"Output-контракт {capability}@{version} не найден в предзагруженных ресурсах")
                    missing_contracts.append(f"{capability}@{version} (output)")

            # Проверяем, все ли контракты загружены
            if missing_contracts:
                self.logger.error(f"ContractService: отсутствуют критические контракты: {missing_contracts}")
                self._initialized = False
                return False

            self._initialized = True
            self.logger.info(
                f"ContractService инициализирован: "
                f"загружено {len(self._cached_contracts)} контрактов"
            )
            return True

        except Exception as e:
            self.logger.error(f"Ошибка инициализации ContractService: {e}")
            return False
    
    def get_contract(self, capability_name: str, direction: str) -> Dict:
        """Возвращает схему контракта из ИЗОЛИРОВАННОГО кэша."""
        if not self._initialized:
            raise RuntimeError(
                f"Сервис '{self.name}' не инициализирован. "
                f"Вызовите .initialize() перед использованием."
            )
        
        key = (capability_name, direction)
        if key not in self._cached_contracts:
            raise KeyError(
                f"Контракт для capability '{capability_name}' ({direction}) не найден в кэше. "
                f"Доступные: {[k for k in self._cached_contracts.keys() if k[0] == capability_name]}"
            )
        
        return self._cached_contracts[key]

    async def preload_contracts(self, component_config) -> bool:
        """
        Предзагрузка всех контрактов, указанных в конфигурации компонента.
        Совместимость с BaseComponent.
        """
        try:
            storage = self.application_context.infrastructure_context.get_contract_storage()

            # Предзагружаем входные контракты
            input_versions = getattr(component_config, 'input_contract_versions', {})
            for capability, version in input_versions.items():
                if not await storage.exists(capability, version, "input"):
                    raise VersionNotFoundError(
                        f"Input-контракт {capability}@{version} отсутствует в хранилище"
                    )
                contract = await storage.load(capability, version, "input")
                self._cached_contracts[(capability, "input")] = contract.schema_data

            # Предзагружаем выходные контракты
            output_versions = getattr(component_config, 'output_contract_versions', {})
            for capability, version in output_versions.items():
                if not await storage.exists(capability, version, "output"):
                    raise VersionNotFoundError(
                        f"Output-контракт {capability}@{version} отсутствует в хранилище"
                    )
                contract = await storage.load(capability, version, "output")
                self._cached_contracts[(capability, "output")] = contract.schema_data

            self.logger.info(
                f"Контракты предзагружены: "
                f"загружено {len(self._cached_contracts)} контрактов"
            )
            return True

        except Exception as e:
            self.logger.error(f"Ошибка предзагрузки контрактов: {e}")
            return False

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
        if key not in self._cached_contracts:
            raise KeyError(
                f"Контракт для capability '{capability_name}' ({direction}) не найден в кэше. "
                f"Доступные: {[k for k in self._cached_contracts.keys() if k[0] == capability_name]}"
            )

        return self._cached_contracts[key]

    async def execute(self, input_data: ServiceInput) -> ServiceOutput:
        """Execute method required by the base class."""
        # For this service, we can implement a basic execution that returns a contract
        # based on input data if needed, but for now just return a dummy output
        return ServiceOutput()