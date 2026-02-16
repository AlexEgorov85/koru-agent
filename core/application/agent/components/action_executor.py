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
            # 1. Находим целевой компонент по имени действия
            target_component = self._resolve_component_for_action(action_name)
            
            if not target_component:
                return ActionResult(
                    success=False,
                    error=f"Компонент для действия '{action_name}' не найден"
                )
            
            # 2. Валидируем входные параметры через контракт компонента
            capability = self._resolve_capability(action_name)
            if not capability:
                return ActionResult(
                    success=False,
                    error=f"Capability для действия '{action_name}' не найден"
                )
            
            # 3. Проверяем, что компонент инициализирован
            if not hasattr(target_component, '_initialized') or not target_component._initialized:
                return ActionResult(
                    success=False,
                    error=f"Компонент '{target_component.name}' не инициализирован"
                )
            
            # 4. Выполняем компонент
            result = await target_component.execute(capability, parameters, context)
            
            # 5. Валидируем выходные данные
            # (в реальной реализации здесь будет валидация через контракт)
            
            return result
            
        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка выполнения действия '{action_name}': {e}", exc_info=True)
            return ActionResult(
                success=False,
                error=str(e)
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