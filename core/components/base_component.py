"""
Единый базовый класс для всех компонентов (навыков, инструментов, сервисов).

АРХИТЕКТУРНЫЕ ГАРАНТИИ:
- Предзагрузка → кэш → выполнение без обращений к хранилищу
- Четкое разделение ответственностей: декларация ≠ данные ≠ реализация
- Обязательная инициализация через ComponentConfig
- Изолированные кэши для каждого экземпляра
- Взаимодействие ТОЛЬКО через ActionExecutor
- Поддержка внедрения зависимостей (DI) через интерфейсы

ЖИЗНЕННЫЙ ЦИКЛ:
- Наследует LifecycleMixin для управления состояниями
- Наследует LoggingMixin для логирования
- Состояния: CREATED → INITIALIZING → READY → SHUTDOWN (или FAILED)
"""
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, TYPE_CHECKING, Type

from core.application.agent.components.action_executor import ExecutionContext
from core.config.component_config import ComponentConfig
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult
from core.models.data.prompt import Prompt
from core.models.enums.common_enums import ComponentType
from pydantic import BaseModel
from core.components.lifecycle import LifecycleMixin, ComponentState
from core.components.logging import LoggingMixin

# Интерфейсы для DI (используются только необходимые)
from core.interfaces.event_bus import EventBusInterface
from core.interfaces.metrics_storage import MetricsStorageInterface
from core.interfaces.log_storage import LogStorageInterface

if TYPE_CHECKING:
    from core.application.context.application_context import ApplicationContext
    from core.application.agent.components.action_executor import ActionExecutor


class BaseComponent(LifecycleMixin, LoggingMixin, ABC):
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
            prompt_obj = self.get_prompt(capability.name)
            prompt_text = prompt_obj.content if prompt_obj else ""
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
    - metrics_storage: MetricsStorageInterface
    - log_storage: LogStorageInterface
    """

    def __init__(
        self,
        name: str,
        application_context: Optional['ApplicationContext'] = None,  # [DEPRECATED Этап 5]
        component_config: Optional[ComponentConfig] = None,
        executor: Optional['ActionExecutor'] = None,  # ← ЕДИНСТВЕННЫЙ способ взаимодействия
        # === ВНЕДРЕНИЕ ЗАВИСИМОСТЕЙ ЧЕРЕЗ ИНТЕРФЕЙСЫ ===
        event_bus: Optional[EventBusInterface] = None,
        metrics_storage: Optional[MetricsStorageInterface] = None,
        log_storage: Optional[LogStorageInterface] = None
    ):
        # Вызов конструктора LifecycleMixin
        LifecycleMixin.__init__(self, name)
        
        # Вызов конструктора LoggingMixin с callback для состояния инициализации
        LoggingMixin.__init__(
            self,
            event_bus=event_bus,
            component_name=name,
            get_init_state_callback=self._get_logger_init_state
        )

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
        self.component_config = component_config
        self.executor = executor  # ← Критически важно!

        # Основные данные компонента (не кэш!)
        self.prompts: Dict[str, Prompt] = {}  # ← Объекты, не строки!
        self.input_contracts: Dict[str, Type[BaseModel]] = {}  # ← Классы схем, не словари!
        self.output_contracts: Dict[str, Type[BaseModel]] = {}

        # ← НОВОЕ: Автоматическое разделение system/user промптов
        self.system_prompts: Dict[str, Prompt] = {}  # {base_capability: Prompt}
        self.user_prompts: Dict[str, Prompt] = {}    # {base_capability: Prompt}

        # ← НОВОЕ: Словарь поддерживаемых capability
        self.supported_capabilities: Dict[str, Any] = {}  # {capability_name: handler}

    # ========================================================================
    # ЛОГИРОВАНИЕ
    # ========================================================================

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

        ЛОГИРОВАНИЕ:
        - Во время инициализации (INITIALIZING) логи выводятся синхронно
        - После перехода в READY логи публикуются асинхронно через EventBus
        """
        import time
        current_time = time.time()

        # Проверка: нельзя инициализировать повторно
        if self._state == ComponentState.READY:
            if self.event_bus_logger:
                await self.event_bus_logger.warning(f"Компонент '{self.name}' уже инициализирован")
            return True

        # Переход в состояние INITIALIZING
        await self._transition_to(ComponentState.INITIALIZING)

        # Явно переключаем логгер в режим инициализации
        if self.event_bus_logger:
            self.event_bus_logger._set_initializing()
            # Первый лог уже пойдёт синхронно
            self.event_bus_logger._write_sync(
                f"BaseComponent.initialize: начало инициализации для {self.name}",
                "INFO"
            )

        try:
            # === ЭТАП 1: Предзагрузка ресурсов ===
            if not await self._preload_resources():
                self._safe_log_sync("error", f"{self.name}: Предзагрузка ресурсов не удалась")
                await self._transition_to(ComponentState.FAILED)
                return False

            # === ЭТАП 2: Валидация загруженных ресурсов ===
            if not await self._validate_loaded_resources():
                self._safe_log_sync("error", f"{self.name}: Валидация загруженных ресурсов не пройдена")
                await self._transition_to(ComponentState.FAILED)
                return False

            msg = f"Компонент '{self.name}' полностью инициализирован. Ресурсы: промпты={len(self.prompts)}, input_contracts={len(self.input_contracts)}, output_contracts={len(self.output_contracts)}"
            self._safe_log_sync("info", msg)

            # Переход в состояние READY
            await self._transition_to(ComponentState.READY)

            # ← НОВОЕ: Устанавливаем флаг инициализации для обратной совместимости
            self._initialized = True

            # Переключаем логгер в асинхронный режим после успешной инициализации
            if self.event_bus_logger:
                self.event_bus_logger._set_ready()

            return True

        except Exception as e:
            self._safe_log_sync("error", f"Ошибка инициализации компонента '{self.name}': {e}")
            await self._transition_to(ComponentState.FAILED)
            return False

    async def _preload_resources(self) -> bool:
        """
        Предзагрузка ресурсов компонента.

        [REFACTOR v5.4.0] Ресурсы УЖЕ загружены в component_config.resolved_*
        через ResourcePreloader в ComponentFactory.
        Этот метод только копирует ресурсы из config в кэш компонента.
        """
        try:
            self._safe_log_sync(
                "debug",
                f"_preload_resources: {self.name} - ресурсы загружаются из component_config.resolved_*"
            )

            # ← НОВОЕ: Инициализация supported_capabilities из get_capabilities()
            await self._init_supported_capabilities()

            # [REFACTOR v5.4.0] Копируем ресурсы из component_config.resolved_*
            # Ресурсы уже загружены через ResourcePreloader в ComponentFactory
            if not await self._copy_resources_from_config():
                return False

            self._separate_system_user_prompts()
            return True

        except Exception as e:
            self._safe_log_sync("error", f"Ошибка предзагрузки ресурсов для '{self.name}': {e}", exc_info=True)
            return False

    async def _copy_resources_from_config(self) -> bool:
        """
        [REFACTOR v5.4.0] Копирование ресурсов из component_config.resolved_*.

        Ресурсы уже загружены через ResourcePreloader в ComponentFactory.
        Этот метод только копирует их в кэш компонента.

        RETURNS:
        - bool: True если все ресурсы скопированы успешно
        """
        # Копируем промпты из resolved_prompts
        for cap_name, prompt_obj in self.component_config.resolved_prompts.items():
            self.prompts[cap_name] = prompt_obj
            self._safe_log_sync(
                "debug",
                f"Скопирован промпт '{cap_name}' из resolved_prompts "
                f"(тип: {prompt_obj.component_type.value if hasattr(prompt_obj, 'component_type') else 'unknown'}, "
                f"статус: {prompt_obj.status.value if hasattr(prompt_obj, 'status') else 'unknown'})"
            )

        # Копируем input контракты из resolved_input_contracts
        for cap_name, contract_obj in self.component_config.resolved_input_contracts.items():
            # Если это объект Contract, получаем pydantic_schema
            if hasattr(contract_obj, 'pydantic_schema'):
                self.input_contracts[cap_name] = contract_obj.pydantic_schema
            else:
                # Если это уже схема (для обратной совместимости)
                self.input_contracts[cap_name] = contract_obj
            self._safe_log_sync("debug", f"Скопирован input контракт '{cap_name}' из resolved_input_contracts")

        # Копируем output контракты из resolved_output_contracts
        for cap_name, contract_obj in self.component_config.resolved_output_contracts.items():
            # Если это объект Contract, получаем pydantic_schema
            if hasattr(contract_obj, 'pydantic_schema'):
                self.output_contracts[cap_name] = contract_obj.pydantic_schema
            else:
                # Если это уже схема (для обратной совместимости)
                self.output_contracts[cap_name] = contract_obj
            self._safe_log_sync("debug", f"Скопирован output контракт '{cap_name}' из resolved_output_contracts")

        # Валидация что критические ресурсы загружены
        if hasattr(self.component_config, 'critical_resources'):
            if self.component_config.critical_resources.get('prompts', False) and not self.prompts:
                self._safe_log_sync("error", f"Критические промпты не загружены для {self.name}")
                return False

            if self.component_config.critical_resources.get('input_contracts', False) and not self.input_contracts:
                self._safe_log_sync("error", f"Критические input контракты не загружены для {self.name}")
                return False

            if self.component_config.critical_resources.get('output_contracts', False) and not self.output_contracts:
                self._safe_log_sync("error", f"Критические output контракты не загружены для {self.name}")
                return False

        return True

    async def _init_supported_capabilities(self):
        """
        Инициализация словаря supported_capabilities из get_capabilities().

        Заполняет supported_capabilities методами-обработчиками из _execute_impl.
        """
        if hasattr(self, 'get_capabilities') and callable(self.get_capabilities):
            try:
                capabilities = self.get_capabilities()
                # supported_capabilities остаётся пустым, так как _execute_impl
                # использует маппинг capability.name на методы внутри навыка
                # Это ожидаемое поведение для новой архитектуры
                self._safe_log_sync("debug", f"{self.name}: инициализировано {len(capabilities)} capability")
            except Exception as e:
                self._safe_log_sync("warning", f"{self.name}: ошибка инициализации capability: {e}")

    # [REFACTOR v5.4.0] Методы _load_prompts, _load_input_contracts, _load_output_contracts удалены
    # Ресурсы загружаются через ResourcePreloader в ComponentFactory и копируются через _copy_resources_from_config()

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
        5. Критичные ресурсы (critical_resources) загружены
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

        # === НОВОЕ: Проверка critical_resources ===
        if hasattr(self.component_config, 'critical_resources'):
            critical = self.component_config.critical_resources
            
            # Проверка критичных промптов
            if critical.get('prompts', False):
                for capability in self.component_config.prompt_versions.keys():
                    if capability not in self.prompts:
                        errors.append(f"Критичный промпт '{capability}' не загружен")
            
            # Проверка критичных input контрактов
            if critical.get('input_contracts', False):
                for capability in self.component_config.input_contract_versions.keys():
                    if capability not in self.input_contracts:
                        errors.append(f"Критичный input контракт '{capability}' не загружен")
            
            # Проверка критичных output контрактов
            if critical.get('output_contracts', False):
                for capability in self.component_config.output_contract_versions.keys():
                    if capability not in self.output_contracts:
                        errors.append(f"Критичный output контракт '{capability}' не загружен")

        if errors:
            for error in errors:
                self._safe_log_sync("error", f"{self.name}: {error}")
            return False

        self._safe_log_sync("debug", f"{self.name}: Все ресурсы валидированы успешно")
        return True

    # ========================================================================
    # [REFACTOR Этап 2.2] TTL-кэширование удалено
    # invalidate_cache() и _is_cache_expired() больше не используются
    # ========================================================================

    # === ОСНОВНЫЕ МЕТОДЫ ДОСТУПА К РЕСУРСАМ ===

    def get_prompt(self, capability_name: str) -> Prompt:
        """
        Получение промпта из кэша.

        [REFACTOR Этап 2.2] TTL-проверки удалены — ресурсы не истекают.

        ARGS:
        - capability_name: имя capability для получения промпта

        RETURNS:
        - Prompt: объект промпта или None если не найден
        """
        self.ensure_ready()

        if capability_name not in self.prompts:
            return None

        return self.prompts[capability_name]

    def get_input_contract(self, capability_name: str) -> Type[BaseModel]:
        """
        Получение входной схемы из кэша.

        [REFACTOR Этап 2.2] TTL-проверки удалены — ресурсы не истекают.

        ARGS:
        - capability_name: имя capability для получения входной схемы

        RETURNS:
        - Type[BaseModel]: класс схемы или базовый BaseModel если не найден
        """
        self.ensure_ready()

        if capability_name not in self.input_contracts:
            return BaseModel

        return self.input_contracts[capability_name]

    def get_output_contract(self, capability_name: str) -> Type[BaseModel]:
        """
        Получение выходной схемы из кэша.

        [REFACTOR Этап 2.2] TTL-проверки удалены — ресурсы не истекают.

        ARGS:
        - capability_name: имя capability для получения выходной схемы

        RETURNS:
        - Type[BaseModel]: класс схемы или базовый BaseModel если не найден
        """
        self.ensure_ready()

        if capability_name not in self.output_contracts:
            return BaseModel

        return self.output_contracts[capability_name]

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

{schema_json}
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

        HOTFIX: Проверка флага schema_in_prompt из component_config.llm_settings
        - Если schema_in_prompt=False → схема НЕ встраивается (будет передана через structured_output)
        - Если schema_in_prompt=True или не указан → встраиваем схему в промпт (старый режим)

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
        # === HOTFIX: Проверка флага schema_in_prompt ===
        if hasattr(self.component_config, 'llm_settings'):
            if not self.component_config.llm_settings.get('schema_in_prompt', True):
                # Схема будет передана через structured_output — не встраиваем в промпт
                prompt_obj = self.get_prompt(capability_name)
                return prompt_obj.content if prompt_obj else ""

        parts = []

        # ← НОВОЕ: Добавляем system prompt если есть
        if capability_name in self.system_prompts:
            system_prompt = self.system_prompts[capability_name].content
            parts.append(system_prompt)
            parts.append("\n\n---\n\n")

        # Получаем базовый user промпт
        prompt_obj = self.get_prompt(capability_name)
        user_prompt = prompt_obj.content if prompt_obj else ""
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

    # === АБСТРАКТНЫЙ МЕТОД ВЫПОЛНЕНИЯ (БЕЗ ПРЯМЫХ ЗАВИСИМОСТЕЙ) ===

    async def execute(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: ExecutionContext
    ) -> ExecutionResult:
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
        start_time = time.time()

        try:
            validated_input = await self._validate_and_prepare_input(capability, parameters)
            if validated_input is None:
                return await self._create_validation_error_result(capability, "Input", start_time)

            result = await self._execute_business_logic(capability, validated_input, execution_context)

            validated_output = await self._validate_output(capability, result)
            if validated_output is None:
                return await self._create_validation_error_result(capability, "Output", start_time)

            await self._publish_execution_metrics(capability, True, start_time)
            return self._create_execution_result(capability, validated_output, start_time)

        except Exception as e:
            return await self._create_error_result(capability, e, start_time)

    async def _validate_and_prepare_input(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any]
    ) -> Optional[BaseModel]:
        """
        Валидация и подготовка входных данных.

        ARGS:
        - capability: capability для выполнения
        - parameters: параметры выполнения

        RETURNS:
        - Pydantic модель валидированных данных или None при ошибке
        """
        return self.validate_input_typed(capability.name, parameters)

    async def _execute_business_logic(
        self,
        capability: 'Capability',
        parameters: BaseModel,
        execution_context: ExecutionContext
    ) -> Any:
        """
        Выполнение бизнес-логики компонента.

        ARGS:
        - capability: capability для выполнения
        - parameters: валидированные параметры
        - execution_context: контекст выполнения

        RETURNS:
        - Результат выполнения бизнес-логики
        """
        return await self._execute_impl(capability, parameters, execution_context)

    async def _validate_output(
        self,
        capability: 'Capability',
        result: Any
    ) -> Optional[BaseModel]:
        """
        Валидация выходных данных.

        ARGS:
        - capability: capability для выполнения
        - result: результат выполнения бизнес-логики

        RETURNS:
        - Pydantic модель валидированных данных или None при ошибке
        """
        return self.validate_output_typed(capability.name, result)

    async def _publish_execution_metrics(
        self,
        capability: 'Capability',
        success: bool,
        start_time: float
    ) -> None:
        """
        Публикация метрик выполнения.

        ARGS:
        - capability: capability для выполнения
        - success: успешность выполнения
        - start_time: время начала выполнения
        """
        import time
        from core.infrastructure.event_bus.unified_event_bus import EventType

        execution_time_ms = (time.time() - start_time) * 1000
        event_type = self._get_event_type_for_success() if success else EventType.ERROR_OCCURRED

        await self._publish_metrics(
            event_type=event_type,
            capability_name=capability.name,
            success=success,
            execution_time_ms=execution_time_ms
        )

    def _create_execution_result(
        self,
        capability: 'Capability',
        data: Any,
        start_time: float
    ) -> ExecutionResult:
        """
        Создание успешного результата выполнения.

        ARGS:
        - capability: capability для выполнения
        - data: валидированные данные результата
        - start_time: время начала выполнения

        RETURNS:
        - ExecutionResult с успешным статусом
        """
        import time
        from core.models.data.execution import ExecutionResult, ExecutionStatus

        execution_time_ms = (time.time() - start_time) * 1000
        return ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            data=data,
            metadata={
                "capability": capability.name,
                "execution_time_ms": execution_time_ms
            }
        )

    async def _create_validation_error_result(
        self,
        capability: 'Capability',
        validation_type: str,
        start_time: float
    ) -> ExecutionResult:
        """
        Создание результата ошибки валидации.

        ARGS:
        - capability: capability для выполнения
        - validation_type: тип валидации ("Input" или "Output")
        - start_time: время начала выполнения

        RETURNS:
        - ExecutionResult с ошибкой валидации
        """
        import time
        from core.models.data.execution import ExecutionResult, ExecutionStatus
        from core.infrastructure.event_bus.unified_event_bus import EventType

        execution_time_ms = (time.time() - start_time) * 1000

        await self._publish_metrics(
            event_type=EventType.ERROR_OCCURRED,
            capability_name=capability.name,
            success=False,
            execution_time_ms=execution_time_ms,
            error=f"{validation_type} validation failed",
            error_category="validation"
        )

        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            error=f"{validation_type} validation failed",
            metadata={"capability": capability.name}
        )

    async def _create_error_result(
        self,
        capability: 'Capability',
        error: Exception,
        start_time: float
    ) -> ExecutionResult:
        """
        Создание результата ошибки выполнения.

        ARGS:
        - capability: capability для выполнения
        - error: исключение
        - start_time: время начала выполнения

        RETURNS:
        - ExecutionResult с ошибкой выполнения
        """
        import time
        from core.models.data.execution import ExecutionResult, ExecutionStatus
        from core.infrastructure.event_bus.unified_event_bus import EventType

        execution_time_ms = (time.time() - start_time) * 1000

        await self._publish_metrics(
            event_type=EventType.ERROR_OCCURRED,
            capability_name=capability.name,
            success=False,
            execution_time_ms=execution_time_ms,
            error=str(error),
            error_type=type(error).__name__
        )

        return ExecutionResult(
            status=ExecutionStatus.FAILED,
            error=str(error),
            metadata={
                "capability": capability.name,
                "error_type": type(error).__name__
            }
        )

    def _get_event_type_for_success(self) -> 'EventType':
        """
        Возвращает тип события для успешного выполнения.

        Переопределяется в наследниках для возврата правильного типа события.
        """
        from core.infrastructure.event_bus.unified_event_bus import EventType
        return EventType.SKILL_EXECUTED  # По умолчанию

    @abstractmethod
    async def _execute_impl(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: ExecutionContext
    ) -> Any:
        """
        Реализация бизнес-логики компонента (ASYNC).

        Этот метод должен быть переопределен в наследниках.

        ПАРАМЕТРЫ:
        - capability: capability для выполнения
        - parameters: параметры выполнения
        - execution_context: контекст выполнения

        ВОЗВРАЩАЕТ:
        - Результат выполнения (тип зависит от компонента)

        ПРИМЕЧАНИЕ:
        - Этот метод вызывается из async execute()
        - Используйте await для вызова async действий через executor
        """
        raise NotImplementedError(
            f"Метод _execute_impl() должен быть реализован в классе {self.__class__.__name__}"
        )

    # === НОВОЕ: Выполнение с нативным structured output ===

    async def execute_with_structured_output(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: ExecutionContext,
        llm_action_name: str = "llm.generate_structured"
    ) -> 'ExecutionResult':
        """
        Выполнение компонента с использованием нативного structured output.

        АРХИТЕКТУРА:
        - Контракты НЕ встраиваются в промпт
        - Схема передаётся через structured_output параметр
        - LLMOrchestrator решает как использовать схему (нативно или в промпт)

        ARGS:
        - capability: capability для выполнения
        - parameters: параметры выполнения
        - execution_context: контекст выполнения
        - llm_action_name: имя действия для генерации (по умолчанию "llm.generate_structured")

        RETURNS:
        - ExecutionResult: результат выполнения

        EXAMPLE:
        ```python
        result = await self.execute_with_structured_output(
            capability=cap,
            parameters=params,
            execution_context=context,
            llm_action_name="llm.generate_structured"
        )
        ```
        """
        import time
        from core.models.data.execution import ExecutionResult, ExecutionStatus
        from core.infrastructure.event_bus.unified_event_bus import EventType

        start_time = time.time()

        try:
            # === ЭТАП 1: Валидация входных данных ===
            validated_input = self.validate_input_typed(capability.name, parameters)
            if validated_input is None:
                return ExecutionResult.failure(
                    error="Input validation failed",
                    metadata={"capability": capability.name}
                )

            # === ЭТАП 2: Получение промпта БЕЗ контрактов ===
            # Контракты будут переданы отдельно через structured_output
            prompt_obj = self.get_prompt(capability.name)
            prompt_text = prompt_obj.content if prompt_obj else ""
            if not prompt_text:
                return ExecutionResult.failure(
                    error=f"Промпт для {capability.name} не найден",
                    metadata={"capability": capability.name}
                )

            # === ЭТАП 3: Получение выходной схемы ===
            output_schema = self.get_output_contract(capability.name)
            if output_schema is BaseModel:
                return ExecutionResult.failure(
                    error=f"Выходная схема для {capability.name} не загружена",
                    metadata={"capability": capability.name}
                )

            # === ЭТАП 4: Выполнение через executor с structured_output ===
            result = await self.executor.execute_action(
                action_name=llm_action_name,
                parameters={
                    "prompt": prompt_text,
                    "schema": output_schema,
                    "parameters": validated_input,
                    "use_native_structured_output": self.component_config.llm_settings.get(
                        'use_native_structured_output', True
                    )
                },
                context=execution_context
            )

            # === ЭТАП 5: Валидация выходных данных ===
            validated_output = self.validate_output_typed(capability.name, result.data if hasattr(result, 'data') else result)
            if validated_output is None:
                return ExecutionResult.failure(
                    error="Output validation failed",
                    metadata={"capability": capability.name}
                )

            # === ЭТАП 6: Публикация метрик ===
            execution_time_ms = (time.time() - start_time) * 1000
            await self._publish_metrics(
                self._get_event_type_for_success(),
                capability.name,
                True,
                execution_time_ms
            )

            return ExecutionResult.success(
                data=validated_output,
                metadata={
                    "capability": capability.name,
                    "execution_time_ms": execution_time_ms,
                    "structured_output": True
                }
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            await self._publish_metrics(
                EventType.ERROR_OCCURRED,
                capability.name,
                False,
                execution_time_ms,
                error=str(e),
                error_type=type(e).__name__
            )
            return ExecutionResult.failure(
                error=str(e),
                metadata={"capability": capability.name, "error_type": type(e).__name__}
            )

    async def shutdown(self) -> None:
        """Корректное завершение работы компонента."""
        pass