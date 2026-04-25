"""
Сервис контрактов с изолированным кэшем.

АРХИТЕКТУРА:
- Не зависит от хранилищ напрямую
- Использует предзагруженные ресурсы из ComponentConfig
- Кэш контрактов изолирован в рамках экземпляра сервиса
"""
from typing import Dict, Tuple, Optional, Any
from core.components.services.service import Service
from core.config.component_config import ComponentConfig
from core.models.errors.version_not_found import VersionNotFoundError


class ContractService(Service):
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
        executor = None
    ):
        # Call the parent constructor with proper parameters - передаём component_config явно
        super().__init__(
            name=name,
            component_config=component_config,
            executor=executor,
            application_context=application_context
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
                self._log_warning(
                    f"Отсутствуют контракты в предзагруженных ресурсах: {missing_contracts}"
                )

            self._initialized = True
            self._log_info(
                f"ContractService инициализирован: загружено {len(self.contracts)} контрактов"
            )
            return True
        except Exception as e:
            self._log_error(f"Ошибка инициализации ContractService: {e}")
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
        
        АРХИТЕКТУРА: Используем get_input_contract() для валидации структуры входных данных.
        """
        # Получаем входной контракт для валидации структуры параметров
        input_schema = self.get_input_contract("contract.service.get_contract")
        if input_schema:
            # Валидация структуры входных данных через контракт
            validated_input = input_schema.model_validate(parameters)
            direction = validated_input.direction
        else:
            # Fallback: если контракт не найден, используем значение по умолчанию
            direction = parameters.get("direction", "input")
        
        # Получение контракта по capability
        contract = self.get_contract(capability.name, direction)

        # Возвращаем результат, соответствующий выходному контракту
        result = {
            "capability": capability.name,
            "direction": direction,
            "schema": contract
        }
        
        # Валидация выхода через контракт (если доступен)
        output_schema = self.get_output_contract("contract.service.get_contract")
        if output_schema:
            return output_schema.model_validate(result).model_dump()
        
        return result
