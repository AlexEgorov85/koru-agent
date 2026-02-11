#!/usr/bin/env python3
"""
Тестовый скрипт для запуска агента с реальным контекстом и реальным вопросом
"""
import asyncio
import sys
import os

# Добавляем корневую директорию в путь Python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import get_config
from core.system_context.system_context import SystemContext

async def main():
    print("Запускаем тест агента с реальным контекстом и реальным вопросом")
    
    # 1. Загрузка конфигурации
    config = get_config(profile='dev')
    print("1. Загрузка конфигурации - OK")
    
    # 2. Создание системного контекста
    system_context = SystemContext(config)
    print("2. Создание системного контекста - OK")
    
    # 3. Инициализация системного контекста
    success = await system_context.initialize()
    print(f"3. Инициализация системного контекста - {'OK' if success else 'FAILED'}")
    
    if not success:
        print("Ошибка инициализации системного контекста")
        return
    
    # Создаем агента
    print("Создаем агента...")
    agent = await system_context.create_agent()
    
    # Запускаем агента с реальным вопросом
    print("Запускаем агента с реальным вопросом: 'Какие книги написал Александр Пушкин?'")
    goal = "Какие книги написал Александр Пушкин?"
    
    try:
        result = await agent.run(goal=goal)
        print("Результат выполнения:")
        print(result)
    except Exception as e:
        print(f"Ошибка при выполнении задачи: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())