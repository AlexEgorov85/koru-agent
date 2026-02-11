"""
Базовый класс для сервисов с поддержкой кэширования промптов и контрактов.
"""
from abc import ABC, abstractmethod
import logging
from typing import Any, Dict, Optional
from core.system_context.base_system_contex import BaseSystemContext
from core.config.agent_config import AgentConfig
from core.config.component_config import ComponentConfig
from core.components.base_component import BaseComponent
from core.infrastructure.services.base_service import ServiceInput, ServiceOutput


class CachedBaseService(BaseComponent):
    """
    Абстрактный базовый класс для всех инфраструктурных сервисов с кэшированием.
    """

    def __init__(self, name: str, system_context: BaseSystemContext, component_config: Optional[ComponentConfig] = None):
        super().__init__(name, system_context, component_config)

        # === КРИТИЧЕСКИ ВАЖНО: изолированные кэши инициализируются ПУСТЫМИ ===
        # Попытка использования до initialize() вызовет ошибку
        self._cached_prompts: Dict[str, str] = {}          # {capability_name: prompt_text}
        self._cached_input_contracts: Dict[str, Dict] = {}  # {capability_name: contract_schema}
        self._cached_output_contracts: Dict[str, Dict] = {} # {capability_name: contract_schema}

    async def initialize_with_config(self, agent_config: Optional[AgentConfig] = None) -> bool:
        """
        Инициализация с единовременной загрузкой ВСЕХ ресурсов из локальной конфигурации.
        После завершения метода компонент НЕ должен обращаться к внешним сервисам.
        """
        # В новой архитектуре инициализация происходит через BaseComponent
        # Этот метод больше не используется, так как инициализация происходит через BaseComponent
        pass

    async def initialize(self) -> bool:
        """
        Инициализация с единовременной загрузкой ВСЕХ ресурсов из локальной конфигурации.
        После завершения метода компонент НЕ должен обращаться к внешним сервисам.
        """
        # Вызов родительской инициализации
        success = await super().initialize()
        
        if success:
            self.logger.info(
                f"Сервис '{self.name}' инициализирован с вариантом '{getattr(self.component_config, 'variant_key', 'default')}'. "
                f"Загружено: промпты={len(self._cached_prompts)}, "
                f"input-контракты={len(self._cached_input_contracts)}, "
                f"output-контракты={len(self._cached_output_contracts)}"
            )
        
        return success

    async def initialize_with_system_config(self, system_resources_config: Any) -> bool:
        """
        Инициализация сервиса с ОДНОКРАТНОЙ загрузкой промптов и контрактов из конфигурации системных ресурсов.
        Используется при инициализации системного контекста.
        """
        # В новой архитектуре инициализация происходит через ComponentConfig
        # Этот метод больше не используется, так как инициализация происходит через BaseComponent
        pass

    # Методы _load_service_prompts_from_system_config, _load_service_contracts_from_system_config,
    # get_required_prompt_names, get_required_contract_names, _load_service_prompts, _load_service_contracts
    # больше не используются в новой архитектуре, так как инициализация происходит через BaseComponent
    # и ComponentConfig

    # Методы get_prompt, get_input_contract, get_output_contract и get_contract
    # наследуются из BaseComponent и обеспечивают доступ к изолированным кэшам
    # компонента, предварительно загруженным при инициализации через ComponentConfig

    # Абстрактные методы, которые должны быть реализованы в дочерних классах
    async def initialize(self) -> bool:
        """Стандартный метод инициализации (реализован в BaseComponent)"""
        # Вызов родительской инициализации
        return await super().initialize()

    @abstractmethod
    async def execute(self, input_data: ServiceInput) -> ServiceOutput:
        """Выполнение сервиса"""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Завершение работы сервиса"""
        pass