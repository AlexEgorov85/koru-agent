"""
Тестирование новой архитектуры стратегий агента.
"""
import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.abspath('.'))

from core.config import get_config
from core.system_context.system_context import SystemContext
from core.session_context.session_context import SessionContext
from core.agent_runtime.runtime import AgentRuntime


async def test_new_strategy_architecture():
    """Тестирование новой архитектуры стратегий."""
    print("=== Тестирование новой архитектуры стратегий ===")
    
    # Загружаем конфигурацию
    config = get_config(profile="dev")
    
    # Создаем системный контекст
    system_context = SystemContext(config)
    await system_context.initialize()
    
    # Создаем сессию
    session = SessionContext()
    session.set_goal("Какие книги написал Пушкин?")
    
    # Создаем агент с новым runtime
    agent = AgentRuntime(
        system_context=system_context,
        session_context=session,
        max_steps=5
    )
    
    print(f"Агент создан. Стратегический менеджер: {hasattr(agent, 'strategy_manager')}")
    print(f"Прогресс-метрики: {hasattr(agent, 'progress_metrics')}")
    
    # Проверяем, что все стратегии доступны
    available_strategies = list(agent._strategy_registry.keys())
    print(f"Доступные стратегии: {available_strategies}")
    
    # Проверяем, что PlanningStrategy теперь использует новую архитектуру
    planning_strategy = agent._strategy_registry.get("planning")
    if planning_strategy:
        print(f"PlanningStrategy загружен: {planning_strategy.__class__.__name__}")
        # Проверяем, что у него есть нужные методы
        has_get_caps = hasattr(planning_strategy, '_get_available_capabilities')
        print(f"PlanningStrategy имеет _get_available_capabilities: {has_get_caps}")
    
    # Проверяем, что EvaluationStrategy обновлена
    evaluation_strategy = agent._strategy_registry.get("evaluation")
    if evaluation_strategy:
        print(f"EvaluationStrategy загружен: {evaluation_strategy.__class__.__name__}")
    
    # Проверяем, что FallbackStrategy обновлена
    fallback_strategy = agent._strategy_registry.get("fallback")
    if fallback_strategy:
        print(f"FallbackStrategy загружен: {fallback_strategy.__class__.__name__}")
    
    # Проверяем, что у агента есть обновленное состояние
    print(f"AgentState имеет новые метрики: {hasattr(agent.state, 'strategy_switches')}")
    print(f"AgentState имеет consecutive_errors: {hasattr(agent.state, 'consecutive_errors')}")
    print(f"AgentState имеет strategy_effectiveness: {hasattr(agent.state, 'strategy_effectiveness')}")
    
    await system_context.shutdown()
    print("=== Тест завершен ===")


if __name__ == "__main__":
    asyncio.run(test_new_strategy_architecture())