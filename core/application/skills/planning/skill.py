"""
НАВЫК ПЛАНИРОВАНИЯ С ПОЛНОЙ ИЗОЛЯЦИЕЙ
"""
import time
from typing import Any, Dict, List
from core.components.base_component import BaseComponent
from core.models.data.capability import Capability
from core.application.agent.components.action_executor import ExecutionContext, ActionResult


class PlanningSkill(BaseComponent):
    """НАВЫК ПЛАНИРОВАНИЯ С ПОЛНОЙ ИЗОЛЯЦИЕЙ"""
    
    def __init__(self, name: str, application_context: Any, component_config=None, executor=None):
        super().__init__(name, application_context, component_config=component_config, executor=executor)
        # Инициализация логгера
        import logging
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def get_capabilities(self) -> List[Capability]:
        return [
            Capability(
                name="planning.create_plan",
                description="Создание первичного плана действий",
                skill_name=self.name,
                visiable=True
            ),
            Capability(
                name="planning.update_plan",
                description="Обновление существующего плана",
                skill_name=self.name,
                visiable=True
            ),
            Capability(
                name="planning.get_next_step",
                description="Получение следующего шага из плана",
                skill_name=self.name,
                visiable=True
            ),
            Capability(
                name="planning.update_step_status",
                description="Обновление статуса шага плана",
                skill_name=self.name,
                visiable=True
            ),
            Capability(
                name="planning.decompose_task",
                description="Декомпозиция сложной задачи на подзадачи",
                skill_name=self.name,
                visiable=True
            ),
            Capability(
                name="planning.mark_task_completed",
                description="Отметка задачи как завершенной",
                skill_name=self.name,
                visiable=True
            )
        ]

    async def execute(
        self,
        capability: 'Capability',
        parameters: Dict[str, Any],
        execution_context: ExecutionContext
    ) -> ActionResult:
        """
        ЕДИНСТВЕННЫЙ метод выполнения логики компонента.
        
        ЗАПРЕЩЕНО:
        - Вызывать другие компоненты напрямую
        - Обращаться к сервисам (PromptService, ContractService)
        - Работать с файловой системой
        
        РАЗРЕШЕНО:
        - Использовать предзагруженные ресурсы из кэшей
        - Вызывать другие действия через self.executor.execute_action()
        - Валидировать входные/выходные данные через контракты из кэша
        """
        # 1. Валидация входных данных через КЭШИРОВАННЫЙ контракт
        try:
            input_contract = self.get_input_contract(capability.name)
            # Валидация через метод базового класса
            if not self.validate_input(capability.name, parameters):
                return ActionResult(
                    success=False,
                    error=f"Валидация входных данных для {capability.name} не пройдена"
                )
        except KeyError:
            # Если контракт не найден в кэше, используем переданные параметры без валидации
            # Это обеспечивает обратную совместимость
            self.logger.warning(f"Контракт для {capability.name} не найден в кэше, валидация пропущена")

        # 2. Делегирование конкретным методам
        if capability.name == "planning.create_plan":
            return await self._create_plan(parameters, execution_context)
        elif capability.name == "planning.update_plan":
            return await self._update_plan(parameters, execution_context)
        elif capability.name == "planning.get_next_step":
            return await self._get_next_step(parameters, execution_context)
        elif capability.name == "planning.update_step_status":
            return await self._update_step_status(parameters, execution_context)
        elif capability.name == "planning.decompose_task":
            return await self._decompose_task(parameters, execution_context)
        elif capability.name == "planning.mark_task_completed":
            return await self._mark_task_completed(parameters, execution_context)
        else:
            return ActionResult(
                success=False,
                error=f"Неизвестная capability: {capability.name}"
            )
    
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
            await self.application_context.infrastructure_context.event_bus.publish(
                event_type=event_type,
                data=data,
                source="planning_skill"
            )
        except Exception as e:
            self.logger.warning(f"Не удалось опубликовать событие {event_type}: {str(e)}")

    async def _create_plan(self, input_data: Dict[str, Any], execution_context: ExecutionContext) -> ActionResult:
        try:
            # 1. Валидация через КЭШИРОВАННЫЙ контракт (без обращения к сервису!)
            input_contract = self.get_input_contract("planning.create_plan")
            # validate_against_schema(input_data, input_contract)
            
            # 2. Получение промпта ИЗ КЭША
            prompt_template = self.get_prompt("planning.create_plan")
            rendered_prompt = prompt_template.format(
                goal=input_data.get("goal", ""),
                capabilities_list=self._format_capabilities(execution_context.available_capabilities)
            )
            
            # 3. Вызов LLM ЧЕРЕЗ EXECUTOR (не напрямую!)
            llm_result = await self.executor.execute_action(
                action_name="llm.generate",
                parameters={
                    "prompt": rendered_prompt,
                    "model": "gpt-4",
                    "temperature": 0.2
                },
                context=execution_context
            )
            
            if not llm_result.success:
                return ActionResult(
                    success=False,
                    error=f"Ошибка генерации плана: {llm_result.error}"
                )
            
            # 4. Валидация выхода через КЭШИРОВАННЫЙ контракт
            output_contract = self.get_output_contract("planning.create_plan")
            # validate_against_schema(llm_result.data, output_contract)

            # 5. Сохранение плана в контекст
            save_result = await self.executor.execute_action(
                action_name="context.record_plan",
                parameters={
                    "plan_data": llm_result.data,
                    "plan_type": "initial"
                },
                context=execution_context
            )

            if not save_result.success:
                return ActionResult(
                    success=False,
                    error=f"Не удалось сохранить план: {save_result.error}"
                )

            # 6. Публикация события о создании плана
            await self._publish_event(
                event_type="planning.plan_created",
                data={
                    "plan_id": llm_result.data.get("plan_id", ""),
                    "steps_count": len(llm_result.data.get("steps", [])),
                    "goal": input_data.get("goal", "")
                },
                execution_context=execution_context
            )

            return ActionResult(
                success=True,
                data=llm_result.data,
                metadata={
                    "steps_count": len(llm_result.data.get("steps", [])),
                    "plan_id": llm_result.data.get("plan_id", "")
                }
            )

        except Exception as e:
            self.logger.error(f"Ошибка создания плана: {str(e)}", exc_info=True)
            return ActionResult(
                success=False,
                error=f"Не удалось создать план: {str(e)[:100]}"
            )

    async def _update_plan(self, input_data: Dict[str, Any], execution_context: ExecutionContext) -> ActionResult:
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
                if not plan_result.success:
                    return ActionResult(
                        success=False,
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
                if not plan_result.success:
                    return ActionResult(
                        success=False,
                        error="Нет текущего плана для обновления"
                    )
                current_plan = plan_result.data

            # 3. Подготовка промпта для обновления плана
            prompt_template = self.get_prompt("planning.update_plan")
            rendered_prompt = prompt_template.format(
                current_plan=str(current_plan),
                new_requirements=str(updates),
                constraints="Сохранить логическую связность плана, не нарушать зависимости шагов",
                context=f"Причина обновления: {reason}" if reason else ""
            )

            # 4. Вызов LLM для обновления плана через executor
            llm_result = await self.executor.execute_action(
                action_name="llm.generate",
                parameters={
                    "prompt": rendered_prompt,
                    "model": "gpt-4",
                    "temperature": 0.3
                },
                context=execution_context
            )

            if not llm_result.success:
                return ActionResult(
                    success=False,
                    error=f"Ошибка обновления плана: {llm_result.error}"
                )

            updated_plan = llm_result.data

            # 5. Сохранение обновленного плана
            save_result = await self.executor.execute_action(
                action_name="context.record_plan",
                parameters={
                    "plan_data": updated_plan,
                    "plan_type": "update"
                },
                context=execution_context
            )

            if not save_result.success:
                return ActionResult(
                    success=False,
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

            return ActionResult(
                success=True,
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
            self.logger.error(f"Ошибка обновления плана: {str(e)}", exc_info=True)
            return ActionResult(
                success=False,
                error=f"Не удалось обновить план: {str(e)[:100]}"
            )

    async def _get_next_step(self, input_data: Dict[str, Any], execution_context: ExecutionContext) -> ActionResult:
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

            if not plan_result.success:
                return ActionResult(
                    success=False,
                    error=f"Нет текущего плана для получения следующего шага: {plan_result.error}"
                )

            # Проверяем, существует ли план
            if not plan_result.data or not plan_result.metadata.get("exists", False):
                return ActionResult(
                    success=True,
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
                return ActionResult(
                    success=True,
                    data={"step": next_step},
                    metadata={"step_found": True}
                )
            else:
                return ActionResult(
                    success=True,
                    data={"step": None},
                    metadata={"step_found": False}
                )

        except Exception as e:
            self.logger.error(f"Ошибка получения следующего шага: {str(e)}", exc_info=True)
            return ActionResult(
                success=False,
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

            if sub_plan_result.success and sub_plan_result.data:
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

    async def _update_step_status(self, input_data: Dict[str, Any], execution_context: ExecutionContext) -> ActionResult:
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

            if not plan_result.success:
                return ActionResult(
                    success=False,
                    error=f"Нет текущего плана для обновления статуса шага: {plan_result.error}"
                )

            # Проверяем, существует ли план
            if not plan_result.data or not plan_result.metadata.get("exists", False):
                return ActionResult(
                    success=False,
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
                return ActionResult(
                    success=False,
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

                if correction_result.success:
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

            if not update_result.success:
                return ActionResult(
                    success=False,
                    error=f"Не удалось обновить план в контексте: {update_result.error}"
                )

            # Пытаемся получить следующий шаг
            next_step = None
            if step_index >= 0 and step_index + 1 < len(updated_steps):
                next_step = updated_steps[step_index + 1]

            return ActionResult(
                success=True,
                data={
                    "updated_step": step_to_update,
                    "next_step": next_step
                },
                metadata={"step_id": target_step_id, "new_status": input_data.get('status', 'pending')}
            )

        except Exception as e:
            self.logger.error(f"Ошибка обновления статуса шага: {str(e)}", exc_info=True)
            return ActionResult(
                success=False,
                error=f"Не удалось обновить статус шага: {str(e)[:100]}"
            )

    async def _correct_plan_after_failure(
        self,
        current_plan: Dict[str, Any],
        failed_step: Dict[str, Any],
        error_info: str,
        execution_context: ExecutionContext
    ) -> ActionResult:
        """
        Автоматическая коррекция плана после ошибки выполнения шага.
        """
        try:
            # Формируем промпт коррекции
            correction_prompt = self.get_prompt("planning.update_plan").format(
                current_plan=str(current_plan),
                new_requirements=f"Исправить шаг {failed_step.get('step_id')} из-за ошибки: {error_info}",
                constraints="Сохранить логическую связность плана, не увеличивать общее количество шагов",
                context=f"Ошибка: {error_info}"
            )

            # Вызов LLM для коррекции плана через executor
            llm_result = await self.executor.execute_action(
                action_name="llm.generate",
                parameters={
                    "prompt": correction_prompt,
                    "model": "gpt-4",
                    "temperature": 0.3
                },
                context=execution_context
            )

            if not llm_result.success:
                return ActionResult(
                    success=False,
                    error=f"Ошибка коррекции плана: {llm_result.error}"
                )

            # Сохраняем исправленный план
            update_result = await self.executor.execute_action(
                action_name="context.record_plan",
                parameters={
                    "plan_data": llm_result.data,
                    "plan_type": "update"
                },
                context=execution_context
            )

            if not update_result.success:
                return ActionResult(
                    success=False,
                    error="Не удалось сохранить скорректированный план"
                )

            return ActionResult(
                success=True,
                data=llm_result.data,
                metadata={"correction_applied": True}
            )
        except Exception as e:
            self.logger.error(f"Ошибка коррекции плана: {str(e)}", exc_info=True)
            return ActionResult(
                success=False,
                error=f"Ошибка коррекции плана: {str(e)[:100]}"
            )

    async def _decompose_task(self, input_data: Dict[str, Any], execution_context: ExecutionContext) -> ActionResult:
        """
        Декомпозиция сложной задачи на иерархию подзадач.
        """
        try:
            # Получение промпта декомпозиции
            prompt_template = self.get_prompt("planning.decompose_task")
            rendered_prompt = prompt_template.format(
                task_id=input_data.get("task_id", ""),
                task_description=input_data.get("task_description", ""),
                context=input_data.get("context", ""),
                capabilities_list=self._format_capabilities(execution_context.available_capabilities)
            )

            # Вызов LLM для декомпозиции через executor
            llm_result = await self.executor.execute_action(
                action_name="llm.generate",
                parameters={
                    "prompt": rendered_prompt,
                    "model": "gpt-4",
                    "temperature": 0.3
                },
                context=execution_context
            )

            if not llm_result.success:
                return ActionResult(
                    success=False,
                    error=f"Ошибка декомпозиции задачи: {llm_result.error}"
                )

            # Создание вложенных планов для подзадач
            sub_plans = []
            subtasks_list = llm_result.data.get('subtasks', []) if isinstance(llm_result.data, dict) else llm_result.data

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
                
                if sub_plan_result.success:
                    sub_plans.append({
                        "subtask_id": subtask_id,
                        "plan_id": sub_plan_result.data.get("plan_id") if isinstance(sub_plan_result.data, dict) else None,
                        "description": description,
                        "complexity": getattr(subtask, 'complexity', '') if hasattr(subtask, 'complexity') else subtask.get('complexity', '')
                    })

            # Сохранение иерархии в контекст
            hierarchy_data = {
                "parent_task_id": llm_result.data.get("parent_task_id"),
                "original_task": llm_result.data.get("original_task"),
                "sub_plans": sub_plans,
                "decomposition_strategy": llm_result.data.get("decomposition_strategy"),
                "metadata": llm_result.data.get("metadata")
            }

            hierarchy_result = await self.executor.execute_action(
                action_name="context.record_plan",
                parameters={
                    "plan_data": hierarchy_data,
                    "plan_type": "initial"  # Используем 'initial' для нового плана иерархии
                },
                context=execution_context
            )

            if not hierarchy_result.success:
                return ActionResult(
                    success=False,
                    error=f"Не удалось сохранить иерархию плана: {hierarchy_result.error}"
                )

            return ActionResult(
                success=True,
                data=hierarchy_data,
                metadata={"subtasks_count": len(sub_plans)}
            )
        except Exception as e:
            self.logger.error(f"Ошибка декомпозиции задачи: {str(e)}", exc_info=True)
            return ActionResult(
                success=False,
                error=f"Не удалось декомпозировать задачу: {str(e)[:100]}"
            )

    async def _mark_task_completed(self, input_data: Dict[str, Any], execution_context: ExecutionContext) -> ActionResult:
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
                if not plan_result.success:
                    return ActionResult(
                        success=False,
                        error=f"План с ID {plan_id} не найден: {plan_result.error}"
                    )
                current_plan = plan_result.data.get("content", {}) if plan_result.data else {}
            else:
                plan_result = await self.executor.execute_action(
                    action_name="context.get_current_plan",
                    parameters={},
                    context=execution_context
                )
                if not plan_result.success:
                    return ActionResult(
                        success=False,
                        error=f"Нет текущего плана для отметки задачи: {plan_result.error}"
                    )
                
                # Проверяем, существует ли план
                if not plan_result.data or not plan_result.metadata.get("exists", False):
                    return ActionResult(
                        success=False,
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
                return ActionResult(
                    success=False,
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

            if not update_result.success:
                return ActionResult(
                    success=False,
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

            return ActionResult(
                success=True,
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
            self.logger.error(f"Ошибка отметки задачи как завершенной: {str(e)}", exc_info=True)
            return ActionResult(
                success=False,
                error=f"Не удалось отметить задачу как завершенную: {str(e)[:100]}"
            )

    async def shutdown(self):
        """Очистка ресурсов навыка."""
        # В PlanningSkill нет специфических ресурсов для очистки
        pass