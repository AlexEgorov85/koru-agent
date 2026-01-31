"""
Пример использования ComposableAgent - чистой реализации ComposableAgentInterface.
"""

import asyncio
import sys
import os

# Добавляем путь корню проекта для импорта модулей
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.composable_agent import ComposableAgent, SimpleComposableAgent
from core.composable_patterns.base import PatternBuilder, ComposablePattern
from core.atomic_actions.base import AtomicAction
from core.agent_runtime.model import StrategyDecision, StrategyDecisionType
from core.session_context.session_context import SessionContext
from core.system_context.system_context import SystemContext


# Создаем мок-классы для демонстрации, чтобы избежать ошибок выполнения
class MockAtomicAction(AtomicAction):
    """Мок-класс для демонстрации выполнения атомарного действия."""
    
    def __init__(self, name: str = "mock_action", result_type: StrategyDecisionType = StrategyDecisionType.CONTINUE):
        super().__init__(name, "Mock atomic action for demonstration")
        self.result_type = result_type

    async def execute(self, runtime, context, parameters=None):
        return StrategyDecision(action=self.result_type, reason="mock_action_executed")


class MockComposablePattern(ComposablePattern):
    """Мок-класс для демонстрации выполнения компонуемого паттерна."""
    
    def __init__(self, name: str = "mock_pattern", result_type: StrategyDecisionType = StrategyDecisionType.CONTINUE):
        super().__init__(name, "Mock composable pattern for demonstration")
        self.result_type = result_type

    async def execute(self, runtime, context, parameters=None):
        return StrategyDecision(action=self.result_type, reason="mock_pattern_executed")


async def main():
    """
    Пример использования ComposableAgent с различными паттернами.
    """
    print("=== Пример использования ComposableAgent ===\n")
    
    # 1. Создание базового компонуемого агента
    print("1. Создание базового компонуемого агента...")
    agent = ComposableAgent("ExampleAgent", "Агент для демонстрации возможностей")
    print(f"Создан агент: {agent.name} - {agent.description}")
    print(f"Доступные домены: {agent.get_available_domains()}\n")
    
    # 2. Адаптация к домену
    print("2. Адаптация агента к домену...")
    agent.adapt_to_domain("code_analysis")
    print(f"Агент адаптирован к домену: code_analysis\n")
    
    # 3. Создание контекста для выполнения
    print("3. Подготовка контекста выполнения...")
    context = {
        "task": "Анализировать производительность алгоритма сортировки",
        "requirements": ["эффективность", "стабильность", "сложность"],
        "constraints": ["время выполнения", "потребление памяти"]
    }
    print(f"Контекст задачи: {context}\n")
    
    # 4. Создание мок-паттерна для демонстрации
    print("4. Создание мок-компонуемого паттерна для демонстрации...")
    mock_pattern = MockComposablePattern("демонстрационный_паттерн", StrategyDecisionType.CONTINUE)
    print(f"Создан мок-паттерн: {mock_pattern.name}\n")
    
    # 5. Выполнение мок-компонуемого паттерна
    print("5. Выполнение компонуемого паттерна...")
    try:
        result = await agent.execute_composable_pattern(mock_pattern, context)
        print(f"Результат выполнения паттерна: {result.action.value}")
        print(f"Причина: {result.reason}\n")
    except Exception as e:
        print(f"Ошибка при выполнении паттерна: {e}\n")
    
    # 6. Создание и выполнение мок-атомарного действия
    print("6. Выполнение атомарного действия...")
    mock_action = MockAtomicAction("mock_think_action", StrategyDecisionType.CONTINUE)
    try:
        result = await agent.execute_atomic_action(mock_action, context)
        print(f"Результат выполнения атомарного действия: {result.action.value}")
        print(f"Причина: {result.reason}\n")
    except Exception as e:
        print(f"Ошибка при выполнении атомарного действия: {e}\n")
    
    # 7. Использование упрощенного агента
    print("7. Создание и использование упрощенного агента...")
    simple_agent = SimpleComposableAgent("SimpleExampleAgent", "Простой агент для демонстрации", "research")
    print(f"Создан простой агент: {simple_agent.name}, адаптирован к домену: {simple_agent.domain_manager.get_current_domain()}")
    
    # Выполнение через упрощенный метод
    result = await simple_agent.simple_execute(mock_pattern, context)
    print(f"Результат выполнения через simple_execute: {result.action.value}")
    print(f"Причина: {result.reason}\n")
    
    # 8. Демонстрация возможности адаптации к нескольким доменам
    print("8. Демонстрация адаптации к нескольким доменам...")
    agent.adapt_to_domain("data_analysis")
    agent.adapt_to_domain("planning")
    print(f"Агент адаптирован к доменам: {agent.domains}\n")
    
    print("=== Пример завершен ===")


if __name__ == "__main__":
    asyncio.run(main())


