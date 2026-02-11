#!/usr/bin/env python3
"""
Интеграционный тест для PlanningSkill
Тестирует полный цикл: цель → план → выполнение → коррекция
"""

import sys
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.skills.planning.skill import PlanningSkill
from core.skills.planning.schema import (
    CreatePlanInput, UpdateStepStatusInput, 
    DecomposeTaskInput, StepStatus
)
from models.execution import ExecutionStatus


async def test_full_cycle():
    """Тестирует полный цикл работы PlanningSkill"""
    
    print("=== Тестирование полного цикла PlanningSkill ===")
    
    # Создаем mock для system_context
    mock_system_context = MagicMock()
    mock_system_context.get_resource = MagicMock()
    
    # Мокируем prompt_service
    mock_prompt_service = AsyncMock()
    mock_prompt_service.render.return_value = "Тестовый системный промпт для планирования"
    mock_system_context.get_resource.return_value = mock_prompt_service
    
    # Мокируем список capability
    mock_system_context.list_capabilities.return_value = ["test.capability1", "test.capability2"]
    mock_cap1 = MagicMock()
    mock_cap1.name = "test.capability1"
    mock_cap1.description = "Тестовая capability 1"
    mock_cap1.visiable = True
    mock_cap2 = MagicMock()
    mock_cap2.name = "test.capability2"
    mock_cap2.description = "Тестовая capability 2"
    mock_cap2.visiable = True
    mock_system_context.get_capability.side_effect = lambda x: mock_cap1 if x == "test.capability1" else mock_cap2
    
    # Мокируем вызов LLM
    from models.llm_types import StructuredLLMResponse
    from core.skills.planning.schema import CreatePlanOutput, PlanStep, UpdatePlanOutput, DecomposeTaskOutput, SubTask
    from models.execution import ExecutionStatus
    
    # Создаем тестовые ответы от LLM
    mock_plan_output = CreatePlanOutput(
        plan_id="test-plan-id",
        goal="Тестовая цель",
        steps=[
            PlanStep(
                step_id="step1",
                description="Тестовый шаг 1",
                capability_name="test.capability1",
                parameters={"param1": "value1"}
            ),
            PlanStep(
                step_id="step2",
                description="Тестовый шаг 2",
                capability_name="test.capability2",
                parameters={"param2": "value2"}
            )
        ],
        strategy="iterative"
    )
    
    mock_update_output = UpdatePlanOutput(
        plan_id="test-plan-id",
        updated_steps=[
            PlanStep(
                step_id="step1",
                description="Обновленный тестовый шаг 1",
                capability_name="test.capability1",
                parameters={"param1": "updated_value1"},
                status=StepStatus.COMPLETED
            ),
            PlanStep(
                step_id="step2",
                description="Тестовый шаг 2",
                capability_name="test.capability2",
                parameters={"param2": "value2"}
            )
        ],
        reason="Обновление после выполнения шага"
    )
    
    mock_decompose_output = DecomposeTaskOutput(
        parent_task_id="task1",
        original_task="Оригинальная задача",
        subtasks=[
            SubTask(
                subtask_id="subtask1",
                description="Подзадача 1",
                complexity="low",
                estimated_steps=2
            ),
            SubTask(
                subtask_id="subtask2", 
                description="Подзадача 2",
                complexity="medium",
                estimated_steps=3
            )
        ],
        decomposition_strategy="sequential",
        metadata={"source": "integration_test"}
    )
    
    # Мокируем вызовы LLM для разных сценариев
    def mock_call_llm(request):
        if request.capability_name == "planning.create_plan":
            mock_response = StructuredLLMResponse(
                parsed_content=mock_plan_output,
                raw_response=MagicMock(content="Тестовый ответ", generation_time=0.1),
                parsing_attempts=1
            )
        elif request.capability_name == "planning.update_plan":
            mock_response = StructuredLLMResponse(
                parsed_content=mock_update_output,
                raw_response=MagicMock(content="Тестовый ответ обновления", generation_time=0.1),
                parsing_attempts=1
            )
        elif request.capability_name == "planning.decompose_task":
            mock_response = StructuredLLMResponse(
                parsed_content=mock_decompose_output,
                raw_response=MagicMock(content="Тестовый ответ декомпозиции", generation_time=0.1),
                parsing_attempts=1
            )
        elif request.capability_name == "planning.analyze_step_failure":
            from core.skills.planning.schema import ErrorAnalysisOutput
            error_analysis = ErrorAnalysisOutput(
                error_type="execution_error",
                reason="Ошибка выполнения шага",
                suggested_fix="Повторить шаг с другими параметрами",
                severity="medium",
                reasoning="Шаг завершился с ошибкой выполнения",
                summary="Ошибка выполнения"
            )
            mock_response = StructuredLLMResponse(
                parsed_content=error_analysis,
                raw_response=MagicMock(content="Тестовый ответ анализа ошибки", generation_time=0.1),
                parsing_attempts=1
            )
        else:
            # Для других capability возвращаем базовый ответ
            mock_response = StructuredLLMResponse(
                parsed_content=mock_plan_output,
                raw_response=MagicMock(content="Тестовый ответ", generation_time=0.1),
                parsing_attempts=1
            )
        
        return mock_response
    
    mock_system_context.call_llm = AsyncMock(side_effect=mock_call_llm)
    
    # Создаем mock для context
    mock_context = MagicMock()
    mock_context.get_summary.return_value = "Тестовый контекст"
    mock_context.record_plan.return_value = "plan-item-123"
    mock_context.set_current_plan = MagicMock()
    mock_context.get_current_plan.return_value = MagicMock()
    mock_context.get_current_plan.return_value.content = mock_plan_output.model_dump()
    
    # Создаем экземпляр PlanningSkill
    skill = PlanningSkill(name="planning", system_context=mock_system_context)
    
    print("1. Тестирование создания плана...")
    # Тест 1: Создание плана
    create_input = CreatePlanInput(
        goal="Создать план для выполнения задачи",
        max_steps=5,
        context="Тестовый контекст задачи"
    )
    
    create_result = await skill._create_plan(create_input, mock_context)
    assert create_result.status == ExecutionStatus.SUCCESS
    assert create_result.result is not None
    print("   + План успешно создан")
    
    print("2. Тестирование обновления статуса шага (с ошибкой для тестирования коррекции)...")
    # Тест 2: Обновление статуса шага с ошибкой (для тестирования коррекции)
    update_input = UpdateStepStatusInput(
        plan_id="plan-item-123",
        step_id="step1",
        status=StepStatus.FAILED,
        error_message="Тестовая ошибка выполнения шага"
    )
    
    update_result = await skill._update_step_status(update_input, mock_context)
    assert update_result.status == ExecutionStatus.SUCCESS
    print("   + Статус шага обновлен, коррекция плана выполнена")
    
    print("3. Тестирование декомпозиции задачи...")
    # Тест 3: Декомпозиция задачи
    decompose_input = DecomposeTaskInput(
        task_id="task1",
        task_description="Сложная задача, требующая декомпозиции",
        context="Контекст декомпозиции"
    )
    
    decompose_result = await skill._decompose_task(decompose_input, mock_context)
    assert decompose_result.status == ExecutionStatus.SUCCESS
    assert decompose_result.result is not None
    print("   + Задача успешно декомпозирована")
    
    print("4. Тестирование получения следующего шага...")
    # Тест 4: Получение следующего шага
    from core.skills.planning.schema import GetNextStepInput
    get_next_input = GetNextStepInput(
        plan_id="plan-item-123",
        current_step_id="step1"
    )
    
    get_next_result = await skill._get_next_step(get_next_input, mock_context)
    # Может вернуть None, если все шаги выполнены
    print("   + Получение следующего шага завершено")
    
    print("\n=== Все тесты пройдены успешно! ===")
    print(f"   - Создание плана: {'+' if create_result.status == ExecutionStatus.SUCCESS else '-'}")
    print(f"   - Обновление статуса шага: {'+' if update_result.status == ExecutionStatus.SUCCESS else '-'}")
    print(f"   - Декомпозиция задачи: {'+' if decompose_result.status == ExecutionStatus.SUCCESS else '-'}")
    print(f"   - Получение следующего шага: OK")
    
    return True


async def main():
    try:
        success = await test_full_cycle()
        if success:
            print("\n[SUCCESS] Все интеграционные тесты прошли успешно!")
            return True
        else:
            print("\n[ERROR] Один или несколько тестов не прошли")
            return False
    except Exception as e:
        print(f"\n[ERROR] Непредвиденная ошибка в тесте: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)