"""
Пример использования AtomicActionExecutor - исполнителя атомарных действий с полным жизненным циклом.
"""

import asyncio
import sys
import os

# Добавляем путь корню проекта для импорта модулей
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.composable_agent import ComposableAgent
from core.atomic_actions.executor import AtomicActionExecutor
from core.atomic_actions.actions import THINK, ACT, OBSERVE, PLAN, REFLECT, EVALUATE, VERIFY, ADAPT

# Создаем упрощенный мок для runtime
class MockRuntime:
    def __init__(self):
        self.session = {}
        self.system = {}


async def main():
    """
    Пример использования AtomicActionExecutor с различными атомарными действиями.
    """
    print("=== Пример использования AtomicActionExecutor ===\n")
    
    # 1. Создание упрощенной среды выполнения
    print("1. Создание упрощенной среды выполнения...")
    runtime = MockRuntime()
    print("Среда выполнения создана\n")
    
    # 2. Создание исполнителя атомарных действий
    print("2. Создание исполнителя атомарных действий...")
    executor = AtomicActionExecutor(runtime)
    print(f"Исполнитель создан: {executor.__class__.__name__}\n")
    
    # 3. Подготовка контекста выполнения
    print("3. Подготовка контекста выполнения...")
    context = {
        "task": "Анализировать производительность алгоритма сортировки",
        "requirements": ["эффективность", "стабильность", "сложность"],
        "constraints": ["время выполнения", "потребление памяти"],
        "current_state": "initial"
    }
    print(f"Контекст задачи: {context}\n")
    
    # 4. Демонстрация обработки ошибок при выполнении атомарных действий
    print("4. Демонстрация обработки ошибок...")
    # Создаем мок-класс для демонстрации ошибки (в реальной ситуации это будет нормальное действие, которое вызывает ошибку)
    from unittest.mock import AsyncMock
    from core.atomic_actions.base import AtomicAction
    from core.agent_runtime.model import StrategyDecisionType
    
    class ErrorAction(AtomicAction):
        def __init__(self):
            super().__init__("error_action", "Action that raises an error for demonstration")
            
        async def execute(self, runtime, context, parameters=None):
            raise Exception("Simulated error in atomic action")
    
    error_action = ErrorAction()
    error_result = await executor.execute_atomic_action(error_action, context)
    print(f"Результат при ошибке: {error_result.action.value}")
    print(f"Причина ошибки: {error_result.reason}")
    print(f"Payload с ошибкой: {error_result.payload}\n")
    
    print("=== Пример завершен ===")


if __name__ == "__main__":
    asyncio.run(main())