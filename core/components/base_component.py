"""
Единый базовый класс для всех компонентов (навыков, инструментов, сервисов).

АРХИТЕКТУРНЫЕ ГАРАНТИИ:
- Предзагрузка → кэш → выполнение без обращений к хранилищу
- Четкое разделение ответственностей: декларация ≠ данные ≠ реализация
- Обязательная инициализация через ComponentConfig
- Изолированные кэши для каждого экземпляра
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from core.config.component_config import ComponentConfig
from core.system_context.base_system_contex import BaseSystemContext
from models.capability import Capability


class BaseComponent(ABC):
    """
    Единый базовый класс для всех компонентов (навыков, инструментов, сервисов).
    Гарантирует: предзагрузка → кэш → выполнение без обращений к хранилищу.
    """
    
    def __init__(self, name: str, system_context: BaseSystemContext, component_config: ComponentConfig):
        if not component_config or not hasattr(component_config, 'variant_id'):
            raise ValueError(
                f"Компонент '{name}' требует полную конфигурацию через ComponentConfig. "
                "Legacy-режим (agent_config) больше не поддерживается."
            )
        self.name = name
        self.system_context = system_context
        self.component_config = component_config

        # Инициализация флага инициализации
        self._initialized = False

        # Изолированные кэши (инициализируются пустыми)
        self._cached_prompts: Dict[str, str] = {}
        self._cached_input_contracts: Dict[str, Dict] = {}
        self._cached_output_contracts: Dict[str, Dict] = {}
    
    async def initialize(self) -> bool:
        """
        ЕДИНСТВЕННЫЙ метод инициализации — предзагрузка ВСЕХ ресурсов.

        RETURNS:
        - bool: True если инициализация прошла успешно
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"BaseComponent.initialize: начало инициализации для {self.name}")
        
        try:
            # 1. Загрузка промптов
            prompt_service = self.system_context.get_resource("prompt_service")
            if prompt_service and hasattr(self.component_config, 'prompt_versions'):
                await prompt_service.preload_prompts(self.component_config)
                for cap_name in self.component_config.prompt_versions:
                    self._cached_prompts[cap_name] = prompt_service.get_prompt_from_cache(cap_name)

            # 2. Загрузка контрактов
            contract_service = self.system_context.get_resource("contract_service")
            if contract_service and hasattr(self.component_config, 'input_contract_versions') and hasattr(self.component_config, 'output_contract_versions'):
                await contract_service.preload_contracts(self.component_config)
                for cap_name in self.component_config.input_contract_versions:
                    self._cached_input_contracts[cap_name] = contract_service.get_contract_schema_from_cache(cap_name, direction="input")
                for cap_name in self.component_config.output_contract_versions:
                    self._cached_output_contracts[cap_name] = contract_service.get_contract_schema_from_cache(cap_name, direction="output")

        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибка в BaseComponent.initialize для {self.name}: {e}")
            return False

        # Устанавливаем флаг инициализации
        self._initialized = True
        logger.info(f"BaseComponent.initialize: {self.name} - _initialized flag set to: {self._initialized}")
        return True
    
    # Безопасные методы получения из кэша
    def get_prompt(self, capability_name: str) -> str:
        """
        Получение промпта ТОЛЬКО из изолированного кэша.
        
        ARGS:
        - capability_name: имя capability для получения промпта
        
        RETURNS:
        - str: текст промпта из кэша
        
        RAISES:
        - RuntimeError: если промпт не загружен в кэш
        """
        if capability_name not in self._cached_prompts:
            raise RuntimeError(f"Промпт для '{capability_name}' не загружен в компонент '{self.name}'")
        return self._cached_prompts[capability_name]
    
    def get_input_contract(self, capability_name: str) -> Dict:
        """
        Получение входящего контракта ТОЛЬКО из кэша.
        
        ARGS:
        - capability_name: имя capability для получения входящего контракта
        
        RETURNS:
        - Dict: схема входящего контракта из кэша
        
        RAISES:
        - RuntimeError: если входящий контракт не загружен в кэш
        """
        if capability_name not in self._cached_input_contracts:
            raise RuntimeError(f"Входящий контракт для '{capability_name}' не загружен в компонент '{self.name}'")
        return self._cached_input_contracts[capability_name]
    
    def get_output_contract(self, capability_name: str) -> Dict:
        """
        Получение исходящего контракта ТОЛЬКО из кэша.
        
        ARGS:
        - capability_name: имя capability для получения исходящего контракта
        
        RETURNS:
        - Dict: схема исходящего контракта из кэша
        
        RAISES:
        - RuntimeError: если исходящий контракт не загружен в кэш
        """
        if capability_name not in self._cached_output_contracts:
            raise RuntimeError(f"Исходящий контракт для '{capability_name}' не загружен в компонент '{self.name}'")
        return self._cached_output_contracts[capability_name]
    
    @abstractmethod
    async def execute(self, capability: Capability, parameters: Dict[str, Any], context: Any):
        """
        Абстрактный метод выполнения компонента.
        
        ARGS:
        - capability: capability для выполнения
        - parameters: параметры выполнения
        - context: контекст выполнения
        """
        pass