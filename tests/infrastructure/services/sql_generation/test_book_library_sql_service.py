import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.abspath('.'))

from core.system_context.system_context import SystemContext
from core.config.models import SystemConfig
from core.skills.book_library.schema import DynamicSQLInput
from core.session_context.session_context import SessionContext


async def test_book_library_with_sql_service():
    """Тестирование BookLibrarySkill с новым SQLGenerationService"""
    print("=== Тестирование BookLibrarySkill с SQLGenerationService ===")
    
    # Создаем конфигурацию
    config = SystemConfig()
    
    # Создаем и инициализируем системный контекст
    system_context = SystemContext(config)
    success = await system_context.initialize()
    
    if not success:
        print("Ошибка инициализации системного контекста")
        return
    
    # Создаем BookLibrarySkill
    from core.skills.book_library.skill import BookLibrarySkill
    skill = BookLibrarySkill("book_library_test", system_context)
    
    print(f"BookLibrarySkill создан: {type(skill).__name__}")
    
    # Проверяем, что SQLGenerationService доступен
    sql_service = system_context.get_resource("sql_generation_service")
    if sql_service:
        print("+ SQLGenerationService доступен для BookLibrarySkill")
    else:
        print("- SQLGenerationService НЕ доступен для BookLibrarySkill")
        await system_context.shutdown()
        return
    
    # Создаем тестовые параметры для dynamic_sql_query
    dynamic_input = DynamicSQLInput(
        user_question="Покажи все книги автора Толстой",
        context_tables=["Lib.books", "Lib.authors"],
        max_rows=5,
        include_reasoning=True
    )
    
    print(f"Входные данные созданы: {dynamic_input.user_question}")
    
    # Создаем сессионный контекст
    session_context = SessionContext()
    
    # Попробуем вызвать _dynamic_sql_query метод
    # Обратите внимание, что мы не будем выполнять реальный SQL запрос,
    # так как у нас нет подключения к базе данных в тестовой среде
    try:
        print("Попытка вызвать _dynamic_sql_query...")
        result = await skill._dynamic_sql_query(dynamic_input, session_context, 1)
        print(f"Результат выполнения: {result.status}")
        print(f"Сводка: {result.summary}")
        if result.error:
            print(f"Ошибка: {result.error}")
        # Результат может быть неуспешным из-за отсутствия реальной базы данных,
        # но главное, что метод был вызван без ошибок
        print("+ Метод _dynamic_sql_query вызван успешно (без исключений)")
    except Exception as e:
        print(f"~ Ошибка при вызове _dynamic_sql_query: {e}")
        import traceback
        traceback.print_exc()

    # Проверим другие методы навыка
    try:
        capabilities = skill.get_capabilities()
        print(f"Навык поддерживает {len(capabilities)} capability:")
        for cap in capabilities:
            print(f"  - {cap.name}")
        
        # Проверим, что capability dynamic_sql_query существует
        dynamic_cap = next((cap for cap in capabilities if cap.name == "book_library.dynamic_sql_query"), None)
        if dynamic_cap:
            print("+ capability 'book_library.dynamic_sql_query' найдена")
        else:
            print("- capability 'book_library.dynamic_sql_query' НЕ найдена")
    except Exception as e:
        print(f"Ошибка при получении capability: {e}")
    
    print("\n=== Тестирование BookLibrarySkill завершено ===")
    
    # Завершаем работу
    await system_context.shutdown()


if __name__ == "__main__":
    asyncio.run(test_book_library_with_sql_service())