"""
Эталонные тесты для рефакторинга базовых классов.

ЗАПУСК:
    python test_baseline.py

СОХРАНЯЕТ:
- Время инициализации агента
- Время выполнения book_library.execute_script (статический)
- Время выполнения book_library.search_books (динамический)
- Количество событий в EventBus
- Потребление памяти (tracemalloc)
"""
import asyncio
import tracemalloc
import time
import json
import sys
import os

# Устанавливаем UTF-8 кодировку для консоли Windows
if sys.platform == 'win32':
    os.system('chcp 65001 >nul')
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

from core.config import get_config
from core.infrastructure.context.infrastructure_context import InfrastructureContext
from core.application.context.application_context import ApplicationContext
from core.models.enums.common_enums import ComponentType, ExecutionStatus


async def run_baseline_tests():
    """Запуск эталонных тестов."""
    print("=" * 60)
    print("ЭТАЛОННЫЕ ТЕСТЫ ДЛЯ РЕФАКТОРИНГА")
    print("=" * 60)
    
    # Запускаем tracemalloc для замера памяти
    tracemalloc.start()
    
    config = get_config(profile='dev')
    
    # === 1. Замер инициализации ===
    print("\n[1] Инициализация инфраструктуры...")
    start_time = time.time()
    
    infrastructure_context = InfrastructureContext(config)
    await infrastructure_context.initialize()
    
    init_time = time.time() - start_time
    print(f"    ✅ Инфраструктура инициализирована за {init_time:.2f} сек")
    
    # Создаём ApplicationContext
    print("\n[2] Создание ApplicationContext...")
    start_time = time.time()
    
    app_context = ApplicationContext(
        infrastructure_context=infrastructure_context,
        agent_id="agent_baseline"
    )
    await app_context.initialize()
    
    app_init_time = time.time() - start_time
    print(f"    ✅ ApplicationContext инициализирован за {app_init_time:.2f} сек")
    
    # === 2. Тест book_library.execute_script (статический) ===
    print("\n[3] Тест: book_library.execute_script (get_all_books)...")
    
    book_library = app_context.components.get(ComponentType.SKILL, "book_library")
    if book_library is None:
        book_library = app_context.components.get(ComponentType.TOOL, "book_library")
    
    if book_library is None:
        print("    ❌ book_library не найден!")
        return
    
    caps = book_library.get_capabilities()
    cap = next((c for c in caps if c.name == "book_library.execute_script"), None)
    
    if cap is None:
        print("    ❌ Capability execute_script не найдена!")
        return
    
    # Параметры
    params = {
        "script_name": "get_all_books",
        "parameters": {"max_rows": 10}
    }
    
    # Замер выполнения (10 раз для среднего)
    execute_times = []
    results = []
    
    for i in range(10):
        start_time = time.time()
        result = await book_library.execute(
            capability=cap,
            parameters=params,
            execution_context=None
        )
        exec_time = time.time() - start_time
        execute_times.append(exec_time)
        results.append(result)
    
    avg_exec_time = sum(execute_times) / len(execute_times)
    print(f"    ✅ Среднее время выполнения: {avg_exec_time:.4f} сек (10 запусков)")
    
    # Проверяем результат
    first_result = results[0]
    if first_result.status == ExecutionStatus.COMPLETED:
        data = first_result.data if isinstance(first_result.data, dict) else {}
        rowcount = data.get('rowcount', len(data.get('rows', []))) if isinstance(data, dict) else 0
        print(f"    ✅ Результат: {rowcount} записей")
    else:
        print(f"    ⚠️ Статус: {first_result.status.value}")
        if first_result.error:
            print(f"    ⚠️ Ошибка: {first_result.error}")
    
    # === 3. Тест book_library.search_books (динамический) ===
    print("\n[4] Тест: book_library.search_books (Пушкин)...")
    
    cap_search = next((c for c in caps if c.name == "book_library.search_books"), None)
    
    if cap_search is None:
        print("    ❌ Capability search_books не найдена!")
    else:
        search_params = {"query": "Пушкин"}
        search_times = []
        search_results = []
        
        for i in range(10):
            start_time = time.time()
            result = await book_library.execute(
                capability=cap_search,
                parameters=search_params,
                execution_context=None
            )
            search_time = time.time() - start_time
            search_times.append(search_time)
            search_results.append(result)
        
        avg_search_time = sum(search_times) / len(search_times)
        print(f"    ✅ Среднее время поиска: {avg_search_time:.4f} сек (10 запусков)")
        
        first_search = search_results[0]
        if first_search.status == ExecutionStatus.COMPLETED:
            data = first_search.data if isinstance(first_search.data, dict) else {}
            count = len(data.get('books', data.get('results', []))) if isinstance(data, dict) else 0
            print(f"    ✅ Найдено книг: {count}")
        else:
            print(f"    ⚠️ Статус: {first_search.status.value}")
    
    # === 4. Замеры памяти ===
    print("\n[5] Замер памяти...")
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    
    print(f"    ✅ Текущее потребление: {current / 1024 / 1024:.2f} MB")
    print(f"    ✅ Пиковое потребление: {peak / 1024 / 1024:.2f} MB")
    
    # === 5. Сохранение эталона ===
    print("\n[6] Сохранение эталона...")
    
    baseline = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "initialization": {
            "infrastructure_seconds": round(init_time, 3),
            "app_context_seconds": round(app_init_time, 3),
            "total_seconds": round(init_time + app_init_time, 3)
        },
        "execute_script": {
            "avg_seconds": round(avg_exec_time, 6),
            "runs": 10
        },
        "search_books": {
            "avg_seconds": round(avg_search_time if 'avg_search_time' in locals() else 0, 6),
            "runs": 10
        },
        "memory": {
            "current_mb": round(current / 1024 / 1024, 2),
            "peak_mb": round(peak / 1024 / 1024, 2)
        }
    }
    
    with open("baseline_results.json", "w", encoding="utf-8") as f:
        json.dump(baseline, f, indent=2, ensure_ascii=False)
    
    print(f"    ✅ Эталон сохранён в baseline_results.json")
    
    # === Итог ===
    print("\n" + "=" * 60)
    print("ЭТАЛОННЫЕ ДАННЫЕ:")
    print("=" * 60)
    print(f"Инициализация:        {init_time + app_init_time:.2f} сек")
    print(f"execute_script (avg): {avg_exec_time*1000:.2f} мс")
    print(f"search_books (avg):   {avg_search_time*1000:.2f} мс" if 'avg_search_time' in locals() else "search_books: N/A")
    print(f"Память (пик):         {peak / 1024 / 1024:.2f} MB")
    print("=" * 60)
    
    # Shutdown
    await app_context.shutdown()
    await infrastructure_context.shutdown()
    
    return baseline


if __name__ == "__main__":
    baseline = asyncio.run(run_baseline_tests())
    print("\n✅ Эталонные тесты завершены успешно!")
