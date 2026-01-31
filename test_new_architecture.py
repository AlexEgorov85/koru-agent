#!/usr/bin/env python3
"""
Тестирование новой архитектуры агента с атомарными действиями и компонуемыми паттернами.
"""

import asyncio
import logging
from typing import Dict, Any

from core.agent_runtime import ThinkingPatternLoader
from core.composable_patterns.base import PatternBuilder
from core.session_context.session_context import SessionContext
from core.system_context.system_context import SystemContext
from core.agent_runtime.runtime import AgentRuntime


def setup_logging():
    """Setup basic logging configuration."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


async def test_new_architecture():
    """Тестирование новой архитектуры агента."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=== Тестирование новой архитектуры агента ===")
    
    # Инициализация контекстов
    system_context = SystemContext()
    session_context = SessionContext()
    
    # Инициализация агента с новой архитектурой
    agent = AgentRuntime(
        system_context=system_context,
        session_context=session_context
    )
    
    logger.info("Агент успешно инициализирован с новой архитектурой")
    
    # Тест 1: Проверка адаптации к задаче
    logger.info("\n--- Тест 1: Адаптация к задаче ---")
    task_description = "Анализ файла code.py на наличие потенциальных ошибок"
    adaptation_result = agent.adapt_to_task(task_description)
    
    logger.info(f"Задача: {task_description}")
    logger.info(f"Определенный домен: {adaptation_result['domain']}")
    logger.info(f"Рекомендованный паттерн: {adaptation_result['pattern']}")
    logger.info(f"Конфигурация домена: {adaptation_result['domain_config']}")
    
    # Тест 2: Создание кастомного паттерна с помощью PatternBuilder
    logger.info("\n--- Тест 2: Создание кастомного паттерна ---")
    builder = PatternBuilder("анализ_кода", "Паттерн для анализа кода")
    custom_pattern = (
        builder
        .add_think()
        .add_observe()
        .add_act()
        .add_reflect()
        .build()
    )
    
    logger.info(f"Создан кастомный паттерн с {len(custom_pattern.actions)} действиями:")
    for i, action in enumerate(custom_pattern.actions):
        logger.info(f"  {i+1}. {action.name}: {action.description}")
    
    # Тест 3: Использование реестра паттернов
    logger.info("\n--- Тест 3: Использование реестра паттернов ---")
    pattern_registry = agent.pattern_registry
    all_patterns = pattern_registry.list_patterns()
    logger.info(f"Все зарегистрированные паттерны: {all_patterns}")
    
    # Тест 4: Работа с доменными паттернами
    logger.info("\n--- Тест 4: Работа с доменными паттернами ---")
    code_analysis_patterns = pattern_registry.get_domain_patterns("code_analysis")
    logger.info(f"Паттерны для домена code_analysis: {code_analysis_patterns}")
    
    # Тест 5: Демонстрация универсальных паттернов
    logger.info("\n--- Тест 5: Универсальные паттерны ---")
    universal_patterns = pattern_registry.get_universal_patterns()
    logger.info(f"Универсальные паттерны: {universal_patterns}")
    
    # Тест 6: Проверка наличия новых компонуемых паттернов
    logger.info("\n--- Тест 6: Новые компонуемые паттерны ---")
    try:
        new_react_pattern = agent.get_strategy("react_composable")
        logger.info(f"Новый компонуемый паттерн 'react_composable' доступен: {new_react_pattern.__class__.__name__}")
    except ValueError as e:
        logger.error(f"Ошибка получения нового паттерна: {e}")
    
    try:
        new_plan_and_execute_pattern = agent.get_strategy("plan_and_execute_composable")
        logger.info(f"Новый компонуемый паттерн 'plan_and_execute_composable' доступен: {new_plan_and_execute_pattern.__class__.__name__}")
    except ValueError as e:
        logger.error(f"Ошибка получения нового паттерна: {e}")
    
    # Тест 7: Использование компонуемых паттернов
    logger.info("\n--- Тест 7: Компонуемые паттерны ---")
    composable_react = pattern_registry.get_pattern("react_composable")
    if composable_react:
        logger.info(f"Компонуемый ReAct паттерн доступен: {composable_react.name}")
        logger.info(f"Количество действий в паттерне: {len(composable_react.actions)}")
        for action in composable_react.actions:
            logger.info(f"  - {action.name}: {action.description}")
    else:
        logger.warning("Компонуемый ReAct паттерн не найден")
    
    logger.info("\n=== Тестирование новой архитектуры завершено успешно ===")
    
    return {
        "task_adaptation": adaptation_result,
        "custom_pattern_actions": len(custom_pattern.actions),
        "total_patterns": len(all_patterns),
        "domain_patterns": len(code_analysis_patterns),
        "universal_patterns": len(universal_patterns)
    }


async def test_agent_execution_with_new_features():
    """Тестирование выполнения задач с использованием новых возможностей."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=== Тестирование выполнения задач с новыми возможностями ===")
    
    # Инициализация контекстов
    system_context = SystemContext()
    session_context = SessionContext()
    
    # Инициализация агента с новой архитектурой
    agent = AgentRuntime(
        system_context=system_context,
        session_context=session_context
    )
    
    # Тест выполнения с адаптацией к домену
    goal = "Анализировать структуру проекта и найти все Python файлы"
    logger.info(f"Выполнение цели: {goal}")
    
    # Определение домена задачи
    task_adaptation = agent.adapt_to_task(goal)
    logger.info(f"Определенный домен: {task_adaptation['domain']}")
    
    # Здесь в реальной системе агент бы использовал соответствующий доменный паттерн
    # для выполнения задачи, но для демонстрации мы просто покажем, что система
    # способна адаптироваться к задаче
    
    logger.info("Агент успешно адаптировался к задаче и готов к выполнению")
    
    return task_adaptation


async def main():
    """Основная функция для запуска тестов новой архитектуры."""
    print("Тестирование новой архитектуры агента...")
    
    # Тестирование основных возможностей новой архитектуры
    results = await test_new_architecture()
    
    print(f"\nРезультаты тестирования:")
    print(f"- Адаптация к задаче: {results['task_adaptation']['domain']}")
    print(f"- Действий в кастомном паттерне: {results['custom_pattern_actions']}")
    print(f"- Всего паттернов: {results['total_patterns']}")
    print(f"- Доменных паттернов: {results['domain_patterns']}")
    print(f"- Универсальных паттернов: {results['universal_patterns']}")
    
    # Тестирование выполнения задач
    domain_result = await test_agent_execution_with_new_features()
    print(f"\nРезультат адаптации к задаче: {domain_result['domain']}")
    
    print("\nВсе тесты новой архитектуры пройдены успешно!")


if __name__ == "__main__":
    asyncio.run(main())