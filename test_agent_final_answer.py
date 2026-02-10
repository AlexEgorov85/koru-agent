"""Тест для проверки интеграции навыка генерации финального ответа с агентом."""
import asyncio
import sys
import os
import argparse

# Добавляем путь к проекту
sys.path.insert(0, os.path.abspath('.'))

from main import Application


async def test_agent_with_final_answer():
    """Тестирование агента с генерацией финального ответа."""
    print("=== Тестирование агента с генерацией финального ответа ===")
    
    # Создаем аргументы вручную
    args = argparse.Namespace()
    args.goal = "Какие книги написал Пушкин?"
    args.profile = "dev"
    args.debug = False
    args.max_steps = 3  # Ограничиваем количество шагов для теста
    args.temperature = None
    args.max_tokens = None
    args.strategy = None
    args.output = None
    
    # Создаем приложение
    app = Application(args)
    
    try:
        # Инициализируем приложение
        await app.initialize()
        
        # Запускаем агента
        result = await app.run()
        
        print(f"Успешно выполнено: {result.get('success', False)}")
        print(f"Цель: {result.get('goal', 'Не указана')}")
        print(f"Результат: {result.get('result', 'Нет результата')}")
        print(f"Финальный ответ: {result.get('final_answer', 'Не сгенерирован')}")
        
        # Проверяем, что финальный ответ присутствует
        if 'final_answer' in result and result['final_answer']:
            final_answer_data = result['final_answer']
            if isinstance(final_answer_data, dict) and 'final_answer' in final_answer_data:
                print(f"SUCCESS: Финальный ответ: {final_answer_data['final_answer']}")
            print("SUCCESS: Финальный ответ успешно сгенерирован и включен в результат")
        else:
            print("WARNING: Финальный ответ не найден в результате")
        
    except Exception as e:
        print(f"Ошибка при выполнении теста: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Завершаем работу приложения
        await app.shutdown()
    
    print("=== Тест завершен ===")


if __name__ == "__main__":
    asyncio.run(test_agent_with_final_answer())