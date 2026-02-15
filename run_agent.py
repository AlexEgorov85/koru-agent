#!/usr/bin/env python3
"""
Запуск агента с вопросом на основе запущенного контекста
"""
import asyncio
from core.config import get_config
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.infrastructure.context.agent_factory import AgentFactory
from core.config.agent_config import AgentConfig

async def run_agent_with_question():
    # Загрузка конфигурации
    config = get_config(profile='dev')

    # Создание и инициализация инфраструктурного контекста
    infrastructure_context = InfrastructureContext(config)
    await infrastructure_context.initialize()

    # Создание прикладного контекста для агента (изолированный)
    application_context = await ApplicationContext.create_from_registry(
        infrastructure_context=infrastructure_context,
        profile="prod"
    )

    # Создание фабрики агентов
    agent_factory = AgentFactory(infrastructure_context)

    # Создание агента с минимальной конфигурацией
    agent_config = AgentConfig(
        max_steps=5,
        default_strategy="react"
    )

    # Создание агента
    agent = await agent_factory.create_agent(agent_config=agent_config)

    # Запуск агента с вопросом
    question = "Какие книги написал Александр Пушкин?"
    result = await agent.run(goal=question)

    return result

def main():
    """
    Основная функция для запуска агента
    """
    print("Запуск агента для проверки работоспособности...")

    # Выполнение асинхронной функции
    result = asyncio.run(run_agent_with_question())

    if result is not None:
        print("\nРезультат выполнения:")
        print(result)
        print("\nТест завершён успешно.")
    else:
        print("\nТест завершён с ошибкой.")

if __name__ == "__main__":
    main()