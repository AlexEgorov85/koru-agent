#!/usr/bin/env python3
"""
Тест для проверки исправления инициализации sql_tool
"""
import asyncio
import sys
import os

# Добавляем путь к проекту
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

async def test_sql_tool_initialization():
    """Тестируем инициализацию sql_tool после исправления"""
    print("=== Тестирование инициализации sql_tool ===")
    
    try:
        # Импортируем необходимые модули
        from core.config.app_config import AppConfig
        from core.application.context.application_context import ApplicationContext
        from core.infrastructure.context.infrastructure_context import InfrastructureContext
        from core.config.models import SystemConfig, LLMProviderConfig, DBProviderConfig
        
        print("+ Импорт модулей выполнен успешно")
        
        # Создаем минимальную системную конфигурацию
        system_config = SystemConfig(
            llm_providers={
                "default_llm": LLMProviderConfig(
                    provider_type="llama_cpp",
                    model_name="test-model",
                    parameters={"model_path": "test"},
                    enabled=True
                )
            },
            db_providers={
                "default_db": DBProviderConfig(
                    provider_type="sqlite",
                    parameters={"database_url": "sqlite:///test.db"},
                    enabled=True
                )
            }
        )
        
        # Создаем инфраструктурный контекст
        infra_context = InfrastructureContext(config=system_config)
        print("+ Инфраструктурный контекст создан")
        
        # Загружаем конфигурацию из реестра
        app_config = AppConfig.from_registry(profile="prod")
        print(f"+ AppConfig загружен из реестра, профиль: {app_config.profile}")
        print(f"  - prompt_versions: {len(app_config.prompt_versions)} записей")
        print(f"  - input_contract_versions: {len(app_config.input_contract_versions)} записей")
        print(f"  - tool_configs: {len(app_config.tool_configs)} инструментов")
        
        # Проверяем конфигурацию sql_tool
        if 'sql_tool' in app_config.tool_configs:
            sql_tool_config = app_config.tool_configs['sql_tool']
            print(f"+ Конфигурация sql_tool найдена:")
            print(f"  - prompt_versions: {sql_tool_config.prompt_versions}")
            print(f"  - input_contract_versions: {sql_tool_config.input_contract_versions}")
            print(f"  - output_contract_versions: {sql_tool_config.output_contract_versions}")
        else:
            print("- Конфигурация sql_tool НЕ найдена!")
            return False
        
        # Инициализируем инфраструктурный контекст
        await infra_context.initialize()
        print("+ InfrastructureContext инициализирован")
        
        # Создаем контекст приложения
        app_context = await ApplicationContext.create_from_registry(infra_context, profile="prod")
        print("+ ApplicationContext создан из реестра")
        
        # Получаем инструмент
        sql_tool = app_context.get_tool("sql_tool")
        if sql_tool is None:
            print("- sql_tool НЕ найден в контексте!")
            return False
            
        print(f"+ sql_tool получен: {sql_tool.name}")
        print(f"  - _initialized: {getattr(sql_tool, '_initialized', 'Не определено')}")
        print(f"  - _cached_prompts: {getattr(sql_tool, '_cached_prompts', {})}")
        print(f"  - _cached_input_contracts: {getattr(sql_tool, '_cached_input_contracts', {})}")
        print(f"  - _cached_output_contracts: {getattr(sql_tool, '_cached_output_contracts', {})}")
        
        # Проверяем, что инструмент инициализирован
        if hasattr(sql_tool, '_initialized') and sql_tool._initialized:
            print("+ sql_tool успешно инициализирован (_initialized = True)")
        else:
            print("- sql_tool НЕ инициализирован (_initialized = False или отсутствует)")
            return False
            
        # Проверяем, что кэши пустые (что нормально для инструментов без промптов)
        cached_prompts = getattr(sql_tool, '_cached_prompts', {})
        cached_input_contracts = getattr(sql_tool, '_cached_input_contracts', {})
        cached_output_contracts = getattr(sql_tool, '_cached_output_contracts', {})
        
        if not cached_prompts and not cached_input_contracts and not cached_output_contracts:
            print("+ Все кэши пустые (нормально для инструментов без промптов)")
        else:
            print("! Кэши содержат данные (возможно, нормально, если промпты были явно заданы)")
            print(f"  - cached_prompts: {cached_prompts}")
            print(f"  - cached_input_contracts: {cached_input_contracts}")
            print(f"  - cached_output_contracts: {cached_output_contracts}")
        
        print("\n=== Тест ПРОЙДЕН: sql_tool инициализируется корректно ===")
        return True
        
    except Exception as e:
        print(f"- ОШИБКА при тестировании: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_sql_tool_initialization())
    if success:
        print("\n+ Все тесты пройдены успешно!")
        sys.exit(0)
    else:
        print("\n- Тесты не пройдены!")
        sys.exit(1)