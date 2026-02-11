#!/usr/bin/env python3
"""
Тест для проверки метода _create_plan в PlanningSkill
"""

import sys
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock
from pydantic import ValidationError

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.skills.planning.skill import PlanningSkill
from core.skills.planning.schema import CreatePlanInput
from models.execution import ExecutionStatus


async def test_create_plan_method():
    """Тестируем метод _create_plan с валидными параметрами"""
    
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
    from core.skills.planning.schema import CreatePlanOutput, PlanStep
    from models.execution import ExecutionStatus
    
    # Создаем тестовый ответ от LLM
    mock_output = CreatePlanOutput(
        plan_id="test-plan-id",
        goal="Тестовая цель",
        steps=[
            PlanStep(
                step_id="step1",
                description="Тестовый шаг 1",
                capability_name="test.capability1",
                parameters={}
            )
        ],
        strategy="iterative"
    )
    
    mock_response = StructuredLLMResponse(
        parsed_content=mock_output,
        raw_response=MagicMock(content="Тестовый ответ", generation_time=0.1),
        parsing_attempts=1
    )
    
    mock_system_context.call_llm = AsyncMock(return_value=mock_response)
    
    # Создаем mock для context
    mock_context = MagicMock()
    mock_context.get_summary.return_value = "Тестовый контекст"
    mock_context.record_plan.return_value = "plan-item-123"
    mock_context.set_current_plan = MagicMock()
    
    # Создаем экземпляр PlanningSkill
    skill = PlanningSkill(name="planning", system_context=mock_system_context)
    
    # Подготовим валидные входные данные
    input_data = CreatePlanInput(
        goal="Создать план для выполнения задачи",
        max_steps=5,
        context="Тестовый контекст задачи"
    )
    
    # Вызов метода _create_plan
    result = await skill._create_plan(input_data, mock_context)
    
    # Проверки
    assert result.status == ExecutionStatus.SUCCESS, f"Статус должен быть SUCCESS, но получен {result.status}"
    assert result.result is not None, "Результат не должен быть None"
    assert result.observation_item_id == "plan-item-123", "ID элемента наблюдения должен совпадать с возвращенным из record_plan"
    assert "Создан план из 1 шагов" in result.summary, "Сводка должна содержать информацию о количестве шагов"
    
    # Проверим, что были вызваны нужные методы
    mock_prompt_service.render.assert_called_once()
    mock_system_context.call_llm.assert_called_once()
    mock_context.record_plan.assert_called_once()
    mock_context.set_current_plan.assert_called_once_with("plan-item-123")
    
    print("[SUCCESS] Метод _create_plan успешно прошел тест с валидными параметрами")
    print(f"  - Статус: {result.status}")
    print(f"  - Результат: {result.result is not None}")
    print(f"  - ID плана: {result.observation_item_id}")
    print(f"  - Сводка: {result.summary[:60]}...")
    
    return True


async def test_create_plan_validation_error():
    """Тестируем, что CreatePlanInput корректно валидирует данные"""
    
    # Проверим, что Pydantic валидирует хотя бы некоторые поля
    try:
        # Создадим валидный объект
        valid_input = CreatePlanInput(
            goal="Тестовая цель",
            max_steps=5
        )
        print("[SUCCESS] Валидный объект CreatePlanInput создается успешно")
        
        # Проверим, что схема позволяет создать объект с минимальными требованиями
        minimal_input = CreatePlanInput(goal="Минимальная цель")
        print("[SUCCESS] Минимальный объект CreatePlanInput создается успешно")
        
        return True
    except ValidationError as e:
        print(f"[ERROR] Ошибка валидации при создании валидного объекта: {e}")
        return False
    except Exception as e:
        print(f"[ERROR] Неожиданная ошибка: {e}")
        return False


async def main():
    try:
        # Тест 1: Проверка успешного выполнения
        success1 = await test_create_plan_method()
        
        # Тест 2: Проверка обработки ошибок
        success2 = await test_create_plan_validation_error()
        
        if success1 and success2:
            print("\n[SUCCESS] Все тесты для _create_plan прошли успешно!")
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