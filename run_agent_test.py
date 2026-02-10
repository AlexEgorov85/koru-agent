import asyncio
from main import Application
import argparse

async def run_simple_agent_test():
    """Простой тест запуска агента с новой архитектурой стратегий"""
    
    # Создаем аргументы для запуска агента
    args = argparse.Namespace()
    args.goal = "Какие книги написал Александр Пушкин?"  # Простой вопрос для тестирования
    args.profile = "dev"  # Профиль конфигурации
    args.debug = True  # Включаем режим отладки для лучшей видимости
    args.max_steps = 10  # Максимальное количество шагов
    args.temperature = 0.3  # Температура генерации
    args.max_tokens = 1000  # Максимальное количество токенов
    args.strategy = None  # Используем автоматический выбор стратегии
    args.output = None  # Не сохраняем результат в файл
    
    # Создаем и запускаем приложение
    app = Application(args)
    
    try:
        # Инициализация приложения
        await app.initialize()
        
        # Запуск агента
        result = await app.run()
        
        # Вывод результата
        print("\n" + "="*80)
        print("РЕЗУЛЬТАТ ВЫПОЛНЕНИЯ АГЕНТА")
        print("="*80)
        print(f"Цель: {result.get('goal', 'Не указана')}")
        
        if result.get("success", False):
            # Проверяем наличие финального ответа
            final_answer = result.get('final_answer')
            if final_answer:
                if isinstance(final_answer, dict) and 'final_answer' in final_answer:
                    print(f"ФИНАЛЬНЫЙ ОТВЕТ: {final_answer['final_answer']}")
                else:
                    print(f"ОТВЕТ: {result.get('result', 'Нет результата')}")
            else:
                print(f"ОТВЕТ: {result.get('result', 'Нет результата')}")
            
            print(f"ID сессии: {result.get('session_id', 'unknown')}")
            print(f"Время выполнения: {result.get('execution_time', 0):.2f} секунд")
            if "steps_taken" in result:
                print(f"Шагов выполнено: {result['steps_taken']}")
        else:
            print(f"ОШИБКА: {result.get('error', 'Неизвестная ошибка')}")
            print(f"ТИП ОШИБКИ: {result.get('error_type', 'Неизвестный тип')}")
        
        print("="*80)
        
    except Exception as e:
        print(f"Ошибка при запуске агента: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Корректное завершение работы
        await app.shutdown()

# Запуск теста
if __name__ == "__main__":
    asyncio.run(run_simple_agent_test())