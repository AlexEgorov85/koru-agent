"""
Единый базовый класс для всех компонентов (навыков, инструментов, сервисов).

АРХИТЕКТУРНЫЕ ГАРАНТИИ:
- Предзагрузка → кэш → выполнение без обращений к хранилищу
- Четкое разделение ответственностей: декларация ≠ данные ≠ реализация
- Обязательная инициализация через AppConfig
- Изолированные кэши для каждого экземпляра
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from core.config.app_config import AppConfig
from core.models.capability import Capability


class BaseComponent(ABC):
    """
    Единый базовый класс для всех компонентов (навыков, инструментов, сервисов).
    Гарантирует: предзагрузка → кэш → выполнение без обращений к хранилищу.
    """

    def __init__(self, name: str, application_context: 'ApplicationContext', app_config: Any):
        # Проверяем, что app_config не None
        # ComponentConfig может быть "истинным" значением даже если все поля пустые
        if app_config is None:
            raise ValueError(
                f"Компонент '{name}' требует полную конфигурацию. "
                "Конфигурация не может быть None."
            )
        self.name = name
        self.application_context = application_context
        self.app_config = app_config  # Единая конфигурация приложения (может быть AppConfig или ComponentConfig)

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
            prompt_service = self.application_context.get_resource("prompt_service")
            
            # Получаем версии промптов с учетом разных форматов конфигурации
            if hasattr(self.app_config, 'prompt_versions'):
                # Это AppConfig формат
                prompt_versions = self.app_config.prompt_versions
            elif hasattr(self.app_config, 'prompt_versions'):
                # Это ComponentConfig формат
                prompt_versions = self.app_config.prompt_versions
            else:
                # Нет информации о версиях промптов
                prompt_versions = {}
            
            if prompt_service and prompt_versions:
                # Создаем временный объект, совместимый с preload_prompts
                temp_config = self._create_temp_config_for_preload(prompt_versions)
                await prompt_service.preload_prompts(temp_config)
                for cap_name in prompt_versions:
                    self._cached_prompts[cap_name] = prompt_service.get_prompt_from_cache(cap_name)

            # 2. Загрузка контрактов
            contract_service = self.application_context.get_resource("contract_service")
            
            # Получаем версии контрактов с учетом разных форматов конфигурации
            if hasattr(self.app_config, 'input_contract_versions') and hasattr(self.app_config, 'output_contract_versions'):
                # Это ComponentConfig формат
                input_contract_versions = self.app_config.input_contract_versions
                output_contract_versions = self.app_config.output_contract_versions
            elif hasattr(self.app_config, 'contract_versions'):
                # Это AppConfig формат, разделяем на входные и выходные
                all_contracts = self.app_config.contract_versions
                input_contract_versions = {}
                output_contract_versions = {}
                
                for capability, version in all_contracts.items():
                    if "input" in capability.lower():
                        input_contract_versions[capability] = version
                    elif "output" in capability.lower():
                        output_contract_versions[capability] = version
                    else:
                        # Если не указан тип, добавляем и туда и туда
                        input_contract_versions[capability] = version
                        output_contract_versions[capability] = version
            else:
                # Нет информации о контрактах
                input_contract_versions = {}
                output_contract_versions = {}
            
            if contract_service and input_contract_versions and output_contract_versions:
                # Создаем временный объект, совместимый с preload_contracts
                temp_config = self._create_temp_config_for_contracts(
                    input_contract_versions,
                    output_contract_versions
                )
                await contract_service.preload_contracts(temp_config)
                for cap_name in input_contract_versions:
                    self._cached_input_contracts[cap_name] = contract_service.get_contract_schema_from_cache(cap_name, direction="input")
                for cap_name in output_contract_versions:
                    self._cached_output_contracts[cap_name] = contract_service.get_contract_schema_from_cache(cap_name, direction="output")

        except Exception as e:
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибка в BaseComponent.initialize для {self.name}: {e}")
            return False

        # Устанавливаем флаг инициализации
        self._initialized = True
        logger.info(f"BaseComponent.initialize: {self.name} - _initialized flag set to: {self._initialized}")
        return True

    def _create_temp_config_for_preload(self, prompt_versions: Dict[str, str]):
        """
        Создание временного объекта конфигурации для предзагрузки промптов.
        Используется для обратной совместимости с существующими сервисами.
        """
        # Создаем объект, совместимый с preload_prompts
        # Используем ComponentConfig для обратной совместимости
        from core.config.component_config import ComponentConfig
        return ComponentConfig(
            variant_id=f"temp_{self.name}",
            prompt_versions=prompt_versions,
            input_contract_versions={},
            output_contract_versions={},
            side_effects_enabled=getattr(self.app_config, 'side_effects_enabled', True),
            detailed_metrics=getattr(self.app_config, 'detailed_metrics', False)
        )

    def _create_temp_config_for_contracts(self, input_contract_versions: Dict[str, str], output_contract_versions: Dict[str, str]):
        """
        Создание временного объекта конфигурации для предзагрузки контрактов.
        Используется для обратной совместимости с существующими сервисами.
        """
        # Создаем объект, совместимый с preload_contracts
        # Используем ComponentConfig для обратной совместимости
        from core.config.component_config import ComponentConfig
        return ComponentConfig(
            variant_id=f"temp_{self.name}",
            prompt_versions={},
            input_contract_versions=input_contract_versions,
            output_contract_versions=output_contract_versions,
            side_effects_enabled=getattr(self.app_config, 'side_effects_enabled', True),
            detailed_metrics=getattr(self.app_config, 'detailed_metrics', False)
        )

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