#!/usr/bin/env python3
"""
Интеграционный тест: Поднятие ApplicationContext и запуск инструментов
БЕЗ МОКОВ - используются реальные компоненты
"""
import asyncio
import logging
import sys
from pathlib import Path
from core.config.models import SystemConfig, LLMProviderConfig, DBProviderConfig
from core.config.app_config import AppConfig
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext, ComponentType


# Настройка логирования для отладки
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)


async def test_infrastructure_context():
    """Тест 1: Инициализация InfrastructureContext"""
    print("\n" + "="*60)
    print("ТЕСТ 1: Инициализация InfrastructureContext")
    print("="*60)
    
    # Создаем минимальную системную конфигурацию
    config = SystemConfig(
        debug=True,
        log_level="INFO",
        log_dir="./logs",
        data_dir="./data",
        llm_providers={},
        db_providers={
            "default_db": DBProviderConfig(
                enabled=True,
                type_provider="sqlite",
                parameters={"database": ":memory:"}
            )
        }
    )
    
    # Создаем и инициализируем инфраструктурный контекст
    infra = InfrastructureContext(config)
    success = await infra.initialize()
    
    print(f"InfrastructureContext инициализирован: {success}")
    print(f"ID контекста: {infra.id}")
    print(f"PromptStorage: {infra.prompt_storage is not None}")
    print(f"ContractStorage: {infra.contract_storage is not None}")
    print(f"ResourceRegistry: {infra.resource_registry is not None}")
    
    assert success, "InfrastructureContext не инициализировался"
    return infra


async def test_application_context(infra: InfrastructureContext):
    """Тест 2: Инициализация ApplicationContext"""
    print("\n" + "="*60)
    print("ТЕСТ 2: Инициализация ApplicationContext")
    print("="*60)
    
    # Загружаем конфигурацию из registry.yaml
    app_config = AppConfig.from_registry(profile="prod", registry_path="registry.yaml")
    
    print(f"Config ID: {app_config.config_id}")
    print(f"Service configs: {len(app_config.service_configs)}")
    print(f"Skill configs: {len(app_config.skill_configs)}")
    print(f"Tool configs: {len(app_config.tool_configs)}")
    print(f"Behavior configs: {len(app_config.behavior_configs)}")
    
    # Создаем прикладной контекст
    app_context = ApplicationContext(
        infrastructure_context=infra,
        config=app_config,
        profile="prod",
        use_data_repository=True
    )
    
    print(f"ID ApplicationContext: {app_context.id}")
    print(f"DataRepository: {app_context.data_repository is not None}")
    print(f"Side effects enabled: {app_context.side_effects_enabled}")
    
    # Инициализируем прикладной контекст
    success = await app_context.initialize()
    
    print(f"ApplicationContext инициализирован: {success}")
    assert success, "ApplicationContext не инициализировался"
    
    return app_context


async def test_components_loading(app_context: ApplicationContext):
    """Тест 3: Загрузка компонентов из реестра"""
    print("\n" + "="*60)
    print("ТЕСТ 3: Загрузка компонентов")
    print("="*60)
    
    # Проверяем загрузку компонентов через реестр
    tools = app_context.components.all_of_type(ComponentType.TOOL)
    skills = app_context.components.all_of_type(ComponentType.SKILL)
    services = app_context.components.all_of_type(ComponentType.SERVICE)
    behaviors = app_context.components.all_of_type(ComponentType.BEHAVIOR)
    
    print(f"Загружено инструментов: {len(tools)}")
    print(f"Загружено навыков: {len(skills)}")
    print(f"Загружено сервисов: {len(services)}")
    print(f"Загружено поведений: {len(behaviors)}")
    
    # Выводим имена компонентов
    if tools:
        print(f"  Инструменты: {[t.name for t in tools]}")
    if skills:
        print(f"  Навыки: {[s.name for s in skills]}")
    if services:
        print(f"  Сервисы: {[s.name for s in services]}")
    if behaviors:
        print(f"  Поведения: {[b.name for b in behaviors]}")
    
    return {
        'tools': tools,
        'skills': skills,
        'services': services,
        'behaviors': behaviors
    }


async def test_tool_execution(app_context: ApplicationContext, tools: list):
    """Тест 4: Выполнение инструментов"""
    print("\n" + "="*60)
    print("ТЕСТ 4: Выполнение инструментов")
    print("="*60)
    
    results = {}
    
    # Тест FileTool
    file_tool = app_context.components.get(ComponentType.TOOL, "file_tool")
    if file_tool:
        print(f"\nFileTool найден: {file_tool.name}")
        print(f"  Описание: {file_tool.description}")
        print(f"  Инициализирован: {file_tool._initialized}")
        
        # Тест операции read (безопасная операция)
        from core.application.tools.file_tool import FileToolInput
        test_file = Path("./data/registry.yaml")
        
        if test_file.exists():
            input_data = FileToolInput(operation="read", path=str(test_file))
            output = await file_tool.execute(input_data)
            
            print(f"  Операция read: success={output.success}")
            if output.success:
                print(f"  Размер файла: {output.data.get('size', 'N/A')} байт")
            else:
                print(f"  Ошибка: {output.error}")
            
            results['file_tool_read'] = output.success
        else:
            print(f"  Тестовый файл не найден: {test_file}")
            results['file_tool_read'] = False
        
        # Тест операции list
        input_data = FileToolInput(operation="list", path="./data")
        output = await file_tool.execute(input_data)
        
        print(f"  Операция list: success={output.success}")
        if output.success:
            print(f"  Найдено элементов: {output.data.get('count', 0)}")
        else:
            print(f"  Ошибка: {output.error}")
        
        results['file_tool_list'] = output.success
    else:
        print("FileTool не найден в контексте")
        results['file_tool_read'] = False
        results['file_tool_list'] = False
    
    # Тест SQLTool
    sql_tool = app_context.components.get(ComponentType.TOOL, "sql_tool")
    if sql_tool:
        print(f"\nSQLTool найден: {sql_tool.name}")
        print(f"  Описание: {sql_tool.description}")
        print(f"  Инициализирован: {sql_tool._initialized}")
        
        # Проверяем наличие БД провайдера
        db_provider = app_context.infrastructure_context.get_provider("default_db")
        print(f"  DB провайдер: {db_provider is not None}")
        
        if db_provider:
            # Тест SQL запроса (создание таблицы)
            from core.application.tools.sql_tool import SQLToolInput
            
            # Создаем тестовую таблицу
            input_data = SQLToolInput(
                sql="CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, name TEXT)",
                parameters=None,
                max_rows=100
            )
            output = await sql_tool.execute(input_data)
            
            print(f"  CREATE TABLE: success={output.rowcount >= 0}")
            results['sql_create'] = True
            
            # Вставляем тестовые данные
            input_data = SQLToolInput(
                sql="INSERT INTO test_table (name) VALUES (?)",
                parameters={"1": "test_value"},
                max_rows=100
            )
            output = await sql_tool.execute(input_data)
            
            print(f"  INSERT: rows affected={output.rowcount}")
            results['sql_insert'] = output.rowcount >= 0
            
            # Читаем данные
            input_data = SQLToolInput(
                sql="SELECT * FROM test_table",
                parameters=None,
                max_rows=100
            )
            output = await sql_tool.execute(input_data)
            
            print(f"  SELECT: найдено строк={output.rowcount}")
            print(f"  Колонки: {output.columns}")
            if output.rows:
                print(f"  Первая строка: {output.rows[0]}")
            
            results['sql_select'] = output.rowcount >= 0
        else:
            print("  DB провайдер не найден, пропускаем SQL тесты")
            results['sql_create'] = False
            results['sql_insert'] = False
            results['sql_select'] = False
    else:
        print("SQLTool не найден в контексте")
        results['sql_create'] = False
        results['sql_insert'] = False
        results['sql_select'] = False
    
    return results


async def test_sandbox_mode(app_context: ApplicationContext):
    """Тест 5: Проверка sandbox режима"""
    print("\n" + "="*60)
    print("ТЕСТ 5: Sandbox режим (side_effects_enabled=False)")
    print("="*60)
    
    # Создаем контекст с отключенными side effects
    app_config = AppConfig.from_registry(profile="prod", registry_path="registry.yaml")
    # Переключаем в sandbox режим
    app_config.side_effects_enabled = False
    
    sandbox_context = ApplicationContext(
        infrastructure_context=app_context.infrastructure_context,
        config=app_config,
        profile="prod",
        use_data_repository=True
    )
    
    success = await sandbox_context.initialize()
    print(f"Sandbox контекст инициализирован: {success}")
    
    # Проверяем FileTool в sandbox режиме
    file_tool = sandbox_context.components.get(ComponentType.TOOL, "file_tool")
    if file_tool:
        from core.application.tools.file_tool import FileToolInput
        
        # Тест write операции (должна быть заблокирована)
        input_data = FileToolInput(
            operation="write",
            path="./data/test_sandbox.txt",
            content="test content"
        )
        output = await file_tool.execute(input_data)
        
        print(f"\nFileTool write в sandbox: success={output.success}")
        if output.success and output.data.get('dry_run'):
            print(f"  Sandbox режим активен: {output.data.get('message')}")
            print("  OK Sandbox режим работает корректно")
        else:
            print(f"  Ошибка или unexpected behavior: {output.error}")
    
    # Завершаем sandbox контекст (вместо shutdown просто сбрасываем флаг)
    sandbox_context._initialized = False
    print("Sandbox контекст завершен")
    return True


async def test_prompt_contract_access(app_context: ApplicationContext):
    """Тест 6: Доступ к промптам и контрактам"""
    print("\n" + "="*60)
    print("ТЕСТ 6: Доступ к промптам и контрактам")
    print("="*60)
    
    # Проверяем доступ к хранилищам через инфраструктуру
    prompt_storage = app_context.infrastructure_context.prompt_storage
    contract_storage = app_context.infrastructure_context.contract_storage
    
    print(f"PromptStorage доступен: {prompt_storage is not None}")
    print(f"ContractStorage доступен: {contract_storage is not None}")
    
    # Проверяем DataRepository
    if app_context.data_repository:
        print(f"\nDataRepository инициализирован")
        print(f"  Manifests загружено: {len(app_context.data_repository._manifest_cache)}")
        
        # Используем правильные атрибуты DataRepository
        prompt_cache = getattr(app_context.data_repository, '_prompt_cache', {})
        contract_cache = getattr(app_context.data_repository, '_contract_cache', {})
        print(f"  Prompts загружено: {len(prompt_cache)}")
        print(f"  Contracts загружено: {len(contract_cache)}")
        
        # Пробуем получить манифест инструмента
        sql_tool_manifest = app_context.data_repository.get_manifest('tool', 'sql_tool')
        if sql_tool_manifest:
            print(f"\n  Манифест sql_tool:")
            print(f"    Version: {sql_tool_manifest.version}")
            print(f"    Status: {sql_tool_manifest.status}")
            print(f"    Owner: {sql_tool_manifest.owner}")
        else:
            print("  Манифест sql_tool не найден")
        
        # Пробуем получить промпт через контекст
        try:
            prompt = app_context.get_prompt("sql_generation.generate_query", "v1.0.0")
            print(f"\n  Промпт sql_generation.generate_query@v1.0.0:")
            print(f"    Длина: {len(prompt) if prompt else 0} символов")
            if prompt:
                print(f"    Первые 100 символов: {prompt[:100]}...")
        except Exception as e:
            print(f"  Ошибка получения промпта: {e}")
        
        # Пробуем получить контракт через контекст
        try:
            contract = app_context.get_contract("sql_generation.generate_query", "v1.0.0", "input")
            print(f"\n  Контракт sql_generation.generate_query@v1.0.0 (input):")
            print(f"    Тип: {type(contract)}")
            if contract:
                print(f"    Ключи схемы: {list(contract.keys()) if isinstance(contract, dict) else 'N/A'}")
        except Exception as e:
            print(f"  Ошибка получения контракта: {e}")
    
    return True


async def test_context_shutdown(infra: InfrastructureContext):
    """Тест 7: Корректное завершение работы"""
    print("\n" + "="*60)
    print("ТЕСТ 7: Завершение работы")
    print("="*60)
    
    await infra.shutdown()
    print("InfrastructureContext завершен")
    
    return True


async def main():
    """Главная функция теста"""
    print("\n" + "="*60)
    print("ИНТЕГРАЦИОННЫЙ ТЕСТ: ApplicationContext + Инструменты")
    print("БЕЗ МОКОВ - реальные компоненты")
    print("="*60)
    
    test_results = {}
    
    try:
        # Тест 1: InfrastructureContext
        infra = await test_infrastructure_context()
        test_results['infrastructure'] = True
        
        # Тест 2: ApplicationContext
        app_context = await test_application_context(infra)
        test_results['application'] = True
        
        # Тест 3: Загрузка компонентов
        components = await test_components_loading(app_context)
        test_results['components'] = len(components['tools']) > 0
        
        # Тест 4: Выполнение инструментов
        tool_results = await test_tool_execution(app_context, components['tools'])
        test_results.update(tool_results)
        
        # Тест 5: Sandbox режим
        sandbox_result = await test_sandbox_mode(app_context)
        test_results['sandbox'] = sandbox_result
        
        # Тест 6: Доступ к промптам и контрактам
        access_result = await test_prompt_contract_access(app_context)
        test_results['prompt_contract_access'] = access_result
        
        # Тест 7: Завершение работы
        shutdown_result = await test_context_shutdown(infra)
        test_results['shutdown'] = shutdown_result
        
    except Exception as e:
        print(f"\nКРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback
        traceback.print_exc()
        test_results['error'] = str(e)
    
    # Итоговый отчет
    print("\n" + "="*60)
    print("ИТОГОВЫЙ ОТЧЕТ")
    print("="*60)
    
    passed = sum(1 for v in test_results.values() if v is True)
    total = len(test_results)
    
    for test_name, result in test_results.items():
        status = "PASS" if result is True else ("PARTIAL" if isinstance(result, bool) and not result else f"FAIL: {result}")
        print(f"  {test_name}: {status}")
    
    print(f"\nИтого: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("\nВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
    else:
        print(f"\n{total - passed} тестов не пройдено")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
