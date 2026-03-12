#!/usr/bin/env python3
"""
Реестр заготовленных SQL-скриптов для навыка book_library.

Этот модуль содержит предопределённые SQL-скрипты для выполнения
через capability book_library.execute_script.

СХЕМА БАЗЫ ДАННЫХ (нормализованная):
    "Lib".books (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        author_id INTEGER REFERENCES "Lib".authors(id),
        year INTEGER,
        isbn TEXT,
        genre TEXT
    )
    
    "Lib".authors (
        id SERIAL PRIMARY KEY,
        first_name TEXT,
        last_name TEXT,
        birth_date DATE
    )

ПРИМЕЧАНИЕ:
Скрипты используют реальную структуру таблиц из БД с JOIN между books и authors.
Для обновления схемы выполните: python analyze_library_schema.py
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


@dataclass
class ScriptConfig:
    """Конфигурация SQL-скрипта."""
    name: str
    sql: str
    description: str
    parameters: List[str] = field(default_factory=list)
    required_parameters: List[str] = field(default_factory=list)
    max_rows: int = 100
    output_contract: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Преобразование в словарь."""
        return {
            "sql": self.sql,
            "description": self.description,
            "parameters": self.parameters,
            "required_parameters": self.required_parameters,
            "max_rows": self.max_rows,
            "output_contract": self.output_contract
        }


# ============================================================================
# РЕЕСТР СКРИПТОВ
# ============================================================================

SCRIPTS_REGISTRY: Dict[str, ScriptConfig] = {
    # -------------------------------------------------------------------------
    # Получение всех книг
    # -------------------------------------------------------------------------
    "get_all_books": ScriptConfig(
        name="get_all_books",
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
        description="Получить все книги с лимитом (с данными авторов)",
        parameters=["max_rows"],
        required_parameters=[],
        max_rows=100,
        output_contract="book_library.get_all_books_output"
    ),

    # -------------------------------------------------------------------------
    # Поиск книг по автору (по фамилии)
    # -------------------------------------------------------------------------
    "get_books_by_author": ScriptConfig(
        name="get_books_by_author",
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
        description="Получить книги по фамилии автора (ILIKE поиск)",
        parameters=["author", "max_rows"],
        required_parameters=["author"],
        max_rows=50,
        output_contract="book_library.get_books_by_author_output"
    ),

    # -------------------------------------------------------------------------
    # Поиск книг по жанру
    # -------------------------------------------------------------------------
    "get_books_by_genre": ScriptConfig(
        name="get_books_by_genre",
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
        description="Получить книги по жанру",
        parameters=["genre", "max_rows"],
        required_parameters=["genre"],
        max_rows=50,
        output_contract="book_library.get_books_by_genre_output"
    ),

    # -------------------------------------------------------------------------
    # Поиск книг по диапазону лет
    # -------------------------------------------------------------------------
    "get_books_by_year_range": ScriptConfig(
        name="get_books_by_year_range",
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
        description="Получить книги по диапазону лет публикации",
        parameters=["year_from", "year_to", "max_rows"],
        required_parameters=["year_from", "year_to"],
        max_rows=100,
        output_contract="book_library.get_books_by_year_range_output"
    ),

    # -------------------------------------------------------------------------
    # Получение книги по ID
    # -------------------------------------------------------------------------
    "get_book_by_id": ScriptConfig(
        name="get_book_by_id",
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
        description="Получить книгу по ID (с данными автора)",
        parameters=["book_id"],
        required_parameters=["book_id"],
        max_rows=1,
        output_contract="book_library.get_book_by_id_output"
    ),

    # -------------------------------------------------------------------------
    # Подсчёт количества книг автора
    # -------------------------------------------------------------------------
    "count_books_by_author": ScriptConfig(
        name="count_books_by_author",
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
        description="Посчитать количество книг по фамилии автора",
        parameters=["author"],
        required_parameters=["author"],
        max_rows=1,
        output_contract="book_library.count_books_by_author_output"
    ),

    # -------------------------------------------------------------------------
    # Поиск книг по названию (LIKE)
    # -------------------------------------------------------------------------
    "get_books_by_title_pattern": ScriptConfig(
        name="get_books_by_title_pattern",
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
        description="Получить книги по шаблону названия (ILIKE)",
        parameters=["title_pattern", "max_rows"],
        required_parameters=["title_pattern"],
        max_rows=50,
        output_contract="book_library.get_books_by_title_pattern_output"
    ),

    # -------------------------------------------------------------------------
    # Список уникальных авторов
    # -------------------------------------------------------------------------
    "get_distinct_authors": ScriptConfig(
        name="get_distinct_authors",
        sql="""
            SELECT DISTINCT
                a.id as author_id,
                a.first_name,
                a.last_name,
                a.birth_date
            FROM "Lib".authors a
            JOIN "Lib".books b ON a.id = b.author_id
            WHERE a.last_name IS NOT NULL
            ORDER BY a.last_name
            LIMIT %s
        """,
        description="Получить список уникальных авторов у которых есть книги",
        parameters=["max_rows"],
        required_parameters=[],
        max_rows=100,
        output_contract="book_library.get_distinct_authors_output"
    ),

    # -------------------------------------------------------------------------
    # Список уникальных жанров
    # -------------------------------------------------------------------------
    "get_distinct_genres": ScriptConfig(
        name="get_distinct_genres",
        sql="""
            SELECT DISTINCT genre
            FROM "Lib".books
            WHERE genre IS NOT NULL
            ORDER BY genre
            LIMIT %s
        """,
        description="Получить список уникальных жанров",
        parameters=["max_rows"],
        required_parameters=[],
        max_rows=50,
        output_contract="book_library.get_distinct_genres_output"
    ),

    # -------------------------------------------------------------------------
    # Статистика по жанрам
    # -------------------------------------------------------------------------
    "get_genre_statistics": ScriptConfig(
        name="get_genre_statistics",
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
        description="Получить статистику по жанрам (количество книг, средний год)",
        parameters=["max_rows"],
        required_parameters=[],
        max_rows=20,
        output_contract="book_library.get_genre_statistics_output"
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
    
    ARGS:
        script_name: имя скрипта
        parameters: параметры для валидации
    
    RETURNS:
        (is_valid, error_message)
    """
    script = get_script(script_name)
    
    if not script:
        return False, f"Скрипт '{script_name}' не найден"
    
    # Проверка обязательных параметров
    missing_params = set(script.required_parameters) - set(parameters.keys())
    if missing_params:
        return False, f"Отсутствуют обязательные параметры: {missing_params}"
    
    return True, None


def get_script_sql(script_name: str, parameters: Dict[str, Any] = None) -> Optional[str]:
    """
    Получение SQL-запроса для скрипта.
    
    ARGS:
        script_name: имя скрипта
        parameters: параметры (для будущей параметризации)
    
    RETURNS:
        SQL-запрос или None
    """
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
