#!/usr/bin/env python3
"""
Прямой запуск навыка book_library с генерацией SQL без полного агента.

Использует минимальную инициализацию контекстов для быстрого тестирования.

ЗАПУСК:
    python run_skill_directly.py

ПРИМЕРЫ:
    python run_skill_directly.py --query "Какие книги написал Пушкин?"
    python run_skill_directly.py --query "Найти книги Толстого" --max 5
    python run_skill_directly.py --script get_all_books --max 10
"""
import asyncio
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, Optional

# Добавим путь к корню проекта
sys.path.insert(0, str(Path(__file__).parent))


async def run_skill_directly(
    query: str = None,
    script_name: str = None,
    script_params: Dict[str, Any] = None,
    max_results: int = 20,
    profile: str = "dev"
):
    """
    Прямой вызов навыка book_library.
    
    Args:
        query: Запрос на естественном языке (для search_books)
        script_name: Имя скрипта (для execute_script)
        script_params: Параметры скрипта
        max_results: Максимальное количество результатов
        profile: Профиль конфигурации
    """
    from core.config.models import SystemConfig
    from core.infrastructure_context.infrastructure_context import InfrastructureContext
    from core.application_context.application_context import ApplicationContext
    from core.config.app_config import AppConfig
    from core.models.enums.common_enums import ComponentType

    print("🚀 Инициализация контекстов...", flush=True)

    # 1. Инициализация контекстов
    config = SystemConfig(data_dir='data')
    infra = InfrastructureContext(config)
    await infra.initialize()

    app_config = AppConfig.from_discovery(
        profile=profile,
        data_dir="data",
        discovery=infra.resource_discovery
    )
    app_context = ApplicationContext(
        infrastructure_context=infra,
        config=app_config,
        profile=profile
    )
    
    success = await app_context.initialize()
    if not success:
        print("❌ Не удалось инициализировать ApplicationContext")
        await infra.shutdown()
        return

    print("✅ Контексты инициализированы", flush=True)

    try:
        # 2. Получение навыка через components.get (новый способ)
        skill = app_context.components.get(ComponentType.SKILL, "book_library")
        if skill is None:
            print("❌ Навык book_library не найден")
            print(f"   Доступные навыки: {list(app_context.components.all_of_type(ComponentType.SKILL))}")
            await infra.shutdown()
            return
        
        # Проверяем что промпты загружены
        if not skill.prompts:
            print(f"⚠️  Навык не имеет загруженных промптов!")
            print(f"   component_config.prompt_versions: {skill.component_config.prompt_versions if skill.component_config else 'N/A'}")
            print(f"   prompts: {skill.prompts}")
        
        await skill.initialize()
        print("✅ Навык book_library инициализирован", flush=True)
        print(f"   Загружено промптов: {len(skill.prompts)}", flush=True)
        print(f"   Промпты: {list(skill.prompts.keys())}", flush=True)

        # 3. Выполнение в зависимости от режима
        from core.models.data.capability import Capability

        if query:
            # Режим 1: Динамическая генерация SQL через LLM
            print(f"\n📚 Запуск поиска книг: {query}", flush=True)
            print("-" * 60, flush=True)
            
            capability = Capability(
                name="book_library.search_books",
                description="Динамический поиск книг с генерацией SQL через LLM",
                skill_name="book_library"
            )
            
            result = await skill.execute(
                capability=capability,
                parameters={
                    "query": query,
                    "max_results": max_results
                },
                execution_context=None
            )
            
            _print_search_result(result)
            
        elif script_name:
            # Режим 2: Выполнение заготовленного скрипта
            print(f"\n📚 Запуск скрипта: {script_name}", flush=True)
            print(f"   Параметры: {script_params or {}}", flush=True)
            print("-" * 60, flush=True)
            
            capability = Capability(
                name="book_library.execute_script",
                description="Выполнение заготовленного SQL-скрипта по имени",
                skill_name="book_library"
            )
            
            result = await skill.execute(
                capability=capability,
                parameters={
                    "script_name": script_name,
                    "parameters": {**script_params, "max_rows": max_results} if script_params else {"max_rows": max_results}
                },
                execution_context=None
            )
            
            _print_script_result(result)
            
        else:
            # Режим 3: Показать доступные скрипты
            print("\n📚 Доступные скрипты:", flush=True)
            print("-" * 60, flush=True)
            
            capability = Capability(
                name="book_library.list_scripts",
                description="Получение списка доступных скриптов",
                skill_name="book_library"
            )
            
            result = await skill.execute(
                capability=capability,
                parameters={},
                execution_context=None
            )
            
            _print_scripts_list(result)

    except Exception as e:
        print(f"\n❌ Ошибка выполнения: {e}", flush=True)
        import traceback
        traceback.print_exc()
        
    finally:
        # 4. Завершение
        print("\n⏹️  Завершение работы...", flush=True)
        await infra.shutdown()
        print("✅ Готово", flush=True)


def _print_search_result(result):
    """Вывод результата поиска книг."""
    from core.models.data.execution import ExecutionResult
    
    # Извлекаем данные из ExecutionResult
    if isinstance(result, ExecutionResult):
        data = result.data if result.data else {}
        if hasattr(data, 'model_dump'):
            data = data.model_dump()
        
        # Проверяем статус и ошибку
        if result.status.value == 'failed':
            print(f"\n❌ Статус: {result.status.value}", flush=True)
            if result.error:
                print(f"   Ошибка: {result.error}", flush=True)
            return
    elif isinstance(result, dict):
        data = result
        if result.get('error'):
            print(f"\n❌ Ошибка: {result['error']}", flush=True)
            return
    else:
        print(f"\n❌ Неожиданный тип результата: {type(result)}", flush=True)
        return
    
    print("\n📊 Результат:", flush=True)
    print(f"   Найдено книг: {data.get('rowcount', 0)}", flush=True)
    print(f"   Тип выполнения: {data.get('execution_type', 'N/A')}", flush=True)
    print(f"   Время выполнения: {data.get('execution_time', 0):.3f}с", flush=True)
    
    if data.get('sql_query'):
        print(f"\n📝 SQL запрос:", flush=True)
        print(f"   {data['sql_query']}", flush=True)
    
    if data.get('warning'):
        print(f"\n⚠️  {data['warning']}", flush=True)
    
    if data.get('rows'):
        print(f"\n📖 Книги ({len(data['rows'])} шт):", flush=True)
        for i, book in enumerate(data['rows'][:10], 1):
            print(f"   {i}. {book}", flush=True)
        if len(data['rows']) > 10:
            print(f"   ... и ещё {len(data['rows']) - 10}", flush=True)
    
    # Показываем статус выполнения
    if isinstance(result, ExecutionResult):
        print(f"\n✅ Статус: {result.status.value}", flush=True)


def _print_script_result(result):
    """Вывод результата выполнения скрипта."""
    from core.models.data.execution import ExecutionResult
    
    # Извлекаем данные из ExecutionResult
    if isinstance(result, ExecutionResult):
        data = result.data if result.data else {}
        if hasattr(data, 'model_dump'):
            data = data.model_dump()
    elif isinstance(result, dict):
        data = result
    else:
        print(f"\n❌ Неожиданный тип результата: {type(result)}", flush=True)
        return
    
    print("\n📊 Результат:", flush=True)
    print(f"   Скрипт: {data.get('script_name', 'N/A')}", flush=True)
    print(f"   Найдено записей: {data.get('rowcount', 0)}", flush=True)
    print(f"   Тип выполнения: {data.get('execution_type', 'N/A')}", flush=True)
    print(f"   Время выполнения: {data.get('execution_time', 0):.3f}с", flush=True)
    
    if data.get('sql_query'):
        print(f"\n📝 SQL запрос:", flush=True)
        print(f"   {data['sql_query']}", flush=True)
    
    if data.get('error'):
        print(f"\n❌ Ошибка: {data['error']}", flush=True)
    
    if data.get('rows'):
        print(f"\n📖 Результаты ({len(data['rows'])} шт):", flush=True)
        for i, row in enumerate(data['rows'][:10], 1):
            print(f"   {i}. {row}", flush=True)
        if len(data['rows']) > 10:
            print(f"   ... и ещё {len(data['rows']) - 10}", flush=True)
    
    # Показываем статус выполнения
    if isinstance(result, ExecutionResult):
        print(f"\n✅ Статус: {result.status.value}", flush=True)


def _print_scripts_list(result):
    """Вывод списка доступных скриптов."""
    from core.models.data.execution import ExecutionResult
    
    # Извлекаем данные из ExecutionResult
    if isinstance(result, ExecutionResult):
        data = result.data if result.data else {}
        if hasattr(data, 'model_dump'):
            data = data.model_dump()
    elif isinstance(result, dict):
        data = result
    else:
        print(f"\n❌ Неожиданный тип результата: {type(result)}", flush=True)
        return
    
    if data.get('scripts'):
        for script in data['scripts']:
            name = script.get('name', 'N/A')
            desc = script.get('description', 'N/A')
            example = script.get('example', '')
            print(f"\n   📄 {name}", flush=True)
            print(f"      {desc}", flush=True)
            if example:
                print(f"      Пример: {example}", flush=True)
    else:
        print("   Список скриптов недоступен", flush=True)


def main():
    """Точка входа."""
    parser = argparse.ArgumentParser(
        description="Прямой запуск навыка book_library с генерацией SQL"
    )
    
    parser.add_argument(
        "--query", "-q",
        type=str,
        help="Запрос на естественном языке (для search_books)"
    )
    
    parser.add_argument(
        "--script", "-s",
        type=str,
        help="Имя скрипта (для execute_script)"
    )
    
    parser.add_argument(
        "--params", "-p",
        type=str,
        help="Параметры скрипта в формате JSON (например: '{\"author\":\"Толстой\"}')"
    )
    
    parser.add_argument(
        "--max", "-m",
        type=int,
        default=20,
        help="Максимальное количество результатов (по умолчанию: 20)"
    )
    
    parser.add_argument(
        "--profile",
        type=str,
        default="dev",
        choices=["dev", "prod"],
        help="Профиль конфигурации (по умолчанию: dev)"
    )
    
    parser.add_argument(
        "--list-scripts",
        action="store_true",
        help="Показать список доступных скриптов"
    )
    
    args = parser.parse_args()
    
    # Парсинг JSON параметров
    script_params = None
    if args.params:
        import json
        try:
            script_params = json.loads(args.params)
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга JSON параметров: {e}", file=sys.stderr)
            sys.exit(1)
    
    # Определение режима
    if args.list_scripts:
        query = None
        script_name = None
    elif args.script:
        query = None
        script_name = args.script
    else:
        query = args.query or "Какие книги есть в библиотеке?"
        script_name = None
    
    # Запуск
    asyncio.run(
        run_skill_directly(
            query=query,
            script_name=script_name,
            script_params=script_params,
            max_results=args.max,
            profile=args.profile
        )
    )


if __name__ == "__main__":
    main()
