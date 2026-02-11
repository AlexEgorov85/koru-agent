"""
Базовый класс для инструментов с поддержкой кэширования промптов и контрактов.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from core.system_context.base_system_contex import BaseSystemContext
from core.config.agent_config import AgentConfig
from core.config.component_config import ComponentConfig
from core.infrastructure.tools.base_tool import BaseTool, ToolInput, ToolOutput


class CachedBaseTool(BaseTool):
    """Базовый класс для инструментов с кэшированием промптов и контрактов."""

    def __init__(self, name: str, system_context: BaseSystemContext, component_config: Optional[ComponentConfig] = None, **kwargs):
        super().__init__(name, system_context, **kwargs)

        # === КРИТИЧЕСКИ ВАЖНО: изолированные кэши инициализируются ПУСТЫМИ ===
        # Попытка использования до initialize() вызовет ошибку
        self._cached_prompts: Dict[str, str] = {}          # {capability_name: prompt_text}
        self._cached_input_contracts: Dict[str, Dict] = {}  # {capability_name: contract_schema}
        self._cached_output_contracts: Dict[str, Dict] = {} # {capability_name: contract_schema}
        self.component_config = component_config
        self._agent_config: Optional[AgentConfig] = None

    async def initialize_with_config(self, agent_config: Optional[AgentConfig] = None) -> bool:
        """
        Инициализация с единовременной загрузкой ВСЕХ ресурсов из локальной конфигурации.
        После завершения метода компонент НЕ должен обращаться к внешним сервисам.
        """
        # === ШАГ 1: Загрузка из локальной конфигурации (приоритет) ===
        if self.component_config:
            # Загрузка промптов
            for cap_name, version in self.component_config.prompt_versions.items():
                prompt_service = self.system_context.get_resource("prompt_service")
                if prompt_service:
                    prompt = await prompt_service.get_prompt(
                        capability_name=cap_name,
                        version=version,
                        allow_inactive=False
                    )
                    self._cached_prompts[cap_name] = prompt
            
            # Загрузка ВХОДЯЩИХ контрактов
            for cap_name, version in self.component_config.input_contract_versions.items():
                contract_service = self.system_context.get_resource("contract_service")
                if contract_service:
                    contract = await contract_service.get_contract(
                        capability_name=cap_name,
                        version=version,
                        direction="input"  # ← ЯВНО указываем направление
                    )
                    self._cached_input_contracts[cap_name] = contract
            
            # Загрузка ИСХОДЯЩИХ контрактов
            for cap_name, version in self.component_config.output_contract_versions.items():
                contract_service = self.system_context.get_resource("contract_service")
                if contract_service:
                    contract = await contract_service.get_contract(
                        capability_name=cap_name,
                        version=version,
                        direction="output"  # ← ЯВНО указываем направление
                    )
                    self._cached_output_contracts[cap_name] = contract
            
            self.system_context.logger.info(
                f"Инструмент '{self.name}' инициализирован с вариантом '{self.component_config.variant_key}'. "
                f"Загружено: промпты={len(self._cached_prompts)}, "
                f"input-контракты={len(self._cached_input_contracts)}, "
                f"output-контракты={len(self._cached_output_contracts)}"
            )
            return True
        
        # === ШАГ 2: Обратная совместимость — загрузка из глобального agent_config ===
        elif agent_config:
            # 1. Сохраняем конфигурацию для внутреннего использования
            self._agent_config = agent_config

            # 2. Загружаем промпты, специфичные для инструмента
            await self._load_tool_prompts()

            # 3. Загружаем контракты, специфичные для инструмента
            await self._load_tool_contracts()

            self.system_context.logger.info(
                f"Инструмент '{self.name}' инициализирован. Загружено промптов: {len(self._cached_prompts)}"
            )
            return True
        
        else:
            raise ValueError(
                f"Инструмент '{self.name}' не может быть инициализирован: "
                f"отсутствует и локальная конфигурация (component_config), "
                f"и глобальная (agent_config)"
            )

    async def initialize_with_system_config(self, system_resources_config: Any) -> bool:
        """
        Инициализация инструмента с ОДНОКРАТНОЙ загрузкой промптов и контрактов из конфигурации системных ресурсов.
        Используется при инициализации системного контекста.
        """
        # 1. Сохраняем конфигурацию системных ресурсов для внутреннего использования
        self._system_resources_config = system_resources_config

        # 2. Загружаем промпты, специфичные для инструмента, из конфигурации системных ресурсов
        await self._load_tool_prompts_from_system_config()

        # 3. Загружаем контракты, специфичные для инструмента, из конфигурации системных ресурсов
        await self._load_tool_contracts_from_system_config()

        self.system_context.logger.info(
            f"Инструмент '{self.name}' инициализирован с кэшированием системных ресурсов. Загружено промптов: {len(self._cached_prompts)}"
        )
        return True

    async def _load_tool_prompts_from_system_config(self):
        """Загрузка промптов для инструмента из конфигурации системных ресурсов"""
        if hasattr(self._system_resources_config, 'resource_prompt_versions'):
            # Загрузка промптов для инструмента
            for prompt_name in self.get_required_prompt_names():
                version = self._system_resources_config.resource_prompt_versions.get(prompt_name)
                
                if version and self.system_context.get_resource("prompt_service"):
                    prompt = await self.system_context.get_resource("prompt_service").get_prompt(
                        capability_name=prompt_name,
                        version=version,
                        allow_inactive=self._system_resources_config.allow_inactive_resources
                    )
                    self._cached_prompts[prompt_name] = prompt

    async def _load_tool_contracts_from_system_config(self):
        """Загрузка контрактов для инструмента из конфигурации системных ресурсов"""
        if not self.system_context.get_resource("contract_service"):
            return
        
        # Загрузка контрактов для инструмента
        for contract_name in self.get_required_contract_names():
            version = self._system_resources_config.resource_contract_versions.get(contract_name)
            
            if version:
                contract = await self.system_context.get_resource("contract_service").get_contract(
                    contract_name=contract_name,
                    version=version,
                    allow_inactive=self._system_resources_config.allow_inactive_resources
                )
                self._cached_contracts[contract_name] = contract

    def get_required_prompt_names(self):
        """Возвращает список имен промптов, необходимых для инструмента"""
        # По умолчанию возвращает пустой список, может быть переопределен в дочерних классах
        return []

    def get_required_contract_names(self):
        """Возвращает список имен контрактов, необходимых для инструмента"""
        # По умолчанию возвращает пустой список, может быть переопределен в дочерних классах
        return []

    async def _load_tool_prompts(self):
        """Загрузка промптов, специфичных для инструмента"""
        # По умолчанию не загружаем ничего, может быть переопределен в дочерних классах
        pass

    async def _load_tool_contracts(self):
        """Загрузка контрактов, специфичных для инструмента"""
        # По умолчанию не загружаем ничего, может быть переопределен в дочерних классах
        pass

    def get_prompt(self, capability_name: str) -> str:
        """Получение промпта ТОЛЬКО из изолированного кэша"""
        if capability_name not in self._cached_prompts:
            raise RuntimeError(
                f"Промпт для capability '{capability_name}' не загружен в инструмент '{self.name}'. "
                f"Возможно, не указана версия в component_config.prompt_versions."
            )
        return self._cached_prompts[capability_name]

    def get_input_contract(self, capability_name: str) -> Dict:
        """Получение входящего контракта ТОЛЬКО из кэша"""
        if capability_name not in self._cached_input_contracts:
            raise RuntimeError(
                f"Входящий контракт для capability '{capability_name}' не загружен в инструмент '{self.name}'. "
                f"Возможно, не указана версия в component_config.input_contract_versions."
            )
        return self._cached_input_contracts[capability_name]

    def get_output_contract(self, capability_name: str) -> Dict:
        """Получение исходящего контракта ТОЛЬКО из кэша"""
        if capability_name not in self._cached_output_contracts:
            raise RuntimeError(
                f"Исходящий контракт для capability '{capability_name}' не загружен в инструмент '{self.name}'. "
                f"Возможно, не указана версия в component_config.output_contract_versions."
            )
        return self._cached_output_contracts[capability_name]

    def get_contract(self, contract_name: str) -> Any:
        """Получение контракта из кэша (для обратной совместимости)"""
        # Проверяем сначала в старом кэше для обратной совместимости
        if contract_name in self._cached_contracts:
            return self._cached_contracts[contract_name]
        
        # Если не найден, пробуем найти в новых кэшах
        # Разделяем имя контракта на capability_name и направление
        parts = contract_name.split('.')
        if len(parts) >= 3:
            direction = parts[-1]  # последняя часть - направление
            capability_name = '.'.join(parts[:-1])  # всё остальное - имя capability
            
            if direction == "input":
                return self.get_input_contract(capability_name)
            elif direction == "output":
                return self.get_output_contract(capability_name)
        
        # Если не найден ни в одном кэше
        raise RuntimeError(
            f"Контракт '{contract_name}' не загружен в инструменте '{self.name}'."
        )

    # Абстрактные методы, которые должны быть реализованы в дочерних классах
    @abstractmethod
    async def initialize(self) -> bool:
        """Стандартный метод инициализации (может быть переопределен)"""
        pass

    @abstractmethod
    async def execute(self, input_data: ToolInput) -> ToolOutput:
        """Выполнение инструмента"""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Завершение работы инструмента"""
        pass