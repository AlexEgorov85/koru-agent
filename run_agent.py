#!/usr/bin/env python3
"""
Запуск агента с вопросом на основе запущенного контекста
"""
import asyncio
from core.config import get_config
from core.system_context.system_context import SystemContext
from core.config.agent_config import AgentConfig

async def run_agent_with_question():
    # Загрузка конфигурации
    config = get_config(profile='dev')
    
    # Создание и инициализация системного контекста
    system_context = SystemContext(config)
    await system_context.initialize()
    
    # Регистрация провайдеров из конфигурации
    await system_context._register_providers_from_config()
    
    # Создание агента с минимальной конфигурацией
    agent_config = AgentConfig(
        max_steps=5,
        default_strategy="react"
    )
    
    # Создание агента
    agent = await system_context.create_agent(agent_config=agent_config)
    
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