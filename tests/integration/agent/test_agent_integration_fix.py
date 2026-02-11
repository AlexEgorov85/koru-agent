#!/usr/bin/env python3
"""
Тест интеграции агента с исправленной логикой шагов
"""

import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Добавляем путь к проекту
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.agent_runtime.runtime import AgentRuntime
from core.agent_runtime.policy import AgentPolicy
from core.session_context.session_context import SessionContext
from core.system_context.system_context import SystemContext
from models.execution import ExecutionStatus
from core.agent_runtime.model import StrategyDecision, StrategyDecisionType
from models.capability import Capability


class MockSystemContext:
    """Мок системного контекста для тестирования"""
    
    def __init__(self):
        self.resources = {}
        self.capabilities = {}
        self.call_llm_result = None
        
    def get_resource(self, resource_name):
        return self.resources.get(resource_name)
    
    def list_capabilities(self):
        return list(self.capabilities.keys())
    
    def get_capability(self, capability_name):
        return self.capabilities.get(capability_name)
    
    async def call_llm(self, request):
        # Возвращаем заранее подготовленный результат
        return self.call_llm_result


class MockCapabilityExecutor:
    """Мок исполнителя capability"""
    
    async def execute_capability(self, capability, parameters, session_context, system_context=None):
        # Возвращаем успешный результат
        return MagicMock(
            status=ExecutionStatus.SUCCESS,
            result=f"Executed {capability.name} with {parameters}",
            observation_item_id=["obs1"],
            summary=f"Executed {capability.name}"
        )


def test_agent_runtime_with_fixed_steps():
    """Тест работы агента с исправленной логикой шагов"""
    print("Тест: Работа агента с исправленной логикой шагов...")
    
    # Создаем моки
    mock_system_context = MockSystemContext()
    
    # Добавляем capability
    test_capability = Capability(
        name="test.skill.action",
        description="Test capability",
        parameters_schema={},
        skill_name="TestSkill",
        supported_strategies=["react"]
    )
    mock_system_context.capabilities["test.skill.action"] = test_capability
    
    # Создаем сессию
    session_context = SessionContext()
    
    # Создаем политику
    policy = AgentPolicy()
    
    # Создаем runtime
    runtime = AgentRuntime(
        system_context=mock_system_context,
        session_context=session_context,
        policy=policy,
        max_steps=3
    )
    
    # Мокаем стратегию, чтобы она возвращала ACT решения
    mock_strategy = MagicMock()
    mock_strategy.next_step = AsyncMock(side_effect=[
        StrategyDecision(
            action=StrategyDecisionType.ACT,
            capability=test_capability,
            payload={"param": "value1"},
            reason="First action"
        ),
        StrategyDecision(
            action=StrategyDecisionType.ACT,
            capability=test_capability,
            payload={"param": "value2"},
            reason="Second action"
        ),
        StrategyDecision(
            action=StrategyDecisionType.STOP,
            reason="Goal achieved"
        )
    ])
    
    runtime.strategy = mock_strategy
    
    # Мокаем executor
    runtime.executor = MockCapabilityExecutor()
    
    # Запускаем агента
    async def run_test():
        result = await runtime.run("Test goal")
        return result
    
    # Запускаем асинхронно
    result = asyncio.run(run_test())
    
    # Проверяем, что сессия завершена
    assert result is not None
    print(f"Сессия завершена, количество шагов: {result.step_context.count()}")
    
    # Проверяем, что все шаги имеют уникальные номера
    step_numbers = [step.step_number for step in result.step_context.steps]
    print(f"Номера шагов: {step_numbers}")
    
    # Ожидаем, что будут шаги с номерами 1 и 2 (шаг 3 - STOP, не создает нового шага)
    expected_numbers = list(range(1, result.step_context.count() + 1))
    assert step_numbers == expected_numbers, f"Ожидались номера {expected_numbers}, получены {step_numbers}"
    
    # Проверяем, что нет дублирующихся номеров
    assert len(set(step_numbers)) == len(step_numbers), "Обнаружены дублирующиеся номера шагов"
    
    print("[OK] Агент успешно завершил работу с уникальными номерами шагов")


def test_multiple_iterations_without_duplication():
    """Тест нескольких итераций без дубликации номеров шагов"""
    print("\nТест: Несколько итераций без дубликации номеров шагов...")
    
    # Создаем моки
    mock_system_context = MockSystemContext()
    
    test_capability = Capability(
        name="test.skill.iteration",
        description="Test iteration capability",
        parameters_schema={},
        skill_name="TestSkill",
        supported_strategies=["react"]
    )
    mock_system_context.capabilities["test.skill.iteration"] = test_capability
    
    # Создаем сессию
    session_context = SessionContext()
    
    # Создаем runtime с большим количеством шагов
    runtime = AgentRuntime(
        system_context=mock_system_context,
        session_context=session_context,
        max_steps=5
    )
    
    # Мокаем стратегию для 4 ACT и 1 STOP
    mock_strategy = MagicMock()
    decisions = []
    for i in range(4):
        decisions.append(StrategyDecision(
            action=StrategyDecisionType.ACT,
            capability=test_capability,
            payload={"iteration": i+1},
            reason=f"Iteration {i+1}"
        ))
    decisions.append(StrategyDecision(
        action=StrategyDecisionType.STOP,
        reason="All iterations completed"
    ))
    
    mock_strategy.next_step = AsyncMock(side_effect=decisions)
    runtime.strategy = mock_strategy
    
    # Мокаем executor
    runtime.executor = MockCapabilityExecutor()
    
    # Запускаем агента
    async def run_test():
        result = await runtime.run("Multi-iteration test goal")
        return result
    
    result = asyncio.run(run_test())
    
    # Проверяем количество шагов
    step_count = result.step_context.count()
    print(f"Количество выполненных шагов: {step_count}")
    
    # Проверяем номера шагов
    step_numbers = [step.step_number for step in result.step_context.steps]
    print(f"Номера шагов: {step_numbers}")
    
    # Ожидаем последовательные номера 1, 2, 3, 4
    expected_numbers = list(range(1, step_count + 1))
    assert step_numbers == expected_numbers, f"Ожидались номера {expected_numbers}, получены {step_numbers}"
    
    # Проверяем, что нет дубликатов
    assert len(set(step_numbers)) == len(step_numbers), "Обнаружены дублирующиеся номера шагов"
    
    print(f"[OK] {step_count} шагов выполнено без дубликации номеров")


if __name__ == "__main__":
    print("Запуск интеграционных тестов для проверки исправления ошибки с шагами...")
    
    try:
        test_agent_runtime_with_fixed_steps()
        test_multiple_iterations_without_duplication()
        
        print("\n[SUCCESS] Все интеграционные тесты пройдены успешно!")
        print("Исправление ошибки с дублированием шагов работает корректно в комплексе.")
    except Exception as e:
        print(f"\n[FAILURE] Ошибка при выполнении интеграционных тестов: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)