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
from typing import Dict, Any, Optional, Type

from core.agent.components.action_executor import ExecutionContext
from core.config.component_config import ComponentConfig
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult
from core.models.data.prompt import Prompt
from core.models.enums.common_enums import ComponentType
from pydantic import BaseModel
from core.agent.components.lifecycle import ComponentLifecycle, ComponentState
from core.agent.components.logging import LoggingMixin

# Интерфейсы для DI (используются только необходимые)
from core.infrastructure.interfaces.event_bus import EventBusInterface
from core.infrastructure.interfaces.metrics_log_interfaces import IMetricsStorage, ILogStorage

# Aliases для обратной совместимости
MetricsStorageInterface = IMetricsStorage
LogStorageInterface = ILogStorage


class BaseComponent(ComponentLifecycle, LoggingMixin, ABC):
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
        event_bus: 'EventBusInterface' = None  # ← Обязательный для логирования
    ):
        # Вызов конструктора ComponentLifecycle
        ComponentLifecycle.__init__(self, name)

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

        if event_bus is None:
            raise ValueError(f"Компонент '{name}' требует event_bus")

        # Сохраняем параметры
        self._application_context = application_context  # [DEPRECATED Этап 5]
        self.component_config = component_config
        self.executor = executor  # ← Критически важно!

        # ← НОВОЕ: Флаг инициализации для ActionExecutor
        self._initialized = False

        # Основные данные компонента (не кэш!)
        self.prompts: Dict[str, Prompt] = {}  # ← Объекты, не строки!
        self.input_contracts: Dict[str, Type[BaseModel]] = {}  # ← Классы схем, не словари!
        self.output_contracts: Dict[str, Type[BaseModel]] = {}

        # ← НОВОЕ: Автоматическое разделение system/user промптов
        self.system_prompts: Dict[str, Prompt] = {}  # {base_capability: Prompt}
        self.user_prompts: Dict[str, Prompt] = {}    # {base_capability: Prompt}

    @property
    def description(self) -> str:
        """Описание компонента"""
        return f"Компонент {self.name}"

    # ========================================================================
    # ЛОГИРОВАНИЕ
    # ========================================================================

    # Контекстные переменные для хранения session_id/agent_id между вызовами
    _session_id_context = None
    _agent_id_context = None

    @classmethod
    def set_execution_context(cls, session_id: str, agent_id: str):
        """Установить контекст выполнения для текущей операции."""
        cls._session_id_context = session_id
        cls._agent_id_context = agent_id

    @classmethod
    def get_execution_context(cls) -> tuple:
        """Получить текущий контекст выполнения."""
        return cls._session_id_context, cls._agent_id_context

    @classmethod
    def clear_execution_context(cls):
        """Очистить контекст выполнения."""
        cls._session_id_context = None
        cls._agent_id_context = None

    def _get_logger_init_state(self):
        """Callback для LoggingMixin: получение текущего состояния инициализации."""
        if self._state == ComponentState.READY:
            return ComponentState.READY
        elif self._state == ComponentState.INITIALIZING:
            return ComponentState.INITIALIZING
        return ComponentState.CREATED

    async def _publish_with_context(
        self,
        event_type,
        data: Dict[str, Any],
        source: str = None,
        execution_context: Optional['ExecutionContext'] = None
    ):
        """
        Публикация события с правильным session_id/agent_id из execution_context.

        ARGS:
        - event_type: тип события
        - data: данные события
        - source: источник события
        - execution_context: контекст выполнения (если None - использует class variables)

        Приоритет: execution_context > class variables > "system"
        """
        if execution_context is not None:
            session_id = getattr(execution_context, 'session_id', None)
            agent_id = getattr(execution_context, 'agent_id', None)
        else:
            session_id, agent_id = self.get_execution_context()

        if session_id is None:
            session_id = 'system'
        if agent_id is None:
            agent_id = 'system'

        await self._event_bus.publish(
            event_type=event_type,
            data=data,
            source=source,
            session_id=session_id,
            agent_id=agent_id
        )

    @property
    def application_context(self) -> Optional['ApplicationContext']:
        """Получить ApplicationContext (DEPRECATED)."""
        return self._application_context

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
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
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

            # ← НОВОЕ: Устанавливаем флаг инициализации для ActionExecutor
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

        Ресурсы УЖЕ загружены в component_config.resolved_*
        через ResourceLoader в ComponentFactory.
        """
        try:
            # Копируем промпты из resolved_prompts
            for cap_name, prompt_obj in self.component_config.resolved_prompts.items():
                self.prompts[cap_name] = prompt_obj

            # Копируем input контракты из resolved_input_contracts
            for cap_name, contract_obj in self.component_config.resolved_input_contracts.items():
                if hasattr(contract_obj, 'pydantic_schema'):
                    self.input_contracts[cap_name] = contract_obj.pydantic_schema
                else:
                    self.input_contracts[cap_name] = contract_obj

            # Копируем output контракты из resolved_output_contracts
            for cap_name, contract_obj in self.component_config.resolved_output_contracts.items():
                if hasattr(contract_obj, 'pydantic_schema'):
                    self.output_contracts[cap_name] = contract_obj.pydantic_schema
                else:
                    self.output_contracts[cap_name] = contract_obj

            return True

        except Exception as e:
            self._safe_log_sync("error", f"Ошибка предзагрузки ресурсов для '{self.name}': {e}", exc_info=True)
            return False

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
    # TTL-кэширование удалено
    # invalidate_cache() и _is_cache_expired() больше не используются
    # ========================================================================

    # === ОСНОВНЫЕ МЕТОДЫ ДОСТУПА К РЕСУРСАМ ===

    def get_prompt(self, capability_name: str) -> Prompt:
        """
        Получение промпта из кэша.

        TTL-проверки удалены — ресурсы не истекают.

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

        TTL-проверки удалены — ресурсы не истекают.

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

        TTL-проверки удалены — ресурсы не истекают.

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

        # Пропускаем валидацию для dataclass — они уже типизированы
        if hasattr(data, '__dataclass_fields__'):
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
        return prompt_obj.render(**kwargs)

    # === АБСТРАКТНЫЙ МЕТОД ВЫПОЛНЕНИЯ (БЕЗ ПРЯМЫХ ЗАВИСИМОСТЕЙ) ===

    async def execute(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: ExecutionContext
    ) -> ExecutionResult:
        """
        УНИВЕРСАЛЬНЫЙ ШАБЛОН ВЫПОЛНЕНИЯ КОМПОНЕНТА.

        НАСЛЕДНИКИ должны переопределить только _execute_impl() для своей бизнес-логики.

        ARCHITECTURE:
        - Валидация через Pydantic модели
        - Сохраняет типизацию до границ приложения
        """
        import time
        from core.models.data.execution import ExecutionResult, ExecutionStatus
        
        start_time = time.time()

        try:
            # Валидация входных данных
            validated_input = self.validate_input_typed(capability.name, parameters)
            if validated_input is None:
                execution_time_ms = (time.time() - start_time) * 1000
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error="Input validation failed",
                    metadata={"capability": capability.name, "execution_time_ms": execution_time_ms}
                )

            # Установка контекста для доступа в любом месте вызова
            self.set_execution_context(
                session_id=getattr(execution_context, 'session_id', 'system'),
                agent_id=getattr(execution_context, 'agent_id', 'system')
            )

            try:
                # Выполнение бизнес-логики
                result = await self._execute_impl(capability, validated_input, execution_context)
            finally:
                self.clear_execution_context()

            # Валидация выходных данных
            validated_output = self.validate_output_typed(capability.name, result)
            if validated_output is None:
                execution_time_ms = (time.time() - start_time) * 1000
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error="Output validation failed",
                    metadata={"capability": capability.name, "execution_time_ms": execution_time_ms}
                )

            execution_time_ms = (time.time() - start_time) * 1000
            return ExecutionResult(
                status=ExecutionStatus.COMPLETED,
                data=validated_output,
                metadata={
                    "capability": capability.name,
                    "execution_time_ms": execution_time_ms
                }
            )

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            await self._publish_with_context(
                event_type="component.execution_error",
                data={
                    "component": self.name,
                    "capability": capability.name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "execution_time_ms": execution_time_ms
                },
                source=self.name,
                execution_context=execution_context
            )
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=str(e),
                metadata={
                    "capability": capability.name,
                    "error_type": type(e).__name__,
                    "execution_time_ms": execution_time_ms
                }
            )

    @abstractmethod
    async def _execute_impl(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: ExecutionContext
    ) -> Any:
        """
        Реализация бизнес-логики компонента.

        Этот метод должен быть переопределен в наследниках.
        """
        raise NotImplementedError(
            f"Метод _execute_impl() должен быть реализован в классе {self.__class__.__name__}"
        )

    async def shutdown(self) -> None:
        """Корректное завершение работы компонента."""
        pass