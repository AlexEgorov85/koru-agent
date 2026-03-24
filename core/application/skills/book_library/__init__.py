"""
BookLibrary skill module.

CAPABILITIES:
- search_books: динамический поиск книг через LLM
- execute_script: выполнение заготовленных SQL-скриптов
- list_scripts: получение списка доступных скриптов
- semantic_search: семантический поиск через векторную БД
"""
from .skill import BookLibrarySkill, create_book_library_skill

__all__ = [
    "BookLibrarySkill",
    "create_book_library_skill",
]
