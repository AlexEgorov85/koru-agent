"""Навык для создания и управления планами действий агента.
ФУНКЦИОНАЛЬНОСТЬ:
- Создание первичного плана из цели
- Обновление плана на основе прогресса
- Декомпозиция сложных задач на подзадачи
- Отслеживание статуса выполнения задач
- Получение следующего шага из плана
- Обновление статуса шага в плане
АРХИТЕКТУРА:
- Зависит только от абстракций (базовых классов)
- Бизнес-логика полностью отделена от инфраструктуры
- Поддержка расширения через новые capability"""
from typing import Dict, Any, List
import logging
import json
import uuid
from datetime import datetime, timezone
from core.session_context.base_session_context import BaseSessionContext
from core.skills.base_skill import BaseSkill
from core.system_context.base_system_contex import BaseSystemContext
from models.capability import Capability
from core.skills.planning.prompt import (
    CREATE_PLAN_PROMPT,
    UPDATE_PLAN_PROMPT,
    DECOMPOSE_TASK_PROMPT,
    MARK_TASK_COMPLETED_PROMPT,
    GET_NEXT_STEP_PROMPT,
    UPDATE_STEP_STATUS_PROMPT
)
from core.skills.planning.schema import (
    CreatePlanInput,
    DecomposeTaskOutput,
    MarkTaskCompletedOutput,
    UpdatePlanInput,
    DecomposeTaskInput,
    MarkTaskCompletedInput,
    CreatePlanOutput,
    PlanStep,
    PlanMetadata,
    UpdatePlanOutput,
    GetNextStepInput,
    GetNextStepOutput,
    UpdateStepStatusInput,
    UpdateStepStatusOutput
)
from models.execution import ExecutionResult, ExecutionStatus

logger = logging.getLogger(__name__)

class PlanningSkill(BaseSkill):
    """Навык для создания и управления планами действий агента."""
    name = "planning"

    def __init__(self, name: str, system_context: BaseSystemContext, **kwargs):
        super().__init__(name, system_context, **kwargs)
        logger.info(f"Инициализирован навык планирования: {self.name}")

    def get_capabilities(self) -> List[Capability]:
        """Возвращает список capability навыка."""
        return [
            Capability(
                name="planning.create_plan",
                description="Создание плана действий",
                parameters_schema=CreatePlanInput.model_json_schema(),
                parameters_class=CreatePlanInput,
                skill_name=self.name,
            ),
            Capability(
                name="planning.update_plan",
                description="Обновление существующего плана на основе прогресса или ошибок",
                parameters_schema=UpdatePlanInput.model_json_schema(),
                parameters_class=UpdatePlanInput,
                skill_name=self.name,
            ),
            Capability(
                name="planning.decompose_task",
                description="Декомпозиция сложной задачи на подзадачи",
                parameters_schema=DecomposeTaskInput.model_json_schema(),
                parameters_class=DecomposeTaskInput,
                skill_name=self.name,
            ),
            Capability(
                name="planning.mark_task_completed",
                description="Отметка задачи как выполненной",
                parameters_schema=MarkTaskCompletedInput.model_json_schema(),
                parameters_class=MarkTaskCompletedInput,
                skill_name=self.name,
                visiable=False
            ),
            Capability(
                name="planning.get_next_step",
                description="Получение следующего незавершенного шага из плана",
                parameters_schema=GetNextStepInput.model_json_schema(),
                parameters_class=GetNextStepInput,
                skill_name=self.name,
                visiable=False
            ),
            Capability(
                name="planning.update_step_status",
                description="Обновление статуса шага в плане",
                parameters_schema=UpdateStepStatusInput.model_json_schema(),
                parameters_class=UpdateStepStatusInput,
                skill_name=self.name,
                visiable=False
            )
        ]

    async def execute(self, capability: Capability, parameters: Dict[str, Any], context: BaseSessionContext) -> ExecutionResult:
        """Выполнение capability навыка планирования.
        
        МАРШРУТИЗАЦИЯ:
        - create_plan → _create_plan()
        - update_plan → _update_plan()
        - decompose_task → _decompose_task()
        - mark_task_completed → _mark_task_completed()
        - get_next_step → _get_next_step()
        - update_step_status → _update_step_status()
        """
        try:
            if capability.name == "planning.create_plan":
                return await self._create_plan(parameters, context)
            elif capability.name == "planning.update_plan":
                return await self._update_plan(parameters, context)
            elif capability.name == "planning.decompose_task":
                return await self._decompose_task(parameters, context)
            elif capability.name == "planning.mark_task_completed":
                return await self._mark_task_completed(parameters, context)
            elif capability.name == "planning.get_next_step":
                return await self._get_next_step(parameters, context)
            elif capability.name == "planning.update_step_status":
                return await self._update_step_status(parameters, context)
            else:
                error_msg = f"Неподдерживаемая capability: {capability.name}"
                logger.error(error_msg)
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    result=None,
                    observation_item_id=None,
                    summary=error_msg,
                    error="UNSUPPORTED_CAPABILITY"
                )
        except Exception as e:
            logger.error(f"Ошибка выполнения capability '{capability.name}': {str(e)}", exc_info=True)
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Ошибка выполнения capability '{capability.name}': {str(e)}",
                error="EXECUTION_ERROR"
            )

    async def _create_plan(self, parameters: Dict[str, Any], context: BaseSessionContext) -> ExecutionResult:
        """Создание нового плана действий."""
        # Валидация параметров через Pydantic
        try:
            input_data = CreatePlanInput(**parameters)
        except Exception as e:
            logger.error(f"Ошибка валидации параметров: {str(e)}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Ошибка валидации параметров: {str(e)}",
                error="VALIDATION_ERROR"
            )
        
        goal = context.get_goal().strip() if context.get_goal() else input_data.goal.strip()
        if not goal:
            raise ValueError("Цель не может быть пустой для создания плана")
        
        # Получаем список доступных capability
        capabilities_list = self._get_capabilities_list()
        
        # Формирование промпта для LLM
        prompt = CREATE_PLAN_PROMPT.format(
            goal=goal,
            max_steps=input_data.max_steps,
            capabilities_list=capabilities_list,
            context=input_data.context or context.get_summary(),
            strategy=input_data.strategy
        )
        
        logger.debug(f"Создание плана для цели: {goal}")
        
        # Генерация структурированного результата
        try:
            llm_response = await self.system_context.call_llm_with_params(
                user_prompt=prompt,
                system_prompt="Ты — эксперт по планированию. Создай детальный и реалистичный план действий.",
                output_schema=CreatePlanOutput.model_json_schema(),
                output_format='json',
                temperature=0.2,
                max_tokens=2048
            )
            
            # Преобразуем ответ в словарь для ExecutionResult
            if hasattr(llm_response, 'content'):
                result_data = llm_response.content
            else:
                result_data = llm_response
            
            # Валидация результата через Pydantic
            try:
                plan = CreatePlanOutput(**result_data)
            except Exception as e:
                logger.warning(f"Ошибка валидации плана: {str(e)}. Создаем fallback-план.")
                # Создаем валидный fallback-план
                plan = self._create_fallback_plan(goal, input_data.max_steps)
            
            # Запись плана
            context.record_plan(plan.model_dump(), plan_type="initial")
            
            logger.info(f"Создан план с {len(plan.steps)} шагами для цели: {goal}")
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=plan.model_dump(),
                observation_item_id=None,
                summary=f"Создан план из {len(plan.steps)} шагов для цели: {goal[:50]}...",
                error=None
            )
        except Exception as e:
            logger.error(f"Ошибка создания плана через LLM: {str(e)}")
            # Создаем fallback-план при ошибке
            plan = self._create_fallback_plan(goal, input_data.max_steps)
            context.record_plan(plan.model_dump(), plan_type="initial")
            logger.info("Создан fallback-план после ошибки")
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=plan.model_dump(),
                observation_item_id=None,
                summary=f"Создан fallback-план из {len(plan.steps)} шагов после ошибки",
                error=None
            )

    async def _update_plan(self, parameters: Dict[str, Any], context: BaseSessionContext) -> ExecutionResult:
        """Обновление существующего плана на основе прогресса."""
        # Валидация параметров через Pydantic
        try:
            input_data = UpdatePlanInput(**parameters)
        except Exception as e:
            logger.error(f"Ошибка валидации параметров: {str(e)}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Ошибка валидации параметров: {str(e)}",
                error="VALIDATION_ERROR"
            )
        
        # Получаем текущий план из контекста
        current_plan_item = context.get_context_item(input_data.plan_id)
        if not current_plan_item:
            raise ValueError(f"План с ID {input_data.plan_id} не найден в контексте")
        
        current_plan = current_plan_item.content
        
        logger.debug(f"Обновление плана ID: {input_data.plan_id}, изменений: {len(input_data.updates)}")
        
        # Получаем список доступных capability
        capabilities_list = self._get_capabilities_list()
        
        # Формирование промпта для LLM
        prompt = UPDATE_PLAN_PROMPT.format(
            current_plan=json.dumps(current_plan, indent=2, ensure_ascii=False),
            updates=json.dumps(input_data.updates, indent=2, ensure_ascii=False),
            capabilities_list=capabilities_list,
            context=input_data.context
        )
        
        try:
            llm_response = await self.system_context.call_llm_with_params(
                user_prompt=prompt,
                system_prompt="Ты — эксперт по планированию. Обнови существующий план, учитывая прогресс и текущую ситуацию.",
                output_schema=UpdatePlanOutput.model_json_schema(),
                output_format='json',
                temperature=0.2,
                max_tokens=2048
            )
            
            # Преобразуем ответ в словарь для ExecutionResult
            if hasattr(llm_response, 'content'):
                result_data = llm_response.content
            else:
                result_data = llm_response
            
            # Запись обновленного плана
            context.record_plan(result_data, plan_type="update")
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=result_data,
                observation_item_id=None,
                summary=f"План {input_data.plan_id} обновлен. Причина: {result_data.get('update_reason', 'не указана')}",
                error=None
            )
        except Exception as e:
            logger.error(f"Ошибка обновления плана через LLM: {str(e)}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Не удалось обновить план: {str(e)}",
                error="PLAN_UPDATE_ERROR"
            )

    async def _decompose_task(self, parameters: Dict[str, Any], context: BaseSessionContext) -> ExecutionResult:
        """Декомпозиция сложной задачи на подзадачи."""
        # Валидация параметров через Pydantic
        try:
            input_data = DecomposeTaskInput(**parameters)
        except Exception as e:
            logger.error(f"Ошибка валидации параметров: {str(e)}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Ошибка валидации параметров: {str(e)}",
                error="VALIDATION_ERROR"
            )
        
        # Получаем список доступных capability
        capabilities_list = self._get_capabilities_list()
        
        # Формирование промпта для LLM
        prompt = DECOMPOSE_TASK_PROMPT.format(
            task_id=input_data.task_id,
            task_description=input_data.task_description,
            capabilities_list=capabilities_list,
            context=input_data.context or "",
            strategy=input_data.strategy.value if input_data.strategy else "по_функциям"
        )
        
        try:
            llm_response = await self.system_context.call_llm_with_params(
                user_prompt=prompt,
                system_prompt="Ты — эксперт по декомпозиции задач. Разбей сложную задачу на логичные подзадачи.",
                output_schema=DecomposeTaskOutput.model_json_schema(),
                output_format='json',
                temperature=0.3,
                max_tokens=2048
            )
            
            # Преобразуем ответ в словарь для ExecutionResult
            if hasattr(llm_response, 'content'):
                result_data = llm_response.content
            else:
                result_data = llm_response
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=result_data,
                observation_item_id=None,
                summary=f"Задача {input_data.task_id} декомпозирована на {len(result_data.get('subtasks', []))} подзадач",
                error=None
            )
        except Exception as e:
            logger.error(f"Ошибка декомпозиции задачи через LLM: {str(e)}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Не удалось декомпозировать задачу: {str(e)}",
                error="TASK_DECOMPOSITION_ERROR"
            )

    async def _mark_task_completed(self, parameters: Dict[str, Any], context: BaseSessionContext) -> ExecutionResult:
        """Отметка задачи как выполненной."""
        # Валидация параметров через Pydantic
        try:
            input_data = MarkTaskCompletedInput(**parameters)
        except Exception as e:
            logger.error(f"Ошибка валидации параметров: {str(e)}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Ошибка валидации параметров: {str(e)}",
                error="VALIDATION_ERROR"
            )
        
        # Получаем список доступных capability
        capabilities_list = self._get_capabilities_list()
        
        # Формирование промпта для LLM
        prompt = MARK_TASK_COMPLETED_PROMPT.format(
            task_id=input_data.task_id,
            result_summary=input_data.result_summary,
            quality_score=input_data.quality_score,
            time_spent_minutes=input_data.time_spent_minutes
        )
        
        try:
            llm_response = await self.system_context.call_llm_with_params(
                user_prompt=prompt,
                system_prompt="Ты — эксперт по отслеживанию прогресса. Проанализируй завершение задачи и определи следующие действия.",
                output_schema=MarkTaskCompletedOutput.model_json_schema(),
                output_format='json',
                temperature=0.3,
                max_tokens=2048
            )
            
            # Преобразуем ответ в словарь для ExecutionResult
            if hasattr(llm_response, 'content'):
                result_data = llm_response.content
            else:
                result_data = llm_response
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=result_data,
                observation_item_id=None,
                summary=f"Задача {input_data.task_id} отмечена как выполненная с качеством {input_data.quality_score:.2f}",
                error=None
            )
        except Exception as e:
            logger.error(f"Ошибка анализа завершения задачи через LLM: {str(e)}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Не удалось проанализировать завершение задачи: {str(e)}",
                error="TASK_COMPLETION_ERROR"
            )

    async def _get_next_step(self, parameters: Dict[str, Any], context: BaseSessionContext) -> ExecutionResult:
        """Получение следующего незавершенного шага из плана."""
        try:
            input_data = GetNextStepInput(**parameters)
        except Exception as e:
            logger.error(f"Ошибка валидации параметров: {str(e)}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Ошибка валидации параметров: {str(e)}",
                error="VALIDATION_ERROR"
            )
        
        # Получаем текущий план из контекста
        current_plan_item = context.get_context_item(input_data.plan_id)
        if not current_plan_item:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"План с ID {input_data.plan_id} не найден в контексте",
                error="PLAN_NOT_FOUND"
            )
        
        plan_data = current_plan_item.content
        steps = plan_data.get("steps", [])
        
        # Поиск первого незавершенного шага
        next_step = None
        for step in steps:
            status = step.get("status", "pending").lower()
            if status not in ["completed", "skipped", "failed"]:
                next_step = step
                break
        
        if not next_step:
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result={"all_steps_completed": True, "plan_id": input_data.plan_id},
                observation_item_id=None,
                summary="Все шаги плана завершены",
                error=None
            )
        
        # Формирование промпта для более детального анализа следующего шага
        capabilities_list = self._get_capabilities_list()
        prompt = GET_NEXT_STEP_PROMPT.format(
            plan_id=input_data.plan_id,
            current_step=json.dumps(next_step, indent=2, ensure_ascii=False),
            capabilities_list=capabilities_list,
            context=input_data.context or "Анализ следующего шага из плана"
        )
        
        try:
            llm_response = await self.system_context.call_llm_with_params(
                user_prompt=prompt,
                system_prompt="Ты — эксперт по планированию. Проанализируй следующий шаг в плане и подготовь рекомендации для его выполнения.",
                output_schema=GetNextStepOutput.model_json_schema(),
                output_format='json',
                temperature=0.3,
                max_tokens=1000
            )
            
            if hasattr(llm_response, 'content'):
                result_data = llm_response.content
            else:
                result_data = llm_response
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result=result_data,
                observation_item_id=None,
                summary=f"Найден следующий шаг: {next_step.get('description', 'без описания')}",
                error=None
            )
        except Exception as e:
            logger.error(f"Ошибка анализа следующего шага через LLM: {str(e)}")
            # Возвращаем базовую информацию о шаге без анализа LLM
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result={
                    "step": next_step,
                    "plan_id": input_data.plan_id,
                    "requires_analysis": False,
                    "recommendations": ["Выполнить шаг как есть"]
                },
                observation_item_id=None,
                summary=f"Найден следующий шаг (без детального анализа): {next_step.get('description', 'без описания')}",
                error=None
            )

    async def _update_step_status(self, parameters: Dict[str, Any], context: BaseSessionContext) -> ExecutionResult:
        """Обновление статуса шага в плане."""
        try:
            input_data = UpdateStepStatusInput(**parameters)
        except Exception as e:
            logger.error(f"Ошибка валидации параметров: {str(e)}")
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Ошибка валидации параметров: {str(e)}",
                error="VALIDATION_ERROR"
            )
        
        # Получаем текущий план из контекста
        current_plan_item = context.get_context_item(input_data.plan_id)
        if not current_plan_item:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"План с ID {input_data.plan_id} не найден в контексте",
                error="PLAN_NOT_FOUND"
            )
        
        plan_data = current_plan_item.content
        steps = plan_data.get("steps", [])
        
        # Поиск шага для обновления
        step_found = False
        previous_status = None
        for step in steps:
            if step.get("step_id") == input_data.step_id:
                previous_status = step.get("status")
                # Обновление статуса и информации о шаге
                step["status"] = input_data.status
                step["updated_at"] = datetime.now(timezone.utc).isoformat()
                
                if input_data.result_summary:
                    step["result_summary"] = input_data.result_summary
                
                if input_data.error:
                    step["error"] = input_data.error
                
                step_found = True
                break
        
        if not step_found:
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                result=None,
                observation_item_id=None,
                summary=f"Шаг с ID {input_data.step_id} не найден в плане",
                error="STEP_NOT_FOUND"
            )
        
        # Формирование промпта для анализа влияния обновления статуса
        capabilities_list = self._get_capabilities_list()
        prompt = UPDATE_STEP_STATUS_PROMPT.format(
            plan_id=input_data.plan_id,
            step_id=input_data.step_id,
            status=input_data.status,
            current_plan=json.dumps(plan_data, indent=2, ensure_ascii=False),
            capabilities_list=capabilities_list,
            context=input_data.context or f"Обновление статуса шага на {input_data.status}"
        )
        
        try:
            llm_response = await self.system_context.call_llm_with_params(
                user_prompt=prompt,
                system_prompt="Ты — эксперт по планированию. Проанализируй влияние обновления статуса шага на общий план.",
                output_schema=UpdateStepStatusOutput.model_json_schema(),
                output_format='json',
                temperature=0.3,
                max_tokens=1000
            )
            
            if hasattr(llm_response, 'content'):
                analysis_result = llm_response.content
            else:
                analysis_result = {}
            
            # Обновляем план с учетом возможных рекомендаций от LLM
            if analysis_result.get("plan_adjustments"):
                for adjustment in analysis_result.get("plan_adjustments", []):
                    step_id = adjustment.get("step_id")
                    for step in steps:
                        if step.get("step_id") == step_id:
                            if "status" in adjustment:
                                step["status"] = adjustment["status"]
                            if "description" in adjustment:
                                step["description"] = adjustment["description"]
                            break
            
            # Запись обновленного плана
            context.record_plan(plan_data, plan_type="step_update")
            
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result={
                    "plan_id": input_data.plan_id,
                    "step_id": input_data.step_id,
                    "previous_status": previous_status,
                    "new_status": input_data.status,
                    "analysis": analysis_result
                },
                observation_item_id=None,
                summary=f"Статус шага {input_data.step_id} обновлен на {input_data.status}",
                error=None
            )
        except Exception as e:
            logger.error(f"Ошибка анализа обновления статуса шага через LLM: {str(e)}")
            # Записываем обновленный план даже без анализа LLM
            context.record_plan(plan_data, plan_type="step_update")
            return ExecutionResult(
                status=ExecutionStatus.SUCCESS,
                result={
                    "plan_id": input_data.plan_id,
                    "step_id": input_data.step_id,
                    "previous_status": previous_status,
                    "new_status": input_data.status,
                    "analysis_skipped": True
                },
                observation_item_id=None,
                summary=f"Статус шага {input_data.step_id} обновлен на {input_data.status} (анализ пропущен из-за ошибки)",
                error=None
            )

    def _create_fallback_plan(self, goal: str, max_steps: int) -> CreatePlanOutput:
        """Создает валидный fallback-план при ошибках LLM"""
        steps = [
            PlanStep(
                step_id=f"step_{i+1}",
                description=desc,
                status="pending",
                estimated_time=15,
                required_capabilities=["generic.execute"],
                dependencies=[],
                priority="medium"
            ) for i, desc in enumerate([
                f"Анализ цели: {goal[:50]}...",
                "Сбор необходимой информации",
                "Выполнение основного действия",
                "Проверка результатов",
                "Корректировка плана при необходимости"
            ][:max_steps])
        ]
        
        return CreatePlanOutput(
            plan_id=f"plan_fallback_{uuid.uuid4().hex[:8]}",
            goal=goal,
            steps=steps,
            metadata=PlanMetadata(
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
                max_steps=max_steps,
                strategy="fallback",
                confidence=0.3,
                version=1
            )
        )

    def _get_capabilities_list(self) -> str:
        """Получение списка доступных capability в формате для промпта."""
        capabilities = self.system_context.list_capabilities()
        if not capabilities:
            return "Нет доступных capability."
        
        result = []
        for i, cap_name in enumerate(capabilities[:10], 1):  # Ограничиваем для краткости
            cap = self.system_context.get_capability(cap_name)
            if cap:
                params_schema = cap.parameters_schema or {}
                params_desc = "Параметры не определены"
                if isinstance(params_schema, dict) and "properties" in params_schema:
                    params_desc = ", ".join([f"{name}" for name in params_schema["properties"].keys()][:3])
                    if len(params_schema["properties"]) > 3:
                        params_desc += ", ..."
                
                result.append(
                    f"{i}. {cap.name}\n"
                    f"   - Описание: {cap.description or 'Без описания'}\n"
                    f"   - Параметры: {params_desc}"
                )
        
        return "\n".join(result)