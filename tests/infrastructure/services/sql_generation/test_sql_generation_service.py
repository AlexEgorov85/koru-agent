import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.abspath('.'))

from core.system_context.system_context import SystemContext
from core.config.models import SystemConfig


async def test_sql_generation_service():
    """Тестирование SQLGenerationService"""
    print("=== Тестирование SQLGenerationService ===")
    
    # Создаем конфигурацию
    config = SystemConfig()
    
    # Создаем и инициализируем системный контекст
    system_context = SystemContext(config)
    success = await system_context.initialize()
    
    if not success:
        print("Ошибка инициализации системного контекста")
        return
    
    # Проверяем, что сервис зарегистрирован
    sql_service = system_context.get_resource("sql_generation_service")
    if not sql_service:
        print("SQLGenerationService не найден в реестре ресурсов")
        return
    
    print(f"SQLGenerationService успешно зарегистрирован: {type(sql_service).__name__}")
    
    # Проверяем, что сервис также доступен через get_service
    sql_service_via_get = await system_context.get_service("sql_generation_service")
    if sql_service_via_get:
        print("SQLGenerationService также доступен через get_service()")
    else:
        print("SQLGenerationService НЕ доступен через get_service()")
    
    # Проверим, что BookLibrarySkill может получить сервис
    from core.skills.book_library.skill import BookLibrarySkill
    
    skill = BookLibrarySkill("book_library_test", system_context)
    capabilities = skill.get_capabilities()
    
    print(f"BookLibrarySkill имеет {len(capabilities)} capability:")
    for cap in capabilities:
        print(f"  - {cap.name}: {cap.description}")
    
    # Протестируем динамический SQL запрос
    from core.skills.book_library.schema import DynamicSQLInput
    
    dynamic_input = DynamicSQLInput(
        user_question="Покажи все книги автора Толстой",
        context_tables=["Lib.books", "Lib.authors"],
        max_rows=10,
        include_reasoning=True
    )
    
    # Создаем фейковый контекст сессии для теста
    from core.session_context.session_context import SessionContext
    session_context = SessionContext()
    
    print("\n=== Тестирование динамического SQL запроса ===")
    try:
        # Вызываем метод напрямую для тестирования
        result = await skill._dynamic_sql_query(dynamic_input, session_context, 1)
        print(f"Результат выполнения: {result.status}")
        print(f"Сводка: {result.summary}")
        if result.error:
            print(f"Ошибка: {result.error}")
        if result.result:
            print(f"Результат: {result.result}")
    except Exception as e:
        print(f"Ошибка при выполнении динамического SQL запроса: {e}")
        import traceback
        traceback.print_exc()
    
    # Завершаем работу
    await system_context.shutdown()
    print("\n=== Тестирование завершено ===")


if __name__ == "__main__":
    asyncio.run(test_sql_generation_service())