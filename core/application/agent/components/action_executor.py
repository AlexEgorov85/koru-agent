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
from typing import Dict, Any, Optional, TYPE_CHECKING, Generic, TypeVar
from pydantic import BaseModel

from core.models.data.execution import ExecutionResult
from core.models.data.capability import Capability

if TYPE_CHECKING:
    from core.application.context.application_context import ApplicationContext

# Generic тип для типизированных данных в ActionResult
T = TypeVar('T')


class ActionResult(Generic[T]):
    """
    Результат выполнения действия через ActionExecutor.
    
    ARCHITECTURE:
    - data сохраняет тип T (Pydantic модель) до границ приложения
    - model_dump() вызывается только при сериализации на границах
    - Generic тип позволяет IDE поддерживать автокомплит и валидацию типов
    
    EXAMPLE:
        # Компонент возвращает типизированный результат
        result: ActionResult[BookLibrarySearchOutput] = await executor.execute(...)
        
        # Доступ к полям через IDE автокомплит
        books = result.data.rows  # ✅ IDE знает тип rows
        count = result.data.rowcount  # ✅ IDE знает тип rowcount
        
        # Сериализация только на границе
        await event_bus.publish(..., data=result.to_dict())  # ← model_dump() здесь
    """
    
    def __init__(
        self, 
        success: bool, 
        data: Optional[T] = None, 
        metadata: Dict[str, Any] = None, 
        error: str = None, 
        llm_called: bool = False
    ):
        self.success = success
        self.data = data  # ← Сохраняем тип T (Pydantic модель или None)
        self.metadata = metadata or {}
        self.error = error
        self.llm_called = llm_called

    def __repr__(self):
        data_repr = f"{type(self.data).__name__}(...)" if isinstance(self.data, BaseModel) else self.data
        return f"ActionResult(success={self.success}, data={data_repr}, error={self.error}, llm_called={self.llm_called})"
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Сериализация в dict — ТОЛЬКО для использования на границах приложения.
        
        ГРАНИЦЫ ПРИЛОЖЕНИЯ:
        - EventBus (публикация событий)
        - Storage (сохранение в БД/файлы)
        - API (HTTP/WebSocket ответы)
        
        ВНУТРИ ПРИЛОЖЕНИЯ:
        - Используйте self.data напрямую (сохраняется типизация)
        - IDE поддерживает автокомплит полей Pydantic модели
        """
        return {
            'success': self.success,
            'data': self.data.model_dump() if isinstance(self.data, BaseModel) else self.data,
            'metadata': self.metadata,
            'error': self.error,
            'llm_called': self.llm_called
        }
    
    @classmethod
    def success_result(cls, data: T, metadata: Optional[Dict[str, Any]] = None) -> 'ActionResult[T]':
        """Factory метод для успешного результата с типизированными данными."""
        return cls(success=True, data=data, metadata=metadata or {})
    
    @classmethod
    def failure_result(cls, error: str, metadata: Optional[Dict[str, Any]] = None) -> 'ActionResult':
        """Factory метод для неудачного результата."""
        return cls(success=False, data=None, error=error, metadata=metadata or {})


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
        # Ленивое получение logger чтобы избежать циклического импорта
        import logging
        self.logger = logging.getLogger(__name__)
    
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

            # 2. Обработка LLM действий (llm.*)
            if action_name.startswith("llm."):
                return await self._execute_llm_action(action_name, parameters, context)

            # 3. Находим целевой компонент по имени действия
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
        - context.get_all_items: получение всех элементов контекста
        - context.get_step_history: получение истории шагов
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
            elif action_name == "context.get_all_items":
                return self._context_get_all_items(parameters, session_context)
            elif action_name == "context.get_step_history":
                return self._context_get_step_history(parameters, session_context)
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

    def _context_get_all_items(
        self,
        parameters: Dict[str, Any],
        session_context
    ) -> ActionResult:
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
                return ActionResult(
                    success=True,
                    data={"items": items_dict},
                    metadata={"count": len(items_dict)}
                )
            else:
                return ActionResult(
                    success=True,
                    data={"items": {}},
                    metadata={"count": 0, "message": "data_context не доступен"}
                )
        except Exception as e:
            return ActionResult(
                success=False,
                error=f"Ошибка получения всех items: {str(e)}"
            )

    def _context_get_step_history(
        self,
        parameters: Dict[str, Any],
        session_context
    ) -> ActionResult:
        """Получение истории шагов выполнения"""
        try:
            # Получаем step_history из session_context
            if hasattr(session_context, 'step_context') and hasattr(session_context.step_context, 'steps'):
                steps = session_context.step_context.steps
                # Конвертируем шаги в dict формат
                steps_data = []
                for step in steps:
                    if hasattr(step, '__dict__'):
                        steps_data.append({
                            "action": getattr(step, 'action', 'unknown'),
                            "result": getattr(step, 'result', ''),
                            "step_number": getattr(step, 'step_number', 0)
                        })
                    else:
                        steps_data.append(step)
                return ActionResult(
                    success=True,
                    data={"steps": steps_data},
                    metadata={"count": len(steps_data)}
                )
            else:
                return ActionResult(
                    success=True,
                    data={"steps": []},
                    metadata={"count": 0, "message": "step_context не доступен"}
                )
        except Exception as e:
            return ActionResult(
                success=False,
                error=f"Ошибка получения step history: {str(e)}"
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

    async def _execute_llm_action(
        self,
        action_name: str,
        parameters: Dict[str, Any],
        context: ExecutionContext
    ) -> ActionResult:
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
                return ActionResult(
                    success=False,
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
                return ActionResult(
                    success=False,
                    error=f"Неизвестное LLM действие: {action_name}"
                )

        except Exception as e:
            if self.logger:
                self.logger.error(f"Ошибка LLM действия '{action_name}': {e}", exc_info=True)
            return ActionResult(
                success=False,
                error=str(e)
            )

    async def _llm_generate(
        self,
        llm_provider,
        parameters: Dict[str, Any],
        orchestrator: Any = None,
        context: ExecutionContext = None
    ) -> ActionResult:
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
            return ActionResult(success=False, error="Параметр 'prompt' обязателен")

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

        return ActionResult(
            success=True,
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
    ) -> ActionResult:
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
            return ActionResult(success=False, error="Параметр 'prompt' обязателен")

        # Получаем конфигурацию структурированного вывода
        structured_output = parameters.get("structured_output")
        if not structured_output:
            return ActionResult(success=False, error="Параметр 'structured_output' обязателен")

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
            return ActionResult(
                success=False,
                error="LLMOrchestrator недоступен — требуется для структурированной генерации"
            )

        response = await orchestrator.execute_structured(
            request=request,
            provider=llm_provider,
            max_retries=parameters.get("max_retries", 3),
            attempt_timeout=parameters.get("attempt_timeout"),
            total_timeout=parameters.get("total_timeout"),
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