from typing import Any, Dict, List
from core.skills.base_skill import BaseSkill
from core.skills.planning.schema import (
    CreatePlanInput, CreatePlanOutput,
    UpdatePlanInput, UpdatePlanOutput,
    GetNextStepInput, GetNextStepOutput,
    UpdateStepStatusInput, UpdateStepStatusOutput,
    DecomposeTaskInput, DecomposeTaskOutput,
    MarkTaskCompletedInput, MarkTaskCompletedOutput,
    ErrorAnalysisOutput, StepStatus
)
from models.capability import Capability
from models.execution import ExecutionResult, ExecutionStatus


class PlanningSkill(BaseSkill):
    name = "planning"
    supported_strategies = ["planning"]  # ← Только для планирования!
    
    def __init__(self, name: str, system_context: Any, **kwargs):
        super().__init__(name, system_context, **kwargs)
        # Получение зависимостей через порты
        self.prompt_service = system_context.get_resource("prompt_service")
        # Используем новый SQLQueryService для безопасного выполнения SQL-запросов
        self.sql_query_service = system_context.get_resource("sql_query_service")
        
        # Получение EventBus для публикации событий
        self.event_bus = system_context.get_resource("event_bus")
        
        # Инициализация логгера
        import logging
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def get_capabilities(self) -> List[Capability]:
        return [
            Capability(
                name="planning.create_plan",
                description="Создание первичного плана действий",
                parameters_schema=CreatePlanInput.model_json_schema(),
                parameters_class=CreatePlanInput,
                skill_name=self.name,
                supported_strategies=self.supported_strategies
            ),
            Capability(
                name="planning.update_plan",
                description="Обновление существующего плана",
                parameters_schema=UpdatePlanInput.model_json_schema(),
                parameters_class=UpdatePlanInput,
                skill_name=self.name,
                supported_strategies=self.supported_strategies
            ),
            Capability(
                name="planning.get_next_step",
                description="Получение следующего шага из плана",
                parameters_schema=GetNextStepInput.model_json_schema(),
                parameters_class=GetNextStepInput,
                skill_name=self.name,
                supported_strategies=self.supported_strategies
            ),
            Capability(
                name="planning.update_step_status",
                description="Обновление статуса шага плана",
                parameters_schema=UpdateStepStatusInput.model_json_schema(),
                parameters_class=UpdateStepStatusInput,
                skill_name=self.name,
                supported_strategies=self.supported_strategies
            ),
            Capability(
                name="planning.decompose_task",
                description="Декомпозиция сложной задачи на подзадачи",
                parameters_schema=DecomposeTaskInput.model_json_schema(),
                parameters_class=DecomposeTaskInput,
                skill_name=self.name,
                supported_strategies=self.supported_strategies
            ),
            Capability(
                name="planning.mark_task_completed",
                description="Отметка задачи как завершенной",
                parameters_schema=MarkTaskCompletedInput.model_json_schema(),
                parameters_class=MarkTaskCompletedInput,
                skill_name=self.name,
                supported_strategies=self.supported_strategies
            )
        ]
    
    async def execute(self, capability: "Capability", parameters: Dict[str, Any], context: "BaseSessionContext") -> ExecutionResult:
        # Делегирование конкретным методам
        if capability.name == "planning.create_plan":
            return await self._create_plan(CreatePlanInput(**parameters), context)
        elif capability.name == "planning.update_plan":
            return await self._update_plan(UpdatePlanInput(**parameters), context)
        elif capability.name == "planning.get_next_step":
            return await self._get_next_step(GetNextStepInput(**parameters), context)
        elif capability.name == "planning.update_step_status":
            return await self._update_step_status(UpdateStepStatusInput(**parameters), context)
        elif capability.name == "planning.decompose_task":
            return await self._decompose_task(DecomposeTaskInput(**parameters), context)
        elif capability.name == "planning.mark_task_completed":
            return await self._mark_task_completed(MarkTaskCompletedInput(**parameters), context)
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
    
    async def _create_plan(self, input_data: CreatePlanInput, context: "BaseSessionContext") -> ExecutionResult:
        try:
            # Публикуем событие начала создания плана
            if self.event_bus:
                await self.event_bus.publish(
                    "PLANNING_START",
                    {
                        "plan_goal": input_data.goal,
                        "session_id": getattr(context, 'session_id', 'unknown'),
                        "timestamp": time.time()
                    }
                )
            
            # 1. Получение списка доступных capability для контекста промпта
            # Так как BaseSessionContext не имеет метода get_available_capabilities,
            # мы получаем их через системный контекст
            all_capabilities = self.system_context.list_capabilities()
            available_capabilities = []
            for cap_name in all_capabilities:
                cap = self.system_context.get_capability(cap_name)
                if cap and getattr(cap, 'visiable', True):  # используем 'visiable' как в react стратегии
                    available_capabilities.append(cap)
            
            capabilities_list = self._format_capabilities_for_prompt(available_capabilities)
            
            # 2. Рендеринг промпта через централизованный сервис
            prompt = await self.prompt_service.render(
                capability_name="planning.create_plan",
                variables={
                    "goal": input_data.goal,
                    "max_steps": input_data.max_steps,
                    "capabilities_list": capabilities_list,
                    "context": input_data.context or context.get_summary()
                }
            )
            
            # 3. Генерация структурированного плана через системный контекст
            from models.llm_types import LLMRequest, StructuredOutputConfig
            import time
            request = LLMRequest(
                prompt=input_data.goal,
                system_prompt=prompt,
                temperature=0.3,
                max_tokens=1000,
                structured_output=StructuredOutputConfig(
                    output_model="CreatePlanOutput",  # Имя модели из реестра
                    schema_def=CreatePlanOutput.model_json_schema(),
                    max_retries=3,
                    strict_mode=True
                ),
                correlation_id=f"plan_gen_{hash(input_data.goal)}",
                capability_name="planning.create_plan"
            )
            
            # 4. Вызов LLM с ожиданием структурированного вывода
            response = await self.system_context.call_llm(request)
            llm_response = response.parsed_content  # Это уже валидный экземпляр CreatePlanOutput
            
            # 5. Сохранение плана в контекст сессии
            plan_item_id = context.record_plan(
                plan_data=llm_response.model_dump(),  # Используем model_dump вместо dict
                plan_type="initial"
            )
            context.set_current_plan(plan_item_id)
            
            # Публикуем событие успешного создания плана
            if self.event_bus:
                await self.event_bus.publish(
                    "PLAN_CREATED",
                    {
                        "plan_id": plan_item_id,
                        "plan_goal": input_data.goal,
                        "steps_count": len(llm_response.steps),
                        "session_id": getattr(context, 'session_id', 'unknown'),
                        "timestamp": time.time()
                    }
                )
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=llm_response.model_dump(),
                observation_item_id=plan_item_id,
                summary=f"Создан план из {len(llm_response.steps)} шагов для цели: {input_data.goal[:50]}...",
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
                        "plan_goal": input_data.goal,
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
    
    async def _update_plan(self, input_data: UpdatePlanInput, context: "BaseSessionContext") -> ExecutionResult:
        # Заглушка для реализации
        pass
    
    async def _get_next_step(self, input_data: GetNextStepInput, context: "BaseSessionContext") -> ExecutionResult:
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

    async def _get_next_step_from_flat_plan(self, plan: Dict[str, Any], input_data: GetNextStepInput, context: "BaseSessionContext") -> Dict[str, Any]:
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

    async def _get_next_step_from_hierarchy(self, hierarchy_plan: Dict[str, Any], input_data: GetNextStepInput, context: "BaseSessionContext") -> Dict[str, Any]:
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
                sub_input = GetNextStepInput(
                    plan_id=sub_plan_info.get("plan_id"),
                    current_step_id=None  # начинаем с начала подплана
                )
                
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
    
    async def _update_step_status(self, input_data: UpdateStepStatusInput, context: "BaseSessionContext") -> ExecutionResult:
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
                        "step_id": input_data.step_id,
                        "new_status": input_data.status.value,
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
                if step.get("step_id") == input_data.step_id:
                    step_to_update = step.copy()
                    step_index = idx
                    break
            
            if not step_to_update:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result=None,
                    observation_item_id=None,
                    summary=f"Шаг с ID {input_data.step_id} не найден в плане",
                    error="STEP_NOT_FOUND"
                )
            
            # Обновляем статус шага
            step_to_update["status"] = input_data.status.value
            if input_data.result:
                step_to_update["result"] = input_data.result
            if input_data.error_message:
                step_to_update["error_message"] = input_data.error_message
            
            # Если статус - FAILED, запускаем коррекцию плана
            if input_data.status == StepStatus.FAILED and input_data.error_message:
                self.logger.info(f"Шаг {input_data.step_id} завершился с ошибкой, запускаем коррекцию плана")
                
                # Публикуем событие ошибки шага
                if self.event_bus:
                    await self.event_bus.publish(
                        "STEP_FAILED",
                        {
                            "step_id": input_data.step_id,
                            "error_message": input_data.error_message,
                            "session_id": getattr(context, 'session_id', 'unknown'),
                            "timestamp": time.time()
                        }
                    )
                
                # Выполняем коррекцию плана
                correction_result = await self._correct_plan_after_failure(
                    current_plan=current_plan,
                    failed_step=step_to_update,
                    error_info=input_data.error_message,
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
                                "step_id": input_data.step_id,
                                "session_id": getattr(context, 'session_id', 'unknown'),
                                "timestamp": time.time()
                            }
                        )
                    
                    return correction_result
                else:
                    # Если коррекция не удалась, продолжаем с обычным обновлением
                    self.logger.warning(f"Коррекция плана не удалась: {correction_result.summary}")
                    
                    # Публикуем событие неудачной коррекции плана
                    if self.event_bus:
                        await self.event_bus.publish(
                            "PLAN_CORRECTION_FAILED",
                            {
                                "step_id": input_data.step_id,
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
                summary=f"Статус шага {input_data.step_id} обновлен на {input_data.status.value}",
                error=None
            )
            
        except Exception as e:
            self.logger.error(f"Ошибка обновления статуса шага: {str(e)}", exc_info=True)
            
            # Публикуем событие ошибки обновления статуса шага
            if self.event_bus:
                await self.event_bus.publish(
                    "STEP_STATUS_UPDATE_FAILED",
                    {
                        "step_id": input_data.step_id,
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
    
    async def _decompose_task(self, input_data: DecomposeTaskInput, context: "BaseSessionContext") -> ExecutionResult:
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
            all_capabilities = self.system_context.list_capabilities()
            available_capabilities = []
            for cap_name in all_capabilities:
                cap = self.system_context.get_capability(cap_name)
                if cap and getattr(cap, 'visiable', True):  # используем 'visiable' как в react стратегии
                    available_capabilities.append(cap)
            
            capabilities_list = self._format_capabilities_for_prompt(available_capabilities)
            
            # 2. Рендеринг промпта декомпозиции
            prompt = await self.prompt_service.render(
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
            import time
            request = LLMRequest(
                prompt=input_data.task_description,
                system_prompt=prompt,
                temperature=0.3,
                max_tokens=1000,
                structured_output=StructuredOutputConfig(
                    output_model="DecomposeTaskOutput",  # Имя модели из реестра
                    schema_def=DecomposeTaskOutput.model_json_schema(),
                    max_retries=3,
                    strict_mode=True
                ),
                correlation_id=f"task_decomp_{hash(input_data.task_description)}",
                capability_name="planning.decompose_task"
            )
            
            # 4. Вызов LLM с ожиданием структурированного вывода
            response = await self.system_context.call_llm(request)
            decomposition = response.parsed_content  # Это уже валидный экземпляр DecomposeTaskOutput
            
            # 5. Создание вложенного плана для каждой подзадачи
            sub_plans = []
            for subtask in decomposition.subtasks:
                # Создаем мини-план для подзадачи
                sub_plan_input = CreatePlanInput(
                    goal=subtask.description,
                    max_steps=min(3, len(subtask.description.split('.'))),  # Максимум 3 шага на подзадачу
                    context=f"Подзадача {subtask.subtask_id} родительской задачи {input_data.task_id}",
                    strategy="iterative"
                )
                sub_plan_result = await self._create_plan(sub_plan_input, context)
                
                if sub_plan_result.status == ExecutionStatus.SUCCESS:
                    sub_plans.append({
                        "subtask_id": subtask.subtask_id,
                        "plan_id": sub_plan_result.observation_item_id,
                        "description": subtask.description,
                        "complexity": subtask.complexity
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
            result = await self.sql_query_service.execute_query_from_user_request(
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
                error_analysis = ErrorAnalysisOutput(
                    error_type="unknown",
                    reason="Не удалось провести детальный анализ ошибки",
                    suggested_fix="Попробуйте повторить шаг или пропустить его",
                    severity="medium",
                    reasoning="Ошибка при анализе ошибки выполнения шага",
                    summary="Ошибка анализа"
                )
            else:
                error_analysis = ErrorAnalysisOutput(**analysis_result.result)

            # 2. Формирование промпта коррекции
            import json
            correction_prompt = await self.prompt_service.render(
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
                    schema_def=UpdatePlanOutput.model_json_schema(),
                    max_retries=3,
                    strict_mode=True
                ),
                correlation_id=f"plan_correction_{hash(error_info)}",
                capability_name="planning.update_plan"
            )
            
            # 4. Вызов LLM с ожиданием структурированного вывода
            response = await self.system_context.call_llm(request)
            corrected_plan = response.parsed_content  # Это уже валидный экземпляр UpdatePlanOutput
            
            # 5. Сохранение исправленного плана
            plan_item_id = context.record_plan(
                plan_data=corrected_plan.model_dump(),
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
            self.logger.warning(f"Не удалось автоматически скорректировать план: {str(e)}")
            
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
            prompt = await self.prompt_service.render(
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
                    schema_def=ErrorAnalysisOutput.model_json_schema(),
                    max_retries=2,
                    strict_mode=True
                ),
                correlation_id=f"error_analysis_{hash(error_info)}",
                capability_name="planning.analyze_step_failure"
            )
            
            # Вызов LLM с ожиданием структурированного вывода
            response = await self.system_context.call_llm(request)
            analysis_result = response.parsed_content  # Это уже валидный экземпляр ErrorAnalysisOutput
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=analysis_result.dict(),
                observation_item_id=None,
                summary=f"Проанализирована ошибка шага {current_step.get('step_id', 'unknown')}: {analysis_result.summary}",
                error=None
            )
            
        except Exception as e:
            self.logger.error(f"Ошибка анализа ошибки шага: {str(e)}", exc_info=True)
            # Возвращаем базовый анализ в случае ошибки
            basic_analysis = ErrorAnalysisOutput(
                error_type="unknown",
                reason="Не удалось провести детальный анализ ошибки",
                suggested_fix="Попробуйте повторить шаг или пропустить его",
                severity="medium",
                reasoning="Ошибка при анализе ошибки выполнения шага",
                summary="Ошибка анализа"
            )
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=basic_analysis.dict(),
                observation_item_id=None,
                summary=f"Базовый анализ ошибки: {basic_analysis.summary}",
                error=None
            )

    async def _mark_task_completed(self, input_data: MarkTaskCompletedInput, context: "BaseSessionContext") -> ExecutionResult:
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