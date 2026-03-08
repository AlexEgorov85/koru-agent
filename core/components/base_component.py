"""
Единый базовый класс для всех компонентов (навыков, инструментов, сервисов).

АРХИТЕКТУРНЫЕ ГАРАНТИИ:
- Предзагрузка → кэш → выполнение без обращений к хранилищу
- Четкое разделение ответственностей: декларация ≠ данные ≠ реализация
- Обязательная инициализация через ComponentConfig
- Изолированные кэши для каждого экземпляра
- Взаимодействие ТОЛЬКО через ActionExecutor
- Поддержка внедрения зависимостей (DI) через интерфейсы

ИНТЕГРИРОВАННОЕ ЛОГИРОВАНИЕ:
- BaseComponent наследует LogComponentMixin для универсального логирования
- Используйте self.log_start(), self.log_success(), self.log_error() для ручного логирования
- Или используйте декоратор @log_execution для автоматического логирования

ЖИЗНЕННЫЙ ЦИКЛ:
- Наследует LifecycleMixin для управления состояниями
- Состояния: CREATED → INITIALIZING → READY → SHUTDOWN (или FAILED)
"""
import asyncio
from abc import ABC
from typing import Dict, Any, Optional, TYPE_CHECKING, Type

from core.config.component_config import ComponentConfig
from core.models.data.capability import Capability
from core.models.data.prompt import Prompt
from core.models.enums.common_enums import ComponentType
from pydantic import BaseModel
from core.infrastructure.logging import EventBusLogger
from core.components.lifecycle import LifecycleMixin, ComponentState

# Интерфейсы для DI
from core.interfaces.database import DatabaseInterface
from core.interfaces.llm import LLMInterface
from core.interfaces.vector import VectorInterface
from core.interfaces.cache import CacheInterface
from core.interfaces.event_bus import EventBusInterface
from core.interfaces.prompt_storage import PromptStorageInterface
from core.interfaces.contract_storage import ContractStorageInterface
from core.interfaces.metrics_storage import MetricsStorageInterface
from core.interfaces.log_storage import LogStorageInterface

if TYPE_CHECKING:
    from core.application.context.application_context import ApplicationContext
    from core.application.agent.components.executor import ActionExecutor


class BaseComponent(LifecycleMixin, ABC):
    """
    БАЗОВЫЙ КЛАСС КОМПОНЕНТА С ПОЛНОЙ ИЗОЛЯЦИЕЙ И УНИВЕРСАЛЬНЫМ ЛОГИРОВАНИЕМ.

    АРХИТЕКТУРНЫЕ ГАРАНТИИ:
    - Никаких обращений к сервисам во время выполнения
    - Все ресурсы предзагружены ДО вызова execute()
    - Никаких прямых зависимостей от других компонентов
    - Взаимодействие ТОЛЬКО через ActionExecutor
    - Поддержка внедрения зависимостей через интерфейсы (DI)

    ЖИЗНЕННЫЙ ЦИКЛ:
    1. __init__ - создание экземпляра с конфигурацией
    2. initialize() - предзагрузка всех ресурсов (промты, контракты)
    3. execute() - выполнение бизнес-логики через универсальный шаблон
    4. shutdown() - корректное завершение работы

    ПРИМЕР ИСПОЛЬЗОВАНИЯ:
    ```python
    class MySkill(BaseSkill):
        async def _execute_impl(self, capability, parameters, context):
            # Ваша бизнес-логика здесь
            prompt = self.get_prompt(capability.name)
            return {"result": "done"}
    ```

    АТРИБУТЫ:
    - name: имя компонента
    - application_context: контекст приложения для доступа к ресурсам (DEPRECATED)
    - component_config: конфигурация компонента с версиями ресурсов
    - executor: ActionExecutor для взаимодействия с другими компонентами
    - prompts: кэш промптов (объекты Prompt)
    - input_contracts: кэш входных контрактов (классы Pydantic)
    - output_contracts: кэш выходных контрактов (классы Pydantic)
    
    DI ЗАВИСИМОСТИ (внедряются через конструктор):
    - db: DatabaseInterface
    - llm: LLMInterface
    - cache: CacheInterface
    - vector: VectorInterface
    - event_bus: EventBusInterface
    - prompt_storage: PromptStorageInterface
    - contract_storage: ContractStorageInterface
    """

    def __init__(
        self,
        name: str,
        application_context: Optional['ApplicationContext'] = None,  # DEPRECATED, будет удалён
        component_config: Optional[ComponentConfig] = None,
        executor: Optional['ActionExecutor'] = None,  # ← ЕДИНСТВЕННЫЙ способ взаимодействия
        # === ВНЕДРЕНИЕ ЗАВИСИМОСТЕЙ ЧЕРЕЗ ИНТЕРФЕЙСЫ ===
        db: Optional[DatabaseInterface] = None,
        llm: Optional[LLMInterface] = None,
        cache: Optional[CacheInterface] = None,
        vector: Optional[VectorInterface] = None,
        event_bus: Optional[EventBusInterface] = None,
        prompt_storage: Optional[PromptStorageInterface] = None,
        contract_storage: Optional[ContractStorageInterface] = None,
        metrics_storage: Optional[MetricsStorageInterface] = None,
        log_storage: Optional[LogStorageInterface] = None
    ):
        # Вызов конструктора LifecycleMixin
        LifecycleMixin.__init__(self, name)

        # Валидация обязательных параметров
        if component_config is None:
            raise ValueError(f"Компонент '{name}' требует component_config")
        
        if not hasattr(component_config, 'variant_id'):
            raise ValueError(
                f"Компонент '{name}' требует полную конфигурацию через ComponentConfig. "
                "Legacy-режим (agent_config) больше не поддерживается."
            )
        
        if executor is None:
            raise ValueError(f"Компонент '{name}' требует executor")

        # Сохраняем параметры
        self._application_context = application_context  # DEPRECATED
        self.component_config = component_config
        self.executor = executor  # ← Критически важно!

        # === ВНЕДРЁННЫЕ ЗАВИСИМОСТИ ===
        self._db = db
        self._llm = llm
        self._cache = cache
        self._vector = vector
        self._event_bus = event_bus
        self._prompt_storage = prompt_storage
        self._contract_storage = contract_storage
        self._metrics_storage = metrics_storage
        self._log_storage = log_storage

        # EventBusLogger для асинхронного логирования
        self.event_bus_logger = None
        self._init_event_bus_logger()

        # Основные данные компонента (не кэш!)
        self.prompts: Dict[str, Prompt] = {}  # ← Объекты, не строки!
        self.input_contracts: Dict[str, Type[BaseModel]] = {}  # ← Классы схем, не словари!
        self.output_contracts: Dict[str, Type[BaseModel]] = {}

        # ← НОВОЕ: Автоматическое разделение system/user промптов
        self.system_prompts: Dict[str, Prompt] = {}  # {base_capability: Prompt}
        self.user_prompts: Dict[str, Prompt] = {}    # {base_capability: Prompt}

        # Временные метки для TTL
        self.prompt_timestamps: Dict[str, float] = {}
        self.input_contract_timestamps: Dict[str, float] = {}
        self.output_contract_timestamps: Dict[str, float] = {}

        # TTL для элементов кэша (в секундах, None означает бессрочный кэш)
        self._cache_ttl_seconds = 3600  # 1 час по умолчанию

    # ========================================================================
    # СВОЙСТВА ДЛЯ ВНЕДРЁННЫХ ЗАВИСИМОСТЕЙ
    # ========================================================================

    @property
    def db(self) -> Optional[DatabaseInterface]:
        """Получить DatabaseInterface."""
        return self._db

    @property
    def llm(self) -> Optional[LLMInterface]:
        """Получить LLMInterface."""
        return self._llm

    @property
    def cache(self) -> Optional[CacheInterface]:
        """Получить CacheInterface."""
        return self._cache

    @property
    def vector(self) -> Optional[VectorInterface]:
        """Получить VectorInterface."""
        return self._vector

    @property
    def event_bus(self) -> Optional[EventBusInterface]:
        """Получить EventBusInterface."""
        return self._event_bus

    @property
    def prompt_storage(self) -> Optional[PromptStorageInterface]:
        """Получить PromptStorageInterface."""
        return self._prompt_storage

    @property
    def contract_storage(self) -> Optional[ContractStorageInterface]:
        """Получить ContractStorageInterface."""
        return self._contract_storage

    @property
    def metrics_storage(self) -> Optional[MetricsStorageInterface]:
        """Получить MetricsStorageInterface."""
        return self._metrics_storage

    @property
    def log_storage(self) -> Optional[LogStorageInterface]:
        """Получить LogStorageInterface."""
        return self._log_storage

    # ========================================================================
    # DEPRECATED: Свойства для обратной совместимости
    # ========================================================================

    @property
    def application_context(self) -> Optional['ApplicationContext']:
        """
        Получить контекст приложения.
        
        DEPRECATED: Используйте внедрение зависимостей через интерфейсы.
        Это свойство будет удалено в следующей мажорной версии.
        
        RETURNS:
        - ApplicationContext или None
        
        RAISES:
        - RuntimeError: Если application_context не был передан
        """
        import warnings
        warnings.warn(
            "application_context deprecated. Используйте внедрение зависимостей через интерфейсы.",
            DeprecationWarning,
            stacklevel=2
        )
        
        if self._application_context is None:
            raise RuntimeError(
                f"Компонент '{self.name}': application_context не был передан. "
                "Используйте внедрение зависимостей через интерфейсы."
            )
        return self._application_context

    @application_context.setter
    def application_context(self, value: 'ApplicationContext'):
        """Установить контекст приложения (для обратной совместимости)."""
        self._application_context = value

    # ========================================================================
    # ЛОГИРОВАНИЕ
    # ========================================================================

    def _init_event_bus_logger(self):
        """Инициализация EventBusLogger для асинхронного логирования."""
        # Сначала пробуем внедрённый event_bus
        if self._event_bus is not None:
            self.event_bus_logger = EventBusLogger(
                self._event_bus,
                session_id="system",
                agent_id="system",
                component=self.__class__.__name__
            )
        # Fallback на application_context для обратной совместимости
        elif self._application_context is not None:
            if hasattr(self._application_context, 'infrastructure_context'):
                event_bus = getattr(self._application_context.infrastructure_context, 'event_bus', None)
                if event_bus:
                    self.event_bus_logger = EventBusLogger(
                        event_bus,
                        session_id="system",
                        agent_id="system",
                        component=self.__class__.__name__
                    )

    def _safe_log_sync(self, level: str, message: str, **kwargs):
        """
        Безопасный синхронный логгер — проверяет event_bus_logger на None.
        
        ПАРАМЕТРЫ:
        - level: уровень логирования ('info', 'debug', 'warning', 'error')
        - message: сообщение
        - **kwargs: дополнительные аргументы для логгера
        """
        if hasattr(self, 'event_bus_logger') and self.event_bus_logger is not None:
            log_method = getattr(self.event_bus_logger, f'{level}_sync', None)
            if log_method:
                log_method(message, **kwargs)

    async def initialize(self) -> bool:
        """
        ЕДИНСТВЕННЫЙ метод инициализации — получает ресурсы ИЗ КОНФИГУРАЦИИ,
        НЕ обращаясь к сервисам напрямую.

        ВАЖНО: Все ресурсы уже загружены в component_config.application_context
        на уровне ApplicationContext.initialize().
        
        ЖИЗНЕННЫЙ ЦИКЛ:
        - Переводит компонент в состояние INITIALIZING
        - При успехе: READY
        - При ошибке: FAILED
        """
        import logging
        import time
        logger = logging.getLogger(__name__)
        current_time = time.time()
        
        # Проверка: нельзя инициализировать повторно
        if self._state == ComponentState.READY:
            if self.event_bus_logger:
                await self.event_bus_logger.warning(f"Компонент '{self.name}' уже инициализирован")
            else:
                logger.warning(f"Компонент '{self.name}' уже инициализирован")
            return True
        
        # Переход в состояние INITIALIZING
        await self._transition_to(ComponentState.INITIALIZING)
        
        if self.event_bus_logger:
            await self.event_bus_logger.info(f"BaseComponent.initialize: начало инициализации для {self.name}")
        else:
            logger.info(f"BaseComponent.initialize: начало инициализации для {self.name}")

        try:
            # === ЭТАП 1: Валидация манифеста (НОВОЕ) ===
            if not await self._validate_manifest():
                self._safe_log_sync("error", f"{self.name}: Валидация манифеста не пройдена")
                await self._transition_to(ComponentState.FAILED)
                return False

            # === ЭТАП 2: Предзагрузка ресурсов ===
            if not await self._preload_resources(current_time):
                self._safe_log_sync("error", f"{self.name}: Предзагрузка ресурсов не удалась")
                await self._transition_to(ComponentState.FAILED)
                return False

            # === ЭТАП 3: Валидация загруженных ресурсов ===
            if not await self._validate_loaded_resources():
                self._safe_log_sync("error", f"{self.name}: Валидация загруженных ресурсов не пройдена")
                await self._transition_to(ComponentState.FAILED)
                return False

            msg = f"Компонент '{self.name}' полностью инициализирован. Ресурсы: промпты={len(self.prompts)}, input_contracts={len(self.input_contracts)}, output_contracts={len(self.output_contracts)}"
            self._safe_log_sync("info", msg)
            
            # Переход в состояние READY
            await self._transition_to(ComponentState.READY)
            return True

        except Exception as e:
            self._safe_log_sync("error", f"Ошибка инициализации компонента '{self.name}': {e}")
            logger.error(f"Ошибка инициализации компонента '{self.name}': {e}", exc_info=True)
            await self._transition_to(ComponentState.FAILED)
            return False

    async def _validate_manifest(self) -> bool:
        """
        Валидация конфигурации компонента вместо манифеста.

        Проверяет:
        1. Наличие component_config
        2. Корректность версий контрактов в config
        3. Доступность зависимостей из DEPENDENCIES
        """
        # Проверка ComponentConfig
        if not self.component_config:
            self._safe_log_sync("debug", f"{self.name}: component_config отсутствует")
            return True  # Не блокируем, но логируем

        # Проверка что версии контрактов указаны корректно
        if hasattr(self.component_config, 'input_contract_versions'):
            for cap, ver in self.component_config.input_contract_versions.items():
                if not ver or not isinstance(ver, str):
                    self._safe_log_sync("error", f"{self.name}: Некорректная версия контракта {cap}@{ver}")
                    return False

        # Проверка зависимостей из DEPENDENCIES
        if hasattr(self, 'DEPENDENCIES'):
            for dep_name in self.DEPENDENCIES:
                # Сначала пробуем найти в registry компонентов
                dep = None
                if self._application_context is not None:
                    dep = (
                        self._application_context.components.get(ComponentType.SERVICE, dep_name) or
                        self._application_context.components.get(ComponentType.TOOL, dep_name) or
                        self._application_context.components.get(ComponentType.SKILL, dep_name) or
                        self._application_context.components.get(ComponentType.BEHAVIOR, dep_name)
                    )
                
                if not dep:
                    self._safe_log_sync("warning", f"{self.name}: Зависимость '{dep_name}' не найдена в registry (будет внедрена через DI)")
                    # Не блокируем - зависимость может быть внедрена через DI

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
                self._safe_log_sync("error", f"{self.name}: {error}")
            return False

        return True

    async def _preload_resources(self, current_time: float) -> bool:
        """Предзагрузка ресурсов компонента."""
        try:
            # Отладочный вывод
            self._safe_log_sync(
                "info",
                f"_preload_resources: {self.name} - "
                f"prompt_versions={list(self.component_config.prompt_versions.keys())}, "
                f"input_contract_versions={list(self.component_config.input_contract_versions.keys())}, "
                f"output_contract_versions={list(self.component_config.output_contract_versions.keys())}"
            )

            # Загрузка промптов как объектов
            for cap_name, version in self.component_config.prompt_versions.items():
                try:
                    # Получаем ПОЛНОЦЕННЫЙ объект из репозитория
                    if hasattr(self.application_context, 'data_repository') and self.application_context.data_repository:
                        prompt_obj: Prompt = self.application_context.data_repository.get_prompt(cap_name, version)
                        self.prompts[cap_name] = prompt_obj

                        self._safe_log_sync(
                            "debug",
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
                        self.prompts[cap_name] = prompt_obj
                        self._safe_log_sync("warning", f"Используется совместимый режим для промпта {cap_name}")

                except Exception as e:
                    self._safe_log_sync("error", f"Ошибка загрузки промпта {cap_name}@{version}: {e}")
                    # Используем безопасный способ проверки критических ресурсов
                    if hasattr(self.component_config, 'critical_resources') and self.component_config.critical_resources.get('prompts', False):
                        self._safe_log_sync("error", f"Критический промпт {cap_name} не загружен")
                        return False

            # Загрузка схем контрактов
            for cap_name, version in self.component_config.input_contract_versions.items():
                try:
                    if hasattr(self.application_context, 'data_repository') and self.application_context.data_repository:
                        schema_cls: Type[BaseModel] = (
                            self.application_context.data_repository
                            .get_contract_schema(cap_name, version, "input")
                        )
                        self.input_contracts[cap_name] = schema_cls
                    else:
                        # Старый путь: получаем из контекста
                        schema_cls = self.application_context.get_input_contract_schema(cap_name, version)
                        self.input_contracts[cap_name] = schema_cls
                        self._safe_log_sync("warning", f"Используется совместимый режим для входной схемы {cap_name}")

                except Exception as e:
                    self._safe_log_sync("error", f"Ошибка загрузки входной схемы {cap_name}@{version}: {e}")
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
                        self.output_contracts[cap_name] = schema_cls
                    else:
                        # Старый путь: используем базовый класс
                        self.output_contracts[cap_name] = BaseModel
                        self._safe_log_sync("warning", f"Используется совместимый режим для выходной схемы {cap_name}")

                except Exception as e:
                    self._safe_log_sync("error", f"Ошибка загрузки выходной схемы {cap_name}@{version}: {e}")
                    # Используем безопасный способ проверки критических ресурсов
                    if hasattr(self.component_config, 'critical_resources') and self.component_config.critical_resources.get('output_contracts', False):
                        return False

            # Устанавливаем временные метки для всех загруженных ресурсов
            for prompt_key in self.prompts:
                self.prompt_timestamps[prompt_key] = current_time
            for schema_key in self.input_contracts:
                self.input_contract_timestamps[schema_key] = current_time
            for schema_key in self.output_contracts:
                self.output_contract_timestamps[schema_key] = current_time

            # ← НОВОЕ: Автоматическое разделение system/user промптов
            self._separate_system_user_prompts()

            return True

        except Exception as e:
            self._safe_log_sync("error", f"Ошибка предзагрузки ресурсов для '{self.name}': {e}", exc_info=True)
            return False

    def _separate_system_user_prompts(self):
        """
        Автоматически разделяет промпты на system/user по соглашению об именовании.

        Соглашение:
        - capability.system → system_prompts[base_capability]
        - capability.user → user_prompts[base_capability]

        Пример:
        - behavior.react.think.system → system_prompts['behavior.react.think']
        - behavior.react.think.user → user_prompts['behavior.react.think']
        """
        for cap_name, prompt in self.prompts.items():
            if '.system' in cap_name:
                base_name = cap_name.replace('.system', '')
                self.system_prompts[base_name] = prompt
                self._safe_log_sync("debug", f"Загружен system промпт: {base_name}")
            elif '.user' in cap_name:
                base_name = cap_name.replace('.user', '')
                self.user_prompts[base_name] = prompt
                self._safe_log_sync("debug", f"Загружен user промпт: {base_name}")

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
            if capability not in self.prompts:
                errors.append(f"Промпт '{capability}@{version}' не загружен")
            elif not self.prompts[capability]:
                errors.append(f"Промпт '{capability}' пустой")

        # Проверка входных контрактов
        for capability, version in self.component_config.input_contract_versions.items():
            if capability not in self.input_contracts:
                errors.append(f"Входной контракт '{capability}@{version}' не загружен")
            elif not self.input_contracts[capability]:
                errors.append(f"Входной контракт '{capability}' пустой")

        # Проверка выходных контрактов
        for capability, version in self.component_config.output_contract_versions.items():
            if capability not in self.output_contracts:
                errors.append(f"Выходной контракт '{capability}@{version}' не загружен")
            elif not self.output_contracts[capability]:
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
                self._safe_log_sync("error", f"{self.name}: {error}")
            return False

        self._safe_log_sync("debug", f"{self.name}: Все ресурсы валидированы успешно")
        return True

    def _get_component_type(self) -> str:
        """Определяет тип компонента (skill/tool/service/behavior)."""
        # Переопределяется в наследниках
        return "component"

    def _ensure_initialized(self):
        """
        Проверяет, что компонент инициализирован перед использованием.
        
        DEPRECATED: Используйте ensure_ready() из LifecycleMixin.
        Этот метод сохранён для обратной совместимости.

        RAISES:
        - RuntimeError: если компонент не инициализирован
        """
        # Для обратной совместимости проверяем старое условие
        if self._state not in (ComponentState.READY, ComponentState.SHUTDOWN):
            raise RuntimeError(
                f"Компонент '{self.name}' не инициализирован (state={self._state.value}). "
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
                if key in self.prompts:
                    del self.prompts[key]
                if key in self.prompt_timestamps:
                    del self.prompt_timestamps[key]
            else:
                self.prompts.clear()
                self.prompt_timestamps.clear()

        if cache_type is None or cache_type == 'input_contracts':
            if key:
                if key in self.input_contracts:
                    del self.input_contracts[key]
                if key in self.input_contract_timestamps:
                    del self.input_contract_timestamps[key]
            else:
                self.input_contracts.clear()
                self.input_contract_timestamps.clear()

        if cache_type is None or cache_type == 'output_contracts':
            if key:
                if key in self.output_contracts:
                    del self.output_contracts[key]
                if key in self.output_contract_timestamps:
                    del self.output_contract_timestamps[key]
            else:
                self.output_contracts.clear()
                self.output_contract_timestamps.clear()

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
            'prompts': self.prompt_timestamps,
            'input_contracts': self.input_contract_timestamps,
            'output_contracts': self.output_contract_timestamps
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

        if capability_name not in self.prompts:
            return ""

        # Проверяем, не истек ли срок действия кэша
        if self._is_cache_expired('prompts', capability_name):
            # Инвалидируем просроченный элемент
            self.invalidate_cache('prompts', capability_name)
            return ""

        # Безопасное извлечение через атрибут объекта
        prompt_obj = self.prompts[capability_name]
        if hasattr(prompt_obj, 'content'):
            return prompt_obj.content
        return str(prompt_obj)

    def get_cached_input_contract_safe(self, capability_name: str) -> Type[BaseModel]:
        """
        Безопасное получение входной схемы из кэша с обработкой ошибок и проверкой срока действия.

        ARGS:
        - capability_name: имя capability для получения входной схемы

        RETURNS:
        - Type[BaseModel]: класс схемы или базовый BaseModel если не найден или истек
        """
        self._ensure_initialized()

        if capability_name not in self.input_contracts:
            return BaseModel

        # Проверяем, не истек ли срок действия кэша
        if self._is_cache_expired('input_contracts', capability_name):
            # Инвалидируем просроченный элемент
            self.invalidate_cache('input_contracts', capability_name)
            return BaseModel

        return self.input_contracts[capability_name]

    def get_cached_output_contract_safe(self, capability_name: str) -> Type[BaseModel]:
        """
        Безопасное получение выходной схемы из кэша с обработкой ошибок и проверкой срока действия.

        ARGS:
        - capability_name: имя capability для получения выходной схемы

        RETURNS:
        - Type[BaseModel]: класс схемы или базовый BaseModel если не найден или истек
        """
        self._ensure_initialized()

        if capability_name not in self.output_contracts:
            return BaseModel

        # Проверяем, не истек ли срок действия кэша
        if self._is_cache_expired('output_contracts', capability_name):
            # Инвалидируем просроченный элемент
            self.invalidate_cache('output_contracts', capability_name)
            return BaseModel

        return self.output_contracts[capability_name]

    # === БЕЗОПАСНЫЙ ДОСТУП К РЕСУРСАМ (ТОЛЬКО ИЗ КЭША) ===

    def get_prompt(self, capability_name: str) -> str:
        """
        Для обратной совместимости возвращаем текст,
        но храним и используем полноценный объект.
        """
        self._ensure_initialized()
        if capability_name not in self.prompts:
            self._safe_log_sync(
                "warning",
                f"Промпт для capability '{capability_name}' не загружен в компонент '{self.name}'. "
                f"Доступные: {list(self.prompts.keys())}. Возвращаем пустую строку."
            )
            return ""  # Возвращаем пустую строку вместо ошибки

        # Безопасное извлечение через атрибут объекта
        return self.prompts[capability_name].content

    def get_input_contract(self, capability_name: str) -> Dict:
        """
        Возвращаем схему как словарь для обратной совместимости,
        но используем типизированный объект.
        """
        self._ensure_initialized()
        if capability_name not in self.input_contracts:
            self._safe_log_sync(
                "warning",
                f"Входная схема для '{capability_name}' не загружена в компонент '{self.name}'. "
                f"Доступные: {list(self.input_contracts.keys())}. Возвращаем пустой словарь."
            )
            return {}  # Возвращаем пустой словарь вместо ошибки

        schema_cls = self.input_contracts[capability_name]
        # Возвращаем словарь схемы для обратной совместимости
        return schema_cls.model_json_schema()

    def get_output_contract(self, capability_name: str) -> Dict:
        """
        Возвращаем схему как словарь для обратной совместимости,
        но используем типизированный объект.
        """
        self._ensure_initialized()
        if capability_name not in self.output_contracts:
            self._safe_log_sync(
                "warning",
                f"Выходная схема для '{capability_name}' не загружена в компонент '{self.name}'. "
                f"Доступные: {list(self.output_contracts.keys())}. Возвращаем пустой словарь."
            )
            return {}  # Возвращаем пустой словарь вместо ошибки

        schema_cls = self.output_contracts[capability_name]
        # Возвращаем словарь схемы для обратной совместимости
        return schema_cls.model_json_schema()

    def validate_input(self, capability_name: str, data: Dict) -> bool:
        """
        Типобезопасная валидация через скомпилированную схему.
        
        ARCHITECTURE:
        - Валидирует входные данные через Pydantic модель
        - Для типизированной валидации используйте validate_input_typed()
        """
        if capability_name not in self.input_contracts:
            self._safe_log_sync("warning", f"Схема для {capability_name} не загружена, пропускаем валидацию")
            return True

        schema_cls = self.input_contracts[capability_name]
        try:
            # Pydantic автоматически валидирует и конвертирует типы
            validated = schema_cls.model_validate(data)
            return True
        except Exception as e:
            self._safe_log_sync("error", f"Валидация входных данных для {capability_name} провалена: {e}")
            return False
    
    def validate_input_typed(self, capability_name: str, data: Dict) -> Optional[BaseModel]:
        """
        Типобезопасная валидация с возвратом Pydantic модели.
        
        ARCHITECTURE:
        - Возвращает валидированную Pydantic модель вместо dict
        - Сохраняет типизацию для IDE автокомплита
        - None если валидация не пройдена
        
        EXAMPLE:
            validated: BookLibrarySearchInput = self.validate_input_typed('search', data)
            if validated:
                query = validated.query  # ✅ IDE знает тип
                max_results = validated.max_results  # ✅ IDE знает тип
        """
        if capability_name not in self.input_contracts:
            self._safe_log_sync("warning", f"Схема для {capability_name} не загружена, пропускаем валидацию")
            # Возвращаем данные как есть если схема не загружена
            return data

        schema_cls = self.input_contracts[capability_name]
        try:
            # Pydantic автоматически валидирует и конвертирует типы
            validated = schema_cls.model_validate(data)
            return validated  # ← Pydantic модель типа T
        except Exception as e:
            self._safe_log_sync("error", f"Валидация входных данных для {capability_name} провалена: {e}")
            return None

    def validate_output(self, capability_name: str, data: Any) -> bool:
        """
        Валидация выходных данных через скомпилированную схему.

        ПАРАМЕТРЫ:
        - capability_name: имя capability
        - data: данные для валидации

        ВОЗВРАЩАЕТ:
        - bool: True если валидация пройдена
        """
        if capability_name not in self.output_contracts:
            self._safe_log_sync("warning", f"Выходная схема для {capability_name} не загружена, пропускаем валидацию")
            return True

        schema_cls = self.output_contracts[capability_name]
        try:
            # Pydantic автоматически валидирует и конвертирует типы
            validated = schema_cls.model_validate(data)
            return True
        except Exception as e:
            self._safe_log_sync("error", f"Валидация выходных данных для {capability_name} провалена: {e}")
            return False
    
    def validate_output_typed(self, capability_name: str, data: Any) -> Optional[BaseModel]:
        """
        Типобезопасная валидация выходных данных с возвратом Pydantic модели.
        
        ARCHITECTURE:
        - Возвращает валидированную Pydantic модель вместо dict
        - Сохраняет типизацию для IDE автокомплита
        - None если валидация не пройдена
        
        EXAMPLE:
            validated: BookLibrarySearchOutput = self.validate_output_typed('search', result)
            if validated:
                rows = validated.rows  # ✅ IDE знает тип
                rowcount = validated.rowcount  # ✅ IDE знает тип
        """
        if capability_name not in self.output_contracts:
            self._safe_log_sync("warning", f"Выходная схема для {capability_name} не загружена, пропускаем валидацию")
            return data

        schema_cls = self.output_contracts[capability_name]
        try:
            # Pydantic автоматически валидирует и конвертирует типы
            validated = schema_cls.model_validate(data)
            return validated  # ← Pydantic модель типа T
        except Exception as e:
            self._safe_log_sync("error", f"Валидация выходных данных для {capability_name} провалена: {e}")
            return None

    def render_prompt(self, capability_name: str, **kwargs) -> str:
        """
        Безопасный рендеринг шаблона с валидацией переменных.
        """
        if capability_name not in self.prompts:
            raise ValueError(f"Промпт '{capability_name}' не загружен")

        prompt_obj: Prompt = self.prompts[capability_name]

        # Используем встроенный метод рендеринга с валидацией
        try:
            return prompt_obj.render(**kwargs)
        except ValueError as e:
            self._safe_log_sync("error", f"Ошибка рендеринга промпта {capability_name}: {e}")
            raise

    def _format_contract_section(
        self,
        json_schema: Dict[str, Any],
        title: str,
        description: str
    ) -> str:
        """
        Форматирует JSON схему для добавления в промпт.

        ARGS:
        - json_schema: JSON Schema словарь
        - title: Заголовок секции (например, "ВХОДНОЙ КОНТРАКТ")
        - description: Описание назначения контракта

        RETURNS:
        - str: Отформатированная секция контракта
        """
        import json

        schema_json = json.dumps(json_schema, indent=2, ensure_ascii=False)

        return f"""
### {title} ###
{description}

```json
{schema_json}
```
"""

    def _render_prompt_with_contract(
        self,
        capability_name: str,
        include_input_contract: bool = True,
        include_output_contract: bool = True,
        position: str = "end"
    ) -> str:
        """
        Рендерит промпт с добавлением схем контрактов.

        АРХИТЕКТУРА:
        - Если есть system prompt → используем его + user prompt
        - Если нет system prompt → используем только user prompt (старый режим)

        ARGS:
        - capability_name: имя capability для получения контрактов
        - include_input_contract: добавить ли входную схему
        - include_output_contract: добавить ли выходную схему
        - position: куда добавить схемы ("start", "end", "after_variables")

        RETURNS:
        - str: Промпт с секциями контрактов

        NOTE:
        - Если контракты не найдены, они пропускаются с предупреждением в лог
        - Выходной контракт всегда добавляется в конце с инструкцией для LLM
        """
        parts = []
        
        # ← НОВОЕ: Добавляем system prompt если есть
        if capability_name in self.system_prompts:
            system_prompt = self.system_prompts[capability_name].content
            parts.append(system_prompt)
            parts.append("\n\n---\n\n")
        
        # Получаем базовый user промпт
        user_prompt = self.get_prompt(capability_name)
        parts.append(user_prompt)

        # Добавляем входной контракт
        if include_input_contract and capability_name in self.input_contracts:
            schema_cls = self.input_contracts[capability_name]
            json_schema = schema_cls.model_json_schema()
            contract_section = self._format_contract_section(
                json_schema,
                "ВХОДНОЙ КОНТРАКТ",
                "Опиши входные данные в этом формате"
            )
            if position == "start":
                parts.insert(0, contract_section)
            elif position == "after_variables":
                parts.insert(1 if capability_name in self.system_prompts else 0, contract_section)
            else:  # end
                parts.append(contract_section)
        elif include_input_contract and capability_name not in self.input_contracts:
            self._safe_log_sync("debug", f"Входной контракт для {capability_name} не найден, пропускаем")

        # Добавляем выходной контракт
        if include_output_contract and capability_name in self.output_contracts:
            schema_cls = self.output_contracts[capability_name]
            json_schema = schema_cls.model_json_schema()
            contract_section = self._format_contract_section(
                json_schema,
                "ВЫХОДНОЙ КОНТРАКТ",
                "Твой ответ ДОЛЖЕН точно соответствовать этой JSON схеме"
            )
            parts.append(contract_section)
            # Критически важное указание для LLM
            parts.append("\n\n⚠️ **ОТВЕТЬ ТОЛЬКО В ФОРМАТЕ JSON СОГЛАСНО ВЫХОДНОМУ КОНТРАКТУ ВЫШЕ!**")
        elif include_output_contract and capability_name not in self.output_contracts:
            self._safe_log_sync("debug", f"Выходной контракт для {capability_name} не найден, пропускаем")

        return "\n".join(parts)

    def get_prompt_with_contract(
        self,
        capability_name: str,
        include_input_contract: bool = True,
        include_output_contract: bool = True,
        position: str = "end"
    ) -> str:
        """
        Публичный метод для получения промпта с контрактами.

        ARGS:
        - capability_name: имя capability для получения промпта
        - include_input_contract: добавить ли входную схему
        - include_output_contract: добавить ли выходную схему
        - position: куда добавить схемы ("start", "end", "after_variables")

        RETURNS:
        - str: Промпт с секциями контрактов

        USAGE:
        ```python
        prompt = self.get_prompt_with_contract("planning.create_plan")
        rendered = prompt.format(goal="...", capabilities_list="...")
        ```
        """
        return self._render_prompt_with_contract(
            capability_name,
            include_input_contract=include_input_contract,
            include_output_contract=include_output_contract,
            position=position
        )

    # === ДОСТУП К ПРОВАЙДЕРАМ ИНФРАСТРУКТУРЫ ===

    def get_provider(self, name: str):
        """
        Универсальный метод получения провайдера из инфраструктуры.

        ARGS:
        - name: имя провайдера

        RETURNS:
        - Провайдер или None если не найден
        """
        if not hasattr(self.application_context, 'infrastructure_context'):
            self._safe_log_sync("warning", f"infrastructure_context не доступен для получения провайдера '{name}'")
            return None
        return self.application_context.infrastructure_context.get_provider(name)

    def get_llm_provider(self, name: str = "default_llm"):
        """
        Получение LLM провайдера.

        ARGS:
        - name: имя LLM провайдера (по умолчанию "default_llm")

        RETURNS:
        - LLM провайдер или None если не найден
        """
        return self.get_provider(name)

    def get_db_provider(self, name: str = "default_db"):
        """
        Получение DB провайдера.

        ARGS:
        - name: имя DB провайдера (по умолчанию "default_db")

        RETURNS:
        - DB провайдер или None если не найден
        """
        return self.get_provider(name)

    # === ПУБЛИКАЦИЯ МЕТОРИК И СОБЫТИЙ ===

    async def _publish_metrics(
        self,
        event_type: 'EventType',
        capability_name: str,
        success: bool,
        execution_time_ms: float,
        tokens_used: int = 0,
        **extra_data
    ) -> None:
        """
        Универсальный метод публикации метрик выполнения компонента через EventBus.

        ARGS:
        - event_type: тип события (EventType.SKILL_EXECUTED, EventType.TOOL_EXECUTED, etc.)
        - capability_name: название выполненной capability
        - success: успешность выполнения
        - execution_time_ms: время выполнения в мс
        - tokens_used: количество использованных токенов
        - **extra_data: дополнительные данные для события
        """
        if not hasattr(self.application_context, 'infrastructure_context'):
            self._safe_log_sync("debug", f"infrastructure_context не доступен для публикации метрик")
            return

        event_bus = self.application_context.infrastructure_context.event_bus
        
        # Формируем базовые данные события
        event_data = {
            'agent_id': getattr(self.application_context, 'agent_id', getattr(self.application_context, 'id', 'unknown')),
            'component_name': self.name,
            'component_type': self._get_component_type(),
            'capability': capability_name,
            'success': success,
            'execution_time_ms': execution_time_ms,
            'tokens_used': tokens_used,
            **extra_data
        }

        await event_bus.publish(
            event_type,
            data=event_data,
            source=self.name
        )

    # === АБСТРАКТНЫЙ МЕТОД ВЫПОЛНЕНИЯ (БЕЗ ПРЯМЫХ ЗАВИСИМОСТЕЙ) ===

    async def execute(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: 'ExecutionContext'
    ) -> 'ExecutionResult':
        """
        УНИВЕРСАЛЬНЫЙ ШАБЛОН ВЫПОЛНЕНИЯ КОМПОНЕНТА С ЛОГИРОВАНИЕМ.

        Этот метод реализует полный цикл выполнения с:
        - Валидацией входных/выходных данных
        - Обработкой ошибок
        - Публикацией метрик
        - Измерением времени выполнения
        - Логированием через LogComponentMixin

        НАСЛЕДНИКИ должны переопределить только _execute_impl() для своей бизнес-логики.

        ЗАПРЕЩЕНО:
        - Вызывать другие компоненты напрямую
        - Обращаться к сервисам (PromptService, ContractService)
        - Работать с файловой системой

        РАЗРЕШЕНО:
        - Использовать предзагруженные ресурсы из кэшей
        - Вызывать другие действия через self.executor.execute_action()
        - Валидировать входные/выходные данные через контракты из кэша
        
        ARCHITECTURE:
        - Сохраняет типизацию Pydantic моделей до границ приложения
        - validate_input_typed возвращает Pydantic модель вместо dict
        - result может быть Pydantic моделью (сохраняется типизация)
        """
        import time
        from core.models.data.execution import ExecutionResult, ExecutionStatus
        from core.infrastructure.event_bus.unified_event_bus import EventType

        start_time = time.time()

        # Логирование начала выполнения
        # TODO: Добавить LogComponentMixin или реализовать логирование
        # self.log_start("execute", {
        #     'capability': capability.name,
        #     'parameters_count': len(parameters)
        # })

        try:
            # === ЭТАП 1: Валидация входных данных ===
            # ✅ ИСПРАВЛЕНО: Используем типизированную валидацию
            validated_input = self.validate_input_typed(capability.name, parameters)
            if validated_input is None:
                execution_time_ms = (time.time() - start_time) * 1000

                # Публикация метрики ошибки валидации
                await self._publish_metrics(
                    EventType.ERROR_OCCURRED,
                    capability_name=capability.name,
                    success=False,
                    execution_time_ms=execution_time_ms,
                    error="Input validation failed",
                    error_category="validation"
                )

                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error="Input validation failed",
                    metadata={"capability": capability.name}
                )

            # === ЭТАП 2: Выполнение бизнес-логики ===
            # ✅ ИСПРАВЛЕНО: Передаем валидированный input (Pydantic модель)
            result = await self._execute_impl(capability, validated_input, execution_context)

            # === ЭТАП 3: Валидация выходных данных ===
            # ✅ ИСПРАВЛЕНО: Используем типизированную валидацию
            validated_output = self.validate_output_typed(capability.name, result)
            if validated_output is None:
                execution_time_ms = (time.time() - start_time) * 1000

                await self._publish_metrics(
                    EventType.ERROR_OCCURRED,
                    capability_name=capability.name,
                    success=False,
                    execution_time_ms=execution_time_ms,
                    error="Output validation failed",
                    error_category="validation"
                )

                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error="Output validation failed",
                    metadata={"capability": capability.name}
                )

            # === ЭТАП 4: Публикация метрик успеха ===
            execution_time_ms = (time.time() - start_time) * 1000

            # Определяем тип события в зависимости от типа компонента
            event_type = self._get_event_type_for_success()

            await self._publish_metrics(
                event_type,
                capability_name=capability.name,
                success=True,
                execution_time_ms=execution_time_ms
            )

            return ExecutionResult(
                status=ExecutionStatus.COMPLETED,
                # ✅ ИСПРАВЛЕНО: Возвращаем Pydantic модель (сохраняется типизация)
                data=validated_output,
                metadata={
                    "capability": capability.name,
                    "execution_time_ms": execution_time_ms
                }
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000

            # Публикация метрик ошибки
            await self._publish_metrics(
                EventType.ERROR_OCCURRED,
                capability.name,
                False,
                execution_time_ms,
                tokens_used=0,
                error=str(e),
                error_type=type(e).__name__
            )

            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=str(e),
                metadata={
                    "capability": capability.name,
                    "error_type": type(e).__name__
                }
            )

    def _get_event_type_for_success(self) -> 'EventType':
        """
        Возвращает тип события для успешного выполнения.

        Переопределяется в наследниках для возврата правильного типа события.
        """
        from core.infrastructure.event_bus.unified_event_bus import EventType
        return EventType.SKILL_EXECUTED  # По умолчанию

    async def _execute_impl(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: 'ExecutionContext'
    ) -> Any:
        """
        Реализация бизнес-логики компонента.

        Этот метод должен быть переопределен в наследниках.
        Реализация по умолчанию вызывает NotImplementedError.

        ПАРАМЕТРЫ:
        - capability: capability для выполнения
        - parameters: параметры выполнения
        - execution_context: контекст выполнения

        ВОЗВРАЩАЕТ:
        - Результат выполнения (тип зависит от компонента)

        ИСКЛЮЧЕНИЯ:
        - NotImplementedError: если метод не переопределен в наследнике
        """
        raise NotImplementedError(
            f"Метод _execute_impl() должен быть реализован в классе {self.__class__.__name__}"
        )

    async def shutdown(self) -> None:
        """Корректное завершение работы компонента."""
        pass