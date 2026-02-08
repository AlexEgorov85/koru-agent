"""
Пример использования паттернов мышления.

Этот пример демонстрирует:
- Создание и использование различных паттернов мышления
- Адаптацию паттернов к задачам
- Выполнение шагов через паттерны
"""
import asyncio
import sys
import os

# Добавляем корневую директорию проекта в путь Python для импорта модулей
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from domain.models.agent.agent_state import AgentState
from application.thinking_patterns.composable.composable_pattern import (
    ReActPattern,
    PlanAndExecutePattern,
    ToolUsePattern,
    ReflectionPattern
)


async def demonstrate_thinking_patterns():
    """Демонстрация работы паттернов мышления."""
    print("=== Демонстрация паттернов мышления ===\n")
    
    # Создаем различные паттерны
    react_pattern = ReActPattern()
    plan_execute_pattern = PlanAndExecutePattern()
    tool_use_pattern = ToolUsePattern()
    reflection_pattern = ReflectionPattern()
    
    print(f"✓ Паттерны созданы:")
    print(f"  - {react_pattern.name}: {type(react_pattern).__name__}")
    print(f"  - {plan_execute_pattern.name}: {type(plan_execute_pattern).__name__}")
    print(f"  - {tool_use_pattern.name}: {type(tool_use_pattern).__name__}")
    print(f"  - {reflection_pattern.name}: {type(reflection_pattern).__name__}")
    
    # Демонстрация адаптации паттернов к задачам
    print(f"\n--- Адаптация паттернов к задачам ---")
    
    tasks = [
        "Напиши программу на Python для сортировки массива",
        "Спланируй выполнение проекта по разработке веб-приложения",
        "Используй инструмент для чтения файла README.md",
        "Проанализируй эффективность предыдущего решения"
    ]
    
    patterns = [react_pattern, plan_execute_pattern, tool_use_pattern, reflection_pattern]
    
    for i, (task, pattern) in enumerate(zip(tasks, patterns)):
        print(f"\nЗадача {i+1}: {task}")
        adaptation_result = await pattern.adapt_to_task(task)
        print(f"  Домен: {adaptation_result.get('domain', 'unknown')}")
        print(f"  Уверенность: {adaptation_result.get('confidence', 0.0)}")
        print(f"  Параметры: {adaptation_result.get('parameters', {})}")
    
    # Демонстрация выполнения через ReAct паттерн
    print(f"\n--- Выполнение через ReAct паттерн ---")
    
    # Создаем состояние агента
    agent_state = AgentState()
    
    # Подготовим контекст для выполнения
    context = {
        "goal": "Тестовая задача для ReAct паттерна",
        "available_tools": ["calculator", "file_reader", "web_search"]
    }
    
    # Выполняем шаг через ReAct паттерн (без LLM ответа, чтобы получить требование рассуждения)
    result = await react_pattern.execute(
        state=agent_state,
        context=context,
        available_capabilities=["calculator", "file_reader", "web_search"],
        llm_response=None  # Это вызовет требование рассуждения
    )
    
    print(f"Результат выполнения ReAct паттерна: {result}")
    
    # Демонстрация выполнения через PlanAndExecute паттерн
    print(f"\n--- Выполнение через PlanAndExecute паттерн ---")
    
    # Подготовим контекст для выполнения
    context = {
        "goal": "Спланируй и выполните задачу по созданию отчета",
        "available_tools": ["report_generator", "data_analyzer"]
    }
    
    # Выполняем шаг через PlanAndExecute паттерн
    result = await plan_execute_pattern.execute(
        state=agent_state,
        context=context,
        available_capabilities=["report_generator", "data_analyzer"],
        llm_response=None  # Это вызовет требование планирования
    )
    
    print(f"Результат выполнения PlanAndExecute паттерна: {result}")
    
    # Демонстрация выполнения через ToolUse паттерн
    print(f"\n--- Выполнение через ToolUse паттерн ---")
    
    # Подготовим контекст для выполнения
    context = {
        "goal": "Выбери и используй подходящий инструмент",
        "available_tools": ["file_reader", "web_scraper", "calculator"]
    }
    
    # Выполняем шаг через ToolUse паттерн
    result = await tool_use_pattern.execute(
        state=agent_state,
        context=context,
        available_capabilities=["file_reader", "web_scraper", "calculator"],
        llm_response=None  # Это вызовет требование выбора инструмента
    )
    
    print(f"Результат выполнения ToolUse паттерна: {result}")
    
    # Демонстрация выполнения через Reflection паттерн
    print(f"\n--- Выполнение через Reflection паттерн ---")
    
    # Подготовим контекст для выполнения
    context = {
        "goal": "Проанализируй и оцени предыдущие действия",
        "previous_results": ["result1", "result2", "result3"]
    }
    
    # Выполняем шаг через Reflection паттерн
    result = await reflection_pattern.execute(
        state=agent_state,
        context=context,
        available_capabilities=[],
        llm_response=None  # Это вызовет требование анализа
    )
    
    print(f"Результат выполнения Reflection паттерна: {result}")
    
    # Демонстрация свойств паттернов
    print(f"\n--- Свойства паттернов ---")
    for pattern in [react_pattern, plan_execute_pattern, tool_use_pattern, reflection_pattern]:
        print(f"  {pattern.name}: max_iterations={getattr(pattern, 'max_iterations', 'N/A')}")
    
    print("\n=== Демонстрация паттернов мышления завершена ===")


if __name__ == "__main__":
    asyncio.run(demonstrate_thinking_patterns())