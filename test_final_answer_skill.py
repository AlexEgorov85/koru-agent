"""
Тестирование навыка генерации финального ответа.
"""
import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.abspath('.'))

from core.skills.final_answer.skill import FinalAnswerSkill
from core.system_context.system_context import SystemContext
from core.config import get_config


async def test_final_answer_skill():
    """Тестирование навыка генерации финального ответа."""
    print("=== Тестирование навыка генерации финального ответа ===")
    
    # Загружаем конфигурацию
    config = get_config(profile="dev")
    
    # Создаем системный контекст
    system_context = SystemContext(config)
    await system_context.initialize()
    
    # Создаем навык
    skill = FinalAnswerSkill(name="final_answer_test", system_context=system_context)
    
    # Проверяем capability
    capabilities = skill.get_capabilities()
    print(f"Доступные capability: {[cap.name for cap in capabilities]}")
    
    # Выполняем capability генерации финального ответа
    if capabilities:
        final_answer_capability = capabilities[0]  # final_answer.generate
        print(f"Тестируем capability: {final_answer_capability.name}")
        
        # Создаем сессию для теста
        from core.session_context.session_context import SessionContext
        session = SessionContext()
        session.set_goal("Какие книги написал Александр Пушкин?")
        
        # Добавляем немного контекста для теста
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
        
        # Выполняем capability
        parameters = {
            "include_steps": True,
            "include_evidence": True,
            "format_type": "detailed"
        }
        
        result = await skill.execute(
            capability=final_answer_capability,
            parameters=parameters,
            context=session
        )
        
        print(f"Статус выполнения: {result.status}")
        print(f"Результат: {result.result}")
        print(f"Сводка: {result.summary}")
        
    await system_context.shutdown()
    print("=== Тест завершен ===")


if __name__ == "__main__":
    asyncio.run(test_final_answer_skill())