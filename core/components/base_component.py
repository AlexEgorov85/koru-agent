"""
Единый базовый класс для всех компонентов (навыков, инструментов, сервисов).

АРХИТЕКТУРНЫЕ ГАРАНТИИ:
- Предзагрузка → кэш → выполнение без обращений к хранилищу
- Четкое разделение ответственностей: декларация ≠ данные ≠ реализация
- Обязательная инициализация через ComponentConfig
- Изолированные кэши для каждого экземпляра
- Взаимодействие ТОЛЬКО через ActionExecutor
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TYPE_CHECKING
from core.config.component_config import ComponentConfig
from models.capability import Capability

if TYPE_CHECKING:
    from core.application.context.application_context import ApplicationContext
    from core.application.agent.components.executor import ActionExecutor


class BaseComponent(ABC):
    """
    БАЗОВЫЙ КЛАСС КОМПОНЕНТА С ПОЛНОЙ ИЗОЛЯЦИЕЙ.
    
    ГАРАНТИИ:
    - Никаких обращений к сервисам во время выполнения
    - Все ресурсы предзагружены ДО вызова execute()
    - Никаких прямых зависимостей от других компонентов
    - Взаимодействие ТОЛЬКО через ActionExecutor
    """

    def __init__(
        self, 
        name: str, 
        application_context: 'ApplicationContext', 
        component_config: ComponentConfig,
        executor: 'ActionExecutor'  # ← ЕДИНСТВЕННЫЙ способ взаимодействия
    ):
        if not component_config or not hasattr(component_config, 'variant_id'):
            raise ValueError(
                f"Компонент '{name}' требует полную конфигурацию через ComponentConfig. "
                "Legacy-режим (agent_config) больше не поддерживается."
            )
        self.name = name
        self.application_context = application_context
        self.component_config = component_config
        self.executor = executor  # ← Критически важно!
        
        # Инициализация флага инициализации
        self._initialized = False

        # Инициализация логгера
        import logging
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.name}")

        # Изолированные кэши (инициализируются пустыми)
        self._cached_prompts: Dict[str, str] = {}
        self._cached_input_contracts: Dict[str, Dict] = {}
        self._cached_output_contracts: Dict[str, Dict] = {}
        
        # Временные метки кэша для возможности инвалидации
        self._prompt_timestamps: Dict[str, float] = {}
        self._input_contract_timestamps: Dict[str, float] = {}
        self._output_contract_timestamps: Dict[str, float] = {}
        
        # TTL для элементов кэша (в секундах, None означает бессрочный кэш)
        self._cache_ttl_seconds = 3600  # 1 час по умолчанию

    async def initialize(self) -> bool:
        """
        ЕДИНСТВЕННЫЙ метод инициализации — получает ресурсы ИЗ КОНФИГУРАЦИИ,
        НЕ обращаясь к сервисам напрямую.

        ВАЖНО: Все ресурсы уже загружены в component_config.application_context
        на уровне ApplicationContext.initialize().
        """
        import logging
        import time
        logger = logging.getLogger(__name__)
        current_time = time.time()
        logger.info(f"BaseComponent.initialize: начало инициализации для {self.name}")

        try:
            # 1. Копируем промпты ИЗ КОНФИГУРАЦИИ (не из сервиса!)
            if hasattr(self.component_config, 'resolved_prompts'):
                self._cached_prompts = self.component_config.resolved_prompts.copy()
                # Устанавливаем временные метки для всех загруженных промтов
                for prompt_key in self._cached_prompts:
                    self._prompt_timestamps[prompt_key] = current_time
                logger.debug(f"Загружено {len(self._cached_prompts)} промптов для {self.name}")

            # 2. Копируем контракты ИЗ КОНФИГУРАЦИИ
            if hasattr(self.component_config, 'resolved_input_contracts'):
                self._cached_input_contracts = self.component_config.resolved_input_contracts.copy()
                # Устанавливаем временные метки для всех загруженных входных контрактов
                for contract_key in self._cached_input_contracts:
                    self._input_contract_timestamps[contract_key] = current_time
                logger.debug(f"Загружено {len(self._cached_input_contracts)} input-контрактов для {self.name}")

            if hasattr(self.component_config, 'resolved_output_contracts'):
                self._cached_output_contracts = self.component_config.resolved_output_contracts.copy()
                # Устанавливаем временные метки для всех загруженных выходных контрактов
                for contract_key in self._cached_output_contracts:
                    self._output_contract_timestamps[contract_key] = current_time
                logger.debug(f"Загружено {len(self._cached_output_contracts)} output-контрактов для {self.name}")

            # Проверяем, есть ли критические ресурсы, которые должны быть загружены
            # Если в конфигурации были определены версии ресурсов, но они не загружены, это ошибка
            has_missing_critical_resources = False
            
            # Проверяем промпты
            if hasattr(self.component_config, 'prompt_versions') and self.component_config.prompt_versions:
                for cap_name, version in self.component_config.prompt_versions.items():
                    if cap_name not in self._cached_prompts:
                        logger.warning(f"Критический промпт {cap_name}@{version} не загружен для компонента {self.name}")
                        has_missing_critical_resources = True
            
            # Проверяем входные контракты
            if hasattr(self.component_config, 'input_contract_versions') and self.component_config.input_contract_versions:
                for cap_name, version in self.component_config.input_contract_versions.items():
                    if cap_name not in self._cached_input_contracts:
                        logger.warning(f"Критический входной контракт {cap_name}@{version} не загружен для компонента {self.name}")
                        has_missing_critical_resources = True
            
            # Проверяем выходные контракты
            if hasattr(self.component_config, 'output_contract_versions') and self.component_config.output_contract_versions:
                for cap_name, version in self.component_config.output_contract_versions.items():
                    if cap_name not in self._cached_output_contracts:
                        logger.warning(f"Критический выходной контракт {cap_name}@{version} не загружен для компонента {self.name}")
                        has_missing_critical_resources = True

            # Устанавливаем флаг инициализации в зависимости от наличия критических ресурсов
            if has_missing_critical_resources:
                logger.warning(f"Компонент '{self.name}' инициализирован частично: отсутствуют критические ресурсы")
                self._initialized = False
                return False
            else:
                self._initialized = True
                logger.info(f"Компонент '{self.name}' полностью инициализирован. Ресурсы: промпты={len(self._cached_prompts)}, input={len(self._cached_input_contracts)}, output={len(self._cached_output_contracts)}")
                return True

        except Exception as e:
            logger.error(f"Ошибка инициализации компонента '{self.name}': {e}", exc_info=True)
            self._initialized = False
            return False

    def _ensure_initialized(self):
        """
        Проверяет, что компонент инициализирован перед использованием.

        RAISES:
        - RuntimeError: если компонент не инициализирован
        """
        if not self._initialized:
            raise RuntimeError(
                f"Компонент '{self.name}' не инициализирован. "
                f"Вызовите .initialize() перед использованием."
            )

    def invalidate_cache(self, cache_type: str = None, key: str = None):
        """
        Инвалидация кэша компонента.
        
        ARGS:
        - cache_type: тип кэша для инвалидации ('prompts', 'input_contracts', 'output_contracts', или None для всех)
        - key: конкретный ключ для инвалидации (или None для инвалидации всего типа кэша)
        """
        import time
        current_time = time.time()
        
        if cache_type is None or cache_type == 'prompts':
            if key:
                if key in self._cached_prompts:
                    del self._cached_prompts[key]
                if key in self._prompt_timestamps:
                    del self._prompt_timestamps[key]
            else:
                self._cached_prompts.clear()
                self._prompt_timestamps.clear()
        
        if cache_type is None or cache_type == 'input_contracts':
            if key:
                if key in self._cached_input_contracts:
                    del self._cached_input_contracts[key]
                if key in self._input_contract_timestamps:
                    del self._input_contract_timestamps[key]
            else:
                self._cached_input_contracts.clear()
                self._input_contract_timestamps.clear()
        
        if cache_type is None or cache_type == 'output_contracts':
            if key:
                if key in self._cached_output_contracts:
                    del self._cached_output_contracts[key]
                if key in self._output_contract_timestamps:
                    del self._output_contract_timestamps[key]
            else:
                self._cached_output_contracts.clear()
                self._output_contract_timestamps.clear()

    def _is_cache_expired(self, cache_type: str, key: str) -> bool:
        """
        Проверяет, истек ли срок действия элемента кэша.
        
        ARGS:
        - cache_type: тип кэша ('prompts', 'input_contracts', 'output_contracts')
        - key: ключ элемента кэша
        
        RETURNS:
        - bool: True если кэш истек, False если действителен
        """
        import time
        
        if self._cache_ttl_seconds is None:
            return False  # Если TTL не установлен, кэш не истекает
            
        timestamps = {
            'prompts': self._prompt_timestamps,
            'input_contracts': self._input_contract_timestamps,
            'output_contracts': self._output_contract_timestamps
        }.get(cache_type)
        
        if not timestamps or key not in timestamps:
            return True  # Если временная метка не найдена, считаем кэш просроченным
            
        return (time.time() - timestamps[key]) > self._cache_ttl_seconds

    def get_cached_prompt_safe(self, capability_name: str) -> str:
        """
        Безопасное получение промта из кэша с обработкой ошибок и проверкой срока действия.
        
        ARGS:
        - capability_name: имя capability для получения промта
        
        RETURNS:
        - str: текст промта или пустая строка если не найден или истек
        """
        self._ensure_initialized()
        
        if capability_name not in self._cached_prompts:
            return ""
        
        # Проверяем, не истек ли срок действия кэша
        if self._is_cache_expired('prompts', capability_name):
            # Инвалидируем просроченный элемент
            self.invalidate_cache('prompts', capability_name)
            return ""
        
        return self._cached_prompts[capability_name]

    def get_cached_input_contract_safe(self, capability_name: str) -> Dict:
        """
        Безопасное получение входного контракта из кэша с обработкой ошибок и проверкой срока действия.
        
        ARGS:
        - capability_name: имя capability для получения входного контракта
        
        RETURNS:
        - Dict: схема контракта или пустой словарь если не найден или истек
        """
        self._ensure_initialized()
        
        if capability_name not in self._cached_input_contracts:
            return {}
        
        # Проверяем, не истек ли срок действия кэша
        if self._is_cache_expired('input_contracts', capability_name):
            # Инвалидируем просроченный элемент
            self.invalidate_cache('input_contracts', capability_name)
            return {}
        
        return self._cached_input_contracts[capability_name]

    def get_cached_output_contract_safe(self, capability_name: str) -> Dict:
        """
        Безопасное получение выходного контракта из кэша с обработкой ошибок и проверкой срока действия.
        
        ARGS:
        - capability_name: имя capability для получения выходного контракта
        
        RETURNS:
        - Dict: схема контракта или пустой словарь если не найден или истек
        """
        self._ensure_initialized()
        
        if capability_name not in self._cached_output_contracts:
            return {}
        
        # Проверяем, не истек ли срок действия кэша
        if self._is_cache_expired('output_contracts', capability_name):
            # Инвалидируем просроченный элемент
            self.invalidate_cache('output_contracts', capability_name)
            return {}
        
        return self._cached_output_contracts[capability_name]

    # === БЕЗОПАСНЫЙ ДОСТУП К РЕСУРСАМ (ТОЛЬКО ИЗ КЭША) ===
    
    def get_prompt(self, capability_name: str) -> str:
        self._ensure_initialized()
        if capability_name not in self._cached_prompts:
            self.logger.warning(
                f"Промпт для capability '{capability_name}' не загружен в компонент '{self.name}'. "
                f"Доступные: {list(self._cached_prompts.keys())}. Возвращаем пустую строку."
            )
            return ""  # Возвращаем пустую строку вместо ошибки
        return self._cached_prompts[capability_name]

    def get_input_contract(self, capability_name: str) -> Dict:
        self._ensure_initialized()
        if capability_name not in self._cached_input_contracts:
            self.logger.warning(
                f"Входной контракт для '{capability_name}' не загружен в компонент '{self.name}'. "
                f"Доступные: {list(self._cached_input_contracts.keys())}. Возвращаем пустой словарь."
            )
            return {}  # Возвращаем пустой словарь вместо ошибки
        return self._cached_input_contracts[capability_name]

    def get_output_contract(self, capability_name: str) -> Dict:
        self._ensure_initialized()
        if capability_name not in self._cached_output_contracts:
            self.logger.warning(
                f"Выходной контракт для '{capability_name}' не загружен в компонент '{self.name}'. "
                f"Доступные: {list(self._cached_output_contracts.keys())}. Возвращаем пустой словарь."
            )
            return {}  # Возвращаем пустой словарь вместо ошибки
        return self._cached_output_contracts[capability_name]

    # === АБСТРАКТНЫЙ МЕТОД ВЫПОЛНЕНИЯ (БЕЗ ПРЯМЫХ ЗАВИСИМОСТЕЙ) ===
    
    @abstractmethod
    async def execute(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: 'ExecutionContext'
    ) -> 'ActionResult':
        """
        ЕДИНСТВЕННЫЙ метод выполнения логики компонента.
        
        ЗАПРЕЩЕНО:
        - Вызывать другие компоненты напрямую
        - Обращаться к сервисам (PromptService, ContractService)
        - Работать с файловой системой
        
        РАЗРЕШЕНО:
        - Использовать предзагруженные ресурсы из кэшей
        - Вызывать другие действия через self.executor.execute_action()
        - Валидировать входные/выходные данные через контракты из кэша
        """
        pass

    async def shutdown(self) -> None:
        """Корректное завершение работы компонента."""
        pass