#!/usr/bin/env python3
"""
Скрипт для анализа реальной схемы базы данных библиотеки книг.
Использует table_description_service для получения метаданных таблиц.

ИСПОЛЬЗОВАНИЕ:
    python analyze_library_schema.py

ПРИМЕЧАНИЕ:
    Для работы требуется:
    1. Настроенная БД PostgreSQL в dev.yaml
    2. Подключение к БД доступно
    3. Таблицы существуют в БД
"""
import asyncio
import sys
import os
from pathlib import Path
from typing import Dict, Any, List

# Установка кодировки для Windows
if sys.platform == 'win32':
    os.system('chcp 65001 >nul')

# Добавим путь к корню проекта
sys.path.insert(0, str(Path(__file__).parent))


async def analyze_library_schema():
    """Анализ реальной схемы базы данных библиотеки книг."""
    
    print("=" * 60)
    print("АНАЛИЗ РЕАЛЬНОЙ СХЕМЫ БАЗЫ ДАННЫХ")
    print("=" * 60)
    
    # ========================================================================
    # 1. ИНИЦИАЛИЗАЦИЯ ЧЕРЕЗ ConfigLoader
    # ========================================================================
    from core.config.config_loader import ConfigLoader
    from core.infrastructure.context.infrastructure_context import InfrastructureContext
    from core.application.context.application_context import ApplicationContext
    from core.config.app_config import AppConfig
    
    # Загрузка конфигурации из dev.yaml
    print("\n[1/6] Загрузка конфигурации из dev.yaml...")
    config_loader = ConfigLoader()
    config = config_loader.load()
    
    print(f"   Profile: {config.profile}")
    print(f"   DB Host: {config.db_providers.get('default_db', {}).parameters.get('host', 'unknown') if hasattr(config, 'db_providers') else 'unknown'}")
    print(f"   DB Name: {config.db_providers.get('default_db', {}).parameters.get('database', 'unknown') if hasattr(config, 'db_providers') else 'unknown'}")
    
    # Создание инфраструктурного контекста
    print("\n[2/6] Инициализация инфраструктурного контекста...")
    infra = InfrastructureContext(config)
    await infra.initialize()
    print("[OK] Инфраструктурный контекст успешно инициализирован!")
    
    # Создание прикладного контекста
    print("\n[3/6] Создание прикладного контекста...")
    app_context = ApplicationContext(
        infrastructure_context=infra,
        config=AppConfig.from_registry(profile="prod"),
        profile="prod"
    )
    await app_context.initialize()
    print("[OK] Прикладной контекст успешно инициализирован!")
    
    # ========================================================================
    # 2. ПОЛУЧЕНИЕ table_description_service
    # ========================================================================
    print("\n[4/6] Получение table_description_service...")
    table_service = app_context.get_service("table_description_service")
    
    if not table_service:
        print("\n[ERROR] ОШИБКА: table_description_service не найден")
        await infra.shutdown()
        return None
    
    print("[OK] table_description_service получен")
    
    # ========================================================================
    # 3. ПОЛУЧЕНИЕ РЕАЛЬНОЙ СТРУКТУРЫ ТАБЛИЦ ИЗ БД
    # ========================================================================
    print("\n" + "-" * 60)
    print("[5/6] ПОЛУЧЕНИЕ РЕАЛЬНОЙ СТРУКТУРЫ ТАБЛИЦ:")
    print("-" * 60)
    
    # Сначала попробуем получить список таблиц из information_schema
    print("\n[INFO] Получение списка таблиц из БД...")
    
    try:
        db_provider = infra.get_provider("default_db")
        if db_provider:
            # Запрос на получение списка таблиц
            tables_query = """
            SELECT table_schema, table_name 
            FROM information_schema.tables 
            WHERE table_type = 'BASE TABLE' 
            AND table_schema NOT IN ('pg_catalog', 'information_schema')
            ORDER BY table_schema, table_name
            """
            result = await db_provider.execute(tables_query, {})
            
            if result and hasattr(result, 'rows') and result.rows:
                print(f"[OK] Найдено {len(result.rows)} таблиц:")
                db_tables = []
                for row in result.rows:
                    if hasattr(row, '__getitem__'):
                        schema = row.get('table_schema', 'public')
                        table = row.get('table_name')
                    else:
                        schema = getattr(row, 'table_schema', 'public')
                        table = getattr(row, 'table_name')
                    print(f"   - {schema}.{table}")
                    db_tables.append((schema, table))
            else:
                print("[WARN] Таблицы не найдены в БД")
                db_tables = []
        else:
            print("[WARN] DB провайдер не доступен")
            db_tables = []
    except Exception as e:
        print(f"[WARN] Ошибка получения списка таблиц: {e}")
        # Fallback: используем стандартные имена таблиц библиотеки
        db_tables = [("Lib", "books"), ("Lib", "authors")]
    
    # Получаем метаданные для каждой таблицы
    schema_info = {
        "schema_name": "Lib",
        "tables": {},
        "analysis_timestamp": None,
        "status": "success",
        "db_config": {
            "host": config.db_providers.get('default_db', {}).parameters.get('host', 'unknown') if hasattr(config, 'db_providers') else 'unknown',
            "database": config.db_providers.get('default_db', {}).parameters.get('database', 'unknown') if hasattr(config, 'db_providers') else 'unknown'
        },
        "real_schema_from_db": True
    }
    
    # Если таблицы найдены в БД, используем их, иначе пробуем стандартные
    tables_to_analyze = db_tables if db_tables else [("Lib", "books"), ("Lib", "authors")]
    
    print(f"\n[INFO] Анализ {len(tables_to_analyze)} таблиц...")
    
    for schema_name, table_name in tables_to_analyze:
        print(f"\n[TABLE] Анализ таблицы: {schema_name}.{table_name}")
        
        try:
            metadata = await table_service.get_table_metadata(
                schema_name=schema_name,
                table_name=table_name,
                context=None,
                step_number=1
            )
            
            if metadata.get('description') == 'Таблица не найдена или не имеет столбцов':
                print(f"   [WARN] Таблица не найдена или пуста")
                schema_info["tables"][table_name] = {
                    "status": "not_found",
                    "message": "Таблица не найдена в БД"
                }
                continue
            
            # Вывод реальной информации о таблице
            print(f"   [DESC] Описание: {metadata.get('description', 'Без описания')}")
            print(f"   [COLS] Реальные колонки ({len(metadata.get('columns', []))}):")
            
            columns_info = []
            for col in metadata.get('columns', []):
                col_name = col.get('column_name', 'unknown')
                col_type = col.get('data_type', 'unknown')
                is_nullable = col.get('is_nullable', True)
                nullable_str = "NULL" if is_nullable else "NOT NULL"
                print(f"       - {col_name}: {col_type} {nullable_str}")
                
                columns_info.append({
                    "name": col_name,
                    "type": col_type,
                    "nullable": is_nullable,
                    "description": col.get('description', 'Без описания')
                })
            
            # Ограничения
            constraints = metadata.get('constraints', [])
            if constraints:
                print(f"   [CONSTRAINTS] Ограничения ({len(constraints)}):")
                for constraint in constraints:
                    constraint_name = constraint.get('name', 'unknown')
                    constraint_type = constraint.get('type', 'unknown')
                    columns = constraint.get('columns', [])
                    print(f"       - {constraint_name}: {constraint_type} ({', '.join(columns)})")
            
            schema_info["tables"][table_name] = {
                "status": "found",
                "description": metadata.get('description', 'Без описания'),
                "columns": columns_info,
                "constraints": constraints,
                "real_schema": True  # Помечаем что это реальная схема из БД
            }
            
        except Exception as e:
            print(f"   [ERROR] Ошибка получения метаданных: {e}")
            schema_info["tables"][table_name] = {
                "status": "error",
                "error": str(e)
            }
    
    # ========================================================================
    # 4. ВАЛИДАЦИЯ РЕАЛЬНОЙ СХЕМЫ
    # ========================================================================
    print("\n" + "-" * 60)
    print("[6/6] ВАЛИДАЦИЯ РЕАЛЬНОЙ СХЕМЫ:")
    print("-" * 60)
    
    validation_errors = []
    validation_warnings = []
    
    # Проверка наличия таблицы books
    if "books" not in schema_info["tables"]:
        validation_errors.append("[ERROR] Таблица 'books' не найдена в БД")
    else:
        books_table = schema_info["tables"]["books"]
        if books_table.get("status") == "found":
            print("[OK] Таблица 'books' найдена в БД")
            
            # Проверка обязательных колонок
            required_columns = ["id", "title", "author"]
            actual_columns = [col["name"] for col in books_table.get("columns", [])]
            
            for req_col in required_columns:
                if req_col not in actual_columns:
                    validation_errors.append(f"[ERROR] В таблице 'books' отсутствует обязательная колонка '{req_col}'")
                else:
                    print(f"    [OK] Колонка '{req_col}' присутствует")
            
            # Вывод реальной структуры таблицы
            print(f"\n[INFO] РЕАЛЬНАЯ СТРУКТУРА ТАБЛИЦЫ 'books':")
            for col in books_table.get("columns", []):
                print(f"    {col['name']}: {col['type']} ({'NOT NULL' if not col['nullable'] else 'NULL'})")
        
        if books_table.get("status") == "not_found":
            validation_warnings.append("[WARN] Таблица 'books' не найдена в БД")
    
    # Проверка наличия таблицы authors
    if "authors" not in schema_info["tables"]:
        validation_warnings.append("[WARN] Таблица 'authors' не найдена в БД (опционально)")
    else:
        authors_table = schema_info["tables"]["authors"]
        if authors_table.get("status") == "found":
            print("[OK] Таблица 'authors' найдена в БД")
    
    # Вывод результатов валидации
    if validation_errors:
        print("\n[ERROR] ОШИБКИ ВАЛИДАЦИИ:")
        for error in validation_errors:
            print(f"   {error}")
    
    if validation_warnings:
        print("\n[WARN] ПРЕДУПРЕЖДЕНИЯ:")
        for warning in validation_warnings:
            print(f"   {warning}")
    
    if not validation_errors and not validation_warnings:
        print("\n[OK] Все проверки пройдены успешно!")
    
    schema_info["validation"] = {
        "errors": validation_errors,
        "warnings": validation_warnings,
        "is_valid": len(validation_errors) == 0
    }
    
    # ========================================================================
    # 5. СОХРАНЕНИЕ РЕАЛЬНОЙ СХЕМЫ В КЭШ
    # ========================================================================
    print("\n" + "-" * 60)
    print("СОХРАНЕНИЕ РЕАЛЬНОЙ СХЕМЫ В КЭШ:")
    print("-" * 60)
    
    cache_dir = Path("data/cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    cache_file = cache_dir / "book_library_schema.yaml"
    
    import yaml
    from datetime import datetime
    
    schema_info["analysis_timestamp"] = datetime.now().isoformat()
    
    with open(cache_file, "w", encoding="utf-8") as f:
        yaml.dump(schema_info, f, allow_unicode=True, default_flow_style=False)
    
    print(f"[OK] Реальная схема сохранена в: {cache_file.absolute()}")
    
    # ========================================================================
    # 6. ГЕНЕРАЦИЯ SQL-СКРИПТА ДЛЯ СОЗДАНИЯ ТАБЛИЦЫ (ЕСЛИ НЕ СУЩЕСТВУЕТ)
    # ========================================================================
    if "books" not in schema_info["tables"] or schema_info["tables"]["books"]["status"] != "found":
        print("\n" + "-" * 60)
        print("ГЕНЕРАЦИЯ SQL-СКРИПТА ДЛЯ СОЗДАНИЯ ТАБЛИЦЫ:")
        print("-" * 60)
        
        create_table_sql = """
-- SQL-скрипт для создания таблицы books
-- Сгенерирован: {timestamp}

CREATE TABLE IF NOT EXISTS books (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    author TEXT,
    year INTEGER,
    isbn TEXT,
    genre TEXT
);

-- Индексы для улучшения производительности
CREATE INDEX IF NOT EXISTS idx_books_author ON books(author);
CREATE INDEX IF NOT EXISTS idx_books_genre ON books(genre);
CREATE INDEX IF NOT EXISTS idx_books_year ON books(year);
""".format(timestamp=datetime.now().isoformat())
        
        sql_file = cache_dir / "create_books_table.sql"
        with open(sql_file, "w", encoding="utf-8") as f:
            f.write(create_table_sql)
        
        print(f"[OK] SQL-скрипт сохранен в: {sql_file.absolute()}")
        print("\n[INFO] Выполните этот скрипт в БД для создания таблицы:")
        print(f"   psql -h {schema_info['db_config']['host']} -d {schema_info['db_config']['database']} -f {sql_file.absolute()}")
    
    # ========================================================================
    # 7. ЗАВЕРШЕНИЕ РАБОТЫ
    # ========================================================================
    await infra.shutdown()
    print("\n[OK] Инфраструктурный контекст завершён")
    
    print("\n" + "=" * 60)
    print("АНАЛИЗ РЕАЛЬНОЙ СХЕМЫ ЗАВЕРШЁН")
    print("=" * 60)
    
    return schema_info


def print_schema_summary(schema_info: Dict[str, Any]):
    """Вывод краткой сводки по реальной схеме."""
    if not schema_info:
        return
    
    print("\n[SUMMARY] КРАТКАЯ СВОДКА:")
    print(f"   Схема: {schema_info.get('schema_name', 'unknown')}")
    print(f"   БД: {schema_info.get('db_config', {}).get('host', 'unknown')}/{schema_info.get('db_config', {}).get('database', 'unknown')}")
    print(f"   Реальная схема из БД: {'Да' if schema_info.get('real_schema_from_db', False) else 'Нет'}")
    print(f"   Таблиц: {len(schema_info.get('tables', {}))}")
    
    for table_name, table_info in schema_info.get('tables', {}).items():
        status = table_info.get('status', 'unknown')
        if status == 'found':
            columns_count = len(table_info.get('columns', []))
            print(f"   - {table_name}: {columns_count} колонок (реальная структура)")
        else:
            print(f"   - {table_name}: {status}")


if __name__ == "__main__":
    schema_info = asyncio.run(analyze_library_schema())
    
    if schema_info:
        print_schema_summary(schema_info)
        
        # Вывод статуса
        if schema_info.get("validation", {}).get("is_valid", False):
            print("\n[OK] Реальная схема валидна и готова к использованию")
            sys.exit(0)
        else:
            print("\n[WARN] Обнаружены проблемы с реальной схемой")
            sys.exit(1)
    else:
        print("\n[ERROR] Не удалось получить информацию о реальной схеме")
        sys.exit(1)
