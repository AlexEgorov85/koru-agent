"""
Тест для проверки интеграции FinalAnswerSkill с агентом.
"""
import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.abspath('.'))

from main import Application
import argparse


async def test_final_answer_integration():
    """Тестирование интеграции навыка финального ответа."""
    print("=== Тест интеграции FinalAnswerSkill ===")
    
    # Создаем аргументы для теста
    args = argparse.Namespace()
    args.goal = "Какие книги написал Александр Пушкин?"
    args.profile = "dev"
    args.debug = True
    args.max_steps = 3
    args.temperature = 0.3
    args.max_tokens = 512
    args.strategy = "react"  # Используем простую стратегию для теста
    args.output = None
    
    try:
        # Создаем приложение
        app = Application(args)
        
        # Инициализируем приложение
        await app.initialize()
        print("✓ Приложение успешно инициализировано")
        
        # Запускаем агента
        result = await app.run()
        print("✓ Агент успешно завершил выполнение")
        
        # Проверяем результаты
        print(f"Успешно: {result.get('success', False)}")
        print(f"Цель: {result.get('goal', 'Не указана')}")
        print(f"Финальный ответ: {result.get('final_answer', 'Не сгенерирован')}")
        
        # Завершаем работу приложения
        await app.shutdown()
        print("✓ Приложение успешно завершено")
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_final_answer_integration())