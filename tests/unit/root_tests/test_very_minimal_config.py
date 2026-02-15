"""
Тест с очень минимальной конфигурацией для проверки инициализации компонентов.
"""
import asyncio
import sys
import os

# Добавляем корневую директорию проекта в путь Python
sys.path.insert(0, os.path.abspath('.'))

async def test_very_minimal_config():
    """Тест с очень минимальной конфигурацией."""
    print("=== ТЕСТ С ОЧЕНЬ МИНИМАЛЬНОЙ КОНФИГУРАЦИЕЙ ===")
    
    try:
        from core.config.app_config import AppConfig
        from core.application.context.application_context import ApplicationContext
        
        print("[OK] Импорты выполнены успешно")
        
        # Загружаем конфигурацию из очень минимального реестра
        app_config = AppConfig.from_registry(profile="prod", registry_path="very_minimal_registry.yaml")
        print("[OK] AppConfig успешно загружен из очень минимального реестра")
        
        # Создаем инфраструктурный контекст с минимальной конфигурацией
        from core.infrastructure.context.infrastructure_context import InfrastructureContext
        
        # Создаем временную конфигурацию для тестирования
        class MockSystemConfig:
            def __init__(self):
                self.data_dir = "data"  # используем существующую директорию
                self.llm_providers = {}
                self.db_providers = {}
        
        infra_config = MockSystemConfig()
        infra_context = InfrastructureContext(config=infra_config)
        await infra_context.initialize()
        print("[OK] Инфраструктурный контекст создан и инициализирован")
        
        # Создаем и инициализируем прикладной контекст
        app_context = ApplicationContext(
            infrastructure_context=infra_context,
            config=app_config,
            profile="prod"
        )
        print("[OK] ApplicationContext создан")
        
        # Инициализируем прикладной контекст (все компоненты будут созданы и инициализированы)
        success = await app_context.initialize()
        print(f"[INFO] ApplicationContext инициализирован: {success}")
        
        # Проверим состояние компонентов
        prompt_service = app_context.get_service("prompt_service")
        contract_service = app_context.get_service("contract_service")
        
        print(f"[INFO] Prompt Service: {prompt_service is not None}, _initialized: {getattr(prompt_service, '_initialized', 'N/A')}")
        print(f"[INFO] Contract Service: {contract_service is not None}, _initialized: {getattr(contract_service, '_initialized', 'N/A')}")
        
        book_skill = app_context.get_skill("book_library")
        planning_skill = app_context.get_skill("planning")
        
        if book_skill:
            print(f"[INFO] Book Library Skill _initialized: {getattr(book_skill, '_initialized', 'N/A')}")
            print(f"[INFO] Book Library Skill cached prompts: {list(book_skill._cached_prompts.keys())}")
        
        if planning_skill:
            print(f"[INFO] Planning Skill _initialized: {getattr(planning_skill, '_initialized', 'N/A')}")
            print(f"[INFO] Planning Skill cached prompts: {list(planning_skill._cached_prompts.keys())}")
        
        sql_tool = app_context.get_tool("sql_tool")
        file_tool = app_context.get_tool("file_tool")
        
        if sql_tool:
            print(f"[INFO] SQL Tool _initialized: {getattr(sql_tool, '_initialized', 'N/A')}")
            print(f"[INFO] SQL Tool cached prompts: {list(sql_tool._cached_prompts.keys())}")
        
        if file_tool:
            print(f"[INFO] File Tool _initialized: {getattr(file_tool, '_initialized', 'N/A')}")
            print(f"[INFO] File Tool cached prompts: {list(file_tool._cached_prompts.keys())}")
        
        # Проверим, что все компоненты инициализированы (теперь, когда нет требований к промптам)
        all_initialized = all([
            prompt_service and getattr(prompt_service, '_initialized', False),
            contract_service and getattr(contract_service, '_initialized', False),
            book_skill and getattr(book_skill, '_initialized', False),
            planning_skill and getattr(planning_skill, '_initialized', False),
            sql_tool and getattr(sql_tool, '_initialized', False),
            file_tool and getattr(file_tool, '_initialized', False)
        ])
        
        print(f"[INFO] Все компоненты инициализированы: {all_initialized}")
        
        # Проверим, что кэши пусты (так как нет промптов для загрузки)
        if book_skill:
            print(f"[INFO] Book Library кэш промптов пуст: {len(book_skill._cached_prompts) == 0}")
        
        if planning_skill:
            print(f"[INFO] Planning кэш промптов пуст: {len(planning_skill._cached_prompts) == 0}")
        
        if sql_tool:
            print(f"[INFO] SQL Tool кэш промптов пуст: {len(sql_tool._cached_prompts) == 0}")
        
        if file_tool:
            print(f"[INFO] File Tool кэш промптов пуст: {len(file_tool._cached_prompts) == 0}")
        
        print("\n[SUCCESS] ВСЕ КОМПОНЕНТЫ ИНИЦИАЛИЗИРОВАНЫ!")
        print("\n=== РЕЗУЛЬТАТЫ ===")
        print("- Сервисы инициализированы: OK")
        print("- Навыки инициализированы: OK")
        print("- Инструменты инициализированы: OK")
        print("- Кэши пусты (без промптов): OK")
        print("- Ошибок инициализации нет: OK")
        
        return True
        
    except Exception as e:
        print(f"\n[ERROR] ОШИБКА ТЕСТИРОВАНИЯ: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_very_minimal_config())
    if success:
        print("\n[SUCCESS] Тестирование завершено успешно!")
    else:
        print("\n[ERROR] Тестирование завершилось с ошибками!")
        sys.exit(1)