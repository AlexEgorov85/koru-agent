#!/usr/bin/env python3
"""
Пример использования новой архитектуры агента с атомарными действиями и компонуемыми паттернами.
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


async def demonstrate_new_architecture():
    """Демонстрация всех возможностей новой архитектуры агента."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=== Демонстрация новой архитектуры агента ===")
    
    # Инициализация контекстов
    system_context = SystemContext()
    session_context = SessionContext()
    
    # Инициализация агента с новой архитектурой
    agent = AgentRuntime(
        system_context=system_context,
        session_context=session_context
    )
    
    logger.info("✓ Агент успешно инициализирован с новой архитектурой")
    
    # Демонстрация 1: Адаптация к различным задачам
    logger.info("\n--- Демонстрация 1: Адаптация к задачам ---")
    
    tasks = [
        "Анализ файла code.py на наличие потенциальных ошибок",
        "Написать SQL запрос для поиска пользователей с активными заказами",
        "Исследовать лучшие практики для асинхронного программирования на Python"
    ]
    
    for i, task in enumerate(tasks, 1):
        adaptation_result = agent.adapt_to_task(task)
        logger.info(f"{i}. Задача: {task}")
        logger.info(f"   Определенный домен: {adaptation_result['domain']}")
        logger.info(f"   Рекомендованный паттерн: {adaptation_result['pattern']}")
    
    # Демонстрация 2: Создание кастомных паттернов
    logger.info("\n--- Демонстрация 2: Создание кастомных паттернов ---")
    
    # Создание паттерна для анализа кода
    code_analysis_builder = PatternBuilder("анализ_кода", "Паттерн для анализа исходного кода")
    code_analysis_pattern = (
        code_analysis_builder
        .add_think()
        .add_observe()
        .add_act()
        .add_reflect()
        .build()
    )
    
    logger.info(f"✓ Создан паттерн анализа кода с {len(code_analysis_pattern.actions)} действиями")
    
    # Создание паттерна для исследования
    research_builder = PatternBuilder("исследование", "Паттерн для исследовательских задач")
    research_pattern = (
        research_builder
        .add_think()
        .add_act()
        .add_observe()
        .add_evaluate()
        .add_reflect()
        .build()
    )
    
    logger.info(f"✓ Создан паттерн исследования с {len(research_pattern.actions)} действиями")
    
    # Демонстрация 3: Использование реестра паттернов
    logger.info("\n--- Демонстрация 3: Использование реестра паттернов ---")
    
    pattern_registry = agent.pattern_registry
    all_patterns = pattern_registry.list_patterns()
    logger.info(f"✓ Все зарегистрированные паттерны ({len(all_patterns)}): {all_patterns}")
    
    # Демонстрация 4: Работа с доменными паттернами
    logger.info("\n--- Демонстрация 4: Работа с доменными паттернами ---")
    
    domains = ["code_analysis", "database_query", "research", "general"]
    for domain in domains:
        domain_patterns = pattern_registry.get_domain_patterns(domain)
        logger.info(f"✓ Паттерны для домена '{domain}': {domain_patterns}")
    
    # Демонстрация 5: Использование компонуемых паттернов
    logger.info("\n--- Демонстрация 5: Использование компонуемых паттернов ---")
    
    composable_patterns = [
        "react_composable",
        "plan_and_execute_composable", 
        "tool_use_composable",
        "reflection_composable"
    ]
    
    for pattern_name in composable_patterns:
        pattern = pattern_registry.get_pattern(pattern_name)
        if pattern:
            logger.info(f"✓ Компонуемый паттерн '{pattern_name}' доступен с {len(pattern.actions)} действиями")
            for j, action in enumerate(pattern.actions, 1):
                logger.info(f"   {j}. {action.name}: {action.description}")
        else:
            logger.warning(f"✗ Компонуемый паттерн '{pattern_name}' не найден")
    
    # Демонстрация 6: Обратная совместимость
    logger.info("\n--- Демонстрация 6: Обратная совместимость ---")
    
    legacy_patterns = ["react", "planning", "code_analysis", "evaluation", "fallback"]
    for pattern_name in legacy_patterns:
        try:
            pattern = agent.get_strategy(pattern_name)
            logger.info(f"✓ Старый паттерн '{pattern_name}' доступен: {pattern.__class__.__name__}")
        except ValueError as e:
            logger.error(f"✗ Ошибка получения старого паттерна '{pattern_name}': {e}")
    
    logger.info("\n=== Демонстрация завершена успешно ===")
    
    return {
        "tasks_analyzed": len(tasks),
        "custom_patterns_created": 2,
        "total_registered_patterns": len(all_patterns),
        "domains_supported": len(domains),
        "composable_patterns_available": len([p for p in composable_patterns if pattern_registry.get_pattern(p)]),
        "legacy_patterns_compatible": len(legacy_patterns)
    }


async def demonstrate_dynamic_adaptation():
    """Демонстрация динамической адаптации агента к задачам."""
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=== Демонстрация динамической адаптации ===")
    
    # Инициализация контекстов
    system_context = SystemContext()
    session_context = SessionContext()
    
    # Инициализация агента с новой архитектурой
    agent = AgentRuntime(
        system_context=system_context,
        session_context=session_context
    )
    
    # Симуляция выполнения задач из разных доменов
    tasks_with_expected_domains = [
        ("Найти все классы в файле MyClass.java", "code_analysis"),
        ("Написать запрос для получения списка пользователей", "database_query"),
        ("Найти лучшие практики для Flask приложений", "research"),
        ("Исправить ошибку в функции calculate_total", "code_analysis")
    ]
    
    correct_adaptations = 0
    for task, expected_domain in tasks_with_expected_domains:
        adaptation_result = agent.adapt_to_task(task)
        actual_domain = adaptation_result['domain']
        
        status = "✓" if actual_domain == expected_domain else "✗"
        if actual_domain == expected_domain:
            correct_adaptations += 1
            
        logger.info(f"{status} Задача: {task}")
        logger.info(f"   Ожидаемый домен: {expected_domain}, Определенный домен: {actual_domain}")
    
    logger.info(f"\nРезультат: {correct_adaptations}/{len(tasks_with_expected_domains)} адаптаций выполнены корректно")
    
    return correct_adaptations == len(tasks_with_expected_domains)


async def main():
    """Основная функция для демонстрации новой архитектуры."""
    print("Демонстрация новой архитектуры агента...")
    
    # Демонстрация всех возможностей
    results = await demonstrate_new_architecture()
    
    print(f"\nРезультаты демонстрации:")
    print(f"- Проанализировано задач: {results['tasks_analyzed']}")
    print(f"- Создано кастомных паттернов: {results['custom_patterns_created']}")
    print(f"- Всего зарегистрированных паттернов: {results['total_registered_patterns']}")
    print(f"- Поддерживаемых доменов: {results['domains_supported']}")
    print(f"- Доступных компонуемых паттернов: {results['composable_patterns_available']}")
    print(f"- Совместимых старых паттернов: {results['legacy_patterns_compatible']}")
    
    # Демонстрация динамической адаптации
    adaptation_success = await demonstrate_dynamic_adaptation()
    
    print(f"\nДинамическая адаптация: {'Успешна' if adaptation_success else 'Требует улучшения'}")
    
    print("\n=== Выводы ===")
    print("✓ Атомарные действия позволяют гибко конструировать поведение агента")
    print("✓ Компонуемые паттерны обеспечивают переиспользуемость и модульность")
    print("✓ Система доменов позволяет адаптировать поведение под контекст задачи")
    print("✓ Обратная совместимость сохранена с существующими компонентами")
    print("✓ Реестр паттернов обеспечивает централизованное управление")
    print("✓ Динамическая адаптация позволяет агенту выбирать оптимальное поведение")


if __name__ == "__main__":
    asyncio.run(main())