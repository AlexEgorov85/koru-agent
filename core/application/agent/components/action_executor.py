"""
ЕДИНСТВЕННЫЙ ПОСРЕДНИК ДЛЯ ВЗАИМОДЕЙСТВИЯ КОМПОНЕНТОВ.

ГАРАНТИИ:
- Изоляция компонентов друг от друга
- Контроль зависимостей и порядка выполнения
- Единая точка для метрик и логирования
- Возможность внедрения мидлварей (ретраи, рейт-лимиты)
"""
from typing import Dict, Any, Optional
from core.models.data.execution import ExecutionResult
from core.models.data.capability import Capability
from core.application.context.application_context import ApplicationContext


class ActionResult:
    """Результат выполнения действия через ActionExecutor"""
    def __init__(self, success: bool, data: Any = None, metadata: Dict[str, Any] = None, error: str = None):
        self.success = success
        self.data = data or {}
        self.metadata = metadata or {}
        self.error = error

    def __repr__(self):
        return f"ActionResult(success={self.success}, data={self.data}, error={self.error})"


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
        self.logger = self.application_context.logger if hasattr(application_context, 'logger') else None
    
    async def execute_action(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        context: ExecutionContext
    ) -> ActionResult:
        """
        Выполнение действия через ActionExecutor.
        
        ARGS:
        - action_name: имя действия для выполнения
        - parameters: параметры выполнения
        - context: контекст выполнения
        
        RETURNS:
        - ActionResult: результат выполнения
        """
        if self.logger:
            self.logger.debug(f"ActionExecutor.execute_action: {action_name} с параметрами {list(parameters.keys())}")

        try:
            # 1. Обработка действий контекста (context.*)
            if action_name.startswith("context."):
                return await self._execute_context_action(action_name, parameters, context)

            # 2. Находим целевой компонент по имени действия
            target_component = self._resolve_component_for_action(action_name)

            if not target_component:
                return ActionResult(
                    success=False,
                    error=f"Компонент для действия '{action_name}' не найден"
                )

            # 3. Валидируем входные параметры через контракт компонента
            capability = self._resolve_capability(action_name)
            if not capability:
                return ActionResult(
                    success=False,
                    error=f"Capability для действия '{action_name}' не найден"
                )

            # 4. Проверяем, что компонент инициализирован
            if not hasattr(target_component, '_initialized') or not target_component._initialized:
                return ActionResult(
                    success=False,
                    error=f"Компонент '{target_component.name}' не инициализирован"
                )

            # 5. Выполняем компонент
            result = await target_component.execute(capability, parameters, context)

            # 6. Валидируем выходные данные
            # (в реальной реализации здесь будет валидация через контракт)

            return result

        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка выполнения действия '{action_name}': {e}", exc_info=True)
            return ActionResult(
                success=False,
                error=str(e)
            )

    async def _execute_context_action(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        context: ExecutionContext
    ) -> ActionResult:
        """
        Выполнение действий контекста (context.*).
        
        Поддерживаемые действия:
        - context.record_plan: сохранение плана в контекст
        - context.get_current_plan: получение текущего плана
        - context.get_context_item: получение элемента контекста по ID
        - context.record_action: запись действия в контекст
        - context.record_observation: запись наблюдения в контекст
        """
        session_context = context.session_context
        
        if not session_context:
            return ActionResult(
                success=False,
                error="session_context не доступен для выполнения действия контекста"
            )

        try:
            if action_name == "context.record_plan":
                return await self._context_record_plan(parameters, session_context)
            elif action_name == "context.get_current_plan":
                return self._context_get_current_plan(parameters, session_context)
            elif action_name == "context.get_context_item":
                return self._context_get_context_item(parameters, session_context)
            elif action_name == "context.record_action":
                return self._context_record_action(parameters, session_context)
            elif action_name == "context.record_observation":
                return self._context_record_observation(parameters, session_context)
            else:
                return ActionResult(
                    success=False,
                    error=f"Неизвестное действие контекста: {action_name}"
                )
        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка выполнения действия контекста '{action_name}': {e}", exc_info=True)
            return ActionResult(
                success=False,
                error=f"Ошибка действия контекста: {str(e)}"
            )

    async def _context_record_plan(
        self,
        parameters: Dict[str, Any],
        session_context
    ) -> ActionResult:
        """Сохранение плана в контекст"""
        plan_data = parameters.get("plan_data")
        plan_type = parameters.get("plan_type", "initial")
        metadata = parameters.get("metadata")

        if not plan_data:
            return ActionResult(
                success=False,
                error="plan_data не указан для сохранения плана"
            )

        item_id = session_context.record_plan(
            plan_data=plan_data,
            plan_type=plan_type,
            metadata=metadata
        )

        return ActionResult(
            success=True,
            data={"item_id": item_id},
            metadata={"plan_type": plan_type}
        )

    def _context_get_current_plan(
        self,
        parameters: Dict[str, Any],
        session_context
    ) -> ActionResult:
        """Получение текущего плана"""
        plan = session_context.get_current_plan()

        if not plan:
            return ActionResult(
                success=True,
                data=None,
                metadata={"exists": False, "message": "Текущий план не найден"}
            )

        return ActionResult(
            success=True,
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
    ) -> ActionResult:
        """Получение элемента контекста по ID"""
        item_id = parameters.get("item_id")
        raise_on_missing = parameters.get("raise_on_missing", False)

        if not item_id:
            return ActionResult(
                success=False,
                error="item_id не указан для получения элемента контекста"
            )

        item = session_context.get_context_item(item_id, raise_on_missing=raise_on_missing)

        if not item:
            return ActionResult(
                success=False,
                error=f"Элемент контекста с ID {item_id} не найден",
                metadata={"item_id": item_id}
            )

        return ActionResult(
            success=True,
            data={
                "item_id": item.item_id if hasattr(item, 'item_id') else item_id,
                "content": item.content if hasattr(item, 'content') else item,
                "item_type": item.item_type if hasattr(item, 'item_type') else None
            },
            metadata={"item_id": item_id}
        )

    def _context_record_action(
        self,
        parameters: Dict[str, Any],
        session_context
    ) -> ActionResult:
        """Запись действия в контекст"""
        action_data = parameters.get("action_data")
        step_number = parameters.get("step_number")
        metadata = parameters.get("metadata")

        if not action_data:
            return ActionResult(
                success=False,
                error="action_data не указан для записи действия"
            )

        item_id = session_context.record_action(
            action_data=action_data,
            step_number=step_number,
            metadata=metadata
        )

        return ActionResult(
            success=True,
            data={"item_id": item_id},
            metadata={"step_number": step_number}
        )

    def _context_record_observation(
        self,
        parameters: Dict[str, Any],
        session_context
    ) -> ActionResult:
        """Запись наблюдения в контекст"""
        observation_data = parameters.get("observation_data")
        source = parameters.get("source")
        step_number = parameters.get("step_number")
        metadata = parameters.get("metadata")

        if not observation_data:
            return ActionResult(
                success=False,
                error="observation_data не указан для записи наблюдения"
            )

        item_id = session_context.record_observation(
            observation_data=observation_data,
            source=source,
            step_number=step_number,
            metadata=metadata
        )

        return ActionResult(
            success=True,
            data={"item_id": item_id},
            metadata={"source": source, "step_number": step_number}
        )
    
    def _resolve_component_for_action(self, action_name: str):
        """
        Разрешение компонента по имени действия.
        
        ARGS:
        - action_name: имя действия
        
        RETURNS:
        - BaseComponent: найденный компонент или None
        """
        # Разбиваем имя действия на тип и имя (например, "llm.generate" -> "llm", "generate")
        if '.' in action_name:
            component_type, component_name = action_name.split('.', 1)
        else:
            component_type = "skill"  # по умолчанию
            component_name = action_name
        
        # Ищем компонент в соответствующем реестре
        from core.application.context.application_context import ComponentType
        
        # Определяем тип компонента
        comp_type_map = {
            "skill": ComponentType.SKILL,
            "tool": ComponentType.TOOL,
            "service": ComponentType.SERVICE,
            "behavior": ComponentType.BEHAVIOR
        }
        
        comp_type = comp_type_map.get(component_type, ComponentType.SKILL)
        
        # Получаем компонент из реестра
        component = self.application_context.components.get(comp_type, component_name)
        
        return component
    
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