import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.abspath('.'))

from core.system_context.system_context import SystemContext
from core.config.models import SystemConfig
from core.infrastructure.service.sql_generation.schema import SQLGenerationInput


async def test_sql_generation_integration():
    """Интеграционное тестирование SQLGenerationService"""
    print("=== Интеграционное тестирование SQLGenerationService ===")
    
    # Создаем конфигурацию
    config = SystemConfig()
    
    # Создаем и инициализируем системный контекст
    system_context = SystemContext(config)
    success = await system_context.initialize()
    
    if not success:
        print("Ошибка инициализации системного контекста")
        return
    
    # Проверяем, что все сервисы успешно зарегистрированы
    sql_service = system_context.get_resource("sql_generation_service")
    if not sql_service:
        print("SQLGenerationService не найден в реестре ресурсов")
        return
    
    print(f"+ SQLGenerationService успешно зарегистрирован: {type(sql_service).__name__}")
    
    # Проверим, что все внутренние компоненты созданы
    if sql_service.validator:
        print(f"+ Validator создан: {type(sql_service.validator).__name__}")
    else:
        print("- Validator не создан")
        
    if sql_service.error_analyzer:
        print(f"+ Error Analyzer создан: {type(sql_service.error_analyzer).__name__}")
    else:
        print("- Error Analyzer не создан")
        
    if sql_service.correction_engine:
        print(f"+ Correction Engine создан: {type(sql_service.correction_engine).__name__}")
    else:
        print("- Correction Engine не создан")
    
    # Проверим, что BookLibrarySkill может получить сервис
    from core.skills.book_library.skill import BookLibrarySkill
    from core.session_context.session_context import SessionContext
    
    skill = BookLibrarySkill("book_library_test", system_context)
    print(f"+ BookLibrarySkill успешно создан: {type(skill).__name__}")
    
    # Проверим, что навык может получить все свои capability
    capabilities = skill.get_capabilities()
    print(f"+ BookLibrarySkill имеет {len(capabilities)} capability:")
    for cap in capabilities:
        print(f"  - {cap.name}: {cap.description}")
    
    # Проверим, что dynamic_sql_query capability присутствует
    dynamic_cap = next((cap for cap in capabilities if cap.name == "book_library.dynamic_sql_query"), None)
    if dynamic_cap:
        print(f"+ Найдена capability dynamic_sql_query")
    else:
        print("- capability dynamic_sql_query не найдена")
    
    # Проверим, что все зависимости системного контекста доступны
    prompt_service = system_context.get_resource("prompt_service")
    if prompt_service:
        print(f"+ PromptService доступен: {type(prompt_service).__name__}")
    else:
        print("- PromptService недоступен")
    
    table_service = system_context.get_resource("table_description_service")
    if table_service:
        print(f"+ TableDescriptionService доступен: {type(table_service).__name__}")
    else:
        print("~ TableDescriptionService недоступен (может быть нормально в тестовой среде)")
    
    # Проверим, что SQLGenerationService может получить доступ к своим зависимостям
    try:
        table_service_via_get = await system_context.get_service("table_description_service")
        if table_service_via_get:
            print(f"+ TableDescriptionService доступен через get_service(): {type(table_service_via_get).__name__}")
        else:
            print("~ TableDescriptionService недоступен через get_service() (может быть нормально в тестовой среде)")
    except Exception as e:
        print(f"~ Ошибка при получении TableDescriptionService через get_service(): {e}")
    
    # Проверим, что сервис может создать правильные входные данные
    test_input = SQLGenerationInput(
        user_question="Покажи все книги автора Толстой",
        tables=["Lib.books", "Lib.authors"],
        max_rows=10
    )
    print(f"+ Входные данные для генерации SQL успешно созданы: {test_input.user_question}")
    
    # Проверим, что все компоненты могут быть корректно инициализированы
    try:
        validator_initialized = await sql_service.validator.initialize()
        if validator_initialized:
            print("+ SQLQueryValidator успешно инициализирован")
        else:
            print("~ SQLQueryValidator не смог инициализироваться")
    except Exception as e:
        print(f"~ Ошибка инициализации SQLQueryValidator: {e}")
    
    try:
        error_analyzer_initialized = await sql_service.error_analyzer.initialize()
        if error_analyzer_initialized:
            print("+ SQLErrorAnalyzer успешно инициализирован")
        else:
            print("~ SQLErrorAnalyzer не смог инициализироваться")
    except Exception as e:
        print(f"~ Ошибка инициализации SQLErrorAnalyzer: {e}")
    
    try:
        correction_engine_initialized = await sql_service.correction_engine.initialize()
        if correction_engine_initialized:
            print("+ SQLCorrectionEngine успешно инициализирован")
        else:
            print("~ SQLCorrectionEngine не смог инициализироваться")
    except Exception as e:
        print(f"~ Ошибка инициализации SQLCorrectionEngine: {e}")
    
    # Проверим, что основной сервис инициализирован
    try:
        service_initialized = await sql_service.initialize()
        if service_initialized:
            print("+ SQLGenerationService успешно переинициализирован")
        else:
            print("~ SQLGenerationService не смог переинициализироваться")
    except Exception as e:
        print(f"~ Ошибка переинициализации SQLGenerationService: {e}")
    
    print("\n=== Интеграционное тестирование завершено ===")
    
    # Завершаем работу
    await system_context.shutdown()


if __name__ == "__main__":
    asyncio.run(test_sql_generation_integration())