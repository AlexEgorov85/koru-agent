#!/usr/bin/env python3
"""
Реестр заготовленных SQL-скриптов для навыка book_library.

СХЕМА БД:
    "Lib".books (id, title, author_id, year, isbn, genre)
    "Lib".authors (id, first_name, last_name, birth_date)

ПОЛНАЯ СТРУКТУРА ПАРАМЕТРОВ:
    ScriptConfig(
        parameters={
            "author": {
                "type": "like",        # "like" | "exact"
                "required": True,       # Обязательный?
                "description": "...",  # Для LLM
            },
            "max_rows": "limit"        # Сокращённая запись
        }
    )

ТИПЫ:
    - "like"   → ILIKE %value%
    - "exact"  → = value
    - "limit"  → LIMIT value
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path


# ============================================================================
# ЗАГРУЗКА РЕАЛЬНОЙ СХЕМЫ ИЗ КЭША
# ============================================================================

def load_real_schema_from_cache() -> Optional[Dict[str, Any]]:
    """
    Загрузка реальной схемы таблиц из кэша.
    
    RETURNS:
        Словарь с реальной схемой или None если кэш не найден
    """
    cache_file = Path("data/cache/book_library_schema.yaml")
    
    if not cache_file.exists():
        return None

    try:
        import yaml
        with open(cache_file, 'r', encoding='utf-8') as f:
            schema = yaml.safe_load(f)

        if schema and schema.get('real_schema', False):
            return schema
        else:
            return None
    except Exception:
        return None


def get_table_columns(table_name: str, schema: Dict[str, Any] = None) -> List[str]:
    """
    Получение списка колонок таблицы из реальной схемы.
    
    ARGS:
        table_name: имя таблицы
        schema: загруженная схема (опционально)
    
    RETURNS:
        Список имен колонок
    """
    if schema is None:
        schema = load_real_schema_from_cache()
    
    if schema and table_name in schema.get('tables', {}):
        table_info = schema['tables'][table_name]
        if table_info.get('status') == 'found':
            return [col['name'] for col in table_info.get('columns', [])]
    
    # Fallback на нормализованную схему
    if table_name == 'books':
        return ['id', 'title', 'author_id', 'year', 'isbn', 'genre']
    elif table_name == 'authors':
        return ['id', 'first_name', 'last_name', 'birth_date']
    return []


# =============================================================================
# КОНФИГУРАЦИЯ СКРИПТА
# =============================================================================
#
# Полная структура:
# ```python
# ScriptConfig(
#     name="script_name",
#     description="Описание скрипта",
#     sql="SELECT ... WHERE status = %s",
#     parameters={                    # Словарь параметров (обязательные + опциональные)
#         "status": {
#             "type": "like",        # "like" | "exact" | "limit"
#             "required": True,       # Обязательный?
#             "description": "...",  # Для LLM
#             "validation": {...}    # Валидация (опционально)
#         },
#         "max_rows": "limit"        # Сокращённая запись для лимита
#     }
# )
# ```
#
# ТИПЫ:
# - "like"   → ILIKE %value% (поиск по подстроке)
# - "exact"  → = value (точное равенство)
# - "limit"  → LIMIT value (число результатов)


@dataclass
class ScriptConfig:
    """Конфигурация SQL-скрипта."""
    name: str
    description: str
    sql: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    max_rows: int = 100
    output_contract: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "sql": self.sql,
            "description": self.description,
            "parameters": self.parameters,
            "max_rows": self.max_rows,
            "output_contract": self.output_contract
        }


# ============================================================================
# РЕЕСТР СКРИПТОВ
# ============================================================================

SCRIPTS_REGISTRY: Dict[str, ScriptConfig] = {
    "get_all_books": ScriptConfig(
        name="get_all_books",
        description="Получить все книги с лимитом (с данными авторов)",
        sql="""
            SELECT
                b.id as book_id,
                b.title as book_title,
                b.isbn,
                b.publication_date,
                a.id as author_id,
                a.first_name,
                a.last_name,
                a.birth_date
            FROM "Lib".books b
            JOIN "Lib".authors a ON b.author_id = a.id
            ORDER BY b.id
            LIMIT %s
        """,
        parameters={"max_rows": "limit"},
        max_rows=100,
        output_contract="book_library.execute_script_output"
    ),

    "get_books_by_author": ScriptConfig(
        name="get_books_by_author",
        description="Получить книги по фамилии автора (ILIKE поиск)",
        sql="""
            SELECT
                b.id as book_id,
                b.title as book_title,
                b.isbn,
                b.publication_date,
                a.id as author_id,
                a.first_name,
                a.last_name,
                a.birth_date
            FROM "Lib".books b
            JOIN "Lib".authors a ON b.author_id = a.id
            WHERE a.last_name ILIKE %s
            ORDER BY b.title
            LIMIT %s
        """,
        parameters={
            "author": {
                "type": "like",
                "required": True,
                "description": "Фамилия автора (можно ввести частично, поиск по LIKE)"
            },
            "max_rows": "limit"
        },
        max_rows=50,
        output_contract="book_library.execute_script_output"
    ),

    "get_books_by_genre": ScriptConfig(
        name="get_books_by_genre",
        description="Получить книги по жанру",
        sql="""
            SELECT
                b.id as book_id,
                b.title as book_title,
                b.isbn,
                b.publication_date,
                a.id as author_id,
                a.first_name,
                a.last_name,
                a.birth_date
            FROM "Lib".books b
            JOIN "Lib".authors a ON b.author_id = a.id
            WHERE b.genre = %s
            ORDER BY b.title
            LIMIT %s
        """,
        parameters={
            "genre": {
                "type": "exact",
                "required": True,
                "description": "Название жанра (точное совпадение)"
            },
            "max_rows": "limit"
        },
        max_rows=50,
        output_contract="book_library.execute_script_output"
    ),

    # -------------------------------------------------------------------------
    # Поиск книг по диапазону лет
    # -------------------------------------------------------------------------
    "get_books_by_year_range": ScriptConfig(
        name="get_books_by_year_range",
        description="Получить книги по диапазону лет публикации",
        sql="""
            SELECT
                b.id as book_id,
                b.title as book_title,
                b.isbn,
                b.publication_date,
                a.id as author_id,
                a.first_name,
                a.last_name,
                a.birth_date
            FROM "Lib".books b
            JOIN "Lib".authors a ON b.author_id = a.id
            WHERE EXTRACT(YEAR FROM b.publication_date) BETWEEN %s AND %s
            ORDER BY b.publication_date
            LIMIT %s
        """,
        parameters={
            "year_from": {"type": "exact", "required": False, "description": "Год публикации ОТ"},
            "year_to": {"type": "exact", "required": False, "description": "Год публикации ДО"},
            "max_rows": "limit"
        },
        max_rows=100,
        output_contract="book_library.execute_script_output"
    ),

    "get_book_by_id": ScriptConfig(
        name="get_book_by_id",
        description="Получить книгу по ID (с данными автора)",
        sql="""
            SELECT
                b.id as book_id,
                b.title as book_title,
                b.isbn,
                b.publication_date,
                a.id as author_id,
                a.first_name,
                a.last_name,
                a.birth_date
            FROM "Lib".books b
            JOIN "Lib".authors a ON b.author_id = a.id
            WHERE b.id = %s
        """,
        parameters={
            "book_id": {"type": "exact", "required": True, "description": "ID книги в БД"}
        },
        max_rows=1,
        output_contract="book_library.execute_script_output"
    ),

    "count_books_by_author": ScriptConfig(
        name="count_books_by_author",
        description="Посчитать количество книг по фамилии автора",
        sql="""
            SELECT
                COUNT(*) as count,
                a.last_name as author_last_name,
                a.first_name as author_first_name
            FROM "Lib".books b
            JOIN "Lib".authors a ON b.author_id = a.id
            WHERE a.last_name ILIKE %s
            GROUP BY a.id, a.first_name, a.last_name
        """,
        parameters={
            "author": {"type": "like", "required": True, "description": "Фамилия автора"}
        },
        max_rows=1,
        output_contract="book_library.execute_script_output"
    ),

    "get_books_by_title_pattern": ScriptConfig(
        name="get_books_by_title_pattern",
        description="Получить книги по шаблону названия (ILIKE)",
        sql="""
            SELECT
                b.id as book_id,
                b.title as book_title,
                b.isbn,
                b.publication_date,
                a.id as author_id,
                a.first_name,
                a.last_name,
                a.birth_date
            FROM "Lib".books b
            JOIN "Lib".authors a ON b.author_id = a.id
            WHERE b.title ILIKE %s
            ORDER BY b.title
            LIMIT %s
        """,
        parameters={
            "title_pattern": {"type": "like", "required": True, "description": "Шаблон названия книги"},
            "max_rows": "limit"
        },
        max_rows=50,
        output_contract="book_library.execute_script_output"
    ),

    "get_distinct_authors": ScriptConfig(
        name="get_distinct_authors",
        description="Получить список уникальных авторов у которых есть книги",
        sql="""
            SELECT DISTINCT a.last_name
            FROM "Lib".authors a
            JOIN "Lib".books b ON a.id = b.author_id
            WHERE a.last_name IS NOT NULL
            ORDER BY a.last_name
            LIMIT %s
        """,
        parameters={"max_rows": "limit"},
        max_rows=100,
        output_contract="book_library.execute_script_output"
    ),

    "get_distinct_genres": ScriptConfig(
        name="get_distinct_genres",
        description="Получить список уникальных жанров",
        sql="""
            SELECT DISTINCT genre
            FROM "Lib".books
            WHERE genre IS NOT NULL
            ORDER BY genre
            LIMIT %s
        """,
        parameters={"max_rows": "limit"},
        max_rows=50,
        output_contract="book_library.execute_script_output"
    ),

    "get_genre_statistics": ScriptConfig(
        name="get_genre_statistics",
        description="Получить статистику по жанрам (количество книг, средний год)",
        sql="""
            SELECT
                genre,
                COUNT(*) as book_count,
                AVG(EXTRACT(YEAR FROM publication_date)) as avg_year
            FROM "Lib".books
            WHERE genre IS NOT NULL
            GROUP BY genre
            ORDER BY book_count DESC
            LIMIT %s
        """,
        parameters={"max_rows": "limit"},
        max_rows=20,
        output_contract="book_library.execute_script_output"
    ),
}


def get_script(script_name: str) -> Optional[ScriptConfig]:
    """
    Получение конфигурации скрипта по имени.
    
    ARGS:
        script_name: имя скрипта
    
    RETURNS:
        ScriptConfig или None если скрипт не найден
    """
    return SCRIPTS_REGISTRY.get(script_name)


def get_all_scripts() -> Dict[str, ScriptConfig]:
    """
    Получение всех доступных скриптов.
    
    RETURNS:
        Словарь всех скриптов
    """
    return SCRIPTS_REGISTRY.copy()


def get_allowed_scripts_list() -> List[str]:
    """
    Получение списка имён доступных скриптов.
    
    RETURNS:
        Список имён скриптов
    """
    return list(SCRIPTS_REGISTRY.keys())


def validate_script_parameters(
    script_name: str,
    parameters: Dict[str, Any]
) -> tuple[bool, Optional[str]]:
    """
    Валидация параметров для скрипта.
    """
    script = get_script(script_name)
    
    if not script:
        return False, f"Скрипт '{script_name}' не найден"
    
    # Проверка обязательных параметров
    required = []
    for param_name, param_config in script.parameters.items():
        if isinstance(param_config, dict) and param_config.get("required", False):
            required.append(param_name)
    
    missing_params = set(required) - set(parameters.keys())
    if missing_params:
        return False, f"Отсутствуют обязательные параметры: {missing_params}"
    
    return True, None


def get_script_sql(script_name: str, parameters: Dict[str, Any] = None) -> Optional[str]:
    """Получение SQL-запроса для скрипта."""
    script = get_script(script_name)
    if not script:
        return None
    return script.sql


# ============================================================================
# КОНСТАНТЫ ДЛЯ ИСПОЛЬЗОВАНИЯ В SKILL
# ============================================================================

# Список всех доступных скриптов (для проверки)
ALLOWED_SCRIPTS = get_allowed_scripts_list()

# Максимальное количество строк по умолчанию
DEFAULT_MAX_ROWS = 100
