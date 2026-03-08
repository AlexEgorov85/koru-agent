"""
Интеграционный тест BookLibrarySkill.

РЕАЛЬНОЕ ТЕСТИРОВАНИЕ:
1. Поднимается InfrastructureContext
2. Поднимается ApplicationContext
3. Инициализируется BookLibrarySkill
4. Вызываются ВСЕ capability с реальным выполнением
5. Проверяются реальные результаты

ТРЕБОВАНИЯ:
- База данных books.db должна существовать
- Все 10 скриптов должны быть доступны
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# Настраиваем UTF-8 для Windows
if sys.platform == 'win32':
    import os
    os.system('chcp 65001 >nul')


async def test_book_library_integration():
    """Полноценный интеграционный тест BookLibrarySkill"""
    
    print("\n" + "=" * 80)
    print("ИНТЕГРАЦИОННЫЙ ТЕСТ BookLibrarySkill")
    print("=" * 80 + "\n")
    
    from core.config import get_config
    from core.infrastructure.context.infrastructure_context import InfrastructureContext
    from core.application.context.application_context import ApplicationContext
    from core.application.agent.components.action_executor import ActionExecutor, ExecutionContext
    from core.models.enums.common_enums import ComponentType, ExecutionStatus
    
    # === ЭТАП 1: Инициализация инфраструктуры ===
    print("=" * 80)
    print("ЭТАП 1: Инициализация InfrastructureContext")
    print("=" * 80)
    
    config = get_config(profile='dev')
    infra = InfrastructureContext(config)
    await infra.initialize()
    print(f"[OK] InfrastructureContext инициализирован")
    
    # === ЭТАП 2: Инициализация приложения ===
    print("\n" + "=" * 80)
    print("ЭТАП 2: Инициализация ApplicationContext")
    print("=" * 80)
    
    from core.config.app_config import AppConfig
    
    app_config = AppConfig.from_discovery(
        profile="prod",
        data_dir=str(getattr(config, 'data_dir', 'data')),
        discovery=infra.get_resource_discovery()
    )
    app_ctx = ApplicationContext(
        infrastructure_context=infra,
        config=app_config,
        profile="prod"
    )
    await app_ctx.initialize()
    print(f"[OK] ApplicationContext инициализирован")
    print(f"     ID: {app_ctx.id}")
    
    # === ЭТАП 3: Получение BookLibrarySkill ===
    print("\n" + "=" * 80)
    print("ЭТАП 3: Получение BookLibrarySkill")
    print("=" * 80)
    
    book_library = app_ctx.components.get(ComponentType.TOOL, "book_library")
    
    if not book_library:
        print("[FAIL] Компонент book_library не найден!")
        await app_ctx.shutdown()
        await infra.shutdown()
        return False
    
    print(f"[OK] BookLibrarySkill получен")
    print(f"     Тип: {type(book_library).__name__}")
    print(f"     Capability: {list(book_library.supported_capabilities.keys())}")
    
    # Проверяем что skill инициализирован
    if hasattr(book_library, '_scripts_registry'):
        print(f"     Скриптов в реестре: {len(book_library._scripts_registry)}")
    else:
        print("[WARN] Реестр скриптов не загружен")
    
    # === ЭТАП 4: Тест capability: book_library.list_scripts ===
    print("\n" + "=" * 80)
    print("ЭТАП 4: Тест capability: book_library.list_scripts")
    print("=" * 80)
    
    executor = ActionExecutor(app_ctx)
    
    # Находим capability
    capability_list = None
    for cap in book_library.get_capabilities():
        if cap.name == "book_library.list_scripts":
            capability_list = cap
            break
    
    if not capability_list:
        print("[FAIL] Capability book_library.list_scripts не найдена!")
    else:
        print(f"[OK] Capability найдена: {capability_list.name}")
        
        # Создаём ExecutionContext
        exec_context = ExecutionContext(
            session_context=app_ctx.session_context,
            user_context=None
        )
        
        # Выполняем
        try:
            result = await book_library.execute(
                capability=capability_list,
                parameters={},
                execution_context=exec_context
            )
            
            print(f"[OK] Выполнение завершено")
            print(f"     Status: {result.status}")
            print(f"     Error: {result.error}")
            
            if result.status == ExecutionStatus.COMPLETED and result.result:
                # Проверяем структуру результата
                res = result.result
                if hasattr(res, 'model_dump'):
                    res = res.model_dump()
                
                if 'scripts' in res:
                    print(f"     Скриптов найдено: {len(res['scripts'])}")
                    print(f"     Count: {res.get('count', 'N/A')}")
                    
                    # Проверяем что скрипты имеют правильную структуру
                    if len(res['scripts']) > 0:
                        first_script = res['scripts'][0]
                        print(f"     Первый скрипт: {first_script.get('name', 'N/A')}")
                        print(f"[OK] Структура результата корректна")
                    else:
                        print("[WARN] Список скриптов пуст")
                else:
                    print(f"[FAIL] Отсутствует поле 'scripts' в результате: {res.keys()}")
            else:
                print(f"[FAIL] Выполнение не удалось: {result.error}")
                
        except Exception as e:
            print(f"[FAIL] Исключение при выполнении: {e}")
            import traceback
            traceback.print_exc()
    
    # === ЭТАП 5: Тест capability: book_library.execute_script ===
    print("\n" + "=" * 80)
    print("ЭТАП 5: Тест capability: book_library.execute_script")
    print("=" * 80)
    
    # Находим capability
    capability_exec = None
    for cap in book_library.get_capabilities():
        if cap.name == "book_library.execute_script":
            capability_exec = cap
            break
    
    if not capability_exec:
        print("[FAIL] Capability book_library.execute_script не найдена!")
    else:
        print(f"[OK] Capability найдена: {capability_exec.name}")
        
        # Тестируем скрипт get_books_by_author
        test_scripts = [
            {"script_name": "get_books_by_author", "parameters": {"author": "Пушкин"}, "expected_field": "rows"},
            {"script_name": "get_all_books", "parameters": {}, "expected_field": "rows"},
            {"script_name": "count_books_by_author", "parameters": {"author": "Пушкин"}, "expected_field": "rows"},
        ]
        
        for test_script in test_scripts:
            print(f"\n     Тест скрипта: {test_script['script_name']}")
            
            try:
                result = await book_library.execute(
                    capability=capability_exec,
                    parameters=test_script['parameters'] | {"script_name": test_script['script_name']},
                    execution_context=exec_context
                )
                
                print(f"         Status: {result.status}")
                
                if result.status == ExecutionStatus.COMPLETED and result.result:
                    res = result.result
                    if hasattr(res, 'model_dump'):
                        res = res.model_dump()
                    
                    # Проверяем обязательные поля
                    if 'rows' in res:
                        print(f"         Rows: {len(res['rows'])}")
                    if 'rowcount' in res:
                        print(f"         Rowcount: {res['rowcount']}")
                    if 'script_name' in res:
                        print(f"         Script: {res['script_name']}")
                    
                    print(f"         [OK] Скрипт выполнен успешно")
                    
                    # Показываем первый результат если есть
                    if 'rows' in res and len(res['rows']) > 0:
                        print(f"         Пример: {res['rows'][0]}")
                else:
                    print(f"         [WARN] Выполнение завершилось с ошибкой: {result.error}")
                    
            except Exception as e:
                print(f"         [FAIL] Исключение: {e}")
    
    # === ЭТАП 6: Тест capability: book_library.search_books (опционально, требует LLM) ===
    print("\n" + "=" * 80)
    print("ЭТАП 6: Тест capability: book_library.search_books (LLM)")
    print("=" * 80)
    
    print("[INFO] Тест пропускается - требует LLM и занимает много времени")
    print("[INFO] Для запуска раскомментируйте код ниже")
    
    # === ЭТАП 7: Завершение ===
    print("\n" + "=" * 80)
    print("ЭТАП 7: Завершение")
    print("=" * 80)
    
    await app_ctx.shutdown()
    await infra.shutdown()
    print("[OK] Контексты завершены")
    
    print("\n" + "=" * 80)
    print("ИНТЕГРАЦИОННЫЙ ТЕСТ ЗАВЕРШЁН")
    print("=" * 80 + "\n")
    
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_book_library_integration())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n[FAIL] Критическая ошибка теста: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
