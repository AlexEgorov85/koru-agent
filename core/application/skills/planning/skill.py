import time
from typing import Any, Dict, List
from core.session_context.base_session_context import BaseSessionContext
from core.application.skills.base_skill import BaseSkill
from core.application.skills.planning.schema import StepStatus
from models.capability import Capability
from models.execution import ExecutionResult, ExecutionStatus


class PlanningSkill(BaseSkill):
    name = "planning"
    supported_strategies = ["planning", "react"]  # ← Поддержка нескольких стратегий

    def __init__(self, name: str, application_context: Any, component_config=None, **kwargs):
        super().__init__(name, application_context, component_config)
        # Получение зависимостей через порты
        self.prompt_service = application_context.get_resource("prompt_service")
        # Используем новый SQLQueryService для безопасного выполнения SQL-запросов
        self.sql_query_service = application_context.get_resource("sql_query_service")

        # Получение EventBus для публикации событий
        self.event_bus = application_context.get_resource("event_bus")

        # Получение ContractService для работы со схемами
        self.contract_service = application_context.get_resource("contract_service")

        # Инициализация логгера
        import logging
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def get_capabilities(self) -> List[Capability]:
        return [
            Capability(
                name="planning.create_plan",
                description="Создание первичного плана действий",
                skill_name=self.name,
                supported_strategies=self.supported_strategies,
                visiable=True
            ),
            Capability(
                name="planning.update_plan",
                description="Обновление существующего плана",
                skill_name=self.name,
                supported_strategies=self.supported_strategies,
                visiable=True
            ),
            Capability(
                name="planning.get_next_step",
                description="Получение следующего шага из плана",
                skill_name=self.name,
                supported_strategies=self.supported_strategies,
                visiable=True
            ),
            Capability(
                name="planning.update_step_status",
                description="Обновление статуса шага плана",
                skill_name=self.name,
                supported_strategies=self.supported_strategies,
                visiable=True
            ),
            Capability(
                name="planning.decompose_task",
                description="Декомпозиция сложной задачи на подзадачи",
                skill_name=self.name,
                supported_strategies=self.supported_strategies,
                visiable=True
            ),
            Capability(
                name="planning.mark_task_completed",
                description="Отметка задачи как завершенной",
                skill_name=self.name,
                supported_strategies=self.supported_strategies,
                visiable=True
            )
        ]

    async def execute(self, capability: "Capability", parameters: Dict[str, Any], context: "BaseSessionContext") -> ExecutionResult:
        # Валидируем параметры через кэшированный контракт
        try:
            input_schema = self.get_input_contract(capability.name)
            
            # Используем кэшированный контракт для валидации
            # В новой архитектуре валидация происходит через кэшированные контракты
            validation_result = await self.contract_service.validate(
                capability_name=capability.name,
                data=parameters,
                direction="input"
            )

            if not validation_result["is_valid"]:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result=None,
                    observation_item_id=None,
                    summary=f"Ошибка валидации параметров: {validation_result['errors']}",
                    error="INVALID_PARAMETERS"
                )

            validated_params = validation_result["validated_data"]
        except RuntimeError:
            # Если контракт не найден в кэше, используем переданные параметры без валидации
            # Это обеспечивает обратную совместимость
            validated_params = parameters
        except Exception as e:
            # Если возникла другая ошибка при валидации, также используем параметры без валидации
            validated_params = parameters

        # Делегирование конкретным методам
        if capability.name == "planning.create_plan":
            return await self._create_plan(validated_params, context)
        elif capability.name == "planning.update_plan":
            return await self._update_plan(validated_params, context)
        elif capability.name == "planning.get_next_step":
            return await self._get_next_step(validated_params, context)
        elif capability.name == "planning.update_step_status":
            return await self._update_step_status(validated_params, context)
        elif capability.name == "planning.decompose_task":
            return await self._decompose_task(validated_params, context)
        elif capability.name == "planning.mark_task_completed":
            return await self._mark_task_completed(validated_params, context)
        else:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Неизвестная capability: {capability.name}",
                error="UNSUPPORTED_CAPABILITY"
            )
    
    def _format_capabilities_for_prompt(self, capabilities):
        """Форматирует список capability для использования в промпте"""
        if not capabilities:
            return "Нет доступных capability"

        formatted = []
        for cap in capabilities:
            formatted.append(f"- {cap.name}: {cap.description}")
        return "\n".join(formatted)

    async def _create_plan(self, input_data: Dict[str, Any], context: "BaseSessionContext") -> ExecutionResult:
        try:
            # Публикуем событие начала создания плана
            if self.event_bus:
                await self.event_bus.publish(
                    "PLANNING_START",
                    {
                        "plan_goal": input_data.get('goal'),
                        "session_id": getattr(context, 'session_id', 'unknown'),
                        "timestamp": time.time()
                    }
                )

            # 1. Получение списка доступных capability для контекста промпта
            # Так как BaseSessionContext не имеет метода get_available_capabilities,
            # мы получаем их через прикладной контекст
            all_capabilities = self.application_context.get_all_capabilities()
            available_capabilities = []
            for cap_name in all_capabilities:
                cap = self.application_context.get_capability(cap_name)
                if cap and getattr(cap, 'visiable', True):  # используем 'visiable' как в react стратегии
                    available_capabilities.append(cap)

            capabilities_list = self._format_capabilities_for_prompt(available_capabilities)

            # 2. Рендеринг промпта через кэшированный сервис
            prompt = self.get_prompt("planning.create_plan")  # Используем кэшированный промпт из BaseComponent

            # 3. Генерация структурированного плана через системный контекст
            from models.llm_types import LLMRequest, StructuredOutputConfig

            # Получаем выходную схему из кэшированного контракта
            output_schema = self.get_output_contract("planning.create_plan")  # Используем кэшированный контракт из BaseComponent
            
            request = LLMRequest(
                prompt=input_data.get('goal', ''),
                system_prompt=prompt,
                temperature=0.3,
                max_tokens=1000,
                structured_output=StructuredOutputConfig(
                    output_model="CreatePlanOutput",  # Имя модели из реестра
                    schema_def=output_schema or {},  # Используем схему из ContractService
                    max_retries=3,
                    strict_mode=True
                ),
                correlation_id=f"plan_gen_{hash(input_data.get('goal', ''))}",
                capability_name="planning.create_plan"
            )

            # 4. Вызов LLM с ожиданием структурированного вывода
            llm_provider = self.application_context.infrastructure_context.get_provider("default_llm")
            llm_response = await llm_provider.generate_structured(
                user_prompt=request.prompt,
                output_schema=request.structured_output.schema_def,
                system_prompt=request.system_prompt,
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )

            # 5. Сохранение плана в контекст сессии
            # Преобразуем результат в словарь для сохранения
            if hasattr(llm_response, 'model_dump'):
                plan_data = llm_response.model_dump()
            elif hasattr(llm_response, 'dict'):
                plan_data = llm_response.dict()
            else:
                plan_data = llm_response  # уже словарь
                
            plan_item_id = context.record_plan(
                plan_data=plan_data,
                plan_type="initial"
            )
            context.set_current_plan(plan_item_id)

            # Публикуем событие успешного создания плана
            if self.event_bus:
                await self.event_bus.publish(
                    "PLAN_CREATED",
                    {
                        "plan_id": plan_item_id,
                        "plan_goal": input_data.get('goal'),
                        "steps_count": len(llm_response.steps) if hasattr(llm_response, 'steps') else 0,
                        "session_id": getattr(context, 'session_id', 'unknown'),
                        "timestamp": time.time()
                    }
                )

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=llm_response.model_dump() if hasattr(llm_response, 'model_dump') else llm_response,
                observation_item_id=plan_item_id,
                summary=f"Создан план из {len(llm_response.steps) if hasattr(llm_response, 'steps') else 0} шагов для цели: {input_data.get('goal', '')[:50]}...",
                error=None
            )

        except Exception as e:
            self.logger.error(f"Ошибка создания плана: {str(e)}", exc_info=True)

            # Публикуем событие ошибки создания плана
            if self.event_bus:
                await self.event_bus.publish(
                    "PLAN_CREATION_FAILED",
                    {
                        "error": str(e),
                        "plan_goal": input_data.get('goal'),
                        "session_id": getattr(context, 'session_id', 'unknown'),
                        "timestamp": time.time()
                    }
                )

            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Не удалось создать план: {str(e)[:100]}",
                error="PLAN_CREATION_ERROR"
            )
    
    async def _update_plan(self, input_data: Dict[str, Any], context: "BaseSessionContext") -> ExecutionResult:
        # Заглушка для реализации
        pass
    
    async def _get_next_step(self, input_data: Dict[str, Any], context: "BaseSessionContext") -> ExecutionResult:
        """
        Получение следующего шага из плана с поддержкой иерархии.
        Обходит вложенные планы (сначала подзадачи, потом родительские).
        """
        try:
            # Получаем текущий план
            current_plan_item = context.get_current_plan()
            if not current_plan_item:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result=None,
                    observation_item_id=None,
                    summary="Нет текущего плана для получения следующего шага",
                    error="NO_CURRENT_PLAN"
                )
            
            current_plan = current_plan_item.content
            
            # Проверяем, является ли это иерархическим планом
            if current_plan.get("plan_type") == "hierarchy" or "sub_plans" in current_plan:
                # Это иерархический план, нужно обработать подпланы
                next_step = await self._get_next_step_from_hierarchy(current_plan, input_data, context)
            else:
                # Это обычный план, обрабатываем как обычно
                next_step = await self._get_next_step_from_flat_plan(current_plan, input_data, context)
            
            if next_step:
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    result={"step": next_step},
                    observation_item_id=None,
                    summary=f"Получен следующий шаг: {next_step.get('step_id', 'unknown')}",
                    error=None
                )
            else:
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    result={"step": None},
                    observation_item_id=None,
                    summary="Больше нет шагов в плане",
                    error=None
                )
                
        except Exception as e:
            self.logger.error(f"Ошибка получения следующего шага: {str(e)}", exc_info=True)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Не удалось получить следующий шаг: {str(e)[:100]}",
                error="GET_NEXT_STEP_ERROR"
            )

    async def _get_next_step_from_flat_plan(self, plan: Dict[str, Any], input_data: Dict[str, Any], context: "BaseSessionContext") -> Dict[str, Any]:
        """
        Получение следующего шага из плоского плана.
        """
        steps = plan.get("steps", [])
        
        # Находим текущий шаг
        current_step_idx = -1
        if input_data.current_step_id:
            for idx, step in enumerate(steps):
                if step.get("step_id") == input_data.current_step_id:
                    current_step_idx = idx
                    break
        
        # Возвращаем следующий шаг после текущего
        next_step_idx = current_step_idx + 1
        if next_step_idx < len(steps):
            return steps[next_step_idx]
        
        return None

    async def _get_next_step_from_hierarchy(self, hierarchy_plan: Dict[str, Any], input_data: Dict[str, Any], context: "BaseSessionContext") -> Dict[str, Any]:
        """
        Получение следующего шага из иерархического плана.
        Обходит подпланы рекурсивно.
        """
        # Получаем подпланы
        sub_plans = hierarchy_plan.get("sub_plans", [])
        
        # Если есть подпланы, ищем следующий шаг в них
        for sub_plan_info in sub_plans:
            # Получаем сам план из контекста
            sub_plan_item = context.get_context_item(sub_plan_info.get("plan_id"))
            if sub_plan_item and sub_plan_item.content:
                # Рекурсивно получаем следующий шаг из подплана
                sub_plan = sub_plan_item.content
                # Создаем временный input_data для подплана
                sub_input = {
                    "plan_id": sub_plan_info.get("plan_id"),
                    "current_step_id": None  # начинаем с начала подплана
                }
                
                # Получаем следующий шаг из подплана
                next_step = await self._get_next_step_from_flat_plan(sub_plan, sub_input, context)
                if next_step:
                    # Добавляем информацию о том, что это часть иерархии
                    next_step["hierarchy_info"] = {
                        "parent_task_id": hierarchy_plan.get("parent_task_id"),
                        "subtask_id": sub_plan_info.get("subtask_id"),
                        "subtask_description": sub_plan_info.get("description")
                    }
                    return next_step
        
        # Если в подпланах больше нет шагов, возвращаем None
        return None
    
    async def _update_step_status(self, input_data: Dict[str, Any], context: "BaseSessionContext") -> ExecutionResult:
        """
        Обновление статуса шага плана.
        При ошибке выполнения шага вызывает автоматическую коррекцию плана.
        """
        try:
            # Публикуем событие обновления статуса шага
            if self.event_bus:
                await self.event_bus.publish(
                    "STEP_STATUS_UPDATE",
                    {
                        "step_id": input_data.get('step_id'),
                        "new_status": input_data.get('status', 'pending'),
                        "session_id": getattr(context, 'session_id', 'unknown'),
                        "timestamp": time.time()
                    }
                )

            # Получаем текущий план
            current_plan_item = context.get_current_plan()
            if not current_plan_item:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result=None,
                    observation_item_id=None,
                    summary="Нет текущего плана для обновления статуса шага",
                    error="NO_CURRENT_PLAN"
                )

            current_plan = current_plan_item.content
            steps = current_plan.get("steps", [])

            # Находим шаг для обновления
            step_to_update = None
            step_index = -1
            for idx, step in enumerate(steps):
                if step.get("step_id") == input_data.get('step_id'):
                    step_to_update = step.copy()
                    step_index = idx
                    break

            if not step_to_update:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result=None,
                    observation_item_id=None,
                    summary=f"Шаг с ID {input_data.get('step_id')} не найден в плане",
                    error="STEP_NOT_FOUND"
                )

            # Обновляем статус шага
            step_to_update["status"] = input_data.get('status', 'pending')
            if input_data.get('result'):
                step_to_update["result"] = input_data.get('result')
            if input_data.get('error_message'):
                step_to_update["error_message"] = input_data.get('error_message')

            # Если статус - FAILED, запускаем коррекцию плана
            if input_data.get('status') == 'FAILED' and input_data.get('error_message'):

                # Публикуем событие ошибки шага
                if self.event_bus:
                    await self.event_bus.publish(
                        "STEP_FAILED",
                        {
                            "step_id": input_data.get('step_id'),
                            "error_message": input_data.get('error_message'),
                            "session_id": getattr(context, 'session_id', 'unknown'),
                            "timestamp": time.time()
                        }
                    )

                # Выполняем коррекцию плана
                correction_result = await self._correct_plan_after_failure(
                    current_plan=current_plan,
                    failed_step=step_to_update,
                    error_info=input_data.get('error_message'),
                    context=context
                )

                if correction_result.status == ExecutionStatus.SUCCESS:
                    # Если коррекция прошла успешно, возвращаем результат коррекции
                    # Публикуем событие успешной коррекции плана
                    if self.event_bus:
                        await self.event_bus.publish(
                            "PLAN_CORRECTED",
                            {
                                "plan_id": correction_result.observation_item_id,
                                "step_id": input_data.get('step_id'),
                                "session_id": getattr(context, 'session_id', 'unknown'),
                                "timestamp": time.time()
                            }
                        )

                    return correction_result
                else:
                    # Если коррекция не удалась, продолжаем с обычным обновлением

                    # Публикуем событие неудачной коррекции плана
                    if self.event_bus:
                        await self.event_bus.publish(
                            "PLAN_CORRECTION_FAILED",
                            {
                                "step_id": input_data.get('step_id'),
                                "error_message": correction_result.summary,
                                "session_id": getattr(context, 'session_id', 'unknown'),
                                "timestamp": time.time()
                            }
                        )

            # Обновляем шаг в плане
            updated_steps = steps.copy()
            updated_steps[step_index] = step_to_update

            # Обновляем план в контексте
            updated_plan = current_plan.copy()
            updated_plan["steps"] = updated_steps

            plan_item_id = context.record_plan(
                plan_data=updated_plan,
                plan_type="update"
            )
            context.set_current_plan(plan_item_id)

            # Пытаемся получить следующий шаг
            next_step = None
            if step_index >= 0 and step_index + 1 < len(updated_steps):
                next_step = updated_steps[step_index + 1]

            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result={
                    "updated_step": step_to_update,
                    "next_step": next_step
                },
                observation_item_id=plan_item_id,
                summary=f"Статус шага {input_data.get('step_id')} обновлен на {input_data.get('status', 'pending')}",
                error=None
            )

        except Exception as e:
            self.logger.error(f"Ошибка обновления статуса шага: {str(e)}", exc_info=True)

            # Публикуем событие ошибки обновления статуса шага
            if self.event_bus:
                await self.event_bus.publish(
                    "STEP_STATUS_UPDATE_FAILED",
                    {
                        "step_id": input_data.get('step_id'),
                        "error": str(e),
                        "session_id": getattr(context, 'session_id', 'unknown'),
                        "timestamp": time.time()
                    }
                )

            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Не удалось обновить статус шага: {str(e)[:100]}",
                error="UPDATE_STEP_STATUS_ERROR"
            )
    
    async def _decompose_task(self, input_data: Dict[str, Any], context: "BaseSessionContext") -> ExecutionResult:
        """
        Декомпозиция сложной задачи на иерархию подзадач.
        РЕЗУЛЬТАТ: создает вложенный план с подзадачами
        """
        try:
            # Публикуем событие начала декомпозиции задачи
            if self.event_bus:
                await self.event_bus.publish(
                    "TASK_DECOMPOSITION_START",
                    {
                        "task_id": input_data.task_id,
                        "task_description": input_data.task_description,
                        "session_id": getattr(context, 'session_id', 'unknown'),
                        "timestamp": time.time()
                    }
                )
            
            # 1. Получение списка доступных capability для контекста промпта
            all_capabilities = self.application_context.get_all_capabilities()
            available_capabilities = []
            for cap_name in all_capabilities:
                cap = self.application_context.get_capability(cap_name)
                if cap and getattr(cap, 'visiable', True):  # используем 'visiable' как в react стратегии
                    available_capabilities.append(cap)
            
            capabilities_list = self._format_capabilities_for_prompt(available_capabilities)
            
            # 2. Рендеринг промпта декомпозиции
            prompt = await self.prompt_services.render(
                capability_name="planning.decompose_task",
                variables={
                    "task_id": input_data.task_id,
                    "task_description": input_data.task_description,
                    "context": input_data.context or "",
                    "capabilities_list": capabilities_list
                }
            )
            
            # 3. Генерация иерархии подзадач
            from models.llm_types import LLMRequest, StructuredOutputConfig
            request = LLMRequest(
                prompt=input_data.task_description,
                system_prompt=prompt,
                temperature=0.3,
                max_tokens=1000,
                structured_output=StructuredOutputConfig(
                    output_model="DecomposeTaskOutput",  # Имя модели из реестра
                    schema_def=self.get_output_contract("planning.decompose_task"),  # Используем кэшированную схему
                    max_retries=3,
                    strict_mode=True
                ),
                correlation_id=f"task_decomp_{hash(input_data.task_description)}",
                capability_name="planning.decompose_task"
            )
            
            # 4. Вызов LLM с ожиданием структурированного вывода
            llm_provider = self.application_context.infrastructure_context.get_provider("default_llm")
            decomposition = await llm_provider.generate_structured(
                user_prompt=request.prompt,
                output_schema=request.structured_output.schema_def,
                system_prompt=request.system_prompt,
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )
            
            # 5. Создание вложенного плана для каждой подзадачи
            sub_plans = []
            
            # Получаем подзадачи из результата
            if hasattr(decomposition, 'subtasks'):
                # Если это Pydantic-модель
                subtasks_list = decomposition.subtasks
            else:
                # Если это словарь
                subtasks_list = decomposition.get('subtasks', []) if isinstance(decomposition, dict) else decomposition
            
            for subtask in subtasks_list:
                # Определяем поля в зависимости от типа subtask
                if hasattr(subtask, 'description'):
                    # Это Pydantic-модель
                    description = subtask.description
                    subtask_id = subtask.subtask_id
                else:
                    # Это словарь
                    description = subtask.get('description', '') if isinstance(subtask, dict) else ''
                    subtask_id = subtask.get('subtask_id', '') if isinstance(subtask, dict) else ''
                
                # Создаем словарь параметров для мини-плана
                sub_plan_params = {
                    "goal": description,
                    "max_steps": min(3, len(description.split('.'))),  # Максимум 3 шага на подзадачу
                    "context": f"Подзадача {subtask_id} родительской задачи {input_data.task_id}",
                    "strategy": "iterative"
                }
                sub_plan_result = await self._create_plan(sub_plan_params, context)
                
                if sub_plan_result.status == ExecutionStatus.SUCCESS:
                    # Определяем значения для добавления в список подпланов
                    if hasattr(subtask, 'subtask_id'):
                        # Это Pydantic-модель
                        subtask_complexity = subtask.complexity
                    else:
                        # Это словарь
                        subtask_complexity = subtask.get('complexity', '') if isinstance(subtask, dict) else ''
                    
                    sub_plans.append({
                        "subtask_id": subtask_id,  # уже получили выше
                        "plan_id": sub_plan_result.observation_item_id,
                        "description": description,  # уже получили выше
                        "complexity": subtask_complexity
                    })
            
            # 6. Сохранение иерархии в контекст
            hierarchy_data = {
                "parent_task_id": decomposition.parent_task_id,
                "original_task": decomposition.original_task,
                "sub_plans": sub_plans,
                "decomposition_strategy": decomposition.decomposition_strategy.value,
                "metadata": decomposition.metadata
            }
            
            hierarchy_id = context.record_plan(
                plan_data=hierarchy_data,
                plan_type="hierarchy"
            )
            
            # Публикуем событие успешной декомпозиции задачи
            if self.event_bus:
                await self.event_bus.publish(
                    "TASK_DECOMPOSED",
                    {
                        "task_id": input_data.task_id,
                        "subtasks_count": len(sub_plans),
                        "session_id": getattr(context, 'session_id', 'unknown'),
                        "timestamp": time.time()
                    }
                )
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=hierarchy_data,
                observation_item_id=hierarchy_id,
                summary=f"Декомпозирована задача {input_data.task_id} на {len(sub_plans)} подзадач",
                error=None
            )
            
        except Exception as e:
            self.logger.error(f"Ошибка декомпозиции задачи: {str(e)}", exc_info=True)
            
            # Публикуем событие ошибки декомпозиции задачи
            if self.event_bus:
                await self.event_bus.publish(
                    "TASK_DECOMPOSITION_FAILED",
                    {
                        "task_id": input_data.task_id,
                        "error": str(e),
                        "session_id": getattr(context, 'session_id', 'unknown'),
                        "timestamp": time.time()
                    }
                )
            
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Не удалось декомпозировать задачу: {str(e)[:100]}",
                error="DECOMPOSITION_ERROR"
            )
    
    async def _execute_safe_sql(
        self,
        user_question: str,
        context_tables: List[str],
        max_rows: int = 50
    ) -> ExecutionResult:
        """
        Безопасное выполнение SQL через централизованный сервис.
        ИСПОЛЬЗУЕТ: только параметризованные запросы через SQLQueryService
        """
        try:
            # Проверяем, что SQLQueryService доступен
            if not self.sql_query_service:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result=None,
                    observation_item_id=None,
                    summary="SQLQueryService не зарегистрирован",
                    error="SQL_SERVICE_UNAVAILABLE"
                )
            
            # Выполнение через SQLQueryService с использованием метода для пользовательских запросов
            result = await self.sql_query_services.execute_query_from_user_request(
                user_question=user_question,
                tables=context_tables,
                max_rows=max_rows
            )
            
            if result.success:
                return ExecutionResult(
                    status=ExecutionStatus.SUCCESS,
                    result={
                        "rows": result.rows,
                        "columns": result.columns,
                        "rowcount": result.rowcount
                    },
                    observation_item_id=None,
                    summary=f"Выполнен безопасный SQL-запрос, получено {result.rowcount} строк",
                    error=None
                )
            else:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result=None,
                    observation_item_id=None,
                    summary=f"Ошибка выполнения SQL: {result.error}",
                    error="SQL_EXECUTION_ERROR"
                )
                
        except Exception as e:
            self.logger.error(f"Ошибка безопасного SQL: {str(e)}", exc_info=True)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Критическая ошибка: {str(e)[:100]}",
                error="SQL_CRITICAL_ERROR"
            )

    async def _correct_plan_after_failure(
        self,
        current_plan: Dict[str, Any],
        failed_step: Dict[str, Any],
        error_info: str,
        context: "BaseSessionContext"
    ) -> ExecutionResult:
        """
        Автоматическая коррекция плана после ошибки выполнения шага.
        ИСПОЛЬЗУЕТ: промпт коррекции + анализ ошибки через системный контекст
        """
        try:
            # Публикуем событие начала коррекции плана
            if self.event_bus:
                await self.event_bus.publish(
                    "PLAN_CORRECTION_START",
                    {
                        "failed_step_id": failed_step.get('step_id'),
                        "error_info": error_info,
                        "session_id": getattr(context, 'session_id', 'unknown'),
                        "timestamp": time.time()
                    }
                )
            
            # 1. Анализ ошибки через структурированный вывод
            analysis_result = await self._analyze_step_failure(failed_step, error_info, context)
            if analysis_result.status != ExecutionStatus.SUCCESS:
                self.logger.warning("Не удалось проанализировать ошибку, используем базовую стратегию коррекции")
                error_analysis = {
                    "error_type": "unknown",
                    "reason": "Не удалось провести детальный анализ ошибки",
                    "suggested_fix": "Попробуйте повторить шаг или пропустить его",
                    "severity": "medium",
                    "reasoning": "Ошибка при анализе ошибки выполнения шага",
                    "summary": "Ошибка анализа"
                }
            else:
                error_analysis = analysis_result.result

            # 2. Формирование промпта коррекции
            import json
            correction_prompt = await self.prompt_services.render(
                capability_name="planning.update_plan",
                variables={
                    "current_plan": json.dumps(current_plan, ensure_ascii=False),
                    "new_requirements": f"Исправить шаг {failed_step['step_id']} из-за ошибки: {error_analysis.summary}",
                    "constraints": "Сохранить логическую связность плана, не увеличивать общее количество шагов",
                    "context": f"Ошибка: {error_info}. Анализ: {error_analysis.reasoning}"
                }
            )
            
            # 3. Генерация исправленного плана
            from models.llm_types import LLMRequest, StructuredOutputConfig
            request = LLMRequest(
                prompt="Исправь план с учетом ошибки выполнения",
                system_prompt=correction_prompt,
                temperature=0.3,
                max_tokens=1000,
                structured_output=StructuredOutputConfig(
                    output_model="UpdatePlanOutput",  # Имя модели из реестра
                    schema_def=self.get_output_contract("planning.update_plan"),  # Используем кэшированную схему
                    max_retries=3,
                    strict_mode=True
                ),
                correlation_id=f"plan_correction_{hash(error_info)}",
                capability_name="planning.update_plan"
            )
            
            # 4. Вызов LLM с ожиданием структурированного вывода
            llm_provider = self.application_context.infrastructure_context.get_provider("default_llm")
            corrected_plan = await llm_provider.generate_structured(
                user_prompt=request.prompt,
                output_schema=request.structured_output.schema_def,
                system_prompt=request.system_prompt,
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )
            
            # 5. Сохранение исправленного плана
            # Преобразуем результат в словарь для сохранения
            if hasattr(corrected_plan, 'model_dump'):
                plan_data = corrected_plan.model_dump()
            elif hasattr(corrected_plan, 'dict'):
                plan_data = corrected_plan.dict()
            else:
                plan_data = corrected_plan  # уже словарь
                
            plan_item_id = context.record_plan(
                plan_data=plan_data,
                plan_type="update"
            )
            context.set_current_plan(plan_item_id)
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=corrected_plan.model_dump(),
                observation_item_id=plan_item_id,
                summary=f"План автоматически скорректирован после ошибки шага {failed_step['step_id']}",
                error=None
            )
            
        except Exception as e:

            # Публикуем событие ошибки коррекции плана
            if self.event_bus:
                await self.event_bus.publish(
                    "PLAN_CORRECTION_FAILED_EVENT",
                    {
                        "failed_step_id": failed_step.get('step_id'),
                        "error": str(e),
                        "session_id": getattr(context, 'session_id', 'unknown'),
                        "timestamp": time.time()
                    }
                )

            # Fallback: помечаем шаг как пропущенный, продолжаем выполнение
            return await self._skip_failed_step(failed_step, context)

    async def _skip_failed_step(
        self,
        failed_step: Dict[str, Any],
        context: "BaseSessionContext"
    ) -> ExecutionResult:
        """
        Помечает неудачный шаг как пропущенный и продолжает выполнение плана.
        """
        try:
            # Обновляем статус шага на "SKIPPED"
            updated_step = {**failed_step, "status": StepStatus.SKIPPED}
            
            # Пытаемся получить следующий шаг плана
            current_plan_item = context.get_current_plan()
            if not current_plan_item:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result=None,
                    observation_item_id=None,
                    summary="Нет текущего плана для продолжения",
                    error="NO_CURRENT_PLAN"
                )
            
            current_plan = current_plan_item.content
            steps = current_plan.get("steps", [])
            
            # Находим следующий шаг
            current_step_idx = -1
            for idx, step in enumerate(steps):
                if step.get("step_id") == failed_step.get("step_id"):
                    current_step_idx = idx
                    break
            
            next_step = None
            if current_step_idx >= 0 and current_step_idx + 1 < len(steps):
                next_step = steps[current_step_idx + 1]
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result={
                    "updated_step": updated_step,
                    "next_step": next_step
                },
                observation_item_id=None,
                summary=f"Шаг {failed_step.get('step_id')} помечен как пропущенный, переход к следующему шагу",
                error=None
            )
        except Exception as e:
            self.logger.error(f"Ошибка при пропуске шага: {str(e)}", exc_info=True)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Не удалось пропустить шаг: {str(e)}",
                error="SKIP_STEP_ERROR"
            )

    async def _analyze_step_failure(
        self,
        current_step: Dict[str, Any],
        error_info: str,
        context: "BaseSessionContext"
    ) -> ExecutionResult:
        """
        Анализ ошибки выполнения шага плана.
        """
        try:
            # Формирование промпта для анализа ошибки
            prompt = await self.prompt_services.render(
                capability_name="planning.analyze_step_failure",
                variables={
                    "step_description": current_step.get("description", ""),
                    "capability_name": current_step.get("capability_name", ""),
                    "parameters": str(current_step.get("parameters", {})),
                    "error_info": error_info,
                    "context": context.get_summary()
                }
            )
            
            # Генерация анализа ошибки через системный контекст
            from models.llm_types import LLMRequest, StructuredOutputConfig
            request = LLMRequest(
                prompt=f"Проанализируй ошибку выполнения шага: {error_info}",
                system_prompt=prompt,
                temperature=0.3,
                max_tokens=500,
                structured_output=StructuredOutputConfig(
                    output_model="ErrorAnalysisOutput",  # Имя модели из реестра
                    schema_def=self.get_output_contract("planning.analyze_step_failure"),  # Используем кэшированную схему
                    max_retries=2,
                    strict_mode=True
                ),
                correlation_id=f"error_analysis_{hash(error_info)}",
                capability_name="planning.analyze_step_failure"
            )
            
            # Вызов LLM с ожиданием структурированного вывода
            llm_provider = self.application_context.infrastructure_context.get_provider("default_llm")
            analysis_result = await llm_provider.generate_structured(
                user_prompt=request.prompt,
                output_schema=request.structured_output.schema_def,
                system_prompt=request.system_prompt,
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )
            
            # Преобразуем результат в словарь для возврата
            if hasattr(analysis_result, 'dict'):
                result_data = analysis_result.dict()
                summary_text = analysis_result.summary if hasattr(analysis_result, 'summary') else str(result_data.get('summary', ''))
            else:
                result_data = analysis_result  # уже словарь
                summary_text = str(result_data.get('summary', '')) if isinstance(result_data, dict) else str(result_data)
                
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=result_data,
                observation_item_id=None,
                summary=f"Проанализирована ошибка шага {current_step.get('step_id', 'unknown')}: {summary_text}",
                error=None
            )
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа ошибки шага: {str(e)}", exc_info=True)
            # Возвращаем базовый анализ в случае ошибки
            basic_analysis = {
                "error_type": "unknown",
                "reason": "Не удалось провести детальный анализ ошибки",
                "suggested_fix": "Попробуйте повторить шаг или пропустить его",
                "severity": "medium",
                "reasoning": "Ошибка при анализе ошибки выполнения шага",
                "summary": "Ошибка анализа"
            }
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=basic_analysis,
                observation_item_id=None,
                summary=f"Базовый анализ ошибки: {basic_analysis.get('summary', 'No summary')}",
                error=None
            )

    async def _mark_task_completed(self, input_data: Dict[str, Any], context: "BaseSessionContext") -> ExecutionResult:
        # Заглушка для реализации
        pass

    async def initialize(self) -> bool:
        """Инициализация навыка."""
        # В PlanningSkill нет специфической инициализации
        return True

    async def shutdown(self):
        """Очистка ресурсов навыка."""
        # В PlanningSkill нет специфических ресурсов для очистки
        pass