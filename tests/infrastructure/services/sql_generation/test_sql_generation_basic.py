import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.abspath('.'))

from core.system_context.system_context import SystemContext
from core.config.models import SystemConfig
from core.infrastructure.service.sql_generation.schema import SQLGenerationInput


async def test_sql_generation_service_basic():
    """Основное тестирование SQLGenerationService"""
    print("=== Основное тестирование SQLGenerationService ===")
    
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
    
    # Проверим, что сервис также доступен через get_service
    sql_service_via_get = await system_context.get_service("sql_generation_service")
    if sql_service_via_get:
        print("SQLGenerationService также доступен через get_service()")
    else:
        print("SQLGenerationService НЕ доступен через get_service()")
    
    # Проверим, что все внутренние сервисы инициализированы
    print(f"Validator: {sql_service.validator}")
    print(f"Error Analyzer: {sql_service.error_analyzer}")
    print(f"Correction Engine: {sql_service.correction_engine}")
    print(f"System Context: {sql_service.system_context}")
    print(f"Prompt Service: {sql_service.prompt_service}")
    
    # Создадим тестовые входные данные
    test_input = SQLGenerationInput(
        user_question="Покажи все книги автора Толстой",
        tables=["Lib.books", "Lib.authors"],
        max_rows=10
    )
    
    print(f"\nТестовые входные данные: {test_input}")
    
    # Попробуем вызвать генерацию (это может завершиться ошибкой из-за отсутствия реального LLM)
    try:
        print("\nПопытка вызвать генерацию SQL...")
        # Для тестирования вызовем один из внутренних методов
        table_metadata = await sql_service._get_table_metadata(test_input.tables)
        print(f"Метаданные таблиц получены: {len(table_metadata.get('tables', []))} таблиц")
        
        formatted_metadata = sql_service._format_table_metadata(table_metadata)
        print(f"Форматированные метаданные: {formatted_metadata[:200]}...")
        
    except Exception as e:
        print(f"Ошибка при тестировании внутренних методов: {e}")
        import traceback
        traceback.print_exc()
    
    # Завершаем работу
    await system_context.shutdown()
    print("\n=== Основное тестирование завершено ===")


if __name__ == "__main__":
    asyncio.run(test_sql_generation_service_basic())