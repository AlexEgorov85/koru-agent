"""
Единый базовый класс для всех компонентов (навыков, инструментов, сервисов).

АРХИТЕКТУРНЫЕ ГАРАНТИИ:
- Предзагрузка → кэш → выполнение без обращений к хранилищу
- Четкое разделение ответственностей: декларация ≠ данные ≠ реализация
- Обязательная инициализация через ComponentConfig
- Изолированные кэши для каждого экземпляра
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TYPE_CHECKING
from core.config.component_config import ComponentConfig
from models.capability import Capability

if TYPE_CHECKING:
    from core.application.context.application_context import ApplicationContext


class BaseComponent(ABC):
    """
    Единый базовый класс для всех компонентов (навыков, инструментов, сервисов).
    Гарантирует: предзагрузка → кэш → выполнение без обращений к хранилищу.
    """
    
    def __init__(self, name: str, application_context: 'ApplicationContext', component_config: ComponentConfig):
        if not component_config or not hasattr(component_config, 'variant_id'):
            raise ValueError(
                f"Компонент '{name}' требует полную конфигурацию через ComponentConfig. "
                "Legacy-режим (agent_config) больше не поддерживается."
            )
        self.name = name
        self.application_context = application_context
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
            # 1. Загрузка промптов ТОЛЬКО если они есть в конфигурации
            prompt_service = self.application_context.get_resource("prompt_service")
            
            if (hasattr(self.component_config, 'prompt_versions') and 
                self.component_config.prompt_versions and 
                prompt_service):
                
                # Используем методы изолированного сервиса промптов для получения нужных версий
                for cap_name, version in self.component_config.prompt_versions.items():
                    try:
                        # Получаем промпт через изолированный сервис
                        prompt_text = await prompt_service.get_prompt(capability_name=cap_name, version=version)
                        self._cached_prompts[cap_name] = prompt_text
                        logger.debug(f"Промпт {cap_name}@{version} загружен для {self.name}")
                    except Exception as e:
                        logger.warning(
                            f"Промпт {cap_name} не найден или ошибка загрузки для компонента {self.name}: {e}. "
                            f"Пропускаем. Компонент может работать без этого промпта."
                        )
                        # Не падаем - компонент может работать без некоторых промптов

            # 2. Загрузка контрактов (аналогично - только если есть в конфигурации)
            contract_service = self.application_context.get_resource("contract_service")
            
            if contract_service and hasattr(self.component_config, 'input_contract_versions'):
                if self.component_config.input_contract_versions:
                    for cap_name, version in self.component_config.input_contract_versions.items():
                        try:
                            # Получаем входной контракт через изолированный сервис
                            input_contract = await contract_service.get_contract(
                                capability_name=cap_name, 
                                version=version, 
                                direction="input"
                            )
                            self._cached_input_contracts[cap_name] = input_contract
                            logger.debug(f"Входной контракт {cap_name}@{version} загружен для {self.name}")
                        except Exception as e:
                            logger.warning(
                                f"Входной контракт {cap_name} не найден или ошибка загрузки для компонента {self.name}: {e}. "
                                f"Пропускаем. Компонент может работать без этого контракта."
                            )

            if contract_service and hasattr(self.component_config, 'output_contract_versions'):
                if self.component_config.output_contract_versions:
                    for cap_name, version in self.component_config.output_contract_versions.items():
                        try:
                            # Получаем выходной контракт через изолированный сервис
                            output_contract = await contract_service.get_contract(
                                capability_name=cap_name, 
                                version=version, 
                                direction="output"
                            )
                            self._cached_output_contracts[cap_name] = output_contract
                            logger.debug(f"Выходной контракт {cap_name}@{version} загружен для {self.name}")
                        except Exception as e:
                            logger.warning(
                                f"Выходной контракт {cap_name} не найден или ошибка загрузки для компонента {self.name}: {e}. "
                                f"Пропускаем. Компонент может работать без этого контракта."
                            )

        except Exception as e:
            logger.error(f"Ошибка в BaseComponent.initialize для {self.name}: {e}", exc_info=True)
            # ВАЖНО: даже при ошибках устанавливаем _initialized = True для компонентов без промптов
            # Но возвращаем False, чтобы показать, что была ошибка
            self._initialized = True
            return False

        # Устанавливаем флаг инициализации ДАЖЕ если ресурсов нет
        self._initialized = True
        logger.info(f"BaseComponent.initialize: {self.name} успешно инициализирован")
        return True
    
    def _ensure_initialized(self):
        """
        Проверяет, что компонент инициализирован перед использованием.
        
        RAISES:
        - RuntimeError: если компонент не инициализирован
        """
        if not getattr(self, '_initialized', False):
            import inspect
            frame = inspect.currentframe().f_back
            caller_info = f"{frame.f_code.co_filename}:{frame.f_lineno} in {frame.f_code.co_name}()"
            raise RuntimeError(
                f"Компонент '{self.name}' не инициализирован. "
                f"Вызовите .initialize() перед использованием. "
                f"Вызван из: {caller_info}"
            )

    # Безопасные методы получения из кэша
    def get_prompt(self, capability_name: str) -> str:
        """
        Получение промпта ТОЛЬКО из изолированного кэша.

        ARGS:
        - capability_name: имя capability для получения промпта

        RETURNS:
        - str: текст промпта из кэша

        RAISES:
        - RuntimeError: если компонент не инициализирован или промпт не загружен в кэш
        """
        self._ensure_initialized()
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
        - RuntimeError: если компонент не инициализирован или входящий контракт не загружен в кэш
        """
        self._ensure_initialized()
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
        - RuntimeError: если компонент не инициализирован или исходящий контракт не загружен в кэш
        """
        self._ensure_initialized()
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