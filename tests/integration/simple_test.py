"""
Простой тест для проверки работы системы с финальным ответом.
"""
import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.abspath('.'))

from main import Application
import argparse


async def simple_test():
    """Простой тест работы агента с финальным ответом."""
    print("=== Simple Test of Agent with Final Answer ===")
    
    # Создаем аргументы для теста
    args = argparse.Namespace()
    args.goal = "Какие книги написал Александр Пушкин?"
    args.profile = "dev"
    args.debug = True
    args.max_steps = 5
    args.temperature = 0.3
    args.max_tokens = 512
    args.strategy = "react"  # Используем простую стратегию для теста
    args.output = None
    
    try:
        # Создаем и запускаем приложение
        app = Application(args)
        await app.initialize()
        
        print("Application initialized successfully")
        
        # Запускаем агента
        result = await app.run()
        
        print("Agent execution completed")
        print(f"Success: {result.get('success', False)}")
        print(f"Goal: {result.get('goal', 'Not specified')}")
        print(f"Result: {result.get('result', 'No result')}")
        print(f"Final Answer: {result.get('final_answer', 'No final answer generated')}")
        
        await app.shutdown()
        print("Application shut down successfully")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(simple_test())