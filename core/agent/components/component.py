"""
Универсальный базовый класс для всех компонентов (навыков, инструментов, сервисов, хендлеров).

АРХИТЕКТУРНЫЕ ГАРАНТИИ:
- Предзагрузка → кэш → выполнение без обращений к хранилищу
- Четкое разделение ответственностей: декларация ≠ данные ≠ реализация
- Обязательная инициализация через ComponentConfig
- Изолированные кэши для каждого экземпляра
- Взаимодействие ТОЛЬКО через ActionExecutor
- Поддержка внедрения зависимостей (DI) через интерфейсы
- Единое логирование с префиксом [ComponentType:Name]

ЖИЗНЕННЫЙ ЦИКЛ:
- Наследует LifecycleMixin для управления состояниями
- Использует LoggingMixin для логирования через event_bus
- Состояния: CREATED → INITIALIZING → READY → SHUTDOWN (или FAILED)

ПРЕИМУЩЕСТВА ПЕРЕД СТАРЫМ ПОДХОДОМ:
- Устранено дублирование кода между BaseSkill/BaseService/BaseTool
- Единая точка изменений для всех компонентов
- Консистентное логирование с автоматическим префиксом
- Прозрачная архитектура без глубокого наследования
"""
import asyncio
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Type, List

from pydantic import BaseModel

from core.agent.components.action_executor import ExecutionContext
from core.config.component_config import ComponentConfig
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.models.enums.common_enums import ComponentType
from core.agent.components.lifecycle import LifecycleMixin, ComponentState


# =============================================================================
# LOGGING MIXIN V2 - С НОВЫМ ПОДХОДОМ
# =============================================================================

class LoggingMixinV2:
    """
    Миксин логирования с автоматическим префиксом [ComponentType:Name].
    
    ИНТЕГРАЦИЯ С EVENT_BUS:
    - Все логи публикуются через event_bus.publish(EventType.XXX, {...})
    - Автоматический префикс [ComponentType:Name] в каждом сообщении
    - Поддержка sync/async режимов
    - Контекст session_id/agent_id из ExecutionContext
    
    USAGE:
    ```python
    class Component(LoggingMixinV2):
        def __init__(self, name, component_type, event_bus):
            super().__init__(component_name=name, component_type=component_type, event_bus=event_bus)
            self._log_info("Компонент создан")  # ← [Skill:MySkill] Компонент создан
    ```
    """
    
    def __init__(
        self,
        component_name: str = "unknown",
        component_type: str = "component",
        event_bus: Optional[Any] = None
    ):
        """
        Инициализация логгера.
        
        ARGS:
        - component_name: Имя компонента
        - component_type: Тип компонента (skill/service/tool/handler)
        - event_bus: EventBusInterface для публикации событий
        """
        self._component_name = component_name
        self._component_type = component_type
        self._event_bus = event_bus
        self._log_prefix = f"[{component_type.capitalize()}:{component_name}]"
        
    def _format_log_message(self, message: str) -> str:
        """Добавляет префикс компонента к сообщению."""
        return f"{self._log_prefix} {message}"
    
    async def _log_event(
        self,
        event_type: EventType,
        message: str,
        level: str = "info",
        execution_context: Optional[ExecutionContext] = None,
        **extra_data
    ):
        """
        Публикация лога через event_bus.
        
        ARGS:
        - event_type: Тип события (LOG_INFO, LOG_WARNING, LOG_ERROR, etc.)
        - message: Сообщение
        - level: Уровень логирования
        - execution_context: Контекст выполнения для session_id/agent_id
        - extra_data: Дополнительные данные
        """
        if not self._event_bus:
            # Fallback: вывод в stdout
            print(f"{self._format_log_message(message)}")
            return
        
        # Формируем данные события
        data = {
            "message": self._format_log_message(message),
            "level": level,
            "component": self._component_name,
            "component_type": self._component_type,
            **extra_data
        }
        
        # Извлекаем session_id/agent_id из execution_context
        session_id = "system"
        agent_id = "system"
        
        if execution_context is not None:
            session_id = getattr(execution_context, 'session_id', 'system')
            agent_id = getattr(execution_context, 'agent_id', 'system')
        
        # Публикуем событие
        await self._event_bus.publish(
            event_type=event_type,
            data=data,
            source=self._component_name,
            session_id=session_id,
            agent_id=agent_id
        )
    
    def _log_sync(self, level: str, message: str, **kwargs):
        """
        Синхронное логирование (для инициализации).
        
        ARGS:
        - level: Уровень логирования (info, debug, warning, error)
        - message: Сообщение
        - **kwargs: Дополнительные данные
        """
        formatted_message = self._format_log_message(message)
        
        # Вывод в stdout для синхронного режима
        if level == "error":
            print(f"[ERROR] {formatted_message}")
        elif level == "warning":
            print(f"[WARNING] {formatted_message}")
        elif level == "debug":
            print(f"[DEBUG] {formatted_message}")
        else:
            print(f"[INFO] {formatted_message}")
    
    async def _log_info(self, message: str, execution_context: Optional[ExecutionContext] = None, **kwargs):
        """Логирование уровня INFO."""
        await self._log_event(
            EventType.LOG_INFO,
            message,
            level="info",
            execution_context=execution_context,
            **kwargs
        )
    
    async def _log_debug(self, message: str, execution_context: Optional[ExecutionContext] = None, **kwargs):
        """Логирование уровня DEBUG."""
        await self._log_event(
            EventType.LOG_DEBUG,
            message,
            level="debug",
            execution_context=execution_context,
            **kwargs
        )
    
    async def _log_warning(self, message: str, execution_context: Optional[ExecutionContext] = None, **kwargs):
        """Логирование уровня WARNING."""
        await self._log_event(
            EventType.LOG_WARNING,
            message,
            level="warning",
            execution_context=execution_context,
            **kwargs
        )
    
    async def _log_error(self, message: str, execution_context: Optional[ExecutionContext] = None, exc_info: bool = False, **kwargs):
        """Логирование уровня ERROR."""
        if exc_info and kwargs.get('exception'):
            message = f"{message}: {kwargs['exception']}"
        
        await self._log_event(
            EventType.LOG_ERROR,
            message,
            level="error",
            execution_context=execution_context,
            **kwargs
        )


# =============================================================================
# UNIVERSAL COMPONENT
# =============================================================================

class Component(LifecycleMixin, LoggingMixinV2, ABC):
    """
    УНИВЕРСАЛЬНЫЙ БАЗОВЫЙ КЛАСС ДЛЯ ВСЕХ КОМПОНЕНТОВ.
    
    ЗАМЕНЯЕТ:
    - BaseComponent
    - BaseSkill
    - BaseService
    - BaseTool
    
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
    class MySkill(Component):
        def __init__(self, name, config, executor, event_bus):
            super().__init__(
                name=name,
                component_type="skill",
                component_config=config,
                executor=executor,
                event_bus=event_bus
            )
        
        async def _execute_impl(self, capability, parameters, context):
            # Ваша бизнес-логика здесь
            return {"result": "done"}
    ```
    
    АТРИБУТЫ:
    - name: имя компонента
    - component_type: тип компонента (skill/service/tool/handler)
    - component_config: конфигурация компонента с версиями ресурсов
    - executor: ActionExecutor для взаимодействия с другими компонентами
    - prompts: кэш промптов (объекты Prompt)
    - input_contracts: кэш входных контрактов (классы Pydantic)
    - output_contracts: кэш выходных контрактов (классы Pydantic)
    """

    def __init__(
        self,
        name: str,
        component_type: str,
        component_config: ComponentConfig,
        executor: Any,
        event_bus: Any,
        application_context: Optional[Any] = None
    ):
        """
        Инициализация компонента.
        
        ARGS:
        - name: Имя компонента
        - component_type: Тип компонента (skill/service/tool/handler)
        - component_config: Конфигурация компонента
        - executor: ActionExecutor для взаимодействия
        - event_bus: EventBusInterface для логирования
        - application_context: ApplicationContext (DEPRECATED)
        """
        # Инициализация LifecycleMixin
        LifecycleMixin.__init__(self, name)
        
        # Инициализация LoggingMixinV2
        LoggingMixinV2.__init__(
            self,
            component_name=name,
            component_type=component_type,
            event_bus=event_bus
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
        self._application_context = application_context
        self.component_config = component_config
        self.executor = executor
        
        # Флаг инициализации
        self._initialized = False
        
        # Основные данные компонента (не кэш!)
        self.prompts: Dict[str, Any] = {}
        self.input_contracts: Dict[str, Type[BaseModel]] = {}
        self.output_contracts: Dict[str, Type[BaseModel]] = {}
        
        # Автоматическое разделение system/user промптов
        self.system_prompts: Dict[str, Any] = {}
        self.user_prompts: Dict[str, Any] = {}
    
    @property
    def description(self) -> str:
        """Описание компонента."""
        return f"Компонент {self.name} ({self._component_type})"
    
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
        current_time = time.time()
        
        # Проверка: нельзя инициализировать повторно
        if self._state == ComponentState.READY:
            await self._log_warning(f"Компонент уже инициализирован")
            return True
        
        # Переход в состояние INITIALIZING
        await self._transition_to(ComponentState.INITIALIZING)
        
        # Синхронный лог о начале инициализации
        self._log_sync("info", "Начало инициализации")
        
        try:
            # === ЭТАП 1: Предзагрузка ресурсов ===
            if not await self._preload_resources():
                self._log_sync("error", "Предзагрузка ресурсов не удалась")
                await self._transition_to(ComponentState.FAILED)
                return False
            
            # === ЭТАП 2: Валидация загруженных ресурсов ===
            if not await self._validate_loaded_resources():
                self._log_sync("error", "Валидация загруженных ресурсов не пройдена")
                await self._transition_to(ComponentState.FAILED)
                return False
            
            # Успешная инициализация
            self._log_sync("info", 
                f"Компонент полностью инициализирован. "
                f"Ресурсы: промпты={len(self.prompts)}, "
                f"input_contracts={len(self.input_contracts)}, "
                f"output_contracts={len(self.output_contracts)}"
            )
            
            # Переход в состояние READY
            await self._transition_to(ComponentState.READY)
            self._initialized = True
            
            return True
        
        except Exception as e:
            self._log_sync("error", f"Ошибка инициализации: {e}", exception=e)
            await self._transition_to(ComponentState.FAILED)
            return False
    
    async def _preload_resources(self) -> bool:
        """
        Предзагрузка ресурсов компонента.
        
        [REFACTOR v5.4.0] Ресурсы УЖЕ загружены в component_config.resolved_*
        через ResourcePreloader в ComponentFactory.
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
            self._log_sync("error", f"Ошибка предзагрузки ресурсов: {e}", exc_info=True)
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
        
        missing_input = output_caps - input_caps
        missing_output = input_caps - output_caps
        
        if missing_input:
            errors.append(f"Отсутствуют input контракты для: {missing_input}")
        if missing_output:
            errors.append(f"Отсутствуют output контракты для: {missing_output}")
        
        # Проверка critical_resources
        if hasattr(self.component_config, 'critical_resources'):
            critical = self.component_config.critical_resources
            
            if critical.get('prompts', False):
                for capability in self.component_config.prompt_versions.keys():
                    if capability not in self.prompts:
                        errors.append(f"Критичный промпт '{capability}' не загружен")
            
            if critical.get('input_contracts', False):
                for capability in self.component_config.input_contract_versions.keys():
                    if capability not in self.input_contracts:
                        errors.append(f"Критичный input контракт '{capability}' не загружен")
            
            if critical.get('output_contracts', False):
                for capability in self.component_config.output_contract_versions.keys():
                    if capability not in self.output_contracts:
                        errors.append(f"Критичный output контракт '{capability}' не загружен")
        
        # Логирование ошибок
        if errors:
            for error in errors:
                self._log_sync("error", error)
            return False
        
        return True
    
    async def execute(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        execution_context: Optional[ExecutionContext] = None
    ) -> ExecutionResult:
        """
        УНИВЕРСАЛЬНЫЙ ШАБЛОН ВЫПОЛНЕНИЯ КОМПОНЕНТА.
        
        ЭТАПЫ:
        1. Проверка готовности компонента
        2. Валидация входных данных через input_contract
        3. Выполнение бизнес-логики (_execute_impl)
        4. Валидация выходных данных через output_contract
        5. Публикация метрик и логов
        6. Возврат ExecutionResult
        
        ARGS:
        - capability: Capability для выполнения
        - parameters: Параметры выполнения
        - execution_context: Контекст выполнения
        
        RETURNS:
        - ExecutionResult с результатом выполнения
        """
        start_time = time.time()
        
        # Этап 1: Проверка готовности
        if not self.is_ready:
            error_msg = f"Компонент не готов к выполнению (state={self._state.value})"
            self._log_sync("error", error_msg)
            return ExecutionResult(
                success=False,
                error=error_msg,
                status=ExecutionStatus.FAILED
            )
        
        try:
            # Этап 2: Валидация входных данных
            validated_params = await self._validate_input(capability, parameters)
            
            # Этап 3: Выполнение бизнес-логики
            result = await self._execute_impl(capability, validated_params, execution_context)
            
            # Этап 4: Валидация выходных данных
            validated_result = await self._validate_output(capability, result)
            
            # Этап 5: Публикация метрик
            execution_time_ms = (time.time() - start_time) * 1000
            await self._publish_metrics(
                capability=capability,
                success=True,
                execution_time_ms=execution_time_ms,
                execution_context=execution_context
            )
            
            # Этап 6: Возврат результата
            return ExecutionResult(
                success=True,
                data=validated_result,
                status=ExecutionStatus.SUCCESS,
                execution_time_ms=execution_time_ms
            )
        
        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            error_msg = f"Ошибка выполнения: {e}"
            
            self._log_sync("error", error_msg, exception=e)
            
            await self._publish_metrics(
                capability=capability,
                success=False,
                execution_time_ms=execution_time_ms,
                error=str(e),
                execution_context=execution_context
            )
            
            return ExecutionResult(
                success=False,
                error=error_msg,
                status=ExecutionStatus.FAILED,
                execution_time_ms=execution_time_ms
            )
    
    async def _validate_input(
        self,
        capability: Capability,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Валидация входных данных через input_contract."""
        cap_name = capability.name
        
        if cap_name in self.input_contracts:
            schema = self.input_contracts[cap_name]
            try:
                return schema.model_validate(parameters)
            except Exception as e:
                raise ValueError(f"Валидация входных данных не пройдена: {e}")
        
        return parameters
    
    async def _validate_output(
        self,
        capability: Capability,
        result: Any
    ) -> Any:
        """Валидация выходных данных через output_contract."""
        cap_name = capability.name
        
        if cap_name in self.output_contracts:
            schema = self.output_contracts[cap_name]
            try:
                return schema.model_validate(result)
            except Exception:
                # Если валидация не прошла, возвращаем как dict
                if hasattr(result, 'model_dump'):
                    return result.model_dump()
                return result
        
        return result
    
    @abstractmethod
    async def _execute_impl(
        self,
        capability: Capability,
        parameters: Dict[str, Any],
        execution_context: Optional[ExecutionContext]
    ) -> Any:
        """
        Реализация бизнес-логики компонента.
        
        Переопределяется в наследниках для конкретной реализации.
        
        ARGS:
        - capability: Capability для выполнения
        - parameters: Параметры выполнения (после валидации)
        - execution_context: Контекст выполнения
        
        RETURNS:
        - Результат выполнения (Dict или Pydantic модель)
        """
        pass
    
    async def _publish_metrics(
        self,
        capability: Capability,
        success: bool,
        execution_time_ms: float,
        execution_context: Optional[ExecutionContext] = None,
        **extra_data
    ):
        """Публикация метрик выполнения."""
        if not self._event_bus:
            return
        
        data = {
            "component": self._component_name,
            "component_type": self._component_type,
            "capability": capability.name,
            "success": success,
            "execution_time_ms": execution_time_ms,
            **extra_data
        }
        
        event_type = EventType.SKILL_EXECUTED if success else EventType.ERROR_OCCURRED
        
        await self._log_event(
            event_type=event_type,
            message=f"Выполнение {capability.name}: {'успешно' if success else 'ошибка'} ({execution_time_ms:.2f}ms)",
            level="info" if success else "error",
            execution_context=execution_context,
            **data
        )
    
    async def shutdown(self):
        """Завершение работы компонента."""
        await self._transition_to(ComponentState.SHUTDOWN)
        self._log_sync("info", "Компонент завершил работу")
    
    async def restart(self) -> bool:
        """Перезапуск компонента."""
        await self.shutdown()
        self._state = ComponentState.CREATED
        return await self.initialize()
    
    # Utility methods
    def get_prompt(self, capability_name: str) -> Optional[Any]:
        """Получение промпта по имени capability."""
        return self.prompts.get(capability_name)
    
    def get_input_contract(self, capability_name: str) -> Optional[Type[BaseModel]]:
        """Получение входного контракта по имени capability."""
        return self.input_contracts.get(capability_name)
    
    def get_output_contract(self, capability_name: str) -> Optional[Type[BaseModel]]:
        """Получение выходного контракта по имени capability."""
        return self.output_contracts.get(capability_name)
