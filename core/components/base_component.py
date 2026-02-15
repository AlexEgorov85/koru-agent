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

    async def initialize(self) -> bool:
        """
        ЕДИНСТВЕННЫЙ метод инициализации — получает ресурсы ИЗ КОНФИГУРАЦИИ,
        НЕ обращаясь к сервисам напрямую.
        
        ВАЖНО: Все ресурсы уже загружены в component_config.application_context
        на уровне ApplicationContext.initialize().
        """
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"BaseComponent.initialize: начало инициализации для {self.name}")

        try:
            # 1. Копируем промпты ИЗ КОНФИГУРАЦИИ (не из сервиса!)
            if hasattr(self.component_config, 'resolved_prompts'):
                self._cached_prompts = self.component_config.resolved_prompts.copy()
                logger.debug(f"Загружено {len(self._cached_prompts)} промптов для {self.name}")
            
            # 2. Копируем контракты ИЗ КОНФИГУРАЦИИ
            if hasattr(self.component_config, 'resolved_input_contracts'):
                self._cached_input_contracts = self.component_config.resolved_input_contracts.copy()
                logger.debug(f"Загружено {len(self._cached_input_contracts)} input-контрактов для {self.name}")
            
            if hasattr(self.component_config, 'resolved_output_contracts'):
                self._cached_output_contracts = self.component_config.resolved_output_contracts.copy()
                logger.debug(f"Загружено {len(self._cached_output_contracts)} output-контрактов для {self.name}")
            
            self._initialized = True
            logger.info(f"Компонент '{self.name}' инициализирован. Ресурсы: промпты={len(self._cached_prompts)}, input={len(self._cached_input_contracts)}, output={len(self._cached_output_contracts)}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка инициализации компонента '{self.name}': {e}", exc_info=True)
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
                f"Возвращаем пустой словарь."
            )
            return {}  # Возвращаем пустой словарь вместо ошибки
        return self._cached_input_contracts[capability_name]

    def get_output_contract(self, capability_name: str) -> Dict:
        self._ensure_initialized()
        if capability_name not in self._cached_output_contracts:
            self.logger.warning(
                f"Выходной контракт для '{capability_name}' не загружен в компонент '{self.name}'. "
                f"Возвращаем пустой словарь."
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