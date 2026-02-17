#!/usr/bin/env python3
"""
Пример запуска навыка book_library в разных режимах.

ИСПОЛЬЗОВАНИЕ:
    python run_book_library_example.py

ТРЕБОВАНИЯ:
    1. Настроенная БД PostgreSQL (dev.yaml)
    2. Таблица Lib.books существует
    3. LLM провайдер доступен (для dynamic режима)
"""
import asyncio
import sys
from pathlib import Path
from typing import Dict, Any

# Добавим путь к корню проекта
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


# ============================================================================
# ПРИМЕР 1: ЗАПУСК ЧЕРЕЗ ApplicationContext (ПРАВИЛЬНЫЙ СПОСОБ)
# ============================================================================

async def run_with_app_context():
    """
    Запуск навыка через ApplicationContext.
    
    Это правильный способ использования навыка в production.
    """
    print("=" * 70)
    print("ПРИМЕР 1: Запуск через ApplicationContext")
    print("=" * 70)
    
    from core.config.config_loader import ConfigLoader
    from core.infrastructure.context.infrastructure_context import InfrastructureContext
    from core.application.context.application_context import ApplicationContext
    from core.config.app_config import AppConfig
    
    # 1. Загрузка конфигурации
    print("\n[1/5] Загрузка конфигурации...")
    config_loader = ConfigLoader()
    config = config_loader.load()
    print(f"   Profile: {config.profile}")
    
    # 2. Инициализация инфраструктурного контекста
    print("\n[2/5] Инициализация инфраструктурного контекста...")
    infra = InfrastructureContext(config)
    await infra.initialize()
    print("   [OK] Инфраструктура готова")
    
    # 3. Создание прикладного контекста
    print("\n[3/5] Создание прикладного контекста...")
    app_context = ApplicationContext(
        infrastructure_context=infra,
        config=AppConfig.from_registry(profile="prod"),
        profile="prod"
    )
    await app_context.initialize()
    print("   [OK] Прикладной контекст готов")
    
    # 4. Получение навыка
    print("\n[4/5] Получение навыка book_library...")
    skill = app_context.get_skill("book_library")
    if not skill:
        print("   [ERROR] Навык не найден!")
        await infra.shutdown()
        return
    
    await skill.initialize()
    print(f"   [OK] Навык инициализирован")
    print(f"   Доступные capability: {skill.get_capability_names()}")
    
    # 5. Запуск в разных режимах
    print("\n[5/5] Запуск в разных режимах...")
    
    # Режим 1: list_scripts - получить список доступных скриптов
    print("\n--- РЕЖИМ 1: list_scripts (informational) ---")
    result = await skill.execute(
        capability="book_library.list_scripts",
        parameters={},
        execution_context=None
    )
    print(f"Результат: {len(result.get('scripts', []))} скриптов доступно")
    for script in result.get('scripts', [])[:3]:  # Показываем первые 3
        print(f"  - {script['name']}: {script['description']}")
    
    # Режим 2: execute_script - выполнение заготовленного скрипта (static)
    print("\n--- РЕЖИМ 2: execute_script (static) ---")
    result = await skill.execute(
        capability="book_library.execute_script",
        parameters={
            "script_name": "get_all_books",
            "parameters": {
                "max_rows": 5
            }
        },
        execution_context=None
    )
    print(f"Результат: найдено {result.get('rowcount', 0)} книг")
    for book in result.get('rows', [])[:2]:  # Показываем первые 2
        print(f"  - {book.get('title', 'N/A')} ({book.get('author', 'N/A')})")
    
    # Режим 3: search_books - динамический поиск (dynamic)
    print("\n--- РЕЖИМ 3: search_books (dynamic) ---")
    result = await skill.execute(
        capability="book_library.search_books",
        parameters={
            "query": "Найти книги Льва Толстого",
            "max_results": 5
        },
        execution_context=None
    )
    print(f"Результат: найдено {result.get('rowcount', 0)} книг")
    print(f"Тип выполнения: {result.get('execution_type', 'unknown')}")
    for book in result.get('rows', [])[:2]:
        print(f"  - {book.get('title', 'N/A')} ({book.get('author', 'N/A')})")
    
    # 6. Завершение работы
    print("\n[6/5] Завершение работы...")
    await infra.shutdown()
    print("   [OK] Инфраструктура остановлена")
    
    print("\n" + "=" * 70)
    print("ПРИМЕР 1 ЗАВЕРШЁН")
    print("=" * 70)


# ============================================================================
# ПРИМЕР 2: ЗАПУСК ЧЕРЕЗ ActionExecutor (ДЛЯ АГЕНТА)
# ============================================================================

async def run_with_executor():
    """
    Запуск навыка через ActionExecutor.
    
    Так агент использует навык в runtime.
    """
    print("\n" + "=" * 70)
    print("ПРИМЕР 2: Запуск через ActionExecutor (как агент)")
    print("=" * 70)
    
    from core.config.config_loader import ConfigLoader
    from core.infrastructure.context.infrastructure_context import InfrastructureContext
    from core.application.context.application_context import ApplicationContext
    from core.config.app_config import AppConfig
    from core.application.agent.components.action_executor import ActionExecutor
    from core.session_context.session_context import SessionContext
    
    # 1. Инициализация контекстов
    print("\n[1/4] Инициализация контекстов...")
    config_loader = ConfigLoader()
    config = config_loader.load()
    
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    app_context = ApplicationContext(
        infrastructure_context=infra,
        config=AppConfig.from_registry(profile="prod"),
        profile="prod"
    )
    await app_context.initialize()
    print("   [OK] Контексты готовы")
    
    # 2. Создание ActionExecutor
    print("\n[2/4] Создание ActionExecutor...")
    executor = ActionExecutor(application_context=app_context)
    print("   [OK] Executor готов")
    
    # 3. Создание SessionContext
    print("\n[3/4] Создание SessionContext...")
    session_context = SessionContext()
    session_context.set_goal("Получить информацию о книгах")
    print("   [OK] SessionContext готов")
    
    # 4. Выполнение через executor
    print("\n[4/4] Выполнение capability через executor...")
    
    # Пример 1: list_scripts
    print("\n--- Выполнение: book_library.list_scripts ---")
    result = await executor.execute_capability(
        capability_name="book_library.list_scripts",
        parameters={},
        session_context=session_context
    )
    print(f"Статус: {result.status.value}")
    if result.result:
        print(f"Доступно скриптов: {result.result.get('total_count', 0)}")
    
    # Пример 2: execute_script
    print("\n--- Выполнение: book_library.execute_script ---")
    result = await executor.execute_capability(
        capability_name="book_library.execute_script",
        parameters={
            "script_name": "get_books_by_author",
            "parameters": {
                "author": "Лев Толстой",
                "max_rows": 3
            }
        },
        session_context=session_context
    )
    print(f"Статус: {result.status.value}")
    if result.result:
        print(f"Найдено книг: {result.result.get('rowcount', 0)}")
    
    # Пример 3: search_books
    print("\n--- Выполнение: book_library.search_books ---")
    result = await executor.execute_capability(
        capability_name="book_library.search_books",
        parameters={
            "query": "Какие книги есть в жанре Роман",
            "max_results": 3
        },
        session_context=session_context
    )
    print(f"Статус: {result.status.value}")
    if result.result:
        print(f"Найдено книг: {result.result.get('rowcount', 0)}")
        print(f"Тип: {result.result.get('execution_type', 'unknown')}")
    
    # 5. Завершение
    await infra.shutdown()
    
    print("\n" + "=" * 70)
    print("ПРИМЕР 2 ЗАВЕРШЁН")
    print("=" * 70)


# ============================================================================
# ПРИМЕР 3: ВСЕ ДОСТУПНЫЕ СКРИПТЫ (DEMO)
# ============================================================================

async def run_all_scripts_demo():
    """
    Демонстрация всех доступных скриптов.
    """
    print("\n" + "=" * 70)
    print("ПРИМЕР 3: Демонстрация всех скриптов")
    print("=" * 70)
    
    from core.config.config_loader import ConfigLoader
    from core.infrastructure.context.infrastructure_context import InfrastructureContext
    from core.application.context.application_context import ApplicationContext
    from core.config.app_config import AppConfig
    
    # Инициализация
    config_loader = ConfigLoader()
    config = config_loader.load()
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    app_context = ApplicationContext(
        infrastructure_context=infra,
        config=AppConfig.from_registry(profile="prod"),
        profile="prod"
    )
    await app_context.initialize()
    
    skill = app_context.get_skill("book_library")
    await skill.initialize()
    
    # Список всех доступных скриптов
    scripts = [
        ("get_all_books", {"max_rows": 3}),
        ("get_books_by_author", {"author": "Лев Толстой", "max_rows": 3}),
        ("get_books_by_genre", {"genre": "Роман", "max_rows": 3}),
        ("get_books_by_year_range", {"year_from": 1800, "year_to": 1900, "max_rows": 3}),
        ("get_book_by_id", {"book_id": 1}),
        ("count_books_by_author", {"author": "Лев Толстой"}),
        ("get_books_by_title_pattern", {"title_pattern": "%Война%", "max_rows": 3}),
        ("get_distinct_authors", {"max_rows": 5}),
        ("get_distinct_genres", {"max_rows": 5}),
        ("get_genre_statistics", {"max_rows": 5}),
    ]
    
    print(f"\nВсего скриптов: {len(scripts)}\n")
    
    for script_name, params in scripts:
        print(f"--- Скрипт: {script_name} ---")
        try:
            result = await skill.execute(
                capability="book_library.execute_script",
                parameters={
                    "script_name": script_name,
                    "parameters": params
                },
                execution_context=None
            )
            
            if result.get('rows'):
                print(f"  Результатов: {len(result['rows'])}")
                print(f"  Время: {result.get('execution_time', 0):.3f}с")
                
                # Показываем первый результат
                first_row = result['rows'][0]
                print(f"  Пример: {first_row}")
            else:
                print(f"  Нет результатов")
                
        except Exception as e:
            print(f"  Ошибка: {e}")
        print()
    
    # Завершение
    await infra.shutdown()
    
    print("=" * 70)
    print("ПРИМЕР 3 ЗАВЕРШЁН")
    print("=" * 70)


# ============================================================================
# ПРИМЕР 4: СРАВНЕНИЕ ПРОИЗВОДИТЕЛЬНОСТИ
# ============================================================================

async def run_performance_comparison():
    """
    Сравнение производительности static vs dynamic.
    """
    print("\n" + "=" * 70)
    print("ПРИМЕР 4: Сравнение производительности")
    print("=" * 70)
    
    import time
    from core.config.config_loader import ConfigLoader
    from core.infrastructure.context.infrastructure_context import InfrastructureContext
    from core.application.context.application_context import ApplicationContext
    from core.config.app_config import AppConfig
    
    # Инициализация
    config_loader = ConfigLoader()
    config = config_loader.load()
    infra = InfrastructureContext(config)
    await infra.initialize()
    
    app_context = ApplicationContext(
        infrastructure_context=infra,
        config=AppConfig.from_registry(profile="prod"),
        profile="prod"
    )
    await app_context.initialize()
    
    skill = app_context.get_skill("book_library")
    await skill.initialize()
    
    # Тест 1: Static script
    print("\n--- Тест 1: Static (execute_script) ---")
    start = time.time()
    for i in range(5):
        result = await skill.execute(
            capability="book_library.execute_script",
            parameters={
                "script_name": "get_books_by_author",
                "parameters": {"author": "Лев Толстой", "max_rows": 10}
            },
            execution_context=None
        )
    static_time = (time.time() - start) / 5
    print(f"Среднее время: {static_time*1000:.2f} мс")
    print(f"Тип: {result.get('execution_type', 'unknown')}")
    
    # Тест 2: Dynamic search
    print("\n--- Тест 2: Dynamic (search_books) ---")
    start = time.time()
    for i in range(5):
        result = await skill.execute(
            capability="book_library.search_books",
            parameters={
                "query": "Найти книги Толстого",
                "max_results": 10
            },
            execution_context=None
        )
    dynamic_time = (time.time() - start) / 5
    print(f"Среднее время: {dynamic_time*1000:.2f} мс")
    print(f"Тип: {result.get('execution_type', 'unknown')}")
    
    # Сравнение
    print("\n--- Сравнение ---")
    print(f"Static:  {static_time*1000:.2f} мс")
    print(f"Dynamic: {dynamic_time*1000:.2f} мс")
    print(f"Разница: {dynamic_time/static_time:.1f}x медленнее")
    
    # Завершение
    await infra.shutdown()
    
    print("\n" + "=" * 70)
    print("ПРИМЕР 4 ЗАВЕРШЁН")
    print("=" * 70)


# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Запуск всех примеров."""
    
    print("\n" + "=" * 70)
    print("BOOK_LIBRARY: ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ")
    print("=" * 70)
    
    try:
        # Пример 1: Базовое использование
        await run_with_app_context()
        
        # Пример 2: Через ActionExecutor
        await run_with_executor()
        
        # Пример 3: Все скрипты
        await run_all_scripts_demo()
        
        # Пример 4: Производительность
        await run_performance_comparison()
        
    except Exception as e:
        print(f"\n[ERROR] Ошибка выполнения: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 70)
    print("ВСЕ ПРИМЕРЫ ЗАВЕРШЕНЫ")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
