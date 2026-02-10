"""
Тестирование агента с mock-провайдером для изоляции от проблем с LLM.
"""
import asyncio
import sys
import os
import logging

# Добавляем путь к проекту
sys.path.insert(0, os.path.abspath('.'))

from main import Application
import argparse


async def test_mock_agent():
    """Тестирование агента с mock-провайдером."""
    print("=== Тестирование агента с mock-провайдером ===")
    
    # Создаем аргументы для теста
    args = argparse.Namespace()
    args.goal = "Какие книги написал Александр Пушкин?"
    args.profile = "test"  # Используем тестовый профиль
    args.debug = True
    args.max_steps = 5  # Ограничиваем количество шагов для теста
    args.temperature = 0.3
    args.max_tokens = 512
    args.strategy = "react"  # Используем реактивную стратегию
    args.output = None
    
    # Создаем приложение
    app = Application(args)
    
    try:
        # Инициализируем приложение
        await app.initialize()
        
        print("Приложение успешно инициализировано")
        
        # Запускаем агента
        result = await app.run()
        
        print("\nРЕЗУЛЬТАТ ВЫПОЛНЕНИЯ АГЕНТА")
        print("="*50)
        print(f"Цель: {result.get('goal', 'Не указана')}")
        print(f"Успешно: {result.get('success', False)}")
        if result.get('success', False):
            print(f"Результат: {result.get('result', 'Нет результата')}")
            print(f"Финальный ответ: {result.get('final_answer', 'Не сгенерирован')}")
        else:
            print(f"Ошибка: {result.get('error', 'Неизвестная ошибка')}")
        
        print(f"ID сессии: {result.get('session_id', 'unknown')}")
        print(f"Время выполнения: {result.get('execution_time', 0):.2f} секунд")
        if "steps_taken" in result:
            print(f"Шагов выполнено: {result['steps_taken']}")
        
    except Exception as e:
        print(f"Ошибка при выполнении теста: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Завершаем работу приложения
        await app.shutdown()
    
    print("\n=== Тест завершен ===")


if __name__ == "__main__":
    # Настройка логирования
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    asyncio.run(test_mock_agent())