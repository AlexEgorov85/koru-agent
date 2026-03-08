"""
Тестирование BookLibrarySkill без запуска агента.

ПРОВЕРЯЕМ:
1. Инициализацию навыка
2. Валидацию входных/выходных контрактов
3. Выполнение capability execute_script
4. Выполнение capability list_scripts
"""
import asyncio
import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from core.config import get_config
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.application.agent.components.action_executor import ActionExecutor, ExecutionContext
from core.models.data.capability import Capability


async def test_book_library_skill():
    """Тестирование BookLibrarySkill"""
    print("=" * 80)
    print("ТЕСТИРОВАНИЕ BookLibrarySkill")
    print("=" * 80)
    
    # 1. Инициализация инфраструктуры
    print("\n1. Инициализация InfrastructureContext...")
    config = get_config(profile='dev')
    infra = InfrastructureContext(config)
    await infra.initialize()
    print("[OK] InfrastructureContext инициализирован")
    
    # 2. Инициализация приложения
    print("\n2. Инициализация ApplicationContext...")
    app_config = ApplicationContext.Config(
        profile="prod",
        data_dir=str(getattr(config, 'data_dir', 'data'))
    )
    app_ctx = ApplicationContext(
        infrastructure_context=infra,
        config=app_config
    )
    await app_ctx.initialize()
    print("✅ ApplicationContext инициализирован")
    
    # 3. Получение компонента book_library
    print("\n3. Получение компонента book_library...")
    from core.models.enums.common_enums import ComponentType
    book_library = app_ctx.components.get(ComponentType.TOOL, "book_library")
    
    if not book_library:
        print("❌ Компонент book_library не найден!")
        return
    
    print(f"✅ Компонент book_library получен: {type(book_library).__name__}")
    print(f"   supported_capabilities: {list(book_library.supported_capabilities.keys())}")
    
    # 4. Проверка контрактов
    print("\n4. Проверка контрактов...")
    
    # Проверяем входные контракты
    input_contracts = book_library.input_contracts
    print(f"   Входные контракты: {list(input_contracts.keys())}")
    
    # Проверяем выходные контракты
    output_contracts = book_library.output_contracts
    print(f"   Выходные контракты: {list(output_contracts.keys())}")
    
    # Проверяем промпты
    prompts = book_library.prompts
    print(f"   Промпты: {list(prompts.keys())}")
    
    # 5. Тест execute_script
    print("\n5. Тест execute_script...")
    
    # Создаём executor
    executor = ActionExecutor(app_ctx)
    
    # Находим capability
    capability = None
    for cap in book_library.get_capabilities():
        if cap.name == "book_library.execute_script":
            capability = cap
            break
    
    if not capability:
        print("❌ Capability book_library.execute_script не найдена!")
        return
    
    print(f"✅ Capability найдена: {capability.name}")
    print(f"   description: {capability.description}")
    
    # Проверяем кэшированные контракты
    print("\n6. Проверка кэшированных контрактов...")
    input_schema = book_library.get_cached_input_contract_safe("book_library.execute_script")
    print(f"   Входная схема: {input_schema is not None}")
    
    output_schema = book_library.get_cached_output_contract_safe("book_library.execute_script")
    print(f"   Выходная схема: {output_schema is not None}")
    
    if output_schema:
        print(f"   Тип выходной схемы: {output_schema}")
    
    # 7. Тест выполнения
    print("\n7. Тест выполнения execute_script...")
    
    # Создаём ExecutionContext
    exec_context = ExecutionContext(
        session_context=app_ctx.session_context,
        user_context=None
    )
    
    # Выполняем capability
    try:
        result = await book_library.execute(
            capability=capability,
            parameters={"script_name": "get_books_by_author", "author": "Пушкин"},
            execution_context=exec_context
        )
        
        print(f"✅ Результат выполнения:")
        print(f"   status: {result.status}")
        print(f"   result type: {type(result.result)}")
        print(f"   error: {result.error}")
        print(f"   metadata: {result.metadata}")
        
        if result.result:
            if hasattr(result.result, 'model_dump'):
                print(f"   result data: {result.result.model_dump()}")
            else:
                print(f"   result data: {result.result}")
        
    except Exception as e:
        print(f"❌ Ошибка выполнения: {e}")
        import traceback
        traceback.print_exc()
    
    # 8. Тест list_scripts
    print("\n8. Тест list_scripts...")
    
    capability_list = None
    for cap in book_library.get_capabilities():
        if cap.name == "book_library.list_scripts":
            capability_list = cap
            break
    
    if capability_list:
        try:
            result = await book_library.execute(
                capability=capability_list,
                parameters={},
                execution_context=exec_context
            )
            
            print(f"✅ Результат list_scripts:")
            print(f"   status: {result.status}")
            if result.result:
                if hasattr(result.result, 'model_dump'):
                    data = result.result.model_dump()
                    print(f"   scripts count: {len(data.get('scripts', []))}")
                else:
                    print(f"   result: {result.result}")
            
        except Exception as e:
            print(f"❌ Ошибка list_scripts: {e}")
            import traceback
            traceback.print_exc()
    
    # 9. Завершение
    print("\n9. Завершение...")
    await app_ctx.shutdown()
    await infra.shutdown()
    print("✅ Тестирование завершено")


if __name__ == "__main__":
    asyncio.run(test_book_library_skill())
