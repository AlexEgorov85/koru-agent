"""
ЕДИНСТВЕННЫЙ ПОСРЕДНИК ДЛЯ ВЗАИМОДЕЙСТВИЯ КОМПОНЕНТОВ.

ГАРАНТИИ:
- Изоляция компонентов друг от друга
- Контроль зависимостей и порядка выполнения
- Единая точка для метрик и логирования
- Возможность внедрения мидлварей (ретраи, рейт-лимиты)

АРХИТЕКТУРНЫЙ ПРИНЦИП:
- Сохранение типизации Pydantic моделей до границ приложения
- Сериализация (model_dump) только на границах (EventBus/Storage/API)
- Generic тип T для data позволяет сохранять тип модели
"""
import asyncio
import logging
from typing import Dict, Any, Optional

from core.components.services.validation_service import ValidationService
from core.infrastructure.logging.event_types import LogEventType
from core.models.data.execution import ExecutionResult, ExecutionStatus, ExecutionStatus, ExecutionStatus
from core.models.data.capability import Capability

_module_logger = logging.getLogger(__name__)


class ExecutionContext:
    """Контекст выполнения для компонентов"""
    def __init__(
        self,
        session_context: Any = None,
        user_context: Any = None,
        available_capabilities: list = None,
        session_id: str = "system",
        agent_id: str = "system"
    ):
        self.session_context = session_context
        self.user_context = user_context
        self.available_capabilities = available_capabilities or []
        self.session_id = session_id
        self.agent_id = agent_id


class ActionExecutor:
    """
    ЕДИНСТВЕННЫЙ ПОСРЕДНИК ДЛЯ ВЗАИМОДЕЙСТВИЯ КОМПОНЕНТОВ.

    ГАРАНТИИ:
    - Изоляция компонентов друг от друга
    - Контроль зависимостей и порядка выполнения
    - Единая точка для метрик и логирования
    - Возможность внедрения мидлварей (ретраи, рейт-лимиты)
    """

    def __init__(self, application_context: 'ApplicationContext'):
        self.application_context = application_context
        self._event_bus = None
        self._log_session = None
        try:
            if hasattr(application_context, 'infrastructure_context'):
                self._event_bus = getattr(application_context.infrastructure_context, 'event_bus', None)
                self._log_session = getattr(application_context.infrastructure_context, 'log_session', None)
        except Exception:
            pass

    def _get_executor_logger(self):
        """Получить логгер для ActionExecutor."""
        if self._log_session is not None:
            return self._log_session.app_logger
        return _module_logger

    def _log_debug(self, msg: str, *args, event_type=None, **kwargs):
        """Отладочное логирование."""
        logger = self._get_executor_logger()
        extra = kwargs.pop("extra", {})
        if event_type:
            extra["event_type"] = event_type
        logger.debug(msg, *args, extra=extra, **kwargs)

    def _log_info(self, msg: str, *args, event_type=None, **kwargs):
        """Информационное логирование."""
        logger = self._get_executor_logger()
        extra = kwargs.pop("extra", {})
        if event_type:
            extra["event_type"] = event_type
        logger.info(msg, *args, extra=extra, **kwargs)

    def _log_error(self, msg: str, *args, event_type=None, exc_info=False, **kwargs):
        """Логирование ошибок."""
        logger = self._get_executor_logger()
        extra = kwargs.pop("extra", {})
        if event_type:
            extra["event_type"] = event_type
        logger.error(msg, *args, extra=extra, exc_info=exc_info, **kwargs)
    
    async def execute_action(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        context: ExecutionContext
    ) -> ExecutionResult:
        """
        Выполнение действия через ActionExecutor.
        """
        # Детальное логирование запуска действия
        self._log_info(
            f"⚙️ [Executor.execute_action] Запуск действия: {action_name}",
            event_type=LogEventType.TOOL_CALL
        )
        self._log_debug(
            f"🔵 [Executor.execute_action] Параметры: {parameters}",
            event_type=LogEventType.TOOL_CALL
        )

        try:
            # 1. Обработка действий контекста (context.*)
            if action_name.startswith("context."):
                return await self._execute_context_action(action_name, parameters, context)

            # 2. Обработка LLM действий (llm.*)
            if action_name.startswith("llm."):
                return await self._execute_llm_action(action_name, parameters, context)

            # 3. Обработка действий валидации (validation.*)
            if action_name.startswith("validation."):
                return await self._execute_validation_action(action_name, parameters, context)

            # 4. Находим целевой компонент по имени действия
            target_component, component_type = self._resolve_component_for_action(action_name)

            if not target_component:
                self._log_error(
                    f"❌ [Executor.execute_action] Компонент для действия '{action_name}' не найден",
                    event_type=LogEventType.TOOL_ERROR
                )
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Компонент для действия '{action_name}' не найден"
                )

            self._log_debug(
                f"📦 [Executor.execute_action] Компонент найден: {target_component.name} (тип={component_type})",
                event_type=LogEventType.TOOL_CALL
            )

            # 5. Проверяем, что компонент инициализирован
            if not hasattr(target_component, '_initialized') or not target_component._initialized:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Компонент '{target_component.name}' не инициализирован"
                )

            # 5. Выполняем компонент в зависимости от типа
            if component_type == "service":
                # Сервисы: вызываем метод напрямую по имени действия
                result = await self._execute_service_action(target_component, action_name, parameters, context)
            elif component_type == "tool":
                # Инструменты: вызываем метод напрямую по имени действия
                result = await self._execute_tool_action(target_component, action_name, parameters, context)
            else:
                # Навыки и behavior: используем capability
                result = await self._execute_skill_or_behavior_action(target_component, action_name, parameters, context)

            # Логируем результат выполнения
            if result.status == ExecutionStatus.COMPLETED:
                self._log_info(
                    f"✅ [Executor.execute_action] Действие {action_name} выполнено успешно",
                    event_type=LogEventType.TOOL_RESULT
                )
                self._log_debug(
                    f"🟢 [Executor.execute_action] Результат {action_name}: {str(result.data) if result.data else 'None'}",
                    event_type=LogEventType.TOOL_RESULT
                )
            else:
                self._log_error(
                    f"❌ [Executor.execute_action] Действие {action_name} завершилось с ошибкой: {result.error}",
                    event_type=LogEventType.TOOL_ERROR
                )

            return result

        except Exception as e:
            _module_logger.error(
                f"Ошибка выполнения действия '{action_name}': {e}",
                extra={"event_type": LogEventType.ERROR},
                exc_info=True
            )
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=str(e)
            )

    def execute_sync(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        context: ExecutionContext
    ) -> asyncio.Future:
        """
        Синхронное выполнение действия (возвращает Future для блокирующего ожидания).

        ИСПОЛЬЗОВАНИЕ:
        ```python
        # В синхронном _execute_impl():
        future = self.executor.execute_sync("llm.generate", {...}, context)
        result = future.result(timeout=30)  # Блокирующее ожидание
        ```

        ARGS:
        - action_name: имя действия для выполнения
        - parameters: параметры выполнения
        - context: контекст выполнения

        RETURNS:
        - asyncio.Future: Future с результатом ExecutionResult
        """
        # Получаем текущий event loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # Если нет running loop, создаём новый
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Создаём coroutine
        coro = self.execute_action(action_name, parameters, context)

        # Запускаем в event loop и возвращаем Future
        future = asyncio.run_coroutine_threadsafe(coro, loop)

        return future

    async def _execute_context_action(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        context: ExecutionContext
    ) -> ExecutionResult:
        """
        Выполнение действий контекста (context.*).

        Поддерживаемые действия:
        - context.record_plan: сохранение плана в контекст
        - context.get_current_plan: получение текущего плана
        - context.get_context_item: получение элемента контекста по ID
        - context.get_all_items: получение всех элементов контекста
        - context.get_step_history: получение истории шагов
        - context.record_action: запись действия в контекст
        - context.record_observation: запись наблюдения в контекст
        """
        # Извлекаем session_context с защитой от вложенного ExecutionContext
        from core.session_context.session_context import SessionContext

        if isinstance(context, SessionContext):
            session_context = context
        elif isinstance(context, ExecutionContext):
            raw_sc = context.session_context
            if isinstance(raw_sc, SessionContext):
                session_context = raw_sc
            else:
                session_context = getattr(raw_sc, 'session_context', None) if raw_sc else None
        else:
            # Пробуем разные варианты
            session_context = getattr(context, 'session_context', None)
            if isinstance(session_context, ExecutionContext):
                session_context = getattr(session_context, 'session_context', None)

        if not session_context:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error="session_context не доступен для выполнения действия контекста"
            )

        try:
            if action_name == "context.record_plan":
                return await self._context_record_plan(parameters, session_context)
            elif action_name == "context.get_current_plan":
                return self._context_get_current_plan(parameters, session_context)
            elif action_name == "context.get_context_item":
                return self._context_get_context_item(parameters, session_context)
            elif action_name == "context.get_all_items":
                return self._context_get_all_items(parameters, session_context)
            elif action_name == "context.get_step_history":
                return self._context_get_step_history(parameters, session_context)
            elif action_name == "context.record_action":
                return self._context_record_action(parameters, session_context)
            elif action_name == "context.record_observation":
                return self._context_record_observation(parameters, session_context)
            # НОВЫЕ ДЕЙСТВИЯ для изоляции компонентов
            elif action_name == "context.get_goal":
                return self._context_get_goal(parameters, session_context)
            elif action_name == "context.get_summary":
                return self._context_get_summary(parameters, session_context)
            elif action_name == "context.get_recent_errors":
                return self._context_get_recent_errors(parameters, session_context)
            elif action_name == "context.get_current_step":
                return self._context_get_current_step(parameters, session_context)
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Неизвестное действие контекста: {action_name}"
                )
        except Exception as e:
            _module_logger.error(
                f"Ошибка выполнения действия контекста '{action_name}': {e}",
                extra={"event_type": LogEventType.ERROR},
                exc_info=True
            )
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=f"Ошибка действия контекста: {str(e)}"
            )

    async def _context_record_plan(
        self,
        parameters: Dict[str, Any],
        session_context
    ) -> ExecutionResult:
        """Сохранение плана в контекст"""
        plan_data = parameters.get("plan_data")
        plan_type = parameters.get("plan_type", "initial")
        metadata = parameters.get("metadata")

        if not plan_data:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error="plan_data не указан для сохранения плана"
            )

        item_id = session_context.record_plan(
            plan_data=plan_data,
            plan_type=plan_type,
            metadata=metadata
        )

        return ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            data={"item_id": item_id},
            metadata={"plan_type": plan_type}
        )

    def _context_get_current_plan(
        self,
        parameters: Dict[str, Any],
        session_context
    ) -> ExecutionResult:
        """Получение текущего плана"""
        plan = session_context.get_current_plan()

        if not plan:
            return ExecutionResult(
                status=ExecutionStatus.COMPLETED,
                data=None,
                metadata={"exists": False, "message": "Текущий план не найден"}
            )

        return ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            data=plan.content if hasattr(plan, 'content') else plan,
            metadata={
                "exists": True,
                "item_id": plan.item_id if hasattr(plan, 'item_id') else None,
                "item_type": plan.item_type if hasattr(plan, 'item_type') else None
            }
        )

    def _context_get_context_item(
        self,
        parameters: Dict[str, Any],
        session_context
    ) -> ExecutionResult:
        """Получение элемента контекста по ID"""
        item_id = parameters.get("item_id")
        raise_on_missing = parameters.get("raise_on_missing", False)

        if not item_id:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error="item_id не указан для получения элемента контекста"
            )

        item = session_context.get_context_item(item_id, raise_on_missing=raise_on_missing)

        if not item:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=f"Элемент контекста с ID {item_id} не найден",
                metadata={"item_id": item_id}
            )

        return ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            data={
                "item_id": item.item_id if hasattr(item, 'item_id') else item_id,
                "content": item.content if hasattr(item, 'content') else item,
                "item_type": item.item_type if hasattr(item, 'item_type') else None
            },
            metadata={"item_id": item_id}
        )

    def _context_get_all_items(
        self,
        parameters: Dict[str, Any],
        session_context
    ) -> ExecutionResult:
        """Получение всех элементов контекста"""
        try:
            # Проверяем тип session_context для отладки
            has_data_context = hasattr(session_context, 'data_context')
            self._log_debug(f"_context_get_all_items: session_context type={type(session_context).__name__}, has_data_context={has_data_context}")
            
            # Получаем все items из data_context
            if has_data_context and hasattr(session_context.data_context, 'get_all_items'):
                all_items = session_context.data_context.get_all_items()
                # Конвертируем в dict по item_id
                items_dict = {}
                for item in all_items:
                    item_id = item.item_id if hasattr(item, 'item_id') else str(item)
                    items_dict[item_id] = item
                return ExecutionResult(
                    status=ExecutionStatus.COMPLETED,
                    data={"items": items_dict},
                    metadata={"count": len(items_dict)}
                )
            else:
                self._log_debug(f"_context_get_all_items: session_context не имеет data_context. Тип: {type(session_context).__name__}")
                return ExecutionResult(
                    status=ExecutionStatus.COMPLETED,
                    data={"items": {}},
                    metadata={"count": 0, "message": "data_context не доступен"}
                )
        except Exception as e:
            self._log_debug(f"_context_get_all_items: Exception: {e}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=f"Ошибка получения всех items: {str(e)}"
            )

    def _context_get_step_history(
        self,
        parameters: Dict[str, Any],
        session_context
    ) -> ExecutionResult:
        """Получение истории шагов выполнения"""
        try:
            # Получаем step_history из session_context
            if hasattr(session_context, 'step_context') and hasattr(session_context.step_context, 'steps'):
                steps = session_context.step_context.steps
                # Конвертируем шаги в dict формат
                steps_data = []
                for step in steps:
                    if hasattr(step, '__dict__'):
                        # AgentStep: capability_name, summary, status, observation_item_ids
                        steps_data.append({
                            "step_number": getattr(step, 'step_number', 0),
                            "capability_name": getattr(step, 'capability_name', getattr(step, 'action', 'unknown')),
                            "skill_name": getattr(step, 'skill_name', ''),
                            "summary": getattr(step, 'summary', ''),
                            "status": getattr(step, 'status', ''),
                            "observation": getattr(step, 'observation', ''),
                            "result": getattr(step, 'result', '')
                        })
                    else:
                        steps_data.append(step)
                return ExecutionResult(
                    status=ExecutionStatus.COMPLETED,
                    data={"steps": steps_data},
                    metadata={"count": len(steps_data)}
                )
            else:
                return ExecutionResult(
                    status=ExecutionStatus.COMPLETED,
                    data={"steps": []},
                    metadata={"count": 0, "message": "step_context не доступен"}
                )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=f"Ошибка получения step history: {str(e)}"
            )

    def _context_record_action(
        self,
        parameters: Dict[str, Any],
        session_context
    ) -> ExecutionResult:
        """Запись действия в контекст"""
        action_data = parameters.get("action_data")
        step_number = parameters.get("step_number")
        metadata = parameters.get("metadata")

        if not action_data:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error="action_data не указан для записи действия"
            )

        item_id = session_context.record_action(
            action_data=action_data,
            step_number=step_number,
            metadata=metadata
        )

        return ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            data={"item_id": item_id},
            metadata={"step_number": step_number}
        )

    def _context_record_observation(
        self,
        parameters: Dict[str, Any],
        session_context
    ) -> ExecutionResult:
        """Запись наблюдения в контекст"""
        observation_data = parameters.get("observation_data")
        source = parameters.get("source")
        step_number = parameters.get("step_number")
        metadata = parameters.get("metadata")

        if not observation_data:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error="observation_data не указан для записи наблюдения"
            )

        item_id = session_context.record_observation(
            observation_data=observation_data,
            source=source,
            step_number=step_number,
            metadata=metadata
        )

        return ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            data={"item_id": item_id},
            metadata={"source": source, "step_number": step_number}
        )

    # === НОВЫЕ МЕТОДЫ ДЛЯ ИЗОЛЯЦИИ КОМПОНЕНТОВ ===

    def _context_get_goal(
        self,
        parameters: Dict[str, Any],
        session_context
    ) -> ExecutionResult:
        """Получение текущей цели из session_context"""
        try:
            goal = session_context.get_goal() if hasattr(session_context, 'get_goal') else None
            return ExecutionResult(
                status=ExecutionStatus.COMPLETED,
                data={"goal": goal if goal else "unknown"},
                metadata={"exists": goal is not None}
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=f"Ошибка получения цели: {str(e)}"
            )

    def _context_get_summary(
        self,
        parameters: Dict[str, Any],
        session_context
    ) -> ExecutionResult:
        """Получение резюме сессии"""
        try:
            summary = session_context.get_summary() if hasattr(session_context, 'get_summary') else None
            return ExecutionResult(
                status=ExecutionStatus.COMPLETED,
                data={"summary": summary if summary else ""},
                metadata={"exists": summary is not None}
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=f"Ошибка получения резюме: {str(e)}"
            )

    def _context_get_recent_errors(
        self,
        parameters: Dict[str, Any],
        session_context
    ) -> ExecutionResult:
        """Получение последних ошибок"""
        try:
            limit = parameters.get("limit", 5)
            errors = session_context.get_recent_errors(limit=limit) if hasattr(session_context, 'get_recent_errors') else []
            return ExecutionResult(
                status=ExecutionStatus.COMPLETED,
                data={"errors": errors},
                metadata={"count": len(errors)}
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=f"Ошибка получения ошибок: {str(e)}"
            )

    def _context_get_current_step(
        self,
        parameters: Dict[str, Any],
        session_context
    ) -> ExecutionResult:
        """Получение текущего номера шага"""
        try:
            current_step = session_context.current_step if hasattr(session_context, 'current_step') else 0
            return ExecutionResult(
                status=ExecutionStatus.COMPLETED,
                data={"current_step": current_step},
                metadata={"step_number": current_step}
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=f"Ошибка получения текущего шага: {str(e)}"
            )

    def _resolve_component_for_action(self, action_name: str):
        """
        Разрешение компонента по имени действия.

        Поддерживает два формата:
        1. Явный: "service.sql_query_service.execute" -> тип=service, имя=sql_query_service
        2. Неявный: "sql_query_service.execute" -> ищем во всех реестрах

        ARGS:
        - action_name: имя действия

        RETURNS:
        - tuple: (найденный компонент или None, тип компонента как строка)
        """
        from core.application_context.application_context import ComponentType

        # Разбиваем имя действия на части
        parts = action_name.split('.', 1)
        
        # Проверяем явный формат (type.name.action)
        if len(parts) >= 2 and parts[0] in ["skill", "tool", "service", "behavior"]:
            component_type = parts[0]
            component_name = parts[1].split('.', 1)[0]
        else:
            # Неявный формат — ищем компонент по имени во всех реестрах
            component_name = parts[0]
            component_type = None

        # Определяем тип компонента
        comp_type_map = {
            "skill": ComponentType.SKILL,
            "tool": ComponentType.TOOL,
            "service": ComponentType.SERVICE,
            "behavior": ComponentType.BEHAVIOR
        }

        # Если тип указан явно, ищем в соответствующем реестре
        if component_type and component_type in comp_type_map:
            comp_type = comp_type_map[component_type]
            component = self.application_context.components.get(comp_type, component_name)
            if component:
                return component, component_type

        # Ищем во всех реестрах (для неявного формата или если не найдено)
        for type_name, comp_type in comp_type_map.items():
            component = self.application_context.components.get(comp_type, component_name)
            if component:
                return component, type_name

        # Отладка: логируем доступные сервисы
        services = self.application_context.components.all_of_type(ComponentType.SERVICE)
        self._log_debug(f"Компонент '{component_name}' не найден. Доступные сервисы: {[s for s in services]}")

        return None, None
    
    def _resolve_capability(self, action_name: str) -> Optional[Capability]:
        """
        Разрешение capability по имени действия.
        
        ARGS:
        - action_name: имя действия
        
        RETURNS:
        - Capability: найденный capability или None
        """
        # В реальной реализации здесь будет логика разрешения capability
        # из реестра capability по имени действия

        # Для простоты создаем capability с именем действия
        from core.models.data.capability import Capability
        # Извлекаем skill_name из action_name (например, planning.create_plan → planning)
        parts = action_name.split('.')
        skill_name = parts[0] if len(parts) >= 2 else action_name
        return Capability(
            name=action_name,
            description=f"Capability для действия {action_name}",
            skill_name=skill_name,
            input_schema={},
            output_schema={}
        )

    async def _execute_validation_action(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        context: ExecutionContext
    ) -> ExecutionResult:
        """
        Выполнение действий валидации (validation.*).

        Поддерживаемые действия:
        - validation.validate: валидация данных через Pydantic схему
        - validation.is_valid: быстрая проверка валидности

        ARGS:
        - action_name: имя действия
        - parameters: параметры для валидации
        - context: контекст выполнения

        RETURNS:
        - ExecutionResult: результат валидации
        """
        # Импортируем сервис лениво для избежания циклического импорта
        from core.components.services.validation_service import ValidationService
        
        service = ValidationService()
        
        try:
            if action_name == "validation.validate":
                return self._validation_validate(parameters, service)
            elif action_name == "validation.is_valid":
                return self._validation_is_valid(parameters, service)
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Неизвестное действие валидации: {action_name}"
                )
        except Exception as e:
            _module_logger.error(
                f"Ошибка валидации '{action_name}': {e}",
                extra={"event_type": LogEventType.ERROR},
                exc_info=True
            )
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=f"Ошибка валидации: {str(e)}"
            )
    
    def _validation_validate(
        self,
        parameters: Dict[str, Any],
        service: ValidationService
    ) -> ExecutionResult:
        """
        Валидация данных через Pydantic схему.
        
        ПАРАМЕТРЫ:
        - schema_name: имя схемы (путь к классу, например "my_module.MySchema")
        - data: данные для валидации
        
        ВОЗВРАЩАЕТ:
        - ExecutionResult с результатом валидации
        """
        schema_name = parameters.get("schema_name")
        data = parameters.get("data")
        
        if not schema_name:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error="schema_name обязателен"
            )
        
        if data is None:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error="data обязателен"
            )
        
        # Получаем класс схемы по имени
        # Формат: "module.Class" или просто "Class" (ищет в pydantic BaseModel)
        try:
            if "." in schema_name:
                module_name, class_name = schema_name.rsplit(".", 1)
                module = __import__(module_name, fromlist=[class_name])
                schema_cls = getattr(module, class_name)
            else:
                # Если нет модуля, используем базовую валидацию dict
                result = service.validate_dict(data)
                return ExecutionResult(
                    status=ExecutionStatus.COMPLETED,
                    data=result.model_dump()
                )
        except (ImportError, AttributeError) as e:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=f"Схема '{schema_name}' не найдена: {str(e)}"
            )
        
        # Выполняем валидацию
        result = service.validate(schema_cls, data)
        
        return ExecutionResult(
            status=ExecutionStatus.COMPLETED if result.is_valid else ExecutionStatus.FAILED,
            data=result.model_dump(),
            error=None if result.is_valid else result.error
        )
    
    def _validation_is_valid(
        self,
        parameters: Dict[str, Any],
        service: ValidationService
    ) -> ExecutionResult:
        """
        Быстрая проверка валидности.
        
        ПАРАМЕТРЫ:
        - schema_name: имя схемы
        - data: данные для проверки
        
        ВОЗВРАЩАЕТ:
        - ExecutionResult с is_valid=True/False
        """
        schema_name = parameters.get("schema_name")
        data = parameters.get("data")
        
        if not schema_name:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error="schema_name обязателен"
            )
        
        try:
            if "." in schema_name:
                module_name, class_name = schema_name.rsplit(".", 1)
                module = __import__(module_name, fromlist=[class_name])
                schema_cls = getattr(module, class_name)
            else:
                # Базовая проверка dict
                is_valid = isinstance(data, dict) and data is not None
                return ExecutionResult(
                    status=ExecutionStatus.COMPLETED,
                    data={"is_valid": is_valid}
                )
        except (ImportError, AttributeError):
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=f"Схема '{schema_name}' не найдена"
            )
        
        is_valid = service.is_valid(schema_cls, data)
        
        return ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            data={"is_valid": is_valid}
        )

    async def _execute_llm_action(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        context: ExecutionContext
    ) -> ExecutionResult:
        """
        Выполнение LLM действий (llm.*).

        Поддерживаемые действия:
        - llm.generate: обычная генерация текста
        - llm.generate_structured: структурированная генерация с JSON Schema

        ARGS:
        - action_name: имя действия (llm.generate или llm.generate_structured)
        - parameters: параметры для LLM запроса
        - context: контекст выполнения

        RETURNS:
        - ExecutionResult: результат выполнения
        """
        try:
            # Получаем LLM провайдер напрямую из инфраструктуры
            llm_provider = None
            if hasattr(self.application_context, 'infrastructure_context'):
                infra = self.application_context.infrastructure_context
                if infra.resource_registry:
                    from core.models.enums.common_enums import ResourceType
                    default_llm_info = infra.resource_registry.get_default_resource(ResourceType.LLM)
                    llm_provider = default_llm_info.instance if default_llm_info else None

            if not llm_provider:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error="LLM провайдер по умолчанию не найден. Проверьте конфигурацию llm_providers."
                )

            # Получаем LLMOrchestrator (если доступен) для retry и валидации
            orchestrator = None
            if hasattr(self.application_context, 'llm_orchestrator'):
                orchestrator = self.application_context.llm_orchestrator

            # Определяем тип действия
            if action_name == "llm.generate":
                return await self._llm_generate(llm_provider, parameters, orchestrator, context)
            elif action_name == "llm.generate_structured":
                return await self._llm_generate_structured(llm_provider, parameters, orchestrator, context, action_name)
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Неизвестное LLM действие: {action_name}"
                )

        except Exception as e:
            _module_logger.error(
                f"Ошибка LLM действия '{action_name}': {e}",
                extra={"event_type": LogEventType.ERROR},
                exc_info=True
            )
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=str(e)
            )

    async def _llm_generate(
        self,
        llm_provider,
        parameters: Dict[str, Any],
        orchestrator: Any = None,
        context: ExecutionContext = None
    ) -> ExecutionResult:
        """
        Обычная генерация текста через LLM.

        PARAMETERS:
        - prompt: текст запроса
        - model: имя модели (опционально)
        - temperature: температура (опционально)
        - max_tokens: максимум токенов (опционально)
        """
        from core.models.types.llm_types import LLMRequest

        prompt = parameters.get("prompt", "")
        if not prompt:
            return ExecutionResult(status=ExecutionStatus.FAILED, error="Параметр 'prompt' обязателен")

        request = LLMRequest(
            prompt=prompt,
            system_prompt=parameters.get("system_prompt"),
            temperature=parameters.get("temperature", 0.7),
            max_tokens=parameters.get("max_tokens", 500),
            top_p=parameters.get("top_p", 0.95),
            frequency_penalty=parameters.get("frequency_penalty", 0.0),
            presence_penalty=parameters.get("presence_penalty", 0.0),
            stop_sequences=parameters.get("stop_sequences")
        )

        # Вызов через оркестратор если доступен
        if orchestrator:
            # Извлекаем контекстные данные для трассировки
            session_id = None
            agent_id = None
            step_number = None
            goal = None
            
            if context and context.session_context:
                session_id = getattr(context.session_context, 'session_id', None)
                agent_id = getattr(context.session_context, 'agent_id', None)
                goal = getattr(context.session_context, 'goal', None)
                if hasattr(context.session_context, 'step_context') and context.session_context.step_context:
                    step_number = context.session_context.step_context.get_current_step_number()
            
            response = await orchestrator.execute(
                request=request,
                provider=llm_provider,
                session_id=session_id,
                agent_id=agent_id,
                step_number=step_number,
                goal=goal,
                phase=parameters.get('phase', 'unknown')
            )
        else:
            # Fallback: прямой вызов
            response = await llm_provider.generate(request)

        return ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            data={"content": response.content},
            metadata={
                # LLMResponse имеет raw_response с метаданными
                "model": response.raw_response.model if hasattr(response, 'raw_response') and response.raw_response else getattr(response, 'model', 'unknown'),
                "tokens_used": response.raw_response.tokens_used if hasattr(response, 'raw_response') and response.raw_response else getattr(response, 'tokens_used', 0),
                "generation_time": response.raw_response.generation_time if hasattr(response, 'raw_response') and response.raw_response else getattr(response, 'generation_time', 0),
                "finish_reason": response.raw_response.finish_reason if hasattr(response, 'raw_response') and response.raw_response else getattr(response, 'finish_reason', 'unknown')
            }
        )

    async def _llm_generate_structured(
        self,
        llm_provider,
        parameters: Dict[str, Any],
        orchestrator: Any = None,
        context: ExecutionContext = None,
        action_name: str = "llm.generate_structured"
    ) -> ExecutionResult:
        """
        Структурированная генерация через LLM с JSON Schema.

        PARAMETERS:
        - prompt: текст запроса
        - structured_output: StructuredOutputConfig или dict с schema_def
        - model: имя модели (опционально)
        - temperature: температура (опционально, по умолчанию 0.1 для точности)
        - max_tokens: максимум токенов (опционально)
        - max_retries: количество попыток (по умолчанию 3)
        """
        from core.models.types.llm_types import LLMRequest, StructuredOutputConfig

        prompt = parameters.get("prompt", "")
        if not prompt:
            return ExecutionResult(status=ExecutionStatus.FAILED, error="Параметр 'prompt' обязателен")

        # Получаем конфигурацию структурированного вывода
        structured_output = parameters.get("structured_output")
        if not structured_output:
            return ExecutionResult(status=ExecutionStatus.FAILED, error="Параметр 'structured_output' обязателен")

        # Если передан dict, создаём StructuredOutputConfig
        # StructuredOutputConfig сам конвертирует Pydantic модель в schema_def
        if isinstance(structured_output, dict):
            structured_output = StructuredOutputConfig(**structured_output)

        request = LLMRequest(
            prompt=prompt,
            system_prompt=parameters.get("system_prompt"),
            temperature=parameters.get("temperature", 0.1),  # Низкая температура для точности
            max_tokens=parameters.get("max_tokens", 4000),
            structured_output=structured_output
        )

        # Вызов через оркестратор если доступен
        if not orchestrator:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error="LLMOrchestrator недоступен — требуется для структурированной генерации"
            )

        # Получаем таймауты из централизованной конфигурации
        from core.config.timeout_config import get_timeout_config
        timeout_config = get_timeout_config()
        
        # Определяем таймаут для действия
        if action_name.startswith("llm."):
            # Для LLM действий используем специфичный таймаут
            attempt_timeout = parameters.get(
                "attempt_timeout",
                timeout_config.get_llm_timeout_for_action(action_name)
            )
            total_timeout = parameters.get(
                "total_timeout",
                timeout_config.llm_total_timeout
            )
        else:
            # Для остальных действий используем дефолтный таймаут
            attempt_timeout = parameters.get(
                "attempt_timeout",
                timeout_config.action_default_timeout
            )
            total_timeout = parameters.get("total_timeout", attempt_timeout)

        # Извлекаем контекстные данные для трассировки (приоритет у параметров)
        session_id = parameters.get('session_id')
        agent_id = parameters.get('agent_id')
        step_number = parameters.get('step_number')
        goal = parameters.get('goal')
        
        # SessionContext имеет атрибуты напрямую (session_id, agent_id, goal)
        if context and hasattr(context, 'session_id'):
            if session_id is None:
                session_id = context.session_id
            if agent_id is None:
                agent_id = context.agent_id
            if goal is None:
                goal = getattr(context, 'goal', None)
            if step_number is None and hasattr(context, 'step_context') and context.step_context:
                step_number = context.step_context.get_current_step_number()

        response = await orchestrator.execute_structured(
            request=request,
            provider=llm_provider,
            max_retries=parameters.get("max_retries", 3),
            session_id=session_id,
            agent_id=agent_id,
            step_number=step_number,
            goal=goal,
            phase=parameters.get('phase', 'unknown')
        )

        # Проверка успеха
        if response.success:
            # ✅ ИСПРАВЛЕНО: Сохраняем Pydantic модель вместо dict
            # Сериализация будет вызвана только на границе через result.to_dict()
            return ExecutionResult.success(
                data=response.parsed_content,  # ← Pydantic модель типа T
                metadata={
                    "model": response.raw_response.model,
                    "tokens_used": response.raw_response.tokens_used,
                    "generation_time": response.raw_response.generation_time,
                    "parsing_attempts": response.parsing_attempts,
                    "success": response.success,
                    "raw_content": response.raw_response.content  # Для отладки
                }
            )
        else:
            # Ошибка валидации
            return ExecutionResult.failure(
                error=f"Structured output failed after {response.parsing_attempts} attempts",
                metadata={
                    "validation_errors": response.validation_errors,
                    "parsing_attempts": response.parsing_attempts,
                    "error_type": "StructuredOutputError"
                }
            )

    async def _execute_service_action(
        self,
        service: Any,
        action_name: str,
        parameters: Dict[str, Any],
        context: ExecutionContext
    ) -> ExecutionResult:
        """
        Выполнение действия сервиса.

        Сервисы не имеют capability, поэтому вызываем метод напрямую по имени действия.
        Например: sql_query_service.execute -> service.execute_query(...)

        ARGS:
        - service: сервис для выполнения
        - action_name: имя действия (например, "sql_query_service.execute")
        - parameters: параметры выполнения
        - context: контекст выполнения

        RETURNS:
        - ExecutionResult: результат выполнения
        """
        try:
            # Извлекаем имя метода из имени действия
            method_name = action_name
            if '.' in action_name:
                method_name = action_name.split('.')[-1]

            # Проверяем наличие метода
            if not hasattr(service, method_name):
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Метод '{method_name}' не найден в сервисе '{service.name}'"
                )

            # Вызываем метод сервиса
            method = getattr(service, method_name)
            result = await method(**parameters)

            # Возвращаем результат
            return ExecutionResult(
                status=ExecutionStatus.COMPLETED,
                data=result
            )

        except Exception as e:
            _module_logger.error(
                f"Ошибка сервиса '{action_name}': {e}",
                extra={"event_type": LogEventType.ERROR},
                exc_info=True
            )
            if self._event_bus:
                await self._event_bus.publish(
                    event_type="executor.service_error",
                    data={"action_name": action_name, "service": service.name, "error": str(e)},
                    source="action_executor",
                    session_id=context.session_id,
                    agent_id=context.agent_id
                )
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=str(e)
            )

    async def _execute_tool_action(
        self,
        tool: Any,
        action_name: str,
        parameters: Dict[str, Any],
        context: ExecutionContext
    ) -> ExecutionResult:
        """
        Выполнение действия инструмента.

        Инструменты не имеют capability, поэтому вызываем метод напрямую по имени действия.
        Например: sql_tool.execute_query -> tool.execute(...)

        ARGS:
        - tool: инструмент для выполнения
        - action_name: имя действия (например, "sql_tool.execute_query")
        - parameters: параметры выполнения
        - context: контекст выполнения

        RETURNS:
        - ExecutionResult: результат выполнения
        """
        try:
            # Создаём Capability объект из action_name
            from core.models.data.capability import Capability
            capability_obj = Capability(
                name=action_name,
                description=f"Capability {action_name}",
                skill_name=tool.name,
                visiable=True,
                supported_strategies=["react", "planning"]
            )

            # Вызываем execute() который вызовет _execute_impl() для FileTool/SQLTool
            # или async execute() для VectorSearchTool
            result = await tool.execute(
                capability=capability_obj,
                parameters=parameters,
                execution_context=context
            )

            # result — это уже ExecutionResult от BaseComponent.execute()
            # Не оборачиваем второй раз!
            if self._event_bus:
                await self._event_bus.publish(
                    event_type="executor.tool_result",
                    data={
                        "action_name": action_name,
                        "tool": tool.name,
                        "status": result.status.name if hasattr(result, 'status') else "completed",
                        "data": result.data if hasattr(result, 'data') else result
                    },
                    source="action_executor",
                    session_id=context.session_id,
                    agent_id=context.agent_id
                )
                self._log_debug(f"Опубликовано executor.tool_result: {action_name}")

            return result

        except Exception as e:
            _module_logger.error(
                f"Ошибка инструмента '{action_name}': {e}",
                extra={"event_type": LogEventType.ERROR},
                exc_info=True
            )
            if self._event_bus:
                await self._event_bus.publish(
                    event_type="executor.tool_error",
                    data={"action_name": action_name, "tool": tool.name, "error": str(e)},
                    source="action_executor",
                    session_id=context.session_id,
                    agent_id=context.agent_id
                )
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=str(e)
            )

    async def _execute_skill_or_behavior_action(
        self,
        component: Any,
        action_name: str,
        parameters: Dict[str, Any],
        context: ExecutionContext
    ) -> ExecutionResult:
        """
        Выполнение действия навыка или behavior паттерна.

        Навыки и behavior имеют capability, поэтому используем execute().

        ARGS:
        - component: навык или behavior для выполнения
        - action_name: имя действия (например, "planning.create_plan")
        - parameters: параметры выполнения
        - context: контекст выполнения

        RETURNS:
        - ExecutionResult: результат выполнения
        """
        try:
            # Валидируем входные параметры через контракт компонента
            capability = self._resolve_capability(action_name)
            if not capability:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Capability для действия '{action_name}' не найден"
                )

            # Выполняем компонент
            result = await component.execute(capability, parameters, context)

            # Публикация события об успешном выполнении
            if self._event_bus and result.status == ExecutionStatus.COMPLETED:
                await self._event_bus.publish(
                    event_type="executor.component_result",
                    data={
                        "action_name": action_name,
                        "component": component.name,
                        "capability": capability.name,
                        "status": "completed",
                        "data": result.data,
                        "metadata": result.metadata
                    },
                    source="action_executor",
                    session_id=context.session_id,
                    agent_id=context.agent_id
                )
                self._log_debug(f"Опубликовано executor.component_result: {action_name}")

            return result

        except Exception as e:
            _module_logger.error(
                f"Ошибка компонента '{action_name}': {e}",
                extra={"event_type": LogEventType.ERROR},
                exc_info=True
            )
            if self._event_bus:
                await self._event_bus.publish(
                    event_type="executor.component_error",
                    data={
                        "action_name": action_name,
                        "component": component.name,
                        "error": str(e),
                        "error_type": type(e).__name__
                    },
                    source="action_executor",
                    session_id=context.session_id,
                    agent_id=context.agent_id
                )
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=str(e)
            )