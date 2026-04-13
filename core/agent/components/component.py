"""
Универсальный базовый класс для всех компонентов (навыков, инструментов, сервисов, хендлеров).

АРХИТЕКТУРНЫЕ ГАРАНТИИ:
- Предзагрузка → кэш → выполнение без обращений к хранилищу
- Четкое разделение ответственностей: декларация ≠ данные ≠ реализация
- Обязательная инициализация через ComponentConfig
- Изолированные кэши для каждого экземпляра
- Взаимодействие ТОЛЬКО через ActionExecutor
- Поддержка внедрения зависимостей (DI) через интерфейсы
- Единое логирование через стандартный logging с LogEventType

ЖИЗНЕННЫЙ ЦИКЛ:
- Наследует LifecycleMixin для управления состояниями
- ComponentLogger: логирование через LoggingSession + LogEventType
- Состояния: CREATED → INITIALIZING → READY → SHUTDOWN (или FAILED)

ПРЕИМУЩЕСТВА ПЕРЕД СТАРЫМ ПОДХОДОМ:
- Устранено дублирование кода между BaseSkill/BaseService/BaseTool
- Единая точка изменений для всех компонентов
- Консистентное логирование с автоматическим префиксом
- Прозрачная архитектура без глубокого наследования
- Логирование через стандартный logging + LogEventType
"""
import asyncio
import logging
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Type, List

from pydantic import BaseModel

from core.agent.components.action_executor import ExecutionContext
from core.config.component_config import ComponentConfig
from core.infrastructure.logging.event_types import LogEventType
from core.models.data.capability import Capability
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.agent.components.lifecycle import ComponentLifecycle
from core.models.enums.component_status import ComponentStatus


# =============================================================================
# LOGGING MIXIN - LOGGING ЧЕРЕЗ LOGGINGSESSION
# =============================================================================

class ComponentLogger:
    """
    Логгер компонента с автоматическим префиксом [ComponentType:Name].

    АРХИТЕКТУРА:
    - Логгер создаётся через LoggingSession.get_component_logger()
    - Файловый хендлер: components.log
    - Консольный хендлер: с EventTypeFilter
    - Все записи содержат extra={"event_type": LogEventType.XXX}
    """

    def __init__(
        self,
        component_name: str = "unknown",
        component_type: str = "component",
        log_session=None,
    ):
        """
        Инициализация логгера.

        ARGS:
        - component_name: Имя компонента
        - component_type: Тип компонента (skill/service/tool/handler)
        - log_session: LoggingSession для создания логгера
        """
        self._component_name = component_name
        self._component_type = component_type
        self._log_prefix = f"[{component_type.capitalize()}:{component_name}]"
        self._log_session = log_session

        # Создаём логгер через LoggingSession (имеет файловые хендлеры)
        if log_session is not None:
            self._logger: logging.LoggerAdapter = log_session.get_component_logger(f"{component_type}.{component_name}")
        else:
            # Fallback: обычный logging.getLogger (без файловых хендлеров)
            self._logger: logging.LoggerAdapter = logging.LoggerAdapter(
                logging.getLogger(f"{component_type}.{component_name}"),
                extra={"component": f"{component_type}.{component_name}"}
            )

    def _format_log_message(self, message: str) -> str:
        """Добавляет префикс компонента к сообщению."""
        return f"{self._log_prefix} {message}"

    def _log_info(self, message: str, event_type: LogEventType = LogEventType.INFO, **extra_data):
        """
        Логирование уровня INFO.
        
        ARGS:
        - message: Сообщение
        - event_type: Тип события для фильтрации в консоли
        - extra_data: Дополнительные данные для extra
        """
        formatted_message = self._format_log_message(message)
        self._logger.info(
            formatted_message,
            extra={"event_type": event_type, **extra_data}
        )

    def _log_debug(self, message: str, event_type: LogEventType = LogEventType.DEBUG, **extra_data):
        """
        Логирование уровня DEBUG.
        
        ARGS:
        - message: Сообщение
        - event_type: Тип события для фильтрации в консоли
        - extra_data: Дополнительные данные для extra
        """
        formatted_message = self._format_log_message(message)
        self._logger.debug(
            formatted_message,
            extra={"event_type": event_type, **extra_data}
        )

    def _log_warning(self, message: str, event_type: LogEventType = LogEventType.WARNING, **extra_data):
        """
        Логирование уровня WARNING.
        
        ARGS:
        - message: Сообщение
        - event_type: Тип события для фильтрации в консоли
        - extra_data: Дополнительные данные для extra
        """
        formatted_message = self._format_log_message(message)
        self._logger.warning(
            formatted_message,
            extra={"event_type": event_type, **extra_data}
        )

    def _log_error(self, message: str, event_type: LogEventType = LogEventType.ERROR, exc_info: bool = False, **extra_data):
        """
        Логирование уровня ERROR.

        ARGS:
        - message: Сообщение
        - event_type: Тип события для фильтрации в консоли
        - exc_info: Включить traceback исключения
        - extra_data: Дополнительные данные для extra
        """
        formatted_message = self._format_log_message(message)
        self._logger.error(
            formatted_message,
            extra={"event_type": event_type, **extra_data},
            exc_info=exc_info
        )

    def _log_sync(self, level: str, message: str, exception: Optional[Exception] = None, **extra_data):
        """
        Универсальный метод логирования для синхронного использования.

        ARGS:
        - level: Уровень логирования ('info', 'debug', 'warning', 'error')
        - message: Сообщение
        - exception: Исключение для traceback (опционально)
        - extra_data: Дополнительные данные для extra
        """
        formatted_message = self._format_log_message(message)
        event_type_map = {
            'info': LogEventType.INFO,
            'debug': LogEventType.DEBUG,
            'warning': LogEventType.WARNING,
            'error': LogEventType.ERROR,
        }
        event_type = event_type_map.get(level, LogEventType.INFO)
        extra = {"event_type": event_type, **extra_data}

        if level == 'error' and exception:
            self._logger.exception(formatted_message, extra=extra)
        else:
            log_func = getattr(self._logger, level, self._logger.info)
            log_func(formatted_message, extra=extra)


# =============================================================================
# UNIVERSAL COMPONENT
# =============================================================================

class Component(ComponentLifecycle, ComponentLogger, ABC):
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
        def __init__(self, name, config, executor):
            super().__init__(
                name=name,
                component_type="skill",
                component_config=config,
                executor=executor
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
        application_context: Optional[Any] = None
    ):
        """
        Инициализация компонента.

        ARGS:
        - name: Имя компонента
        - component_type: Тип компонента (skill/service/tool/handler)
        - component_config: Конфигурация компонента
        - executor: ActionExecutor для взаимодействия
        - application_context: ApplicationContext (опционально для доступа к ресурсам)
        """
        # Инициализация ComponentLifecycle
        ComponentLifecycle.__init__(self, name)

        # Получаем log_session из application_context
        log_session = None
        if application_context is not None:
            infra = getattr(application_context, 'infrastructure_context', None)
            if infra is not None:
                log_session = getattr(infra, 'log_session', None)

        # Инициализация ComponentLogger
        ComponentLogger.__init__(
            self,
            component_name=name,
            component_type=component_type,
            log_session=log_session,
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

    @property
    def application_context(self):
        """Доступ к ApplicationContext (только для чтения)."""
        return self._application_context

    @application_context.setter
    def application_context(self, value):
        """Установка ApplicationContext."""
        self._application_context = value

    async def _publish_with_context(self, event_type: str, data: Dict[str, Any] = None, source: str = None):
        """
        Публикация события через event_bus (если доступен).

        ARGS:
        - event_type: Тип события
        - data: Данные события
        - source: Источник события
        """
        try:
            if self._application_context is not None:
                infra = getattr(self._application_context, 'infrastructure_context', None)
                if infra is not None:
                    event_bus = getattr(infra, 'event_bus', None)
                    if event_bus is not None:
                        await event_bus.publish(event_type, data=data, session_id=getattr(infra, 'id', 'unknown'))
        except Exception as e:
            # Тихое игнорирование ошибок публикации — не критично, но логируем для отладки
            self._logger.debug(f"_publish_with_context ошибка: {e}")

    def _safe_log_sync(self, level: str, message: str, **kwargs):
        """
        Безопасный синхронный вызов логирования.

        ARGS:
        - level: Уровень логирования ('info', 'debug', 'warning', 'error')
        - message: Сообщение
        - kwargs: Дополнительные параметры
        """
        try:
            self._log_sync(level, message, **kwargs)
        except Exception:
            # Тихое игнорирование ошибок логирования
            pass
    
    async def initialize(self) -> bool:
        """
        ЕДИНСТВЕННЫЙ метод инициализации — получает ресурсы ИЗ КОНФИГУРАЦИИ,
        НЕ обращаясь к сервисам напрямую.

        ВАЖНО: Все ресурсы уже загружены в component_config на уровне
        ApplicationContext.initialize().

        ЖИЗНЕННЫЙ ЦИКЛ:
        - Переводит компонент в состояние INITIALIZING
        - При успехе: READY
        - При ошибке: FAILED
        """
        current_time = time.time()

        # Проверка: нельзя инициализировать повторно
        if self._state == ComponentStatus.READY:
            self._log_warning(f"Компонент уже инициализирован", event_type=LogEventType.SYSTEM_INIT)
            return True

        # Переход в состояние INITIALIZING
        await self._transition_to(ComponentStatus.INITIALIZING)

        # Лог о начале инициализации
        self._log_info("Начало инициализации", event_type=LogEventType.SYSTEM_INIT)

        try:
            # === ЭТАП 1: Предзагрузка ресурсов ===
            if not await self._preload_resources():
                self._log_error("Предзагрузка ресурсов не удалась", event_type=LogEventType.SYSTEM_ERROR)
                await self._transition_to(ComponentStatus.FAILED)
                return False

            # === ЭТАП 2: Валидация загруженных ресурсов ===
            if not await self._validate_loaded_resources():
                self._log_error("Валидация загруженных ресурсов не пройдена", event_type=LogEventType.SYSTEM_ERROR)
                await self._transition_to(ComponentStatus.FAILED)
                return False

            # Успешная инициализация
            self._log_info(
                f"Компонент полностью инициализирован. "
                f"Ресурсы: промпты={len(self.prompts)}, "
                f"input_contracts={len(self.input_contracts)}, "
                f"output_contracts={len(self.output_contracts)}",
                event_type=LogEventType.SYSTEM_READY
            )

            # Переход в состояние READY
            await self._transition_to(ComponentStatus.READY)
            self._initialized = True

            return True

        except Exception as e:
            self._log_error(f"Ошибка инициализации: {e}", event_type=LogEventType.SYSTEM_ERROR, exc_info=True)
            await self._transition_to(ComponentStatus.FAILED)
            return False
    
    async def _preload_resources(self) -> bool:
        """
        Предзагрузка ресурсов компонента.
        
        Ресурсы УЖЕ загружены в component_config.resolved_*
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
            self._log_error(f"Ошибка предзагрузки ресурсов: {e}", event_type=LogEventType.SYSTEM_ERROR, exc_info=True)
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
                self._log_error(error, event_type=LogEventType.SYSTEM_ERROR)
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
            self._log_error(error_msg, event_type=LogEventType.SYSTEM_ERROR)
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
            return ExecutionResult.success(
                data=validated_result,
                metadata={"execution_time_ms": execution_time_ms}
            )
        
        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            error_msg = f"Ошибка выполнения: {e}"

            self._log_error(error_msg, event_type=LogEventType.SYSTEM_ERROR, exc_info=True)

            await self._publish_metrics(
                capability=capability,
                success=False,
                execution_time_ms=execution_time_ms,
                error=str(e),
                execution_context=execution_context
            )
            
            return ExecutionResult.failure(
                error=error_msg,
                metadata={"execution_time_ms": execution_time_ms}
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
        capability: Optional[Capability],
        success: bool,
        execution_time_ms: float,
        execution_context: Optional[ExecutionContext] = None,
        **extra_data
    ):
        """Публикация метрик выполнения."""
        # Метрики теперь публикуются через EventBus отдельно (если нужно)
        # Логи выполнения — через стандартный logging
        
        # Если event_type передан в extra_data — используем его, иначе дефолтный
        event_type = extra_data.get(
            'event_type',
            LogEventType.TOOL_CALL if success else LogEventType.TOOL_ERROR
        )
        
        capability_name = capability.name if capability else extra_data.get('capability_name', 'unknown')

        self._log_info(
            f"Выполнение {capability_name}: {'успешно' if success else 'ошибка'} ({execution_time_ms:.2f}ms)",
            event_type=event_type,
            **extra_data
        )

    async def shutdown(self):
        """Завершение работы компонента."""
        await self._transition_to(ComponentStatus.SHUTDOWN)
        self._log_info("Компонент завершил работу", event_type=LogEventType.SYSTEM_SHUTDOWN)

    async def restart(self) -> bool:
        """Перезапуск компонента."""
        await self.shutdown()
        self._state = ComponentStatus.CREATED
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
