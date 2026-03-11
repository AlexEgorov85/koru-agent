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
from typing import Dict, Any, Optional, TYPE_CHECKING
from pydantic import BaseModel

from core.models.data.execution import ExecutionResult, ExecutionStatus, ExecutionStatus, ExecutionStatus
from core.models.data.capability import Capability

if TYPE_CHECKING:
    from core.application.context.application_context import ApplicationContext




class ExecutionContext:
    """Контекст выполнения для компонентов"""
    def __init__(self, session_context: Any = None, user_context: Any = None, available_capabilities: list = None):
        self.session_context = session_context
        self.user_context = user_context
        self.available_capabilities = available_capabilities or []


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
        # Используем event_bus_logger из infrastructure_context если доступен
        self._event_bus_logger = None
        try:
            if hasattr(application_context, 'infrastructure_context'):
                self._event_bus_logger = getattr(application_context.infrastructure_context, 'event_bus_logger', None)
        except Exception:
            pass

    def _log_debug(self, msg: str, *args, **kwargs):
        """Отладочное логирование."""
        if self._event_bus_logger:
            asyncio.create_task(self._event_bus_logger.debug(msg, *args, **kwargs))
    
    async def execute_action(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        context: ExecutionContext
    ) -> ExecutionResult:
        """
        Выполнение действия через ActionExecutor.

        ARGS:
        - action_name: имя действия для выполнения
        - parameters: параметры выполнения
        - context: контекст выполнения

        RETURNS:
        - ActionResult: результат выполнения
        """
        self._log_debug(f"ActionExecutor.execute_action: {action_name} с параметрами {list(parameters.keys())}")

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
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Компонент для действия '{action_name}' не найден"
                )

            # 4. Проверяем, что компонент инициализирован
            if not hasattr(target_component, '_initialized') or not target_component._initialized:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Компонент '{target_component.name}' не инициализирован"
                )

            # 5. Выполняем компонент в зависимости от типа
            if component_type == "service":
                # Сервисы: вызываем метод напрямую по имени действия
                return await self._execute_service_action(target_component, action_name, parameters, context)
            elif component_type == "tool":
                # Инструменты: вызываем метод напрямую по имени действия
                return await self._execute_tool_action(target_component, action_name, parameters, context)
            else:
                # Навыки и behavior: используем capability
                return await self._execute_skill_or_behavior_action(target_component, action_name, parameters, context)

        except Exception as e:
            if self._event_bus_logger:
                asyncio.create_task(self._event_bus_logger.error(f"Ошибка выполнения действия '{action_name}': {e}", exc_info=True))
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=str(e)
            )

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
        session_context = context.session_context

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
            if self._event_bus_logger:
                asyncio.create_task(self._event_bus_logger.error(f"Ошибка выполнения действия контекста '{action_name}': {e}", exc_info=True))
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
            # Получаем все items из data_context
            if hasattr(session_context, 'data_context') and hasattr(session_context.data_context, 'get_all_items'):
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
                return ExecutionResult(
                    status=ExecutionStatus.COMPLETED,
                    data={"items": {}},
                    metadata={"count": 0, "message": "data_context не доступен"}
                )
        except Exception as e:
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
        from core.application.context.application_context import ComponentType

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
        return Capability(
            name=action_name,
            description=f"Capability для действия {action_name}",
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
        from core.application.services.validation_service import ValidationService
        
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
            if self._event_bus_logger:
                asyncio.create_task(self._event_bus_logger.error(f"Ошибка валидации '{action_name}': {e}", exc_info=True))
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
        - ActionResult: результат выполнения
        """
        try:
            # Получаем LLM провайдер напрямую из инфраструктуры
            llm_provider = None
            if hasattr(self.application_context, 'infrastructure_context'):
                llm_provider = self.application_context.infrastructure_context.get_provider("default_llm")

            if not llm_provider:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error="LLM провайдер 'default_llm' не найден"
                )

            # Получаем LLMOrchestrator (если доступен) для retry и валидации
            orchestrator = None
            if hasattr(self.application_context, 'llm_orchestrator'):
                orchestrator = self.application_context.llm_orchestrator

            # Определяем тип действия
            if action_name == "llm.generate":
                return await self._llm_generate(llm_provider, parameters, orchestrator, context)
            elif action_name == "llm.generate_structured":
                return await self._llm_generate_structured(llm_provider, parameters, orchestrator, context)
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Неизвестное LLM действие: {action_name}"
                )

        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка LLM действия '{action_name}': {e}", exc_info=True)
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
            response = await orchestrator.execute(
                request=request,
                provider=llm_provider,
                session_id=getattr(context, 'session_id', None) if context else None,
                agent_id=getattr(context, 'agent_id', None) if context else None,
                step_number=getattr(context, 'step_number', None) if context else None,
                phase=parameters.get('phase', 'unknown')
            )
        else:
            # Fallback: прямой вызов
            response = await llm_provider.generate(request)

        return ExecutionResult(
            status=ExecutionStatus.COMPLETED,
            data={"content": response.content},
            metadata={
                # ✅ ИСПРАВЛЕНО: StructuredLLMResponse не имеет model напрямую
                "model": response.raw_response.model if hasattr(response, 'raw_response') and response.raw_response else getattr(response, 'model', 'unknown'),
                # ✅ ИСПРАВЛЕНО: StructuredLLMResponse не имеет tokens_used напрямую
                "tokens_used": response.raw_response.tokens_used if hasattr(response, 'raw_response') and response.raw_response else getattr(response, 'tokens_used', 0),
                # ✅ ИСПРАВЛЕНО: StructuredLLMResponse не имеет generation_time/finish_reason напрямую
                "generation_time": response.raw_response.generation_time if hasattr(response, 'raw_response') and response.raw_response else getattr(response, 'generation_time', 0),
                "finish_reason": response.raw_response.finish_reason if hasattr(response, 'raw_response') and response.raw_response else getattr(response, 'finish_reason', 'unknown')
            }
        )

    async def _llm_generate_structured(
        self,
        llm_provider,
        parameters: Dict[str, Any],
        orchestrator: Any = None,
        context: ExecutionContext = None
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
        if isinstance(structured_output, dict):
            structured_output = StructuredOutputConfig(**structured_output)

        request = LLMRequest(
            prompt=prompt,
            system_prompt=parameters.get("system_prompt"),
            temperature=parameters.get("temperature", 0.1),  # Низкая температура для точности
            max_tokens=parameters.get("max_tokens", 1000),
            structured_output=structured_output
        )

        # Вызов через оркестратор если доступен
        if not orchestrator:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error="LLMOrchestrator недоступен — требуется для структурированной генерации"
            )

        response = await orchestrator.execute_structured(
            request=request,
            provider=llm_provider,
            max_retries=parameters.get("max_retries", 3),
            attempt_timeout=parameters.get("attempt_timeout", 60.0),  # Timeout на одну попытку
            total_timeout=parameters.get("total_timeout", parameters.get("timeout", 120.0)),  # Общий timeout
            session_id=parameters.get('session_id'),
            agent_id=parameters.get('agent_id'),
            step_number=parameters.get('step_number'),
            phase=parameters.get('phase', 'unknown')
        )

        # Проверка успеха
        if response.success:
            # ✅ ИСПРАВЛЕНО: Сохраняем Pydantic модель вместо dict
            # Сериализация будет вызвана только на границе через result.to_dict()
            return ActionResult.success_result(
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
            return ActionResult.failure_result(
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
            # sql_query_service.execute -> execute
            if '.' in action_name:
                _, method_name = action_name.split('.', 1)
                # service.execute -> execute_query (добавляем префикс если нужно)
                if method_name == "execute":
                    method_name = "execute_query"
            else:
                method_name = action_name

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
            if self.logger:
                self.logger.error(f"Ошибка выполнения сервиса '{service.name}': {e}", exc_info=True)
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
        Например: file_tool.read -> tool.execute(FileToolInput(...))

        ARGS:
        - tool: инструмент для выполнения
        - action_name: имя действия (например, "file_tool.read")
        - parameters: параметры выполнения
        - context: контекст выполнения

        RETURNS:
        - ExecutionResult: результат выполнения
        """
        try:
            # Извлекаем имя метода из имени действия
            # file_tool.read -> read
            if '.' in action_name:
                _, method_name = action_name.split('.', 1)
            else:
                method_name = action_name

            # Для инструментов используем execute с параметрами
            # Если метод не найден, пробуем execute
            if not hasattr(tool, method_name):
                method_name = "execute"

            # Вызываем метод инструмента
            method = getattr(tool, method_name)
            
            # Проверяем signature метода
            import inspect
            sig = inspect.signature(method)
            
            # Если метод принимает Pydantic модель, создаём её из parameters
            if len(sig.parameters) > 0:
                param_type = list(sig.parameters.values())[0].annotation
                if hasattr(param_type, '__fields__'):  # Pydantic модель
                    result = await method(param_type(**parameters))
                else:
                    result = await method(parameters)
            else:
                result = await method()

            # Возвращаем результат
            return ExecutionResult(
                status=ExecutionStatus.COMPLETED,
                data=result
            )

        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка выполнения инструмента '{tool.name}': {e}", exc_info=True)
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
        - action_name: имя действия (например, "book_library.execute_script")
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

            return result

        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка выполнения компонента '{component.name}': {e}", exc_info=True)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=str(e)
            )