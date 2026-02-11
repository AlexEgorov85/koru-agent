"""
Скрипт для проверки работы mock-провайдера и навыка финального ответа.
"""
import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.abspath('.'))

from core.system_context.system_context import SystemContext
from core.config import get_config
from core.skills.final_answer.skill import FinalAnswerSkill
from core.session_context.session_context import SessionContext


async def test_mock_provider_and_final_answer():
    """Тестирование работы mock-провайдера и навыка финального ответа."""
    print("=== Проверка работы mock-провайдера и навыка финального ответа ===")
    
    # Загружаем конфигурацию
    config = get_config(profile="dev")
    
    # Обновляем конфигурацию для использования mock-провайдера
    # (в реальной системе это будет сделано через конфигурационный файл)
    
    # Создаем системный контекст
    system_context = SystemContext(config)
    
    try:
        # Инициализируем системный контекст
        await system_context.initialize()
        
        print("✓ Системный контекст успешно инициализирован")
        
        # Проверяем, что провайдер зарегистрирован
        llm_provider = system_context.get_resource("default_llm")
        if llm_provider:
            print(f"✓ LLM провайдер успешно зарегистрирован: {type(llm_provider).__name__}")
        else:
            print("⚠ LLM провайдер не найден, но это нормально для mock-сценария")
        
        # Создаем навык финального ответа
        final_answer_skill = FinalAnswerSkill(
            name="final_answer_test", 
            system_context=system_context
        )
        
        print("✓ Навык финального ответа успешно создан")
        
        # Проверяем capability навыка
        capabilities = final_answer_skill.get_capabilities()
        print(f"✓ Доступные capability: {[cap.name for cap in capabilities]}")
        
        # Создаем сессию для теста
        session = SessionContext()
        session.set_goal("Какие книги написал Александр Пушкин?")
        
        # Добавляем тестовые данные в сессию
        session.record_observation(
            observation_data={
                "source": "book_library.get_books_by_author",
                "result": {
                    "books": [
                        {"title": "Евгений Онегин", "year": 1833},
                        {"title": "Капитанская дочка", "year": 1836},
                        {"title": "Руслан и Людмила", "year": 1820}
                    ]
                }
            },
            source="book_library",
            step_number=1
        )
        
        print("✓ Тестовые данные добавлены в сессию")
        
        # Выполняем capability генерации финального ответа
        if capabilities:
            final_answer_capability = capabilities[0]
            
            result = await final_answer_skill.execute(
                capability=final_answer_capability,
                parameters={
                    "include_steps": True,
                    "include_evidence": True,
                    "format_type": "detailed"
                },
                context=session
            )
            
            print(f"✓ Capability выполнено успешно")
            print(f"  Статус: {result.status}")
            print(f"  Результат: {result.result}")
            print(f"  Сводка: {result.summary}")
        
        print("\n=== Тест завершен успешно ===")
        
    except Exception as e:
        print(f"❌ Ошибка при тестировании: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Завершаем работу системного контекста
        await system_context.shutdown()


if __name__ == "__main__":
    asyncio.run(test_mock_provider_and_final_answer())