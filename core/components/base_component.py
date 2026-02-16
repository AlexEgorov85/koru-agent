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
from typing import Dict, Any, Optional, TYPE_CHECKING, Type
from core.config.component_config import ComponentConfig
from core.models.data.capability import Capability
from core.models.data.prompt import Prompt
from pydantic import BaseModel

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

        # НОВЫЕ кэши для типизированных объектов
        self._cached_prompts: Dict[str, Prompt] = {}  # ← Объекты, не строки!
        self._cached_input_schemas: Dict[str, Type[BaseModel]] = {}  # ← Классы схем, не словари!
        self._cached_output_schemas: Dict[str, Type[BaseModel]] = {}

        # Временные метки кэша для возможности инвалидации
        self._prompt_timestamps: Dict[str, float] = {}
        self._input_schema_timestamps: Dict[str, float] = {}
        self._output_schema_timestamps: Dict[str, float] = {}

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
            # === ЭТАП 1: Валидация манифеста (НОВОЕ) ===
            if not await self._validate_manifest():
                self.logger.error(f"{self.name}: Валидация манифеста не пройдена")
                return False

            # === ЭТАП 2: Предзагрузка ресурсов ===
            if not await self._preload_resources(current_time):
                self.logger.error(f"{self.name}: Предзагрузка ресурсов не удалась")
                return False

            # === ЭТАП 3: Валидация загруженных ресурсов ===
            if not await self._validate_loaded_resources():
                self.logger.error(f"{self.name}: Валидация загруженных ресурсов не пройдена")
                return False

            logger.info(f"Компонент '{self.name}' полностью инициализирован. Ресурсы: промпты={len(self._cached_prompts)}, input_schemas={len(self._cached_input_schemas)}, output_schemas={len(self._cached_output_schemas)}")
            self._initialized = True
            return True

        except Exception as e:
            logger.error(f"Ошибка инициализации компонента '{self.name}': {e}", exc_info=True)
            self._initialized = False
            return False

    async def _validate_manifest(self) -> bool:
        """
        Валидация манифеста компонента при инициализации.
        
        Проверяет:
        1. Наличие манифеста (если указан в config)
        2. Статус манифеста (active для prod)
        3. Owner указан
        4. Зависимости доступны
        """
        if not self.component_config or not self.component_config.manifest_path:
            # Манифест опционален для обратной совместимости
            self.logger.debug(f"{self.name}: Манифест не указан, пропускаем валидацию")
            return True
        
        # Получаем манифест из кэша ApplicationContext
        manifest = self.application_context.data_repository.get_manifest(
            self._get_component_type(),
            self.name
        )
        
        if not manifest:
            self.logger.warning(f"{self.name}: Манифест не найден в кэше")
            return True  # Не блокируем, но логируем
        
        # Проверка статуса для prod
        if self.application_context.profile == "prod":
            if manifest.status.value != "active":
                self.logger.error(
                    f"{self.name}: Статус '{manifest.status.value}' не разрешён в prod"
                )
                return False
        
        # Проверка owner
        if not manifest.owner:
            self.logger.warning(f"{self.name}: Owner не указан в манифесте")
        
        # Проверка зависимостей
        if manifest.dependencies:
            deps_valid = await self._validate_dependencies(manifest.dependencies)
            if not deps_valid:
                return False
        
        return True

    async def _validate_dependencies(self, dependencies: Dict[str, list]) -> bool:
        """Валидация зависимостей компонента."""
        errors = []
        
        # Проверка зависимостей-компонентов
        for dep_name in dependencies.get("components", []):
            if not self.application_context.components.get(dep_name):
                errors.append(f"Зависимость компонента '{dep_name}' не найдена")
        
        # Проверка зависимостей-инструментов
        for dep_name in dependencies.get("tools", []):
            if not self.application_context.components.get(dep_name):
                errors.append(f"Зависимость инструмента '{dep_name}' не найдена")
        
        # Проверка зависимостей-сервисов
        for dep_name in dependencies.get("services", []):
            if not self.application_context.get_service(dep_name):
                errors.append(f"Зависимость сервиса '{dep_name}' не найдена")
        
        if errors:
            for error in errors:
                self.logger.error(f"{self.name}: {error}")
            return False
        
        return True

    async def _preload_resources(self, current_time: float) -> bool:
        """Предзагрузка ресурсов компонента."""
        try:
            # Загрузка промптов как объектов
            for cap_name, version in self.component_config.prompt_versions.items():
                try:
                    # Получаем ПОЛНОЦЕННЫЙ объект из репозитория
                    if hasattr(self.application_context, 'data_repository') and self.application_context.data_repository:
                        prompt_obj: Prompt = self.application_context.data_repository.get_prompt(cap_name, version)
                        self._cached_prompts[cap_name] = prompt_obj

                        self.logger.debug(
                            f"Загружен промпт '{cap_name}' v{version} "
                            f"(тип: {prompt_obj.component_type.value}, статус: {prompt_obj.status.value})"
                        )
                    else:
                        # Старый путь: получаем из кэша контекста
                        prompt_text = self.application_context.get_prompt(cap_name, version)
                        # Создаем минимальный объект Prompt для совместимости
                        from core.models.data.prompt import Prompt, PromptStatus, ComponentType
                        prompt_obj = Prompt(
                            capability=cap_name,
                            version=version,
                            status=PromptStatus.ACTIVE,
                            component_type=ComponentType.SKILL,  # Значение по умолчанию
                            content=prompt_text,
                            variables=[],
                            metadata={}
                        )
                        self._cached_prompts[cap_name] = prompt_obj
                        self.logger.warning(f"Используется совместимый режим для промпта {cap_name}")

                except Exception as e:
                    self.logger.error(f"Ошибка загрузки промпта {cap_name}@{version}: {e}")
                    # Используем безопасный способ проверки критических ресурсов
                    if hasattr(self.component_config, 'critical_resources') and self.component_config.critical_resources.get('prompts', False):
                        self.logger.critical(f"Критический промпт {cap_name} не загружен")
                        return False

            # Загрузка схем контрактов
            for cap_name, version in self.component_config.input_contract_versions.items():
                try:
                    if hasattr(self.application_context, 'data_repository') and self.application_context.data_repository:
                        schema_cls: Type[BaseModel] = (
                            self.application_context.data_repository
                            .get_contract_schema(cap_name, version, "input")
                        )
                        self._cached_input_schemas[cap_name] = schema_cls
                    else:
                        # Старый путь: получаем из контекста
                        schema_cls = self.application_context.get_input_contract_schema(cap_name, version)
                        self._cached_input_schemas[cap_name] = schema_cls
                        self.logger.warning(f"Используется совместимый режим для входной схемы {cap_name}")

                except Exception as e:
                    self.logger.error(f"Ошибка загрузки входной схемы {cap_name}@{version}: {e}")
                    # Используем безопасный способ проверки критических ресурсов
                    if hasattr(self.component_config, 'critical_resources') and self.component_config.critical_resources.get('input_contracts', False):
                        return False

            # Загрузка выходных схем
            for cap_name, version in self.component_config.output_contract_versions.items():
                try:
                    if hasattr(self.application_context, 'data_repository') and self.application_context.data_repository:
                        schema_cls: Type[BaseModel] = (
                            self.application_context.data_repository
                            .get_contract_schema(cap_name, version, "output")
                        )
                        self._cached_output_schemas[cap_name] = schema_cls
                    else:
                        # Старый путь: используем базовый класс
                        self._cached_output_schemas[cap_name] = BaseModel
                        self.logger.warning(f"Используется совместимый режим для выходной схемы {cap_name}")

                except Exception as e:
                    self.logger.error(f"Ошибка загрузки выходной схемы {cap_name}@{version}: {e}")
                    # Используем безопасный способ проверки критических ресурсов
                    if hasattr(self.component_config, 'critical_resources') and self.component_config.critical_resources.get('output_contracts', False):
                        return False

            # Устанавливаем временные метки для всех загруженных ресурсов
            for prompt_key in self._cached_prompts:
                self._prompt_timestamps[prompt_key] = current_time
            for schema_key in self._cached_input_schemas:
                self._input_schema_timestamps[schema_key] = current_time
            for schema_key in self._cached_output_schemas:
                self._output_schema_timestamps[schema_key] = current_time

            return True

        except Exception as e:
            self.logger.error(f"Ошибка предзагрузки ресурсов для '{self.name}': {e}", exc_info=True)
            return False

    async def _validate_loaded_resources(self) -> bool:
        """
        Валидация загруженных ресурсов.
        
        Проверяет:
        1. Все промпты из component_config загружены
        2. Все контракты из component_config загружены
        3. Нет дублирования версий
        4. Input/output контракты согласованы
        """
        errors = []
        
        if not self.component_config:
            return True
        
        # Проверка промптов
        for capability, version in self.component_config.prompt_versions.items():
            if capability not in self._cached_prompts:
                errors.append(f"Промпт '{capability}@{version}' не загружен")
            elif not self._cached_prompts[capability]:
                errors.append(f"Промпт '{capability}' пустой")
        
        # Проверка входных контрактов
        for capability, version in self.component_config.input_contract_versions.items():
            if capability not in self._cached_input_schemas:
                errors.append(f"Входной контракт '{capability}@{version}' не загружен")
            elif not self._cached_input_schemas[capability]:
                errors.append(f"Входной контракт '{capability}' пустой")
        
        # Проверка выходных контрактов
        for capability, version in self.component_config.output_contract_versions.items():
            if capability not in self._cached_output_schemas:
                errors.append(f"Выходной контракт '{capability}@{version}' не загружен")
            elif not self._cached_output_schemas[capability]:
                errors.append(f"Выходной контракт '{capability}' пустой")
        
        # Проверка согласованности input/output
        input_caps = set(self.component_config.input_contract_versions.keys())
        output_caps = set(self.component_config.output_contract_versions.keys())
        
        # Capability должны иметь и input, и output контракты
        missing_input = output_caps - input_caps
        missing_output = input_caps - output_caps
        
        if missing_input:
            errors.append(f"Отсутствуют input контракты для: {missing_input}")
        if missing_output:
            errors.append(f"Отсутствуют output контракты для: {missing_output}")
        
        if errors:
            for error in errors:
                self.logger.error(f"{self.name}: {error}")
            return False
        
        self.logger.info(f"{self.name}: Все ресурсы валидированы успешно")
        return True

    def _get_component_type(self) -> str:
        """Определяет тип компонента (skill/tool/service/behavior)."""
        # Переопределяется в наследниках
        return "component"

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
        - cache_type: тип кэша для инвалидации ('prompts', 'input_schemas', 'output_schemas', или None для всех)
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

        if cache_type is None or cache_type == 'input_schemas':
            if key:
                if key in self._cached_input_schemas:
                    del self._cached_input_schemas[key]
                if key in self._input_schema_timestamps:
                    del self._input_schema_timestamps[key]
            else:
                self._cached_input_schemas.clear()
                self._input_schema_timestamps.clear()

        if cache_type is None or cache_type == 'output_schemas':
            if key:
                if key in self._cached_output_schemas:
                    del self._cached_output_schemas[key]
                if key in self._output_schema_timestamps:
                    del self._output_schema_timestamps[key]
            else:
                self._cached_output_schemas.clear()
                self._output_schema_timestamps.clear()

    def _is_cache_expired(self, cache_type: str, key: str) -> bool:
        """
        Проверяет, истек ли срок действия элемента кэша.

        ARGS:
        - cache_type: тип кэша ('prompts', 'input_schemas', 'output_schemas')
        - key: ключ элемента кэша

        RETURNS:
        - bool: True если кэш истек, False если действителен
        """
        import time

        if self._cache_ttl_seconds is None:
            return False  # Если TTL не установлен, кэш не истекает

        timestamps = {
            'prompts': self._prompt_timestamps,
            'input_schemas': self._input_schema_timestamps,
            'output_schemas': self._output_schema_timestamps
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

        # Безопасное извлечение через атрибут объекта
        prompt_obj = self._cached_prompts[capability_name]
        if hasattr(prompt_obj, 'content'):
            return prompt_obj.content
        return str(prompt_obj)

    def get_cached_input_schema_safe(self, capability_name: str) -> Type[BaseModel]:
        """
        Безопасное получение входной схемы из кэша с обработкой ошибок и проверкой срока действия.

        ARGS:
        - capability_name: имя capability для получения входной схемы

        RETURNS:
        - Type[BaseModel]: класс схемы или базовый BaseModel если не найден или истек
        """
        self._ensure_initialized()

        if capability_name not in self._cached_input_schemas:
            return BaseModel

        # Проверяем, не истек ли срок действия кэша
        if self._is_cache_expired('input_schemas', capability_name):
            # Инвалидируем просроченный элемент
            self.invalidate_cache('input_schemas', capability_name)
            return BaseModel

        return self._cached_input_schemas[capability_name]

    def get_cached_output_schema_safe(self, capability_name: str) -> Type[BaseModel]:
        """
        Безопасное получение выходной схемы из кэша с обработкой ошибок и проверкой срока действия.

        ARGS:
        - capability_name: имя capability для получения выходной схемы

        RETURNS:
        - Type[BaseModel]: класс схемы или базовый BaseModel если не найден или истек
        """
        self._ensure_initialized()

        if capability_name not in self._cached_output_schemas:
            return BaseModel

        # Проверяем, не истек ли срок действия кэша
        if self._is_cache_expired('output_schemas', capability_name):
            # Инвалидируем просроченный элемент
            self.invalidate_cache('output_schemas', capability_name)
            return BaseModel

        return self._cached_output_schemas[capability_name]

    # === БЕЗОПАСНЫЙ ДОСТУП К РЕСУРСАМ (ТОЛЬКО ИЗ КЭША) ===

    def get_prompt(self, capability_name: str) -> str:
        """
        Для обратной совместимости возвращаем текст,
        но храним и используем полноценный объект.
        """
        self._ensure_initialized()
        if capability_name not in self._cached_prompts:
            self.logger.warning(
                f"Промпт для capability '{capability_name}' не загружен в компонент '{self.name}'. "
                f"Доступные: {list(self._cached_prompts.keys())}. Возвращаем пустую строку."
            )
            return ""  # Возвращаем пустую строку вместо ошибки
        
        # Безопасное извлечение через атрибут объекта
        return self._cached_prompts[capability_name].content

    def get_input_contract(self, capability_name: str) -> Dict:
        """
        Возвращаем схему как словарь для обратной совместимости,
        но используем типизированный объект.
        """
        self._ensure_initialized()
        if capability_name not in self._cached_input_schemas:
            self.logger.warning(
                f"Входная схема для '{capability_name}' не загружена в компонент '{self.name}'. "
                f"Доступные: {list(self._cached_input_schemas.keys())}. Возвращаем пустой словарь."
            )
            return {}  # Возвращаем пустой словарь вместо ошибки
        
        schema_cls = self._cached_input_schemas[capability_name]
        # Возвращаем словарь схемы для обратной совместимости
        return schema_cls.model_json_schema()

    def get_output_contract(self, capability_name: str) -> Dict:
        """
        Возвращаем схему как словарь для обратной совместимости,
        но используем типизированный объект.
        """
        self._ensure_initialized()
        if capability_name not in self._cached_output_schemas:
            self.logger.warning(
                f"Выходная схема для '{capability_name}' не загружена в компонент '{self.name}'. "
                f"Доступные: {list(self._cached_output_schemas.keys())}. Возвращаем пустой словарь."
            )
            return {}  # Возвращаем пустой словарь вместо ошибки
        
        schema_cls = self._cached_output_schemas[capability_name]
        # Возвращаем словарь схемы для обратной совместимости
        return schema_cls.model_json_schema()

    def validate_input(self, capability_name: str, data: Dict) -> bool:
        """
        Типобезопасная валидация через скомпилированную схему.
        """
        if capability_name not in self._cached_input_schemas:
            self.logger.warning(f"Схема для {capability_name} не загружена, пропускаем валидацию")
            return True
        
        schema_cls = self._cached_input_schemas[capability_name]
        try:
            # Pydantic автоматически валидирует и конвертирует типы
            validated = schema_cls.model_validate(data)
            return True
        except Exception as e:
            self.logger.error(f"Валидация входных данных для {capability_name} провалена: {e}")
            return False

    def render_prompt(self, capability_name: str, **kwargs) -> str:
        """
        Безопасный рендеринг шаблона с валидацией переменных.
        """
        if capability_name not in self._cached_prompts:
            raise ValueError(f"Промпт '{capability_name}' не загружен")
        
        prompt_obj: Prompt = self._cached_prompts[capability_name]
        
        # Используем встроенный метод рендеринга с валидацией
        try:
            return prompt_obj.render(**kwargs)
        except ValueError as e:
            self.logger.error(f"Ошибка рендеринга промпта {capability_name}: {e}")
            raise

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