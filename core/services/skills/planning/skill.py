"""
НАВЫК ПЛАНИРОВАНИЯ С ПОЛНОЙ ИЗОЛЯЦИЕЙ
"""
import asyncio
import time
from typing import Any, Dict, List
from core.agent.components.base_component import BaseComponent
from core.infrastructure.event_bus.unified_event_bus import EventType
from core.models.data.capability import Capability
from core.agent.components.action_executor import ExecutionContext
from core.models.data.execution import ExecutionResult, ExecutionStatus
from core.infrastructure.logging import EventBusLogger
  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()


class PlanningSkill(BaseComponent):
    """НАВЫК ПЛАНИРОВАНИЯ С ПОЛНОЙ ИЗОЛЯЦИЕЙ"""

    # Явная декларация зависимостей
    DEPENDENCIES = ["prompt_service"]

    def __init__(self, name: str, application_context: Any, component_config=None, executor=None, event_bus=None):
        super().__init__(
            name,
            application_context,
            component_config=component_config,
            executor=executor,
            event_bus=event_bus
        )

    async def execute(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: ExecutionContext
    ) -> ExecutionResult:
        """
        Переопределение execute() для вызова _execute_impl.

        BaseComponent.execute() оборачивает результат в ExecutionResult.
        """
        return await self._execute_impl(capability, parameters, execution_context)

    def _get_event_type_for_success(self) -> EventType:
        """Возвращает тип события для успешного выполнения навыка планирования."""
        return EventType.SKILL_EXECUTED

    def get_capabilities(self) -> List[Capability]:
        return [
            Capability(
                name="planning.create_plan",
                description="Создание первичного плана действий",
                skill_name=self.name,
                supported_strategies=["planning"],  # ← Только planning_pattern
                visiable=True
            ),
            Capability(
                name="planning.update_plan",
                description="Обновление существующего плана",
                skill_name=self.name,
                supported_strategies=["planning"],  # ← Только planning_pattern
                visiable=True
            ),
            Capability(
                name="planning.get_next_step",
                description="Получение следующего шага из плана",
                skill_name=self.name,
                supported_strategies=["planning"],  # ← Только planning_pattern
                visiable=True
            ),
            Capability(
                name="planning.update_step_status",
                description="Обновление статуса шага плана",
                skill_name=self.name,
                supported_strategies=["planning"],  # ← Только planning_pattern
                visiable=True
            ),
            Capability(
                name="planning.decompose_task",
                description="Декомпозиция сложной задачи на подзадачи",
                skill_name=self.name,
                supported_strategies=["planning"],  # ← Только planning_pattern
                visiable=True
            ),
            Capability(
                name="planning.mark_task_completed",
                description="Отметка задачи как завершенной",
                skill_name=self.name,
                supported_strategies=["planning"],  # ← Только planning_pattern
                visiable=True
            )
        ]

    async def _execute_impl(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: ExecutionContext
    ) -> Dict[str, Any]:
        """
        Реализация бизнес-логики навыка планирования (ASYNC).

        ВАЖНО: Валидация входа/выхода и метрики выполняются в BaseComponent.execute()
        Здесь только бизнес-логика.

        ВОЗВРАЩАЕТ:
        - Dict[str, Any]: Данные результата (не ExecutionResult!)
        """
        # Делегирование конкретным методам
        if capability.name == "planning.create_plan":
            result = await self._create_plan(parameters, execution_context)
        elif capability.name == "planning.update_plan":
            result = await self._update_plan(parameters, execution_context)
        elif capability.name == "planning.get_next_step":
            result = await self._get_next_step(parameters, execution_context)
        elif capability.name == "planning.update_step_status":
            result = await self._update_step_status(parameters, execution_context)
        elif capability.name == "planning.decompose_task":
            result = await self._decompose_task(parameters, execution_context)
        elif capability.name == "planning.mark_task_completed":
            result = await self._mark_task_completed(parameters, execution_context)
        else:
            raise ValueError(f"Неизвестная capability: {capability.name}")

        # Извлекаем данные из ExecutionResult
        if isinstance(result, ExecutionResult):
            return result.data if result.data else {}
        return result if result else {}

    def _format_capabilities(self, capabilities: List[Capability]) -> str:
        """Форматирование списка возможностей для промпта"""
        return "\n".join([f"- {cap.name}: {cap.description}" for cap in capabilities])

    async def _publish_event(
        self,
        event_type: str,
        data: Dict[str, Any],
        execution_context: ExecutionContext
    ) -> None:
        """
        Публикация события в EventBus.
        """
        try:
            # Используем event_bus_logger для публикации событий
            if self.event_bus_logger:
                await self.event_bus_logger.info(f"Событие {event_type}: {data}")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.warning(f"Не удалось опубликовать событие {event_type}: {str(e)}")
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            else:
                self.logger.warning(f"Не удалось опубликовать событие {event_type}: {str(e)}")
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()

    async def _create_plan(self, input_data: Dict[str, Any], execution_context: ExecutionContext) -> ExecutionResult:
        try:
            # 1. Валидация через КЭШИРОВАННЫЙ контракт (без обращения к сервису!)
            input_contract = self.get_input_contract("planning.create_plan")
            # validate_against_schema(input_data, input_contract)

            # 2. Получение промпта ИЗ КЭША
            prompt_obj = self.get_prompt("planning.create_plan")
            rendered_prompt = prompt_obj.content if prompt_obj else ""

            # 3. Получаем схему выхода для structured output
            output_schema = self.get_output_contract("planning.create_plan")

            # 4. Вызов LLM ЧЕРЕЗ EXECUTOR С STRUCTURED OUTPUT
            llm_result = await self.executor.execute_action(
                action_name="llm.generate_structured",
                parameters={
                    "prompt": rendered_prompt,
                    "structured_output": {
                        "output_model": "planning.create_plan.output",
                        "schema_def": output_schema,
                        "max_retries": 3,
                        "strict_mode": True
                    },
                    "temperature": 0.1  # Низкая температура для точности
                },
                context=execution_context
            )

            if not llm_result.status == ExecutionStatus.COMPLETED:
                error_type = llm_result.metadata.get("error_type", "unknown") if isinstance(llm_result.metadata, dict) else "unknown"
                attempts = llm_result.metadata.get("attempts", 0) if isinstance(llm_result.metadata, dict) else 0
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Ошибка генерации плана: {llm_result.error}",
                    metadata={
                        "error_type": error_type,
                        "attempts": attempts
                    }
                )

            # 5. Получаем структурированные данные
            # ✅ ИСПРАВЛЕНО: Работаем с Pydantic моделью или dict
            llm_result_data = llm_result.result
            if hasattr(llm_result_data, 'parsed_content'):
                # StructuredLLMResponse — извлекаем parsed_content
                plan_data = llm_result_data.parsed_content
            elif isinstance(llm_result_data, dict):
                plan_data = llm_result_data.get("parsed_content", {})
            else:
                plan_data = llm_result_data if llm_result_data else {}

            # Логирование успешного structured output
            parsing_attempts = llm_result.metadata.get('parsing_attempts', 1) if isinstance(llm_result.metadata, dict) else 1
            if self.event_bus_logger:
                await self.event_bus_logger.info(
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    f"Plan создан с structured output (попыток: {parsing_attempts})"
                )
            else:
                self.logger.info(
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    f"Plan создан с structured output (попыток: {parsing_attempts})"
                )

            # 6. Сохранение плана в контекст
            save_result = await self.executor.execute_action(
                action_name="context.record_plan",
                parameters={
                    "plan_data": plan_data,
                    "plan_type": "initial"
                },
                context=execution_context
            )

            if not save_result.status == ExecutionStatus.COMPLETED:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Не удалось сохранить план: {save_result.error}"
                )

            # 7. Публикация события о создании плана
            await self._publish_event(
                event_type="planning.plan_created",
                data={
                    "plan_id": plan_data.get("plan_id", ""),
                    "steps_count": len(plan_data.get("plan", [])),
                    "goal": input_data.get("goal", "")
                },
                execution_context=execution_context
            )

            parsing_attempts = llm_result.metadata.get("parsing_attempts", 1) if isinstance(llm_result.metadata, dict) else 1
            return ExecutionResult(
                status=ExecutionStatus.COMPLETED,
                data=plan_data,
                metadata={
                    "steps_count": len(plan_data.get("plan", [])),
                    "plan_id": plan_data.get("plan_id", ""),
                    "parsing_attempts": parsing_attempts,
                    "structured_output": True
                }
            )

        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка создания плана: {str(e)}", exc_info=True)
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            else:
                self.logger.error(f"Ошибка создания плана: {str(e)}", exc_info=True)
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=f"Не удалось создать план: {str(e)[:100]}"
            )

    async def _update_plan(self, input_data: Dict[str, Any], execution_context: ExecutionContext) -> ExecutionResult:
        """
        Обновление существующего плана.
        Поддерживает добавление, модификацию, удаление и переупорядочивание шагов.
        """
        try:
            # 1. Валидация входных данных через контракт
            input_contract = self.get_input_contract("planning.update_plan")
            # validate_against_schema(input_data, input_contract)

            plan_id = input_data.get("plan_id", "")
            updates = input_data.get("updates", {})
            reason = input_data.get("reason", "")

            # 2. Загрузка текущего плана
            if plan_id:
                plan_result = await self.executor.execute_action(
                    action_name="context.get_context_item",
                    parameters={"item_id": plan_id},
                    context=execution_context
                )
                if not plan_result.status == ExecutionStatus.COMPLETED:
                    return ExecutionResult(
                        status=ExecutionStatus.FAILED,
                        error=f"План с ID {plan_id} не найден"
                    )
                current_plan = plan_result.data.get("content", {}) if plan_result.data else {}
            else:
                # Используем текущий план из контекста
                plan_result = await self.executor.execute_action(
                    action_name="context.get_current_plan",
                    parameters={},
                    context=execution_context
                )
                if not plan_result.status == ExecutionStatus.COMPLETED:
                    return ExecutionResult(
                        status=ExecutionStatus.FAILED,
                        error="Нет текущего плана для обновления"
                    )
                current_plan = plan_result.data

            # 3. Подготовка промпта для обновления плана
            prompt_obj = self.get_prompt("planning.update_plan")
            rendered_prompt = prompt_obj.content if prompt_obj else ""

            # 4. Получаем схему выхода для structured output
            output_schema = self.get_output_contract("planning.update_plan")

            # 5. Вызов LLM для обновления плана через executor С STRUCTURED OUTPUT
            llm_result = await self.executor.execute_action(
                action_name="llm.generate_structured",
                parameters={
                    "prompt": rendered_prompt,
                    "structured_output": {
                        "output_model": "planning.update_plan.output",
                        "schema_def": output_schema,
                        "max_retries": 3,
                        "strict_mode": True
                    },
                    "temperature": 0.1  # Низкая температура для точности
                },
                context=execution_context
            )

            if not llm_result.status == ExecutionStatus.COMPLETED:
                error_type = llm_result.metadata.get("error_type", "unknown") if isinstance(llm_result.metadata, dict) else "unknown"
                attempts = llm_result.metadata.get("attempts", 0) if isinstance(llm_result.metadata, dict) else 0
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Ошибка обновления плана: {llm_result.error}",
                    metadata={
                        "error_type": error_type,
                        "attempts": attempts
                    }
                )

            # 6. Получаем структурированные данные
            # ✅ ИСПРАВЛЕНО: Работаем с Pydantic моделью или dict
            llm_result_data = llm_result.result
            if hasattr(llm_result_data, 'parsed_content'):
                # StructuredLLMResponse — извлекаем parsed_content
                updated_plan = llm_result_data.parsed_content
            elif isinstance(llm_result_data, dict):
                updated_plan = llm_result_data.get("parsed_content", {})
            else:
                updated_plan = llm_result_data if llm_result_data else {}

            # Логирование успешного structured output
            parsing_attempts = llm_result.metadata.get('parsing_attempts', 1) if isinstance(llm_result.metadata, dict) else 1
            if self.event_bus_logger:
                await self.event_bus_logger.info(
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    f"Plan обновлён с structured output (попыток: {parsing_attempts})"
                )
            else:
                self.logger.info(
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    f"Plan обновлён с structured output (попыток: {parsing_attempts})"
                )

            # 5. Сохранение обновленного плана
            save_result = await self.executor.execute_action(
                action_name="context.record_plan",
                parameters={
                    "plan_data": updated_plan,
                    "plan_type": "update"
                },
                context=execution_context
            )

            if not save_result.status == ExecutionStatus.COMPLETED:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error="Не удалось сохранить обновленный план"
                )

            # 6. Публикация события об обновлении плана
            await self._publish_event(
                event_type="planning.plan_updated",
                data={
                    "plan_id": updated_plan.get("plan_id", plan_id),
                    "reason": reason,
                    "steps_count": len(updated_plan.get("steps", []))
                },
                execution_context=execution_context
            )

            return ExecutionResult(
                status=ExecutionStatus.COMPLETED,
                data={
                    "plan": updated_plan,
                    "update_applied": True
                },
                metadata={
                    "plan_id": updated_plan.get("plan_id", plan_id),
                    "steps_count": len(updated_plan.get("steps", []))
                }
            )

        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка обновления плана: {str(e)}", exc_info=True)
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            else:
                self.logger.error(f"Ошибка обновления плана: {str(e)}", exc_info=True)
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=f"Не удалось обновить план: {str(e)[:100]}"
            )

    async def _get_next_step(self, input_data: Dict[str, Any], execution_context: ExecutionContext) -> ExecutionResult:
        """
        Получение следующего шага из плана с поддержкой иерархии.
        Обходит вложенные планы (сначала подзадачи, потом родительские).
        """
        try:
            # В новой архитектуре работа с контекстом сессии осуществляется через executor
            # Получаем текущий план через действие
            plan_result = await self.executor.execute_action(
                action_name="context.get_current_plan",
                parameters={},
                context=execution_context
            )

            if not plan_result.status == ExecutionStatus.COMPLETED:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Нет текущего плана для получения следующего шага: {plan_result.error}"
                )

            # Проверяем, существует ли план
            exists = plan_result.metadata.get("exists", False) if isinstance(plan_result.metadata, dict) else False
            if not plan_result.data or not exists:
                return ExecutionResult(
                    status=ExecutionStatus.COMPLETED,
                    data={"step": None},
                    metadata={"step_found": False, "message": "Текущий план не найден"}
                )

            current_plan = plan_result.data

            # Проверяем, является ли это иерархическим планом
            if current_plan.get("plan_type") == "hierarchy" or "sub_plans" in current_plan:
                # Это иерархический план, нужно обработать подпланы
                next_step = await self._get_next_step_from_hierarchy(current_plan, input_data, execution_context)
            else:
                # Это обычный план, обрабатываем как обычно
                next_step = await self._get_next_step_from_flat_plan(current_plan, input_data)

            if next_step:
                return ExecutionResult(
                    status=ExecutionStatus.COMPLETED,
                    data={"step": next_step},
                    metadata={"step_found": True}
                )
            else:
                return ExecutionResult(
                    status=ExecutionStatus.COMPLETED,
                    data={"step": None},
                    metadata={"step_found": False}
                )

        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка получения следующего шага: {str(e)}", exc_info=True)
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            else:
                self.logger.error(f"Ошибка получения следующего шага: {str(e)}", exc_info=True)
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=f"Не удалось получить следующего шага: {str(e)[:100]}"
            )

    async def _get_next_step_from_flat_plan(self, plan: Dict[str, Any], input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Получение следующего шага из плоского плана.
        """
        steps = plan.get("steps", [])

        # Находим текущий шаг
        current_step_idx = -1
        current_step_id = input_data.get("current_step_id")
        if current_step_id:
            for idx, step in enumerate(steps):
                if step.get("step_id") == current_step_id:
                    current_step_idx = idx
                    break

        # Возвращаем следующий шаг после текущего
        next_step_idx = current_step_idx + 1
        if next_step_idx < len(steps):
            return steps[next_step_idx]

        return None

    async def _get_next_step_from_hierarchy(self, hierarchy_plan: Dict[str, Any], input_data: Dict[str, Any], execution_context: ExecutionContext) -> Dict[str, Any]:
        """
        Получение следующего шага из иерархического плана.
        Обходит подпланы рекурсивно.
        """
        # Получаем подпланы
        sub_plans = hierarchy_plan.get("sub_plans", [])

        # Если есть подпланы, ищем следующий шаг в них
        for sub_plan_info in sub_plans:
            # Получаем сам план из контекста через executor
            sub_plan_result = await self.executor.execute_action(
                action_name="context.get_context_item",
                parameters={"item_id": sub_plan_info.get("plan_id")},
                context=execution_context
            )

            if sub_plan_result.status == ExecutionStatus.COMPLETED and sub_plan_result.data:
                # Извлекаем контент из результата
                sub_plan = sub_plan_result.data.get("content", sub_plan_result.data)
                # Создаем временный input_data для подплана
                sub_input = {
                    "plan_id": sub_plan_info.get("plan_id"),
                    "current_step_id": None  # начинаем с начала подплана
                }

                # Получаем следующий шаг из подплана
                next_step = await self._get_next_step_from_flat_plan(sub_plan, sub_input)
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

    async def _update_step_status(self, input_data: Dict[str, Any], execution_context: ExecutionContext) -> ExecutionResult:
        """
        Обновление статуса шага плана.
        При ошибке выполнения шага вызывает автоматическую коррекцию плана.
        """
        try:
            # Получаем текущий план через executor
            plan_result = await self.executor.execute_action(
                action_name="context.get_current_plan",
                parameters={},
                context=execution_context
            )

            if not plan_result.status == ExecutionStatus.COMPLETED:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Нет текущего плана для обновления статуса шага: {plan_result.error}"
                )

            # Проверяем, существует ли план
            exists = plan_result.metadata.get("exists", False) if isinstance(plan_result.metadata, dict) else False
            if not plan_result.data or not exists:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error="Текущий план не найден в контексте"
                )

            current_plan = plan_result.data
            steps = current_plan.get("steps", [])

            # Находим шаг для обновления
            step_to_update = None
            step_index = -1
            target_step_id = input_data.get('step_id')
            for idx, step in enumerate(steps):
                if step.get("step_id") == target_step_id:
                    step_to_update = step.copy()
                    step_index = idx
                    break

            if not step_to_update:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Шаг с ID {target_step_id} не найден в плане"
                )

            # Обновляем статус шага
            step_to_update["status"] = input_data.get('status', 'pending')
            if input_data.get('result'):
                step_to_update["result"] = input_data.get('result')
            if input_data.get('error_message'):
                step_to_update["error_message"] = input_data.get('error_message')

            # Если статус - FAILED, запускаем коррекцию плана
            if input_data.get('status') == 'FAILED' and input_data.get('error_message'):
                # Выполняем коррекцию плана через executor
                correction_result = await self._correct_plan_after_failure(
                    current_plan=current_plan,
                    failed_step=step_to_update,
                    error_info=input_data.get('error_message'),
                    execution_context=execution_context
                )

                if correction_result.status == ExecutionStatus.COMPLETED:
                    # Если коррекция прошла успешно, возвращаем результат коррекции
                    return correction_result

            # Обновляем шаг в плане
            updated_steps = steps.copy()
            updated_steps[step_index] = step_to_update

            # Обновляем план в контексте через executor
            update_result = await self.executor.execute_action(
                action_name="context.record_plan",
                parameters={
                    "plan_data": {
                        **current_plan,
                        "steps": updated_steps
                    },
                    "plan_type": "update"
                },
                context=execution_context
            )

            if not update_result.status == ExecutionStatus.COMPLETED:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Не удалось обновить план в контексте: {update_result.error}"
                )

            # Пытаемся получить следующий шаг
            next_step = None
            if step_index >= 0 and step_index + 1 < len(updated_steps):
                next_step = updated_steps[step_index + 1]

            return ExecutionResult(
                status=ExecutionStatus.COMPLETED,
                data={
                    "updated_step": step_to_update,
                    "next_step": next_step
                },
                metadata={"step_id": target_step_id, "new_status": input_data.get('status', 'pending')}
            )

        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка обновления статуса шага: {str(e)}", exc_info=True)
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            else:
                self.logger.error(f"Ошибка обновления статуса шага: {str(e)}", exc_info=True)
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=f"Не удалось обновить статус шага: {str(e)[:100]}"
            )

    async def _correct_plan_after_failure(
        self,
        current_plan: Dict[str, Any],
        failed_step: Dict[str, Any],
        error_info: str,
        execution_context: ExecutionContext
    ) -> ExecutionResult:
        """
        Автоматическая коррекция плана после ошибки выполнения шага.
        """
        try:
            # Формируем промпт коррекции
            prompt_obj = self.get_prompt("planning.update_plan")
            correction_prompt = prompt_obj.content if prompt_obj else ""

            # Получаем схему выхода для structured output
            output_schema = self.get_output_contract("planning.update_plan")

            # Вызов LLM для коррекции плана через executor С STRUCTURED OUTPUT
            llm_result = await self.executor.execute_action(
                action_name="llm.generate_structured",
                parameters={
                    "prompt": correction_prompt,
                    "structured_output": {
                        "output_model": "planning.update_plan.output",
                        "schema_def": output_schema,
                        "max_retries": 3,
                        "strict_mode": True
                    },
                    "temperature": 0.1  # Низкая температура для точности
                },
                context=execution_context
            )

            if not llm_result.status == ExecutionStatus.COMPLETED:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Ошибка коррекции плана: {llm_result.error}",
                    metadata={
                        "error_type": llm_result.metadata.get("error_type", "unknown") if isinstance(llm_result.metadata, dict) else "unknown",
                        "attempts": llm_result.metadata.get("attempts", 0) if isinstance(llm_result.metadata, dict) else 0
                    }
                )

            # Получаем структурированные данные
            # ✅ ИСПРАВЛЕНО: Работаем с Pydantic моделью или dict
            llm_result_data = llm_result.result
            if hasattr(llm_result_data, 'parsed_content'):
                # StructuredLLMResponse — извлекаем parsed_content
                corrected_plan = llm_result_data.parsed_content
            elif isinstance(llm_result_data, dict):
                corrected_plan = llm_result_data.get("parsed_content", {})
            else:
                corrected_plan = llm_result_data if llm_result_data else {}

            # Логирование успешного structured output
            if self.event_bus_logger:
                await self.event_bus_logger.info(
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    f"Коррекция плана выполнена с structured output (попыток: {llm_result.metadata.get('parsing_attempts', 1) if isinstance(llm_result.metadata, dict) else 1})"
                )
            else:
                self.logger.info(
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    f"Коррекция плана выполнена с structured output (попыток: {llm_result.metadata.get('parsing_attempts', 1) if isinstance(llm_result.metadata, dict) else 1})"
                )

            # Сохраняем исправленный план
            update_result = await self.executor.execute_action(
                action_name="context.record_plan",
                parameters={
                    "plan_data": corrected_plan,
                    "plan_type": "update"
                },
                context=execution_context
            )

            if not update_result.status == ExecutionStatus.COMPLETED:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error="Не удалось сохранить скорректированный план"
                )

            return ExecutionResult(
                status=ExecutionStatus.COMPLETED,
                data=llm_result.result,
                metadata={"correction_applied": True}
            )
        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка коррекции плана: {str(e)}", exc_info=True)
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            else:
                self.logger.error(f"Ошибка коррекции плана: {str(e)}", exc_info=True)
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=f"Ошибка коррекции плана: {str(e)[:100]}"
            )

    async def _decompose_task(self, input_data: Dict[str, Any], execution_context: ExecutionContext) -> ExecutionResult:
        """
        Декомпозиция сложной задачи на иерархию подзадач.
        """
        try:
            # Получение промпта декомпозиции
            prompt_obj = self.get_prompt("planning.decompose_task")
            rendered_prompt = prompt_obj.content if prompt_obj else ""

            # Получаем схему выхода для structured output
            output_schema = self.get_output_contract("planning.decompose_task")

            # Вызов LLM для декомпозиции через executor С STRUCTURED OUTPUT
            llm_result = await self.executor.execute_action(
                action_name="llm.generate_structured",
                parameters={
                    "prompt": rendered_prompt,
                    "structured_output": {
                        "output_model": "planning.decompose_task.output",
                        "schema_def": output_schema,
                        "max_retries": 3,
                        "strict_mode": True
                    },
                    "temperature": 0.1  # Низкая температура для точности
                },
                context=execution_context
            )

            if not llm_result.status == ExecutionStatus.COMPLETED:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Ошибка декомпозиции задачи: {llm_result.error}",
                    metadata={
                        "error_type": llm_result.metadata.get("error_type", "unknown") if isinstance(llm_result.metadata, dict) else "unknown",
                        "attempts": llm_result.metadata.get("attempts", 0) if isinstance(llm_result.metadata, dict) else 0
                    }
                )

            # Получаем структурированные данные
            # ✅ ИСПРАВЛЕНО: Работаем с Pydantic моделью или dict
            llm_result_data = llm_result.result
            if hasattr(llm_result_data, 'parsed_content'):
                # StructuredLLMResponse — извлекаем parsed_content
                decompose_data = llm_result_data.parsed_content
            elif isinstance(llm_result_data, dict):
                decompose_data = llm_result_data.get("parsed_content", {})
            else:
                decompose_data = llm_result_data if llm_result_data else {}

            # Логирование успешного structured output
            if self.event_bus_logger:
                await self.event_bus_logger.info(
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    f"Декомпозиция выполнена с structured output (попыток: {llm_result.metadata.get('parsing_attempts', 1) if isinstance(llm_result.metadata, dict) else 1})"
                )
            else:
                self.logger.info(
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
                    f"Декомпозиция выполнена с structured output (попыток: {llm_result.metadata.get('parsing_attempts', 1) if isinstance(llm_result.metadata, dict) else 1})"
                )

            # Создание вложенных планов для подзадач
            sub_plans = []
            subtasks_list = decompose_data.get('subtasks', [])

            for subtask in subtasks_list:
                if isinstance(subtask, dict):
                    description = subtask.get('description', '')
                    subtask_id = subtask.get('subtask_id', '')
                else:
                    # Если это Pydantic-модель
                    description = getattr(subtask, 'description', '')
                    subtask_id = getattr(subtask, 'subtask_id', '')

                # Создаем мини-план для подзадачи
                sub_plan_params = {
                    "goal": description,
                    "max_steps": min(3, len(description.split('.'))),
                    "context": f"Подзадача {subtask_id} родительской задачи {input_data.get('task_id', '')}",
                }
                
                sub_plan_result = await self._create_plan(sub_plan_params, execution_context)
                
                if sub_plan_result.status == ExecutionStatus.COMPLETED:
                    sub_plans.append({
                        "subtask_id": subtask_id,
                        "plan_id": sub_plan_result.data.get("plan_id") if isinstance(sub_plan_result.data, dict) else None,
                        "description": description,
                        "complexity": getattr(subtask, 'complexity', '') if hasattr(subtask, 'complexity') else subtask.get('complexity', '')
                    })

            # Сохранение иерархии в контекст
            hierarchy_data = {
                "parent_task_id": llm_result.result.get("parent_task_id") if llm_result.result else None,
                "original_task": llm_result.result.get("original_task") if llm_result.result else None,
                "sub_plans": sub_plans,
                "decomposition_strategy": llm_result.result.get("decomposition_strategy") if llm_result.result else None,
                "metadata": llm_result.result.get("metadata") if llm_result.result else None
            }

            hierarchy_result = await self.executor.execute_action(
                action_name="context.record_plan",
                parameters={
                    "plan_data": hierarchy_data,
                    "plan_type": "initial"  # Используем 'initial' для нового плана иерархии
                },
                context=execution_context
            )

            if not hierarchy_result.status == ExecutionStatus.COMPLETED:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Не удалось сохранить иерархию плана: {hierarchy_result.error}"
                )

            return ExecutionResult(
                status=ExecutionStatus.COMPLETED,
                data=hierarchy_data,
                metadata={"subtasks_count": len(sub_plans)}
            )
        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка декомпозиции задачи: {str(e)}", exc_info=True)
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            else:
                self.logger.error(f"Ошибка декомпозиции задачи: {str(e)}", exc_info=True)
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=f"Не удалось декомпозировать задачу: {str(e)[:100]}"
            )

    async def _mark_task_completed(self, input_data: Dict[str, Any], execution_context: ExecutionContext) -> ExecutionResult:
        """
        Отметка задачи как завершенной.
        Обновляет статус шага, проверяет завершение всех задач и определяет следующий шаг.
        """
        try:
            # 1. Валидация входных данных через контракт
            input_contract = self.get_input_contract("planning.mark_task_completed")
            # validate_against_schema(input_data, input_contract)

            step_id = input_data.get("step_id")
            plan_id = input_data.get("plan_id", "")
            result_data = input_data.get("result_data", "")

            # 2. Загрузка текущего плана
            if plan_id:
                plan_result = await self.executor.execute_action(
                    action_name="context.get_context_item",
                    parameters={"item_id": plan_id},
                    context=execution_context
                )
                if not plan_result.status == ExecutionStatus.COMPLETED:
                    return ExecutionResult(
                        status=ExecutionStatus.FAILED,
                        error=f"План с ID {plan_id} не найден: {plan_result.error}"
                    )
                current_plan = plan_result.data.get("content", {}) if plan_result.data else {}
            else:
                plan_result = await self.executor.execute_action(
                    action_name="context.get_current_plan",
                    parameters={},
                    context=execution_context
                )
                if not plan_result.status == ExecutionStatus.COMPLETED:
                    return ExecutionResult(
                        status=ExecutionStatus.FAILED,
                        error=f"Нет текущего плана для отметки задачи: {plan_result.error}"
                    )

                # Проверяем, существует ли план
                exists = plan_result.metadata.get("exists", False) if isinstance(plan_result.metadata, dict) else False
                if not plan_result.data or not exists:
                    return ExecutionResult(
                        status=ExecutionStatus.FAILED,
                        error="Текущий план не найден в контексте"
                    )
                
                current_plan = plan_result.data

            steps = current_plan.get("steps", [])

            # 3. Поиск шага для обновления
            step_to_update = None
            step_index = -1
            for idx, step in enumerate(steps):
                if step.get("step_id") == step_id:
                    step_to_update = step.copy()
                    step_index = idx
                    break

            if not step_to_update:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Шаг с ID {step_id} не найден в плане"
                )

            # 4. Обновление статуса шага
            import datetime
            step_to_update["status"] = "completed"
            step_to_update["completed_at"] = datetime.datetime.utcnow().isoformat()
            if result_data:
                step_to_update["result"] = result_data

            # 5. Обновление шага в плане
            updated_steps = steps.copy()
            updated_steps[step_index] = step_to_update

            # 6. Проверка, все ли задачи завершены
            all_completed = all(
                s.get("status") == "completed"
                for s in updated_steps
            )

            # 7. Определение следующего шага
            next_step = None
            if not all_completed and step_index + 1 < len(updated_steps):
                next_step = {
                    "step_id": updated_steps[step_index + 1].get("step_id"),
                    "action": updated_steps[step_index + 1].get("action")
                }

            # 8. Сохранение обновленного плана
            update_result = await self.executor.execute_action(
                action_name="context.record_plan",
                parameters={
                    "plan_data": {
                        **current_plan,
                        "steps": updated_steps
                    },
                    "plan_type": "update"
                },
                context=execution_context
            )

            if not update_result.status == ExecutionStatus.COMPLETED:
                return ExecutionResult(
                    status=ExecutionStatus.FAILED,
                    error=f"Не удалось сохранить обновленный план: {update_result.error}"
                )

            # 9. Публикация события о завершении задачи
            await self._publish_event(
                event_type="planning.task_completed",
                data={
                    "step_id": step_id,
                    "plan_id": current_plan.get("plan_id", ""),
                    "all_tasks_completed": all_completed
                },
                execution_context=execution_context
            )

            return ExecutionResult(
                status=ExecutionStatus.COMPLETED,
                data={
                    "step_id": step_id,
                    "all_tasks_completed": all_completed,
                    "updated_step": step_to_update,
                    "next_step": next_step
                },
                metadata={
                    "step_id": step_id,
                    "completed_at": step_to_update.get("completed_at")
                }
            )

        except Exception as e:
            if self.event_bus_logger:
                await self.event_bus_logger.error(f"Ошибка отметки задачи как завершенной: {str(e)}", exc_info=True)
                  # TODO: Замени EventBusLogger на event_bus.publish(EventType.XXX, {...})
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            else:
                self.logger.error(f"Ошибка отметки задачи как завершенной: {str(e)}", exc_info=True)
                  # TODO: Используй event_bus.publish(EventType.XXX, {...}) вместо logging.getLogger()
            return ExecutionResult(
                status=ExecutionStatus.FAILED,
                error=f"Не удалось отметить задачу как завершенную: {str(e)[:100]}"
            )

    async def shutdown(self):
        """Очистка ресурсов навыка."""
        # В PlanningSkill нет специфических ресурсов для очистки
        pass